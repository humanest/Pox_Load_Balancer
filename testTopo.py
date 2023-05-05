from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info


class InbandController(RemoteController):

    def checkListening(self):
        "Overridden to do nothing."
        return


def emptyNet():
    "Create an empty network and add nodes to it."

    net = Mininet(topo=None,
                  build=False,)

    # net.addController('c0',
    #                   controller=InbandController,
    #                   ip='10.0.0.1',
    #                   port=6633)
    net.addController('c0',
                    controller=RemoteController)

    h1 = net.addHost('h1', ip='10.0.0.1')
    h2 = net.addHost('h2', ip='10.0.0.2')
    h3 = net.addHost('h3', ip='10.0.0.3')

    s1 = net.addSwitch('s1', cls=OVSSwitch, inband=True)
    #print("before port:",s1.listenPort)
    #s1.listenPort = 6633

    net.addLink(h1, s1)
    net.addLink(h2, s1)
    net.addLink(h3, s1)

    net.start()
    s1.cmd('ifconfig s1-eth1 inet 10.0.0.10')
    #print("before port:",s1.listenPort)
    #h1.cmd('~/pox/pox.py forwarding.l2_pairs&')

    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    emptyNet()
