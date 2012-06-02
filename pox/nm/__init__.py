'''
This module gives access to the configuration of Linux network stack.
There is Stack singleton object containing other configuration elements.
'''
import os
import subprocess

import threading

OVS_CONTROLLER_URL = 'tcp:127.0.0.1:6633'

tap_dl_addr='b8:8d:12:53:76:45'
tap_nw_addr='10.255.255.254'
tapgw_dl_addr='b8:8d:12:53:76:46'
tapgw_nw_addr='10.255.255.253'
tap_nw_masklen=30
tap_nw_bcast='10.255.255.255'

class Iface(object):
    def __init__(self, up, loopback, carrier):
        self.up = up
        self.loopback = loopback
        self.carrier = carrier

    def set_duplex(self, duplex): self.duplex = duplex

    def set_speed(self, speed): self.speed = speed


class Sudo:
    @staticmethod
    def do(cmd):
      if subprocess.call(cmd, close_fds=True) != 0:
    	raise RuntimeError('command "%s" has failed"' % cmd)

    @staticmethod
    def sudo(cmd):
      sudo_cmd = ['sudo']
      sudo_cmd.extend(cmd)
      if subprocess.call(sudo_cmd, close_fds=True) != 0:
    	raise RuntimeError('command "%s" has failed"' % sudo_cmd)

class Stack(object):
    def __init__(self):
	self.refresh()

    def refresh(self):
        out = Sudo.do(['ip', 'link', 'list'])
        self.parse_ip_links_out(out)
        pass

  def parse_ip_links_out(self, out):
   self.links = []
   out_lines = out.split('\n')

   i = 0
   while i < range(len(out_lines):
    # -- extract interface name from the first line
    # 3: wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP qlen 1000
    line0_match = re.search('^\d+: (\w+):', out_lines[i])
    if line0_match is None:
      raise RuntimeError('malformed line in the output: %s' % out_lines[i])
    iface = line0_match.group(1)
    i += 1

    # -- parse the remaining lines of the output containing addresses
    addresses = dict()

    while i < len(out_lines):
      # tokenize the line
      line = out_lines[i]
      words = line.split(' ')
      if len(words) == 0:
        continue  # skip empty lines
      if len(words) < 3:
        raise RuntimeError('malformed line in the output: %s' % line)

      # link/ether 00:27:10:ea:51:f4 brd ff:ff:ff:ff:ff:ff
      # inet 10.252.48.103/24 brd 10.252.48.255 scope global wlan0

      layer = words[0]
      if not addresses.has_key(layer): addresses[layer] = []
      addresses[layer].append({'addr': words[1], 'other': words[2:]))

      i += 1

    link = {name: iface, addrs: addresses}
    self.ifaces.append(link)

    #def parse_ethtool_out(self, link, out):
    #    pass

    def get_iface(self, iface):
        return self.links[iface]

#    def set_iface_policy(self, iface, policy):
#
#        self.links[iface].policy = policy
#
#    def set_global_policy(self, policy):
#        self.policy = policy


class Controller(object):
    should_stop = False
    bridge_name = 'mitm0'

    def __init__(self):
        #threading.Thread.__init__(self, target = self.run)
        self.initialized = False

    def run(self):
        pass

    def start(self):
	pass

    def stop(self):
        self.should_stop = True

    def join(self):
	pass

    def sudo(self, *kargs, **kwargs):
        return Sudo.sudo(*kargs, **kwargs)

    def spawn(self, cmd):
        return subprocess.Popen(cmd, close_fds=True)

    def init_mitm_switch(self, standalone=False):
        assert not self.initialized, 'double initialization'
        self.sudo(['ovs-vsctl', 'add-br', self.bridge_name])
        try:
            # assume freshly created vswitch, no need to clean
            if not standalone:
              self.sudo(['ovs-vsctl', 'set-fail-mode', self.bridge_name, 'secure'])
              self.sudo(['ovs-vsctl', 'set-controller', self.bridge_name, OVS_CONTROLLER_URL])
            self.sudo(['ovs-vsctl', 'add-port', self.bridge_name, self.iface1])
            self.sudo(['ovs-vsctl', 'add-port', self.bridge_name, self.iface2])

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
            self.initialized = False

    def set_mitm_ifaces(self, iface1, iface2):
        self.iface1 = iface1
        self.iface2 = iface2

    def enable_mitm_tap(self):
        self.sudo(['ip', 'link', 'set', 'dev', self.bridge_name, 'up'])
        self.sudo(['ip', 'addr', 'add', '%s/%d' % (tap_nw_addr, tap_nw_masklen), 'broadcast', tap_nw_bcast, 'dev', self.bridge_name])

    def disable_mitm_tap(self):
        self.sudo(['ip', 'addr', 'del', '%s/%d' % (tap_nw_addr, tap_nw_masklen), 'broadcast', tap_nw_bcast, 'dev', self.bridge_name])
        self.sudo(['ip', 'link', 'set', 'dev', self.bridge_name, 'down'])

    def add_metaflow(self, mf):
        raise NotImplemented()

    def remove_metaflow(self, mf):
        raise NotImplemented()

stack = Stack()
controller = Controller()
