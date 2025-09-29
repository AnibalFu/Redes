from mininet.net import Mininet
from mininet.node import Controller
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.topo import Topo

net = Mininet(controller=Controller, link=TCLink)

c0 = net.addController('c0')

# Add one server host
h1 = net.addHost('h1', ip='10.0.0.1/24')

# Add two client host
h2 = net.addHost('h2', ip='10.0.0.2/24')
h3 = net.addHost('h3', ip='10.0.0.3/24')

s1 = net.addSwitch('s1')

net.addLink(h1, s1, loss=0)
net.addLink(h2, s1, loss=0)
net.addLink(h3, s1, loss=0)

net.start()

CLI(net)

net.stop()
