import argparse
import logging
import multiprocessing
import random
import socket
import time
import pickle

from commonData import Request, SenderSocket

REQUEST_CPU_USAGE_RANGE = [0, 40]  # In percentage
REQUEST_TIME_USAGE_RANGE = [500, 1000]  # In ms
REQUEST_SIZE = 20
SERVER_IP = "127.0.1.1"
SERVER_PORT = 5000
MONITOR_IP = "127.0.2.1"
MONITOR_PORT = 6000
FIX_USAGE = True


def get_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('-log', '--loglevel', default='warning',
                        help='Provide logging level. Example --loglevel debug, default=warning')
    parser.add_argument(
        '--client_ip', default=socket.gethostbyname(socket.gethostname()))
    parser.add_argument('--client_id', default='client')
    parser.add_argument('--server_ip', default=SERVER_IP)
    parser.add_argument('--server_port', default=SERVER_PORT, type=int)
    parser.add_argument('--monitor_ip', default=MONITOR_IP)
    parser.add_argument('--monitor_port', default=MONITOR_PORT, type=int)
    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel.upper(
    ), filename="/tmp/server_status/{}.log".format(args.client_id), filemode='w')
    return args


class Client():
    def __init__(self, args, sub_name=""):
        self.read_argument(args)
        self.client_id += sub_name

        self.server_socket = SenderSocket(
            self.server_ip, self.server_port, "{}-server".format(self.client_id))

        self.monitor_socket = SenderSocket(
            self.monitor_ip, self.monitor_port, "{}-monitor".format(self.client_id))
        self.request_log = []

        self.request_cpu_usage_range = REQUEST_CPU_USAGE_RANGE
        self.use_fix_usage = FIX_USAGE
        self.fixed_usage = random.randint(
            self.request_cpu_usage_range[0], self.request_cpu_usage_range[1])
        self.request_time_usage_range = REQUEST_TIME_USAGE_RANGE
        self.request_size = REQUEST_SIZE
        self.request_id = 0

    def read_argument(self, args):
        self.ip = args.client_ip
        self.client_id = args.client_id
        self.server_ip = args.server_ip
        self.server_port = args.server_port
        self.monitor_ip = args.monitor_ip
        self.monitor_port = args.monitor_port

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
            cpu_usage = self.fixed_usage
            if not self.use_fix_usage:
                cpu_usage = random.randint(
                    self.request_cpu_usage_range[0], self.request_cpu_usage_range[1])
            time_usage = round(random.uniform(
                self.request_time_usage_range[0], self.request_time_usage_range[1]), 2)
            requests.append(
                Request(self.client_id, self.request_id, cpu_usage, time_usage))
            self.request_id += 1
        return requests

    def run(self):
        requests = self.generate_requests()
        self.send_requests(requests)


def run_a_client(args, name=""):
    client = Client(args, name)
    client.run()


if __name__ == '__main__':
    args = get_arguments()
    clinet_num = 1
    for i in range(clinet_num):
        name = ""
        if clinet_num > 1:
            name = "-" + str(chr(65+i))
        multiprocessing.Process(target=run_a_client,
                                args=(args, name,)).start()
