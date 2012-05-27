'''
This module gives access to the configuration of Linux network stack.
There is Stack singleton object containing other configuration elements.
'''
import os
import subprocess

import threading

OVS_CONTROLLER_URL = 'tcp:127.0.0.1:6633'

class Iface(object):
    def __init__(self, up, loopback, carrier):
        self.up = up
        self.loopback = loopback
        self.carrier = carrier

    def set_duplex(self, duplex): self.duplex = duplex

    def set_speed(self, speed): self.speed = speed


class Stack(object):
    def run(self):
        out = run_ext_command(['ip', 'link', 'list'])
        self.parse_ip_links_out(out)

        for link in self.links:
            if not link.loopback:
                out = run_ext_command(['ethtool', link])
                self.parse_ethtool_out(link, out)

    def parse_ip_links_out(self, out):
        self.links = dict()
        pass

    def parse_ethtool_out(self, link, out):
        pass

    def get_iface(self, iface):
        return self.links[iface]

    def set_iface_policy(self, iface, policy):

        self.links[iface].policy = policy

    def set_global_policy(self, policy):
        self.policy = policy

class Controller(threading.Thread):
    should_stop = False
    bridge_name = 'mitm0'

    def __init__(self):
        threading.Thread.__init__(self, target = self.run)
        self.initialized = False

    def run(self):
        pass

    def stop(self):
        self.should_stop = True

    def sudo(self, cmd, bg=False):
        sudo_cmd = ['sudo']
        sudo_cmd.extend(cmd)
        if subprocess.call(sudo_cmd) != 0:
            raise RuntimeError('command "%s" has failed"' % sudo_cmd)

    def spawn(self, cmd):
        return subprocess.Popen(cmd)

    def init_mitm_switch(self, failmode_standalone=False):
        assert not self.initialized, 'double initialization'
        self.sudo(['ovs-vsctl', 'add-br', self.bridge_name])
        try:
            # assume freshly created vswitch, no need to clean
            self.sudo(['ovs-vsctl', 'set-fail-mode', self.bridge_name, 'secure'])
            self.sudo(['ovs-vsctl', 'add-port', self.bridge_name, self.iface1])
            self.sudo(['ovs-vsctl', 'add-port', self.bridge_name, self.iface2])
            self.sudo(['ovs-vsctl', 'set-controller', self.bridge_name, OVS_CONTROLLER_URL])

            self.pox = self.spawn(['env', 'PYTHONPATH=../pox', 'python',
                       '../pox/pox.py', '--no-cli', 'forwarding.l2_learning'])
            self.initialized = True
        except:
            try:
                self.sudo(['ovs-vsctl', 'del-br', self.bridge_name])
            except:
                pass
            raise

    def deinit_mitm_switch(self):
        if self.initialized:
            self.sudo(['ovs-vsctl', 'del-br', self.bridge_name])
            self.pox.terminate()
            self.initialized = False

    def set_mitm_ifaces(self, iface1, iface2):
        self.iface1 = iface1
        self.iface2 = iface2

    def enable_mitm_tap(self):
        raise NotImplemented()

    def disable_mitm_tap(self):
        raise NotImplemented()

    def add_metaflow(self, mf):
        raise NotImplemented()

    def remove_metaflow(self, mf):
        raise NotImplemented()

stack = Stack()
controller = Controller()
