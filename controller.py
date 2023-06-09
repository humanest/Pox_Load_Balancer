from pox.core import core
from pox.openflow import *
import pox.openflow.discovery
import pox.openflow.libopenflow_01 as of
from pox.lib.packet.arp import arp
from pox.lib.packet.ipv4 import ipv4
from pox.lib.addresses import EthAddr, IPAddr
from pox.lib.packet.ethernet import ethernet, ETHER_BROADCAST
from pox.lib.recoco import Timer
import random
import pickle
import threading
import time
import traceback

import sys
import os
 
sys.path.insert(1, os.getcwd())

CHECK_SERVER_PERIOD = 10  # in ms
LOG_FOLDER_PATH = "/tmp/server_status/"
log = core.getLogger()


class readFile(threading.Thread):
    def __init__(self, server_ips, server_status):
        threading.Thread.__init__(self)
        self.server_ips = server_ips
        self.server_status = server_status

    def updateStatus(self, ip):
        #print("try open:", LOG_FOLDER_PATH+ip)
        file_address = LOG_FOLDER_PATH+ip
        try:
            if os.path.isfile(file_address) and os.path.getsize(file_address) > -1:
                f = open(file_address, "rb")
                data = pickle.load(f)
                cpu_usage = data.status_log[-1].cpu_usage
                timestamp = data.status_log[-1].timestamp
                self.server_status[IPAddr(ip)] = cpu_usage
                #print("server {}, usage: {}".format(ip, cpu_usage))
                f.close()
        except:
            print(traceback.format_exc())
            #print("status file not exist")
            self.server_status[IPAddr(ip)] = 0
    

    def run(self):
        while True:
            for ip in self.server_ips:
                self.updateStatus(ip.toStr())
            time.sleep(CHECK_SERVER_PERIOD/1000)


