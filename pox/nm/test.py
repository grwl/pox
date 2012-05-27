import unittest

from pox import nm

TESTBED_MITMER_IFACE1 = 'eth1'
TESTBED_MITMER_IFACE2 = 'eth2'

TESTBED_SERVER2 = '10.255.254.1'
TESTBED_SERVER2 = '10.255.254.2'

OOB_TESTBED_HOST1 = 'mitmer-testbed-host1.local'
OOB_TESTBED_MITMER = 'mitmer-testbed-mitmer.local'
OOB_TESTBED_HOST2 = 'mitmer-testbed-host2.local'

class TestController(unittest.TestCase):
    def setUp(self):
        self.controller = nm.Controller()
        self.controller.set_mitm_ifaces(TESTBED_MITMER_IFACE1, TESTBED_MITMER_IFACE2)
        self.controller.start()

    def tearDown(self):
        self.controller.deinit_mitm_switch()
        self.controller.stop()
        self.controller.join()

    def test_0010_testbed_httpservers_run(self):
        self.assert_wget('http://%s/mitmer.txt' % OOB_TESTBED_MITMER, 'mitmer\n')
        self.assert_wget('http://%s/mitmer.txt' % OOB_TESTBED_HOST2, 'host2\n')

    def test_0020_no_connectivity_without_switch(self):
        ''' there is no connectivity without the switch '''
        self.assertRaises(
            IOError,
            self.assert_wget, 'http://%s:10080/mitmer.txt' % OOB_TESTBED_HOST1, 'whatever\n');

    def test_0030_can_init_mitm_switch(self):
        ''' just test that we can initialize the switch '''
        self.controller.init_mitm_switch()

    def test_0040_empty_switch_transparent(self):
        ''' empty switch is transparent '''
        self.controller.init_mitm_switch()
	import time
	time.sleep(10)
        self.assert_wget('http://%s:10080/mitmer.txt' % OOB_TESTBED_HOST1, 'host2\n')

    def _test_add_metaflow(self):
        self.controller.init_mitm_switch()
        self.controller.enable_mitm_tap()

        mf = MetaFlow(
            of.ofp_match(in_port = TEST_MITM_IFACE1, nw_dst = TEST_HOST2, tp_dst = 80),
            OneWayInterceptor()
        )
        self.controller.add_metaflow(mf)

        self.assert_wget('http://%s:10080/mitmer.txt' % OOB_TEST_HOST1, 'mitmer\n')

        self.controller.remove_metaflow(mf)

        self.controller.disable_mitm_tap()

    def _test_enable_mitm_tap(self):
        self.controller.init_mitm_switch()
        self.controller.enable_mitm_tap()
        self.controller.disable_mitm_tap()

    def assert_wget(self, url, expected_content):
        ''' This method fetches data from the specified URL and compared the returned content with the expected one '''
        import urllib
        f = urllib.urlopen(url)
        actual_content = f.read()
        f.close()
        self.assertEqual(expected_content, actual_content)

if __name__ == '__main__':
    unittest.main()
