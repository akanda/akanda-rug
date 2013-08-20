import mock
import unittest2 as unittest

from quantumclient.common import exceptions as q_exceptions

from akanda.rug import populate
from akanda.rug.api import quantum


class TestPrePopulateWorkers(unittest.TestCase):

    @mock.patch('akanda.rug.api.quantum.Quantum')
    def test_retry_loop(self, mocked_quantum_api):
        quantum_client = mock.Mock()
        returned_value = [Exception, []]
        quantum_client.get_routers.side_effect = returned_value

        mocked_quantum_api.return_value = quantum_client

        sched = mock.Mock()
        populate._pre_populate_workers(sched)
        self.assertEqual(
            quantum_client.get_routers.call_args_list,
            [mock.call() for value in xrange(len(returned_value))]
        )
        self.assertEqual(
            quantum_client.get_routers.call_count,
            len(returned_value)
        )

    def _exit_loop_bad_auth(self, mocked_quantum_api, log, exc):
        quantum_client = mock.Mock()
        quantum_client.get_routers.side_effect = exc
        mocked_quantum_api.return_value = quantum_client
        sched = mock.Mock()
        populate._pre_populate_workers(sched)
        log.warning.assert_called_once_with(
            'PrePopulateWorkers thread failed: %s',
            mock.ANY
        )

    @mock.patch('akanda.rug.populate.LOG')
    @mock.patch('akanda.rug.api.quantum.Quantum')
    def test_exit_loop_unauthorized(self, mocked_quantum_api, log):
        exc = q_exceptions.Unauthorized
        self._exit_loop_bad_auth(mocked_quantum_api, log, exc)

    @mock.patch('akanda.rug.populate.LOG')
    @mock.patch('akanda.rug.api.quantum.Quantum')
    def test_exit_loop_forbidden(self, mocked_quantum_api, log):
        exc = q_exceptions.Forbidden
        self._exit_loop_bad_auth(mocked_quantum_api, log, exc)

    @mock.patch('akanda.rug.populate.LOG')
    @mock.patch('akanda.rug.api.quantum.Quantum')
    def test_retry_loop_logging(self, mocked_quantum_api, log):
        quantum_client = mock.Mock()
        message = mock.Mock(tenant_id='1', router_id='2')
        returned_value = [
            quantum.client.exceptions.QuantumClientException,
            [message]
        ]
        quantum_client.get_routers.side_effect = returned_value

        mocked_quantum_api.return_value = quantum_client

        sched = mock.Mock()
        populate._pre_populate_workers(sched)
        expected = [
            mock.call.warning(u'Could not fetch routers from quantum: '
                              'An unknown exception occurred.'),
            mock.call.warning('sleeping 1 seconds before retrying'),
            mock.call.debug('Start pre-populating the workers '
                            'with %d fetched routers', 1)
        ]
        self.assertEqual(log.mock_calls, expected)

    @mock.patch('akanda.rug.event.Event')
    @mock.patch('akanda.rug.api.quantum.Quantum')
    def test_scheduler_handle_message(self, mocked_quantum_api, event):
        quantum_client = mock.Mock()
        message1 = {'tenant_id': '1', 'router_id': '2',
                    'body': {}, 'crud': 'poll'}
        message2 = {'tenant_id': '3', 'router_id': '4',
                    'body': {}, 'crud': 'poll'}
        return_value = [mock.Mock(**message1), mock.Mock(** message2)]
        quantum_client.get_routers.return_value = return_value

        sched = mock.Mock()
        mocked_quantum_api.return_value = quantum_client
        populate._pre_populate_workers(sched)

        self.assertEqual(sched.handle_message.call_count, len(return_value))
        expected = [
            mock.call(message1['tenant_id'], mock.ANY),
            mock.call(message2['tenant_id'], mock.ANY)
        ]
        self.assertEqual(sched.handle_message.call_args_list, expected)

        self.assertEqual(event.call_count, 2)
        expected = [mock.call(**message1), mock.call(**message2)]
        self.assertEqual(event.call_args_list, expected)

    @mock.patch('threading.Thread')
    def test_pre_populate_workers(self, thread):
        sched = mock.Mock()
        t = populate.pre_populate_workers(sched)
        thread.assert_called_once_with(
            target=populate._pre_populate_workers,
            args=(sched,),
            name='PrePopulateWorkers'
        )
        self.assertEqual(
            t.mock_calls,
            [mock.call.setDaemon(True), mock.call.start()]
        )
