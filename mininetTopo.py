import atexit
import threading
import time
from mininet.net import Mininet
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.topo import Topo
from mininet.link import TCLink
from mininet.node import RemoteController

net = None
MONITOR_NAME = 'monitor'
MONITOR_IP = '10.0.3.1'
MONITOR_CLIENT_PORT = 6000
MONITOR_SERVER_PORT = 6001
# FAKE_SERVER_IP = '10.0.2.1'
FAKE_SERVER_IP = '10.0.0.1'
SERVER_PORT = 5000
CONTROLLER_IP = '0.0.0.0'


class LoadBalanceNetLauncher:
    def __init__(self):
        self.net_mask = "/8"
        self.monitor_name = MONITOR_NAME
        self.monitor_ip = MONITOR_IP
        self.monitor_client_port = MONITOR_CLIENT_PORT
        self.monitor_server_port = MONITOR_SERVER_PORT
        self.fake_server_ip = FAKE_SERVER_IP
        self.server_port = SERVER_PORT
        self.controller_ip = CONTROLLER_IP
        self.clients = []
        self.servers = []
        self.monitor = None
        self.switch = None
        self.net = None
        self.topo = Topo()

    def getContents(self, contents):
        client_num = int(contents[0])
        server_num = int(contents[1])
        return client_num, server_num

    def build_net(self):
        info('** Creating the network\n')
        self.net = Mininet(topo=self.topo, link=TCLink,
                           controller=lambda name: RemoteController(
                               name, ip=self.controller_ip),
                           listenPort=6633, autoSetMacs=True, build=False,)

        # Read file contents
        f = open('topology.in', "r")
        contents = f.read().split()
        client_num, server_num = self.getContents(contents)
        host_num = client_num + server_num + 1
        print("Hosts: ", host_num)
        print("Switch: ", 1)
        print("Clients: ", client_num)
        print("Servers: ", server_num)

        # Add switch
        sconfig = {'dpid': "%016x" % 1}
        switch_name = 's1'
        self.switch = self.net.addSwitch(switch_name, **sconfig)
        # Add monitor
        monitor_ip = self.monitor_ip + self.net_mask
        monitor_name = self.monitor_name
        self.monitor = self.net.addHost(monitor_name, ip=monitor_ip)
        self.net.addLink(monitor_name, switch_name)
        print('monitor:', monitor_ip)
        # Add clients
        for i in range(1, client_num + 1):
            ip = '10.0.1.{}/8'.format(i)
            name = 'client{}'.format(i)
            self.clients.append(self.net.addHost(name, ip=ip))
            self.net.addLink(name, switch_name)
            print(name, ip)
        # Add servers
        for i in range(1, server_num + 1):
            ip = '10.0.0.{}/8'.format(i)
            name = 'server{}'.format(i)
            self.servers.append(self.net.addHost(name, ip=ip))
            self.net.addLink(name, switch_name)
            print(name, ip)

    def launch_host(self):
        command = "python3 monitor.py --monitor_ip {} --monitor_client_port {} --monitor_server_port {} --log INFO &".format(
            self.monitor_ip, self.monitor_client_port, self.monitor_server_port)
        self.monitor.cmdPrint(command)
        time.sleep(0.01)
        for server in self.servers:
            command = "python3 server.py --server_ip {} --server_port {} --monitor_ip {} --monitor_port {} --log INFO &".format(
                server.IP(), self.server_port, self.monitor_ip, self.monitor_server_port)
            server.cmdPrint(command)
            time.sleep(0.01)
        for client in self.clients:
            command = "python3 client.py --client_ip {} --client_id {} --server_ip {} --server_port {} --monitor_ip {} --monitor_port {} --log INFO &".format(
                client.IP(), client.name, self.fake_server_ip, self.server_port, self.monitor_ip, self.monitor_client_port)
            client.cmdPrint(command)
            client.cmdPrint("ifconfig")
            time.sleep(0.01)
        pass

    def start(self):
        self.net.start()

    def stop(self):
        if self.net is not None:
            self.net.stop()


if __name__ == '__main__':
    launcher = LoadBalanceNetLauncher()
    # Force cleanup on exit by registering a cleanup function
    atexit.register(launcher.stop)

    # Tell mininet to print useful information
    setLogLevel('info')
    launcher.build_net()
    launcher.start()
    launcher.launch_host()
    CLI(launcher.net)
