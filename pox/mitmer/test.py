import os, signal
import unittest
import time
import urllib2
import threading

from pox.core import core
from pox.mitmer import nm

TESTBED_MITMER_IFACE1 = 'eth1'
TESTBED_MITMER_IFACE2 = 'eth2'

TESTBED_SERVER2 = '10.255.254.1'
TESTBED_SERVER2 = '10.255.254.2'

OOB_TESTBED_HOST1 = 'mitmer-testbed-host1.local'
OOB_TESTBED_MITMER = 'mitmer-testbed-mitmer.local'
OOB_TESTBED_HOST2 = 'mitmer-testbed-host2.local'

class TestController(unittest.TestCase):
    def setUp(self):
        nm.controller.set_mitm_ifaces(TESTBED_MITMER_IFACE1, TESTBED_MITMER_IFACE2)
        nm.controller.start()

    def tearDown(self):
        nm.controller.deinit_mitm_switch()
        nm.controller.stop()
        nm.controller.join()

    def test_0060_add_oneway_redirector(self):
        nm.controller.init_mitm_switch()
        nm.controller.enable_mitm_tap()
	time.sleep(1)
	core.mitmer.add_oneway_redirector(
          in_port = 1, out_port = 2,  # XXX
	  dst = 'tcp:%s:80' % TESTBED_SERVER2,
          tap_tp_port=80
	)
        nm.controller.disable_mitm_tap()

    def test_0070_use_oneway_redirector(self):
        nm.controller.init_mitm_switch()
        nm.controller.enable_mitm_tap()
        time.sleep(1)
        core.mitmer.add_oneway_redirector(
          in_port = 1, out_port = 2,  # XXX,
          dst = 'tcp:%s:80' % TESTBED_SERVER2,
          tap_tp_port=80
        )

        self.assert_wget('http://%s:10080/mitmer.txt' % OOB_TESTBED_HOST1, 'mitmer\n', timeout=10, ntries=1)
        nm.controller.disable_mitm_tap()

    def assert_wget(self, url, expected_content, timeout=5, ntries=1):
        ''' This method fetches data from the specified URL and compared the returned content with the expected one '''
	assert(ntries > 0)

	while ntries > 0:
		try:
        		f = urllib2.urlopen(url, timeout=timeout)
        		actual_content = f.read()
        		f.close()
        		self.assertEqual(expected_content, actual_content)
			return
		except Exception as ex:
			last_exception = ex
			ntries -= 1
			time.sleep(timeout)
	raise last_exception

    @staticmethod
    def suite():
	suite = unittest.TestSuite()
    	  suite.addTest(TestController('test_0060_add_oneway_redirector'))
    	  suite.addTest(TestController('test_0070_use_oneway_redirector'))

    	return suite

def run_tests():
	s = TestController.suite()
	if unittest.TextTestRunner(verbosity=2).run(s):
		os.kill(os.getpid(), signal.SIGTERM)
        else:
		os.kill(os.getpid(), signal.SIGABRT)

def launch():
	s = TestController.suite()
	threading.Thread(target = run_tests).start()

#launch()