class Controller(EventMixin):
    def __init__(self, switch_ip, server_ips_lst, client_ips_lst, monitor_ip, switch_mac, policy):
        self.listenTo(core.openflow)
        core.openflow_discovery.addListeners(self)
        # loadbalancing policy
        self.policy = policy
        # list of client and server ip
        self.monitor_ip = monitor_ip
        self.server_status = {}
        self.server_ips = server_ips_lst
        self.client_ips = client_ips_lst
        # index for round robin decision making
        self.index = 0
        self.all_ip = []
        for ip in self.client_ips:
            self.all_ip.append(ip)
        for ip in self.server_ips:
            self.server_status[ip] = 0
            self.all_ip.append(ip)
        self.all_ip.append(self.monitor_ip)
        # every packet is sent to this ip address and be modified and forwarded
        self.switch_ip = switch_ip
        self.switch_mac = switch_mac
        # ip -> mac and port table
        self.server_iptomac = {}
        self.client_iptomac = {}
        self.monitor_macport = ()
        if int(self.policy) == 3:
            self.run_read_usage_thread(self.server_ips, self.server_status)

    def run_read_usage_thread(self, server_ips, server_status):
        thread = readFile(server_ips, server_status)
        thread.start()

    def target_server(self):
        # random policy
        if int(self.policy) == 1:
            ip = random.choice(self.server_ips)
            print("************randomIP: " + str(ip) + "************")
            return ip
        # round robin policy
        elif int(self.policy) == 2:
            ip = self.server_ips[self.index]
            self.index = self.index + 1
            if self.index > len(self.server_ips) - 1:
                self.index = 0
            print("************roundrobinIP: " + str(ip) + "************")
            return ip
        # resource based policy
        elif int(self.policy) == 3:
            print("server status: " + str(self.server_status))
            ip = min(self.server_status, key=self.server_status.get)
            print("************resourceIP: " + str(ip) + "************")
            return ip

    def handle_arp_packet(self, packet, connection, inport):
        srcip = packet.payload.protosrc
        dstip = packet.payload.protodst
        if packet.payload.opcode == arp.REQUEST:
            # packet is from client
            if srcip == self.monitor_ip:
                arp_packet = arp()
                if dstip in self.client_iptomac:
                    dstmac = self.client_iptomac[dstip][0]
                elif dstip in self.server_iptomac:
                    dstmac = self.server_iptomac[dstip][0]
                arp_packet.hwsrc = dstmac
                arp_packet.hwdst = self.monitor_macport[0]
                arp_packet.opcode = arp_packet.REPLY
                arp_packet.prototype = arp_packet.PROTO_TYPE_IP
                arp_packet.protosrc = packet.payload.protodst
                arp_packet.protodst = packet.payload.protosrc
                ether_packet = ethernet()
                ether_packet.type = ethernet.ARP_TYPE
                ether_packet.src = dstmac
                ether_packet.dst = self.monitor_macport[0]
                ether_packet.set_payload(arp_packet)
                msg = of.ofp_packet_out()
                msg.data = ether_packet.pack()
                msg.actions.append(of.ofp_action_output(port=inport))
                connection.send(msg)
            elif dstip == self.monitor_ip:
                arp_packet = arp()
                if srcip in self.client_iptomac:
                    srcmac = self.client_iptomac[srcip][0]
                elif srcip in self.server_iptomac:
                    srcmac = self.server_iptomac[srcip][0]
                arp_packet.hwsrc = self.monitor_macport[0]
                arp_packet.hwdst = srcmac
                arp_packet.opcode = arp_packet.REPLY
                arp_packet.prototype = arp_packet.PROTO_TYPE_IP
                arp_packet.protosrc = packet.payload.protodst
                arp_packet.protodst = packet.payload.protosrc
                ether_packet = ethernet()
                ether_packet.type = ethernet.ARP_TYPE
                ether_packet.src = self.monitor_macport[0]
                ether_packet.dst = srcmac
                ether_packet.set_payload(arp_packet)
                msg = of.ofp_packet_out()
                msg.data = ether_packet.pack()
                msg.actions.append(of.ofp_action_output(port=inport))
                connection.send(msg)
            else:
                if srcip in self.client_ips:
                    self.client_iptomac[srcip] = (packet.src, inport)
                    if dstip == self.switch_ip:
                        # send the arp reply packet
                        arp_packet = arp()
                        arp_packet.hwsrc = self.switch_mac
                        arp_packet.hwdst = packet.src
                        arp_packet.opcode = arp_packet.REPLY
                        arp_packet.prototype = arp_packet.PROTO_TYPE_IP
                        arp_packet.protosrc = packet.payload.protodst
                        arp_packet.protodst = packet.payload.protosrc
                        ether_packet = ethernet()
                        ether_packet.type = ethernet.ARP_TYPE
                        ether_packet.src = self.switch_mac
                        ether_packet.dst = packet.src
                        ether_packet.set_payload(arp_packet)
                        msg = of.ofp_packet_out()
                        msg.data = ether_packet.pack()
                        msg.actions.append(of.ofp_action_output(port=inport))
                        connection.send(msg)
                elif srcip in self.server_ips:
                    if dstip in self.client_iptomac:
                        client_mac = self.client_iptomac[dstip][0]
                        arp_packet = arp()
                        arp_packet.hwsrc = client_mac
                        arp_packet.hwdst = packet.src
                        arp_packet.opcode = arp_packet.REPLY
                        arp_packet.prototype = arp_packet.PROTO_TYPE_IP
                        arp_packet.protosrc = packet.payload.protodst
                        arp_packet.protodst = packet.payload.protosrc
                        ether_packet = ethernet()
                        ether_packet.type = ethernet.ARP_TYPE
                        ether_packet.src = client_mac
                        ether_packet.dst = packet.src
                        ether_packet.set_payload(arp_packet)
                        msg = of.ofp_packet_out()
                        msg.data = ether_packet.pack()
                        msg.actions.append(of.ofp_action_output(port=inport))
                        connection.send(msg)
        if packet.payload.opcode == arp.REPLY:
            if srcip in self.server_ips:
                self.server_iptomac[srcip] = (packet.src, inport)
            if srcip in self.client_ips:
                self.client_iptomac[srcip] = (packet.src, inport)
            if srcip == self.monitor_ip:
                self.monitor_macport = (packet.src, inport)

    def install_rule(self, connection, outport, src_ip, dst_ip, isServerToClient):
        # server to client rule
        if isServerToClient:
            fm = of.ofp_flow_mod()
            fm.match.dl_type = 0x800
            fm.match.nw_dst = dst_ip
            fm.match.nw_src = src_ip
            # make the packet looks like from switch to client
            fm.actions.append(of.ofp_action_nw_addr.set_src(self.switch_ip))
            fm.actions.append(of.ofp_action_dl_addr.set_src(self.switch_mac))
            (client_mac, _) = self.client_iptomac[dst_ip]
            fm.actions.append(of.ofp_action_dl_addr.set_dst(client_mac))
            fm.actions.append(of.ofp_action_output(port=outport))
            connection.send(fm)

        # client to server rule
        else:
            fm = of.ofp_flow_mod()
            fm.match.dl_type = 0x800
            fm.match.nw_dst = self.switch_ip
            fm.match.nw_src = src_ip
            (server_mac, _) = self.server_iptomac[dst_ip]
            fm.actions.append(of.ofp_action_nw_addr.set_dst(dst_ip))
            fm.actions.append(of.ofp_action_dl_addr.set_dst(server_mac))
            fm.actions.append(of.ofp_action_dl_addr.set_src(self.switch_mac))
            fm.actions.append(of.ofp_action_output(port=outport))
            connection.send(fm)

    def handle_ip_packet(self, packet, connection):
        srcip = packet.payload.srcip
        dstip = packet.payload.dstip
        if srcip == self.monitor_ip or dstip == self.monitor_ip:
            fm = of.ofp_flow_mod()
            fm.match.dl_type = 0x800
            fm.match.nw_dst = dstip
            fm.match.nw_src = srcip
            fm.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
            connection.send(fm)
            msg = of.ofp_packet_out()
            msg.data = packet
            action = of.ofp_action_output(port=of.OFPP_FLOOD)
            msg.actions.append(action)
            connection.send(msg)
        # packet from client to switch
        if srcip in self.client_ips and dstip == self.switch_ip:
            msg = of.ofp_packet_out()
            target_server_ip = self.target_server()
            # install rule, modify packet and resend packet
            (server_mac, server_port) = self.server_iptomac[target_server_ip]
            (client_mac, client_port) = self.client_iptomac[srcip]
            self.install_rule(connection, server_port, srcip, target_server_ip, isServerToClient=False)
            self.install_rule(connection, client_port, target_server_ip, srcip, isServerToClient=True)
            packet.payload.dstip = target_server_ip
            packet.dst = server_mac
            msg.data = packet
            action = of.ofp_action_output(port=server_port)
            msg.actions.append(action)
            connection.send(msg)
        # packet from server to client
        elif srcip in self.server_ips and dstip in self.client_ips:
            msg = of.ofp_packet_out()
            (server_mac, server_port) = self.server_iptomac[srcip]
            (client_mac, client_port) = self.client_iptomac[dstip]
            self.install_rule(connection, server_port, dstip, srcip, isServerToClient=False)
            self.install_rule(connection, client_port, srcip, dstip, isServerToClient=True)
            packet.payload.dstip = dstip
            packet.dst = client_mac
            msg.data = packet
            action = of.ofp_action_output(port=client_port)
            msg.actions.append(action)

    def _handle_ConnectionUp(self, event):
        # send arp request packet to form the ip -> mac and port table when connection up
        for ip in self.all_ip:
            arp_packet = arp()
            arp_packet.opcode = arp.REQUEST
            arp_packet.hwtype = arp.HW_TYPE_ETHERNET
            arp_packet.prototype = arp.PROTO_TYPE_IP
            arp_packet.hwlen = 6
            arp_packet.protodst = ip
            arp_packet.protosrc = self.switch_ip

            ether_packet = ethernet()
            ether_packet.type = ethernet.ARP_TYPE
            ether_packet.dst = ETHER_BROADCAST
            ether_packet.src = self.switch_mac
            ether_packet.set_payload(arp_packet)

            msg = of.ofp_packet_out()
            msg.data = ether_packet.pack()
            msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
            event.connection.send(msg)

    def _handle_PacketIn(self, event):
        packet = event.parsed
        if packet.type == packet.ARP_TYPE:
            self.handle_arp_packet(event.parsed, event.connection, event.port)
        elif packet.type == packet.IP_TYPE:
            self.handle_ip_packet(event.parsed, event.connection)
        else:
            log.debug("unknown packet received")

def read_config_from_file():
    contents = None
    with open('topology.in', "r") as f:
        contents = f.read().split()
    client_num = int(contents[0])
    server_num = int(contents[1])
    return client_num, server_num

def launch(policy):
    client_num, server_num = read_config_from_file()
    s_ip_lst = []
    c_ip_lst = []
    for i in range(client_num):
        c_ip_lst.append(IPAddr('10.0.1.'+str(i+1)))
    for i in range(server_num):
        s_ip_lst.append(IPAddr('10.0.0.'+str(i+1)))
    fake_switch_ip = IPAddr("10.0.2.1")
    fake_switch_mac = EthAddr("00:00:00:00:00:11")
    pox.openflow.discovery.launch()
    core.registerNew(Controller, fake_switch_ip, s_ip_lst, c_ip_lst, IPAddr('10.0.3.1'), fake_switch_mac, policy)