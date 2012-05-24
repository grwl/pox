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
L2 Mitmer.
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

log = core.getLogger()

# Default flow idle timeout value to use when creating new flows
FLOW_IDLE_TIMEOUT = 60


class Tap(object):
	port = 65534
	tap_dl_addr = EthAddr('b8:8d:12:53:76:45')
	tap_nw_addr = IPAddr('10.255.255.254')
	tapgw_dl_addr = EthAddr('b8:8d:12:53:76:46')
	tapgw_nw_addr = IPAddr('10.255.255.253')


class Mitmer (EventMixin):
  '''
  By default Mitmer behaves like a wire, forwarding packets between two ports.
  For each new L3 connection it creates a flow.
  If connection redirection is setup, it will create a redirection flow.
  '''
  def __init__ (self, connection):
    self.connection = connection

    self.ports = [1, 2]
    self.tap = Tap()

    self.redirectors = [
	TFTP_Redirector(
		self,
		in_port = 2,
		server_nw_addr = '10.66.98.1'
	)
    ]

    # We want to hear PacketIn messages, so we listen
    self.listenTo(connection)

    log.info("Initializing Mitmer, ports=%s", self.ports)

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
    	log.info("from port %d got a packet: %s" % (in_port, packet))

	buffer_id = event.ofp.buffer_id

	if self.isTapPort(in_port):
    		log.debug("dropping a packet received on the tap port: %s" % packet)
		return
	elif not self.redirect(in_port, buffer_id, packet):
		# just forward it through to another port
		anotherPort = self.getAnotherPort(in_port)
		self.straight_forward(in_port, buffer_id, packet, anotherPort)

  def straight_forward(self, in_port, buffer_id, packet, out_port):
	'''
	This method:
		1) forwards the given buffer to the specified port
		2) creates a flow to forward packets similar to the given one
	'''
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
			log.info('processed with redirector %s' % redirector)
			return True
	log.debug('not processed with any redirector')
	return False

  def mk_flow(self, match, actions, buffer_id=None):
	msg = of.ofp_flow_mod()
	msg.match = match
	msg.idle_timeout = FLOW_IDLE_TIMEOUT
	if buffer_id != None:
		msg.buffer_id = buffer_id
	msg.actions.extend(actions)
	self.connection.send(msg)


class TFTP_Redirector(object):
  '''
  This redirector will capture TFTP requests to the given server and redirect them to the tap
  '''
  TFTP_SERVER_PORT = 69

  def __init__(self, mitmer, in_port, server_nw_addr):
	self.mitmer = mitmer
  	self.in_port = in_port
	self.server_nw_addr = server_nw_addr

  def qualify(self, in_port, packet):
	if self.in_port != in_port:
		log.debug('packet disqualified because of ingress port mismatch')
		return False
	ip4h = packet.find("ipv4")  # XXX what about IPv6?
	if (ip4h == None
		or (ip4h.dstip != self.server_nw_addr)
		or (ip4h.protocol != ipv4.UDP_PROTOCOL)):
		log.debug('packet disqualified because of IPv4 headers mismatch: %s' % ip4h)
		return False
    	udph = packet.find("udp")
	if (udph == None
		or (udph.dstport != self.TFTP_SERVER_PORT)):
		log.info('packet disqualified because of UDP headers mismatch: %s' % udph)
		return False
	return True

  def process(self, in_port, buffer_id, packet):
	if not self.qualify(in_port, packet):
		return False

	ip4h = packet.find("ipv4")  # XXX what about IPv6?
    	udph = packet.find("udp")

	# -- forward flow
	# capture all similar packets, but ignore destination UDP port
        match1 = of.ofp_match.from_packet(packet)
        match1.tp_dst = None  # XXX should add a flag to from_packet() instead

	actions1 = []
	# L2/L3 SNAT to TAPGW
	actions1.append(of.ofp_action_dl_addr(type=OFPAT_SET_DL_SRC, dl_addr=self.mitmer.tap.tapgw_dl_addr))
	actions1.append(of.ofp_action_nw_addr(type=OFPAT_SET_NW_SRC, nw_addr=self.mitmer.tap.tapgw_nw_addr))
	# L2/L3 DNAT to TAP
	actions1.append(of.ofp_action_dl_addr(type=OFPAT_SET_DL_DST, dl_addr=self.mitmer.tap.tap_dl_addr))
	actions1.append(of.ofp_action_nw_addr(type=OFPAT_SET_NW_DST, nw_addr=self.mitmer.tap.tap_nw_addr))
	# output to TAP port
	actions1.append(of.ofp_action_output(port = self.mitmer.tap.port))
	self.mitmer.mk_flow(match1, actions1, buffer_id)

	# -- reverse flow
	# capture the expected TFTP server response, bearing in mind our translations
	match2 = of.ofp_match(
		dl_src = self.mitmer.tap.tap_dl_addr, dl_dst = self.mitmer.tap.tapgw_dl_addr,
		nw_src = self.mitmer.tap.tap_nw_addr, nw_dst = self.mitmer.tap.tapgw_nw_addr,
		tp_src = match1.tp_dst, tp_dst = match1.tp_src)

	actions2 = []
	# L2/L3 DNAT to original packet source
	actions2.append(of.ofp_action_dl_addr(type=OFPAT_SET_DL_DST, dl_addr=packet.src))
	actions2.append(of.ofp_action_nw_addr(type=OFPAT_SET_NW_DST, nw_addr=ip4h.srcip))
	# L2/L3 SNAT to original packet destination
	actions2.append(of.ofp_action_dl_addr(type=OFPAT_SET_DL_SRC, dl_addr=packet.dst))
	actions2.append(of.ofp_action_nw_addr(type=OFPAT_SET_NW_SRC, nw_addr=ip4h.dstip))
	# output to the original ingress port
	actions2.append(of.ofp_action_output(port = in_port))
	self.mitmer.mk_flow(match2, actions2)

	return True

class l2_mitmer (EventMixin):
  """
  Waits for OpenFlow switches to connect and makes them Mitmers.
  """
  def __init__ (self):
    self.listenTo(core.openflow)

  def _handle_ConnectionUp (self, event):
    log.debug("Connection %s" % (event.connection,))
    Mitmer(event.connection)


def launch ():
  """
  Starts Mitmer.
  """
  core.registerNew(l2_mitmer)

