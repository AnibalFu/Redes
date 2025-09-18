from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.cli import CLI

class FTTopo(Topo):
    def build(self):
        s = self.addSwitch('s1')
        srv = self.addHost('h1')  # servidor
        c1  = self.addHost('h2')  # cliente 1
        c2  = self.addHost('h3')  # cliente 2
        link = dict(bw=10, delay='10ms', loss=10)  # 10% pérdida
        self.addLink(srv, s, **link)
        self.addLink(c1,  s, **link)
        self.addLink(c2,  s, **link)

if __name__ == '__main__':
    net = Mininet(topo=FTTopo(), link=TCLink)
    net.start()
    CLI(net)
    net.stop()
