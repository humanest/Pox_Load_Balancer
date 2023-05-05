import logging
import multiprocessing
import random
import socket
import time
import pickle

from commonData import Request, SenderSocket, set_up_log

REQUEST_CPU_USAGE_RANGE = [10, 20]  # In percentage
REQUEST_TIME_USAGE_RANGE = [50, 100]  # In ms
REQUEST_SIZE = 40
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
        is_monitor_connected = self.monitor_socket.connect()

        for request in requests:
            request.request_send_time = time.time()
            message = pickle.dumps(request)
            request_done_data = self.server_socket.send_and_receive(message)
            request_done = pickle.loads(request_done_data)
            request_done.reply_receive_time = time.time()
            logging.info("Client {} received reply: {}, time info: {}".format(
                self.client_id, request_done.info(), request_done.time_info()))

            if is_monitor_connected:
                self.monitor_socket.send_and_receive(
                    pickle.dumps(request_done))
        self.server_socket.close()
        self.monitor_socket.close()
        return True

    def generate_requests(self):
        requests = []
        for _ in range(self.request_size):
            cpu_usage = round(random.uniform(
                self.request_cpu_usage_range[0], self.request_cpu_usage_range[1]), 2)
            time_usage = round(random.uniform(
                self.request_time_usage_range[0], self.request_time_usage_range[1]), 2)
            requests.append(
                Request(self.client_id, self.request_id, cpu_usage, time_usage))
            self.request_id += 1
        return requests

    def run(self):
        requests = self.generate_requests()
        self.send_requests(requests)


def run_a_client(name="client"):
    client = Client(name)
    client.run()


if __name__ == '__main__':
    set_up_log()
    for i in range(20):
        name = str(chr(65+i))
        multiprocessing.Process(target=run_a_client, args=(name,)).start()
