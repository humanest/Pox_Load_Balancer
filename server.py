import logging
import multiprocessing
import os
import pickle
import socket
import time
import traceback

from commonData import SenderSocket, ServerStatus, ServerReport, set_up_log

CPU_RESOURCE = 100  # In percentage
CPU_IDLE_USAGE = 0  # In percentage
MAX_CONNECTION_NUMBER = 100
SERVER_IP = "127.0.1.1"
SERVER_PORT = 5000
MONITOR_IP = "127.0.2.1"
MONITOR_PORT = 6001
CONTROLLER_IP = "10.0.1.1"
CONTROLLER_PORT = 7000
LOG_FREQUENCY = 10  # In ms
LOG_BATCH = 10
LOG_FOLDER_PATH = "/tmp/server_status/"


class Server():
    def __init__(self):
        self.host = socket.gethostname()
        self.ip = socket.gethostbyname(self.host)
        self.server_id = self.ip
        self.port = SERVER_PORT
        self.address = (self.ip, self.port)
        self.socket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)  # Use Internet, TCP
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.address)

        self.monitor_socket = SenderSocket(
            MONITOR_IP, MONITOR_PORT, "{}-monitor".format(self.ip))
        self.controller_socket = SenderSocket(
            CONTROLLER_IP, CONTROLLER_PORT, "{}-controller".format(self.ip))
        self.status_log = []
        self.log_frequency = LOG_FREQUENCY
        self.log_batch = LOG_BATCH
        self.log_file_path = LOG_FOLDER_PATH + self.server_id
        if not os.path.exists(LOG_FOLDER_PATH):
            os.makedirs(LOG_FOLDER_PATH)

        self.max_cpu_resource = CPU_RESOURCE
        self.max_connection_number = MAX_CONNECTION_NUMBER

        self.request_manager = multiprocessing.Manager()
        self.request_queue = self.request_manager.Queue()
        self.lock = multiprocessing.Lock()
        self.cpu_usage = multiprocessing.Value('i', CPU_IDLE_USAGE)
        self.cpu_condition = multiprocessing.Condition()

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
            except Exception as e:
                logging.error(e)
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
        logging.info("Request {} finished, reply sent, current cpu usage: {}%".format(
            request.id, self.cpu_usage.value))
        with self.cpu_condition:
            self.cpu_condition.notify_all()

    def handle_request_in_queue(self):
        logging.info("Start handling request in queue")
        while True:
            request, client = self.request_queue.get()
            while self.cpu_usage.value + request.cpu_usage > self.max_cpu_resource:
                logging.warning(
                    "Insufficient cpu usage: {}%".format(self.cpu_usage.value))
                with self.cpu_condition:
                    self.cpu_condition.wait()
            logging.info("Ready to handle request: {}, current cpu usage: {}%".format(
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

        while True:
            current_status = self.get_current_status()
            self.status_log.append(current_status)
            if len(self.status_log) >= self.log_batch:
                server_report = ServerReport(self.server_id, self.status_log)
                message = pickle.dumps(server_report)
                for listener_socket in listener_sockets:
                    listener_socket.send_and_receive(message)
                with open(self.log_file_path, 'wb') as file:
                    pickle.dump(server_report, file)
                self.status_log.clear()
            time.sleep(self.log_frequency * 1e-3)

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
    set_up_log()
    server = Server()
    server.run()
