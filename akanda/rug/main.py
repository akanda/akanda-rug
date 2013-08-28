import logging
import multiprocessing
import socket
import sys

from oslo.config import cfg

from akanda.rug import notifications
from akanda.rug import scheduler
from akanda.rug import worker
from akanda.rug.api import quantum as quantum_api

LOG = logging.getLogger(__name__)


def shuffle_notifications(notification_queue, sched):
    """Copy messages from the notification queue into the scheduler.
    """
    while True:
        try:
            target, message = notification_queue.get()
            sched.handle_message(target, message)
        except KeyboardInterrupt:
            sched.stop()
            break


def main(argv=sys.argv[1:]):
    cfg.CONF.register_opts([
        cfg.StrOpt('host',
                   default=socket.getfqdn(),
                   help="The hostname Akanda is running on"),

        # Note(rods): This options, togheter with the AGENT_OPTIONS
        #             below, were definded in the manager module.
        #             Since that module is not imported anymore we need
        #             to define them somewhere else. Adding them here
        #             temporarely while we figure out what's the best
        #             to put them
        cfg.StrOpt('admin_user'),
        cfg.StrOpt('admin_password', secret=True),
        cfg.StrOpt('admin_tenant_name'),
        cfg.StrOpt('auth_url'),
        cfg.StrOpt('auth_strategy', default='keystone'),
        cfg.StrOpt('auth_region'),

        # needed for plugging locally into management network
        cfg.StrOpt('interface_driver'),
        cfg.StrOpt('ovs_integration_bridge', default='br-int'),
        cfg.BoolOpt('ovs_use_veth', default=False),

    ])

    AGENT_OPTIONS = [
        cfg.StrOpt('root_helper', default='sudo'),
    ]

    cfg.CONF.register_opts(AGENT_OPTIONS, 'AGENT')

    # FIXME: Convert these to regular options, not command line options.
    cfg.CONF.register_cli_opts([
        cfg.IntOpt('health-check-period',
                   default=60,
                   help='seconds between health checks'),
        cfg.IntOpt('num-workers',
                   short='n',
                   default=16,
                   help='the number of worker processes to run'),
        cfg.StrOpt('amqp-url',
                   default='amqp://guest:secrete@localhost:5672/',
                   help='connection for AMQP server'),
    ])
    cfg.CONF(argv, project='akanda')

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(processName)s:%(name)s:%(levelname)s:%(message)s',
    )

    # Purge the mgt tap interface on startup
    quantum = quantum_api.Quantum(cfg.CONF)
    quantum.purge_management_interface()

    # Set up the queue to move messages between the eventlet-based
    # listening process and the scheduler.
    notification_queue = multiprocessing.Queue()

    # Listen for notifications.
    #
    # TODO(dhellmann): We will need to pass config settings through
    # here, or have the child process reset the cfg.CONF object.
    notification_proc = multiprocessing.Process(
        target=notifications.listen,
        args=(cfg.CONF.host, cfg.CONF.amqp_url, notification_queue,),
        name='NotificationListener',
    )
    notification_proc.start()
    # notifications.listen(amqp_url, notification_queue)

    worker_dispatcher = worker.Worker()

    # Set up the scheduler that knows how to manage the routers and
    # dispatch messages.
    sched = scheduler.Scheduler(
        num_workers=cfg.CONF.num_workers,
        worker_func=worker_dispatcher.handle_message,
    )

    # Block the main process, copying messages from the notification
    # listener to the scheduler
    shuffle_notifications(notification_queue, sched)

    # Terminate the listening process
    notification_proc.terminate()

    # Purge the mgt tap interface
    quantum.purge_management_interface()

    LOG.info('exiting')
