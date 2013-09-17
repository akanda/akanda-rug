"""Populate the workers with the existing routers
"""

import logging
import threading
import time

from oslo.config import cfg
from neutronclient.common import exceptions as n_exceptions

from akanda.rug import event
from akanda.rug.api import neutron

LOG = logging.getLogger(__name__)


def _pre_populate_workers(scheduler):
    """Fetch the existing routers from neutron.

    Wait for neutron to return the list of the existing routers.
    Pause up to max_sleep seconds between each attempt and ignore
    neutron client exceptions.


    """
    nap_time = 1
    max_sleep = 15

    neutron_client = neutron.Neutron(cfg.CONF)

    while True:
        try:
            neutron_routers = neutron_client.get_routers()
            break
        except (n_exceptions.Unauthorized, n_exceptions.Forbidden) as err:
            LOG.warning('PrePopulateWorkers thread failed: %s', err)
            return
        except Exception as err:
            LOG.warning(
                '%s: %s' % ('Could not fetch routers from neutron', err))
            LOG.warning('sleeping %s seconds before retrying' % nap_time)
            time.sleep(nap_time)
            # FIXME(rods): should we get max_sleep from the config file?
            nap_time = min(nap_time * 2, max_sleep)

    LOG.debug('Start pre-populating the workers with %d fetched routers',
              len(neutron_routers))

    for router in neutron_routers:
        message = event.Event(
            tenant_id=router.tenant_id,
            router_id=router.id,
            crud=event.POLL,
            body={}
        )
        scheduler.handle_message(router.tenant_id, message)


def pre_populate_workers(scheduler):
    """Start the pre-populating task
    """

    t = threading.Thread(
        target=_pre_populate_workers,
        args=(scheduler,),
        name='PrePopulateWorkers'
    )

    t.setDaemon(True)
    t.start()
    return t
