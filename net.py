#!/usr/bin/env python3
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.node import OVSBridge
from mininet.log import setLogLevel

class FTTopo(Topo):
    def build(self):
        s  = self.addSwitch('s1')
        srv = self.addHost('h1')  # servidor
        c1  = self.addHost('h2')  # cliente 1
        c2  = self.addHost('h3')  # cliente 2
        self.addLink(srv, s, cls=TCLink, bw=20, delay='5ms', loss=10)      # h1-s1
        self.addLink(c1,  s, cls=TCLink, bw=10, delay='5ms', loss=0)       # h2-s1
        self.addLink(c2,  s, cls=TCLink, bw=10, delay='5ms', loss=0)       # h3-s1
        
        
if __name__ == '__main__':
    setLogLevel('info')
    net = Mininet(topo=FTTopo(), link=TCLink, switch=OVSBridge, controller=None, autoSetMacs=True)
    net.start()
    CLI(net)
    net.stop()
