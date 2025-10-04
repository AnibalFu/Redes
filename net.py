from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.node import OVSBridge
from mininet.log import setLogLevel

class FTTopo(Topo):
    def build(self):
        s1  = self.addSwitch('s1')

        # Add server host
        h1 = self.addHost('h1', ip='10.0.0.1/24')
        
        # Add two client hosts
        h2  = self.addHost('h2', ip='10.0.0.2/24')
        h3  = self.addHost('h3', ip='10.0.0.3/24')

        self.addLink(h1, s1, cls=TCLink, bw=20, delay='5ms', loss=10)
        self.addLink(h2, s1, cls=TCLink, bw=10, delay='5ms', loss=0)
        self.addLink(h3, s1, cls=TCLink, bw=10, delay='5ms', loss=0)
        
if __name__ == '__main__':

    setLogLevel('info')
    net = Mininet(topo=FTTopo(), link=TCLink, switch=OVSBridge, controller=None, autoSetMacs=True)
    
    net.start()
    
    CLI(net)
    
    net.stop()
