import argparse
import logging
import multiprocessing
import os
import pickle
import socket
import time
import traceback

from commonData import SenderSocket, ServerStatus, ServerReport

CPU_RESOURCE = 100  # In percentage
CPU_IDLE_USAGE = 0  # In percentage
MAX_CONNECTION_NUMBER = 100
SERVER_IP = "127.0.1.1"
SERVER_PORT = 5000
MONITOR_IP = "127.0.2.1"
MONITOR_PORT = 6001
CONTROLLER_IP = "10.0.1.1"
CONTROLLER_PORT = 7000
LOG_FREQUENCY = 20  # In ms
LOG_BATCH = 1
LOG_FOLDER_PATH = "/tmp/server_status/"

def get_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('-log', '--loglevel', default='warning',
                        help='Provide logging level. Example --loglevel debug, default=warning')
    parser.add_argument('--server_ip', default=SERVER_IP)
    parser.add_argument('--server_port', default=SERVER_PORT, type=int)
    parser.add_argument('--monitor_ip', default=MONITOR_IP)
    parser.add_argument('--monitor_port', default=MONITOR_PORT, type=int)
    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel.upper(),filename="/tmp/server_status/server_{}.log".format(args.server_ip), filemode='w')
    return args


class Server():
    def __init__(self, args):
        self.read_argument(args)
        self.server_id = self.ip
        self.address = (self.ip, self.port)
        self.socket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)  # Use Internet, TCP
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.address)

        self.monitor_socket = SenderSocket(
            self.monitor_ip, self.monitor_port, "{}-monitor".format(self.ip))
        self.controller_socket = SenderSocket(
            CONTROLLER_IP, CONTROLLER_PORT, "{}-controller".format(self.ip))
        self.status_log = []
        self.log_frequency = LOG_FREQUENCY
        self.log_batch = LOG_BATCH
        self.log_tmp_file_path = LOG_FOLDER_PATH + self.server_id + ".tmp"
        self.log_file_path = LOG_FOLDER_PATH + self.server_id
        if not os.path.exists(LOG_FOLDER_PATH):
            os.makedirs(LOG_FOLDER_PATH)

        self.max_cpu_resource = CPU_RESOURCE
        self.max_connection_number = MAX_CONNECTION_NUMBER

        self.request_manager = multiprocessing.Manager()
        self.request_queue = self.request_manager.Queue()
        self.lock = multiprocessing.Lock()
        self.cpu_usage = multiprocessing.Value('d', CPU_IDLE_USAGE)
        self.cpu_condition = multiprocessing.Condition()

    def read_argument(self, args):
        self.ip = args.server_ip
        self.port = args.server_port
        self.monitor_ip = args.monitor_ip
        self.monitor_port = args.monitor_port

    def wait_for_client(self):
        self.socket.listen(self.max_connection_number)
        while True:
            client, address = self.socket.accept()
            logging.info("Got connection from: {}".format(address))
            client.settimeout(60)
            multiprocessing.Process(target=self.serve_client,
                                    args=(client, address)).start()

    def serve_client(self, client, address):
        logging.info("Start serving client: {}".format(address))
        while True:
            try:
                request_data = client.recv(1024)
                if request_data:
                    request = pickle.loads(request_data)
                    logging.info(
                        "Got request id: {}, added to queue".format(request.id))
                    request.request_receive_time = time.time()
                    self.request_queue.put((request, client))
                else:
                    logging.info("Client {} disconnected".format(address))
                    break
            except:
                logging.error(traceback.format_exc())
                client.close()
                return False

    def handle_request(self, request, client):
        logging.info("Handling request {}...".format(request.id))
        request.request_process_time = time.time()
        time_in_sec = float(request.time_usage) * 1e-3
        time.sleep(time_in_sec)
        request.reply_send_time = time.time()
        client.send(pickle.dumps(request))
        with self.cpu_usage.get_lock():
            self.cpu_usage.value -= request.cpu_usage
        logging.info("Request {} finished, reply sent, current cpu usage: {:.2f}%".format(
            request.id, self.cpu_usage.value))
        with self.cpu_condition:
            self.cpu_condition.notify_all()

    def handle_request_in_queue(self):
        logging.info("Start handling request in queue")
        while True:
            request, client = self.request_queue.get()
            while self.cpu_usage.value + request.cpu_usage > self.max_cpu_resource:
                logging.warning(
                    "Insufficient cpu usage: {:.2f}%, {:.2f}% more needed for request {}-{}"
                    .format(self.cpu_usage.value, request.cpu_usage, request.client_id, request.request_id))
                with self.cpu_condition:
                    self.cpu_condition.wait()
            logging.info("Ready to handle request: {}, current cpu usage: {:.2f}%".format(
                request.info(), self.cpu_usage.value))
            with self.cpu_usage.get_lock():
                self.cpu_usage.value += request.cpu_usage
            multiprocessing.Process(target=self.handle_request,
                                    args=(request, client)).start()

    def generate_log_and_send(self):
        listener_sockets = []
        for listener_socket in [self.monitor_socket,]:
            if listener_socket.connect():
                listener_sockets.append(listener_socket)
        target_time = time.time() + self.log_frequency * 1e-3
        while True:
            target_time += self.log_frequency * 1e-3
            current_status = self.get_current_status()
            self.status_log.append(current_status)
            if len(self.status_log) >= self.log_batch:
                server_report = ServerReport(self.server_id, self.status_log)
                self.unblocking_send(listener_sockets, server_report)
                self.blocking_write(server_report)
                self.status_log = []
            while time.time() < target_time:
                time.sleep(1e-3)

    def unblocking_send(self, listener_sockets, server_report):
        message = pickle.dumps(server_report)
        for listener_socket in listener_sockets:
            multiprocessing.Process(target=listener_socket.send_and_receive, args=(message,)).start()

    def unblocking_write(self, server_report):
        multiprocessing.Process(target=self.blocking_write, args=(server_report,)).start()

    def blocking_write(self, server_report):
        with open(self.log_tmp_file_path, 'wb') as file:
            pickle.dump(server_report, file)
        os.replace(self.log_tmp_file_path, self.log_file_path)

    def get_current_status(self):
        cpu_usage = self.cpu_usage.value
        is_idle = (cpu_usage > 0)
        is_unavailable = not self.request_queue.empty()
        timestamp = time.time()
        return ServerStatus(cpu_usage, is_idle, is_unavailable, timestamp)

    def run(self):
        multiprocessing.Process(target=self.handle_request_in_queue).start()
        multiprocessing.Process(target=self.generate_log_and_send).start()
        self.wait_for_client()


if __name__ == '__main__':
    args = get_arguments()
    server = Server(args)
    server.run()
