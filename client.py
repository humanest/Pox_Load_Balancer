import argparse
import logging
import multiprocessing
import random
import socket
import traceback
import time
import pickle

from commonData import Request, ClientReport, set_up_log

REQUEST_CPU_USAGE_RANGE = [20, 40]  # In percentage
REQUEST_TIME_USAGE_RANGE = [100, 200]  # In ms
REQUEST_SIZE = 2
SERVER_IP = "127.0.1.1"
SERVER_PORT = 5000
MONITOR_IP = "127.0.2.1"
MONITOR_PORT = 6000


class Client():
    def __init__(self, name="client"):
        self.server_ip = SERVER_IP
        self.server_port = SERVER_PORT
        self.server_host = socket.gethostbyname(self.server_ip)
        self.server = (self.server_host, self.server_port)
        self.server_socket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)  # Use Internet, TCP
        
        self.monitor_ip = MONITOR_IP
        self.monitor_port = MONITOR_PORT
        self.monitor_host = socket.gethostbyname(self.monitor_ip)
        self.monitor = (self.monitor_host, self.monitor_port)
        self.monitor_socket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)  # Use Internet, TCP
        self.monitor_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.request_log = []

        self.host = socket.gethostname()
        self.ip = socket.gethostbyname(self.host)
        self.client_id = name

        self.request_cpu_usage_range = REQUEST_CPU_USAGE_RANGE
        self.request_time_usage_range = REQUEST_TIME_USAGE_RANGE
        self.request_size = REQUEST_SIZE
        self.request_id = 0


    def send_requests(self, requests):
        try:
            self.server_socket.connect(self.server)
        except:
            logging.error("Client {} failed to connect: {}".format(
                self.client_id, str(self.server)))
            logging.error(traceback.format_exc())
            return False

        for request in requests:
            request.request_send_time = time.time()
            message = pickle.dumps(request)
            try:
                self.server_socket.send(message)
                logging.info("Client {} sent {}.".format(
                    self.client_id, request.info()))
                request_done_data = self.server_socket.recv(1024)
                if not request_done_data:
                    raise TypeError("No reply from {} for {}".format(
                        str(self.server), self.client_id))
                request_done = pickle.loads(request_done_data)
                request_done.reply_receive_time = time.time()
                self.request_log.append(request)
                logging.info("Client {} received reply: {}, time info: {}".format(
                    self.client_id, request_done.info(), request_done.time_info()))
            except Exception as e:
                logging.error(e)
                logging.error(traceback.format_exc())
                self.server_socket.close()
                return False
        self.server_socket.close()
        return True

    def generate_requests(self):
        requests = []
        for _ in range(self.request_size):
            cpu_usage = random.randint(
                self.request_cpu_usage_range[0], self.request_cpu_usage_range[1])
            time_usage = random.randint(
                self.request_time_usage_range[0], self.request_time_usage_range[1])
            requests.append(
                Request(self.client_id, self.request_id, cpu_usage, time_usage))
            self.request_id += 1
        return requests
    
    def send_client_report(self, report_type):
        if report_type == "start":
            try:
                self.monitor_socket.connect(self.monitor)
            except:
                logging.error("Client {} failed to connect monitor: {}".format(
                    self.client_id, str(self.monitor)))
                logging.error(traceback.format_exc())
                return False
        client_report = ClientReport(self.client_id, report_type, self.request_log)
        message = pickle.dumps(client_report)
        try:
            self.monitor_socket.send(message)
            logging.info("Client {} sent log to monitor.".format(
                self.client_id))
            reply = self.monitor_socket.recv(1024).decode()
            if not reply:
                raise TypeError("No reply from monitor {}".format(
                    str(self.monitor)))
            logging.info("Client {} received monitor reply: {}".format(self.client_id, reply))
        except Exception as e:
            logging.error(e)
            logging.error(traceback.format_exc())
            return False
        if report_type == "finish":
            self.monitor_socket.close()


    def run(self):
        self.send_client_report("start")
        requests = self.generate_requests()
        self.send_requests(requests)
        self.send_client_report("finish")
        self.monitor_socket.close()


def run_a_client(name="client"):
    client = Client(name)
    client.run()


if __name__ == '__main__':
    set_up_log()
    for i in range(2):
        name = str(chr(65+i))
        multiprocessing.Process(target=run_a_client, args=(name,)).start()
