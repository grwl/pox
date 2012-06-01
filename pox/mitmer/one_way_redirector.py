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
Redirector module for L2 Mitmer.
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

cookie = 0x1234

class OneWayRedirector(object):
  '''
  This redirector will capture and redirect L3 connection to the specified destination
  '''
  def __init__(self, mitmer, in_port, out_port, proto, nw_dst, tp_dst, tap_tp_port):
	self.mitmer = mitmer
  	self.in_port = in_port
  	self.out_port = out_port  # XXX not implemented 

	if proto == 'udp':   self.nw_proto = ipv4.UDP_PROTOCOL
	elif proto == 'tcp': self.nw_proto = ipv4.TCP_PROTOCOL
	else: raise ValueError()

	self.nw_dst = nw_dst
	self.tp_dst = tp_dst

	self.tap_tp_port = tap_tp_port

  def qualify(self, in_port, packet):
	if self.in_port != in_port:
		log.debug('packet disqualified because of ingress port mismatch')
		return False
	ip4h = packet.find("ipv4")  # XXX what about IPv6?
	if ((ip4h == None) or (ip4h.dstip != self.nw_dst) or (ip4h.protocol != self.nw_proto)):
		log.debug('packet disqualified because of IPv4 headers mismatch: %s' % ip4h)
		return False

        if ip4h.protocol == ipv4.UDP_PROTOCOL:
                tph = packet.find("udp")
        elif ip4h.protocol == ipv4.TCP_PROTOCOL:
                tph = packet.find("tcp")
        else: raise NotImplemented()

	if ((tph == None) or (tph.dstport != self.tp_dst)):
		log.debug('packet disqualified because of TP headers mismatch: %s' % tph)
		return False
	return True

  def process(self, in_port, buffer_id, packet):
	if not self.qualify(in_port, packet):
		return False

        # get TCP/UDP port (XXX refactor XXX)
        ip4h = packet.find("ipv4")  # XXX what about IPv6?
        if ip4h is None: raise ValueError()
        if ip4h.protocol == ipv4.UDP_PROTOCOL:
                tph = packet.find("udp")
        elif ip4h.protocol == ipv4.TCP_PROTOCOL:
                tph = packet.find("tcp")
        else: raise ValueError()
        if tph is None: raise ValueError()

	# -- the forward flow --
	# capture all similar packets
        match1 = of.ofp_match.from_packet(packet)

	actions1 = []
	# L2/L3 SNAT to TAPGW
	actions1.append(of.ofp_action_dl_addr(type=OFPAT_SET_DL_SRC, dl_addr=self.mitmer.tap.tapgw_dl_addr))
	actions1.append(of.ofp_action_nw_addr(type=OFPAT_SET_NW_SRC, nw_addr=self.mitmer.tap.tapgw_nw_addr))
	# L2/L3 DNAT to TAP
	actions1.append(of.ofp_action_dl_addr(type=OFPAT_SET_DL_DST, dl_addr=self.mitmer.tap.tap_dl_addr))
	actions1.append(of.ofp_action_nw_addr(type=OFPAT_SET_NW_DST, nw_addr=self.mitmer.tap.tap_nw_addr))
	actions1.append(of.ofp_action_tp_port(type=OFPAT_SET_TP_DST, tp_port=self.tap_tp_port))

	# output to TAP port
	actions1.append(of.ofp_action_output(port = self.mitmer.tap.port))
	self.mitmer.mk_flow(match1, actions1, buffer_id, cookie=cookie)

	# -- the reverse flow --
	# capture the expected tap server response, bearing in mind our translations
	# XXX here and in other places: match nw_proto, vlan, etc
	match2 = of.ofp_match(
		dl_src = self.mitmer.tap.tap_dl_addr, dl_dst = self.mitmer.tap.tapgw_dl_addr,
		nw_src = self.mitmer.tap.tap_nw_addr, nw_dst = self.mitmer.tap.tapgw_nw_addr,
		tp_src = self.tap_tp_port, tp_dst = tph.srcport)

	actions2 = []
	# L2/L3 DNAT to original packet source
	actions2.append(of.ofp_action_dl_addr(type=OFPAT_SET_DL_DST, dl_addr=packet.src))
	actions2.append(of.ofp_action_nw_addr(type=OFPAT_SET_NW_DST, nw_addr=ip4h.srcip))
	# L2/L3 SNAT to original packet destination
	actions2.append(of.ofp_action_dl_addr(type=OFPAT_SET_DL_SRC, dl_addr=packet.dst))
	actions2.append(of.ofp_action_nw_addr(type=OFPAT_SET_NW_SRC, nw_addr=ip4h.dstip))
	actions2.append(of.ofp_action_tp_port(type=OFPAT_SET_TP_SRC, tp_port=tph.dstport))
	# output to the original ingress port
	actions2.append(of.ofp_action_output(port = in_port))
	self.mitmer.mk_flow(match2, actions2, cookie=cookie)

	return True

