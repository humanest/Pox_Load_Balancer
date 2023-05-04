import argparse
import logging
import multiprocessing
import random
import socket
import traceback
import time
import pickle

from commonData import Request, ClientReport, SenderSocket, set_up_log

REQUEST_CPU_USAGE_RANGE = [20, 40]  # In percentage
REQUEST_TIME_USAGE_RANGE = [100, 200]  # In ms
REQUEST_SIZE = 2
SERVER_IP = "127.0.1.1"
SERVER_PORT = 5000
MONITOR_IP = "127.0.2.1"
MONITOR_PORT = 6000


class Client():
    def __init__(self, name="client"):
        self.host = socket.gethostname()
        self.ip = socket.gethostbyname(self.host)
        self.client_id = name

        self.server_socket = SenderSocket(
            SERVER_IP, SERVER_PORT, "{}-server".format(self.client_id))

        self.monitor_socket = SenderSocket(
            MONITOR_IP, MONITOR_PORT, "{}-monitor".format(self.client_id))
        self.request_log = []

        self.request_cpu_usage_range = REQUEST_CPU_USAGE_RANGE
        self.request_time_usage_range = REQUEST_TIME_USAGE_RANGE
        self.request_size = REQUEST_SIZE
        self.request_id = 0

    def send_requests(self, requests):
        self.server_socket.connect()

        for request in requests:
            request.request_send_time = time.time()
            message = pickle.dumps(request)
            request_done_data = self.server_socket.send_and_receive(message)
            request_done = pickle.loads(request_done_data)
            request_done.reply_receive_time = time.time()
            self.request_log.append(request)
            logging.info("Client {} received reply: {}, time info: {}".format(
                self.client_id, request_done.info(), request_done.time_info()))
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
        self.monitor_socket.connect()
        client_report = ClientReport(
            self.client_id, report_type, self.request_log)
        message = pickle.dumps(client_report)
        self.monitor_socket.send_and_receive(message)
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
