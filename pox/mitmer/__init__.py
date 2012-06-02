# Copyright 2012 Alexandre Bezroutchko abb@gremwell.com
# Based on forwarding.l2_learning, copyright 2011 James McCauley
#
# This file is part of POX.
#
# POX is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# POX is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with POX.  If not, see <http://www.gnu.org/licenses/>.

'''
Mitmer.
'''

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.revent import *
from pox.lib.util import dpidToStr
from pox.lib.util import str_to_bool
import time
from pox.lib.packet.ipv4 import ipv4
from pox.openflow.libopenflow_01 import *
from pox.lib.addresses import *
from pox.mitmer.one_way_redirector import OneWayRedirector

log = core.getLogger()

# Default flow idle timeout value to use when creating new flows
FLOW_IDLE_TIMEOUT = 60


class Tap(object):
	port = 65534
	tap_dl_addr = None
	tap_nw_addr = IPAddr('10.255.255.254')
	tapgw_dl_addr = EthAddr('b8:8d:12:53:76:46')
	tapgw_nw_addr = IPAddr('10.255.255.253')


class Mitmer (EventMixin):
  '''
  By default Mitmer behaves like a wire, forwarding packets between two ports.
  For each new L3 connection it creates a flow.
  If connection redirection is set up, it will create a redirection flow.
  '''
  def __init__ (self, connection, in_port, out_port, dst, tap_tp_port):
    self.connection = connection

    # XXX should this parsing happen here or in launch()?
    in_port = int(in_port)
    out_port = int(out_port)

    self.ports = [in_port, out_port]
    self.tap = Tap()
    self.redirectors = []

    if dst and tap_tp_port:
      self.add_oneway_redirector(self, in_port, out_port, dst, tap_tp_port)

    # We want to hear PacketIn messages, so we listen
    self.listenTo(connection)

    log.info("Initializing Mitmer, ports=%s", self.ports)

  def add_oneway_redirector(self, in_port, out_port, dst, tap_tp_port):
    '''
    This method can be used to create a one-way redirect to divert
    packet flow 'dst' towards a listener on 'tap_tp_port' port on the local host.
    The destination parameter format is 'tcp:8.8.8.8:53'.
    '''
    (proto, nw_dst, tp_dst) = dst.split(':')
    tp_dst = int(tp_dst)
    tap_tp_port = int(tap_tp_port)

    redirector = OneWayRedirector(self,
      in_port = in_port, out_port = out_port,
      proto = proto, nw_dst = nw_dst, tp_dst = tp_dst,
      tap_tp_port = tap_tp_port
    )

    self.add_redirector(redirector)
    return redirector

  def add_redirector(self, redirector):
    self.redirectors.append(redirector)

  def isTapPort(self, port):
    '''
    Returns true of the given port is the tap port.
    '''
    return (port == self.tap.port)

  def getAnotherPort(self, port):
    '''
    Returns the port complimentary to the given one.
    '''
    if port == self.ports[0]: return self.ports[1]
    elif port == self.ports[1]: return self.ports[0]
    else: raise ValueError('unexpected port %d' % port)

  def _handle_PacketIn (self, event):
	'''
	Handles an incoming packets.
	'''
	packet = event.parse()
	in_port = event.port
    	log.debug("from port %d got a packet: %s" % (in_port, packet))

	buffer_id = event.ofp.buffer_id

	if self.isTapPort(in_port):
    		log.debug("dropping a packet received on the tap port: %s" % packet)
		return
	elif not self.redirect(in_port, buffer_id, packet):
		# just forward it through to another port
		anotherPort = self.getAnotherPort(in_port)
		self.straight_forward(in_port, buffer_id, packet, anotherPort)

  def straight_forward(self, in_port, buffer_id, packet, out_port, cookie=None):
	'''
	This method:
		1) forwards the given buffer to the specified port
		2) creates a flow to forward packets similar to the given one
	'''
	# XXX refactor to use mk_flow
	log.info("installing flow for %s.%i -> %s.%i" % (packet.src, in_port, packet.dst, out_port))
	msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(packet)
        msg.idle_timeout = FLOW_IDLE_TIMEOUT
        msg.actions.append(of.ofp_action_output(port = out_port))
        msg.buffer_id = buffer_id
        self.connection.send(msg)

  def redirect(self, in_port, buffer_id, packet):
	'''
	'''
	for redirector in self.redirectors:
		if redirector.process(in_port, buffer_id, packet):
			log.debug('processed with redirector %s' % redirector)
			return True
	log.debug('not processed with any redirector')
	return False

  def mk_flow(self, match, actions, buffer_id=None, cookie=None):
	msg = of.ofp_flow_mod(cookie=cookie)
	msg.match = match
	msg.idle_timeout = FLOW_IDLE_TIMEOUT
	if buffer_id != None:
		msg.buffer_id = buffer_id
	msg.actions.extend(actions)
	self.connection.send(msg)


class mitmer (EventMixin):
  """
  Waits for OpenFlow switches to connect and makes them Mitmers.
  """
  def __init__ (self, in_port, out_port, dst, tap_tp_port):
    self.in_port = in_port
    self.out_port = out_port
    self.dst = dst
    self.tap_tp_port = tap_tp_port
    self.listenTo(core.openflow)
    self.mitmer = None

  def _handle_ConnectionUp (self, event):
    log.info("Connection %s" % (event.connection,))
    self.mitmer = Mitmer(event.connection, self.in_port, self.out_port, self.dst, self.tap_tp_port)

  def add_oneway_redirector(self, in_port, out_port, dst, tap_tp_port):
    self.mitmer.add_oneway_redirector(in_port, out_port, dst, tap_tp_port)

def launch (in_port=1, out_port=2, dst=None, tap_tp_port=None):
  """
  Starts Mitmer.
  """
  core.registerNew(mitmer, in_port, out_port, dst, tap_tp_port)

