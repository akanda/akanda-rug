import mock
import unittest2 as unittest

from akanda.rug.api import nova


class FakeModel(object):
    def __init__(self, id_, **kwargs):
        self.id = id_
        self.__dict__.update(kwargs)


fake_ext_port = FakeModel(
    '1',
    mac_address='aa:bb:cc:dd:ee:ff',
    network_id='ext-net',
    fixed_ips=[FakeModel('', ip_address='9.9.9.9', subnet_id='s2')])

fake_mgt_port = FakeModel(
    '2',
    mac_address='aa:bb:cc:cc:bb:aa',
    network_id='mgt-net')

fake_int_port = FakeModel(
    '3',
    mac_address='aa:aa:aa:aa:aa:aa',
    network_id='int-net',
    fixed_ips=[FakeModel('', ip_address='192.168.1.1', subnet_id='s1')])

fake_router = FakeModel(
    'router_id',
    tenant_id='tenant_id',
    external_port=fake_ext_port,
    management_port=fake_mgt_port,
    internal_ports=[fake_int_port],
    ports=[fake_mgt_port, fake_ext_port, fake_int_port])


class FakeConf:
    admin_user = 'admin'
    admin_password = 'password'
    admin_tenant_name = 'admin'
    auth_url = 'http://127.0.0.1/'
    auth_strategy = 'keystone'
    auth_region = 'RegionOne'
    router_image_uuid = 'akanda-image'
    router_instance_flavor = 1


class TestNovaWrapper(unittest.TestCase):
    def setUp(self):
        self.addCleanup(mock.patch.stopall)
        patch = mock.patch('novaclient.v1_1.client.Client')
        self.client = mock.Mock()
        self.client_cls = patch.start()
        self.client_cls.return_value = self.client
        self.nova = nova.Nova(FakeConf)

    def test_create_router_instance(self):
        expected = [
            mock.call.servers.create(
                'ak-router_id',
                nics=[{'port-id': '2',
                       'net-id': 'mgt-net',
                       'v4-fixed-ip': ''},
                      {'port-id': '1',
                       'net-id': 'ext-net',
                       'v4-fixed-ip': ''},
                      {'port-id': '3',
                       'net-id': 'int-net',
                       'v4-fixed-ip': ''}],
                flavor=1,
                image='akanda-image'
            )
        ]

        self.nova.create_router_instance(fake_router)
        self.client.assert_has_calls(expected)

    def test_get_instance(self):
        instance = mock.Mock()
        self.client.servers.list.return_value = [instance]

        expected = [
            mock.call.servers.list(search_opts={'name': 'ak-router_id'})
        ]

        result = self.nova.get_instance(fake_router)
        self.client.assert_has_calls(expected)
        self.assertEqual(result, instance)

    def test_get_instance_not_found(self):
        self.client.servers.list.return_value = []

        expected = [
            mock.call.servers.list(search_opts={'name': 'ak-router_id'})
        ]

        result = self.nova.get_instance(fake_router)
        self.client.assert_has_calls(expected)
        self.assertIsNone(result)

    def test_get_router_instance_status(self):
        instance = mock.Mock()
        instance.status = 'ACTIVE'
        self.client.servers.list.return_value = [instance]

        expected = [
            mock.call.servers.list(search_opts={'name': 'ak-router_id'})
        ]

        result = self.nova.get_router_instance_status(fake_router)
        self.client.assert_has_calls(expected)
        self.assertEqual(result, 'ACTIVE')

    def test_get_router_instance_status_not_found(self):
        self.client.servers.list.return_value = []

        expected = [
            mock.call.servers.list(search_opts={'name': 'ak-router_id'})
        ]

        result = self.nova.get_router_instance_status(fake_router)
        self.client.assert_has_calls(expected)
        self.assertIsNone(result)

    def test_destroy_router_instance(self):
        with mock.patch.object(self.nova, 'get_instance') as get_instance:
            get_instance.return_value.id = 'instance_id'

            expected = [
                mock.call.servers.delete('instance_id')
            ]

            self.nova.destroy_router_instance(fake_router)
            self.client.assert_has_calls(expected)

    def test_reboot_router_instance_exists(self):
        with mock.patch.object(self.nova, 'get_instance') as get_instance:
            get_instance.return_value.id = 'instance_id'
            get_instance.return_value.status = 'ACTIVE'
            setattr(
                get_instance.return_value,
                'OS-EXT-AZ:availability_zone',
                'zone1'
            )
            setattr(
                get_instance.return_value,
                'OS-EXT-SRV-ATTR:hypervisor_hostname',
                'hypervisor1'
            )
            get_instance.return_value.status = 'ACTIVE'

            expected = [
                mock.call.servers.delete('instance_id'),
                mock.call.servers.create(mock.ANY, nics=mock.ANY,
                                         flavor=1, image=mock.ANY,
                                         availability_zone='zone1:hypervisor1')
            ]

            self.nova.reboot_router_instance(fake_router)
            self.client.assert_has_calls(expected)

    def test_reboot_router_instance_rebooting(self):
        with mock.patch.object(self.nova, 'get_instance') as get_instance:
            get_instance.return_value.id = 'instance_id'
            get_instance.return_value.status = 'BUILD'

            self.nova.reboot_router_instance(fake_router)
            self.assertEqual(self.client.mock_calls, [])

    def test_reboot_router_instance_missing(self):
        with mock.patch.object(self.nova, 'get_instance') as get_instance:
            with mock.patch.object(self.nova, 'create_router_instance') as cr:
                get_instance.return_value = None

                self.nova.reboot_router_instance(fake_router)
                self.assertEqual(self.client.mock_calls, [])
                cr.assert_called_once_with(fake_router)
