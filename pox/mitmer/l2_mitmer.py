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

log = core.getLogger()

# We don't want to flood immediately when a switch connects.
FLOW_IDLE_TIMEOUT = 60

class Mitmer (EventMixin):
  '''
  By default Mitmer behaves like a wire, forwarding packets between two ports.
  For each new L3 connection it creates a flow.
  If connection redirection is setup, it will create a redirection flow.
  '''
  def __init__ (self, connection):
    self.connection = connection

    self.ports = [1, 2]
    self.tap_port = 65534

    # We want to hear PacketIn messages, so we listen
    self.listenTo(connection)

    log.info("Initializing Mitmer, ports=%s", self.ports)

  def isTapPort(self, port):
    return (port == self.tap_port)

  def getAnotherPort(self, port):
    if port == self.ports[0]: return self.ports[1]
    elif port == self.ports[1]: return self.ports[0]
    else: raise ValueError('unexpected port %d' % port)

  def _handle_PacketIn (self, event):
	'''
	'''
	packet = event.parse()
    	#log.info("got a packet %s" % packet)

	in_port = event.port
	buffer_id = event.ofp.buffer_id

	anotherPort = self.getAnotherPort(in_port)
	self.forward_flow(in_port, buffer_id, packet, anotherPort)

  def forward_flow(self, in_port, buffer_id, packet, out_port):
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

class l2_mitmer (EventMixin):
  """
  Waits for OpenFlow switches to connect and makes them Mitmers.
  """
  def __init__ (self):
    self.listenTo(core.openflow)

  def _handle_ConnectionUp (self, event):
    log.info("Connection %s" % (event.connection,))
    Mitmer(event.connection)


def launch ():
  """
  Starts Mitmer.
  """
  core.registerNew(l2_mitmer)

