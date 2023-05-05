import atexit
from mininet.net import Mininet
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.topo import Topo
from mininet.link import TCLink
from mininet.node import RemoteController

net = None

class TreeTopo(Topo):		
    def __init__(self):
        self.monitor_name = 'monitor'
        self.monitor_ip = '10.0.3.1/8'
        self.fake_server_ip = '10.0.2.1/8'
        self.clients = []
        self.servers = []
        self.monitor = None
        self.switch = None
        Topo.__init__(self)
    
    def getContents(self, contents):
        client_num = int(contents[0])
        server_num = int(contents[1])
        return client_num, server_num

    def build(self):
        # Read file contents
        f = open('topology.in',"r")
        contents = f.read().split()
        client_num, server_num = self.getContents(contents)
        host_num = client_num + server_num + 1
        print("Hosts: ", host_num)
        print("Switch: ", 1)
        print("Clients: ", client_num)
        print("Servers: ", server_num)

        # Add switch
        sconfig = {'dpid': "%016x" %1}
        switch_name = 's1'
        self.switch = self.addSwitch(switch_name, **sconfig)
        # Add monitor
        monitor_ip = self.monitor_ip
        monitor_name = self.monitor_name
        self.monitor = self.addHost(monitor_name, ip=monitor_ip)
        self.addLink(monitor_name, switch_name)
        print('monitor:',monitor_ip)
        # Add clients
        for i in range(1, client_num + 1):
            ip = '10.0.1.{}/8'.format(i)
            name = 'client{}'.format(i)
            self.clients.append(self.addHost(name, ip=ip))
            self.addLink(name, switch_name)
            print(name, ip)
        # Add servers
        for i in range(1, server_num + 1):
            ip = '10.0.0.{}/8'.format(i)
            name = 'server{}'.format(i)
            self.clients.append(self.addHost(name, ip=ip))
            self.addLink(name, switch_name)
            print(name, ip)

def startNetwork():
    info('** Creating the tree network\n')
    topo = TreeTopo()
    controllerIP = '0.0.0.0'

    global net
    net = Mininet(topo=topo, link = TCLink,
                  controller=lambda name: RemoteController(name, ip=controllerIP),
                  listenPort=6633, autoSetMacs=True)

    info('** Starting the network\n')
    net.start()

    info('** Running CLI\n')
    CLI(net)

def stopNetwork():
    if net is not None:
        net.stop()

if __name__ == '__main__':
    # Force cleanup on exit by registering a cleanup function
    atexit.register(stopNetwork)

    # Tell mininet to print useful information
    setLogLevel('info')
    startNetwork()
