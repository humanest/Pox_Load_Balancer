import argparse
import logging
import statistics
import pickle
import socket
import time
import traceback
import threading


from commonData import Request, ClientReport, set_up_log

CPU_RESOURCE = 100  # In percentage
CPU_IDLE_USAGE = 0  # In percentage
MAX_CONNECTION_NUMBER = 100
MONITOR_IP = "127.0.2.1"
MONITOR_CLIENT_PORT = 6000
MONITOR_SERVER_PORT = 6001
LOG_START_PERCENTILE = 0.0
LOG_END_PERCENTILE = 1.0


class ListStats():
    def __init__(self, nums, name=""):
        self.name = name
        if len(nums) < 2:
            nums = [0,0]
        self.nums = sorted(nums.copy())
        self.min = self.nums[0]
        self.max = self.nums[-1]
        self.mean = statistics.mean(self.nums)
        self.median = self.get_percentile(50)
        self.var = statistics.variance(self.nums)
        self.p95 = self.get_percentile(95)
        self.p99 = self.get_percentile(99)

    def get_percentile(self, percent):
        n = len(self.nums)
        index = int(n * percent * 0.01) - 1
        index = max(min(index, n), 0)
        return self.nums[index]

    def get_info(self):
        info = "{}: min={:.2f}, max={:.2f}, median={:.2f}, p95={:.2f}, p99={:.2f}, mean={:.2f}, var={:.2f}".format(
            self.name, self.min, self.max, self.median, self.p95, self.p99, self.mean, self.var)
        return info


class Monitor():
    def __init__(self):
        self.host = socket.gethostname()
        # self.ip = socket.gethostbyname(self.host)
        self.ip = MONITOR_IP
        self.max_connection_number = MAX_CONNECTION_NUMBER

        self.client_port = MONITOR_CLIENT_PORT
        self.client_address = (self.ip, self.client_port)
        self.client_socket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)  # Use Internet, TCP
        self.client_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.client_socket.bind(self.client_address)

        self.server_port = MONITOR_SERVER_PORT
        self.server_address = (self.ip, self.server_port)
        self.server_socket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)  # Use Internet, TCP
        self.server_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(self.server_address)

        self.is_listening = False
        self.listening_time_range = [0., 0.]
        self.listening_time_range_factor = [
            LOG_START_PERCENTILE, LOG_END_PERCENTILE]
        self.active_clients = set()
        self.client_log = {}
        self.server_log = {}

    def wait_for_client(self):
        self.client_socket.listen(self.max_connection_number)
        while True:
            client, address = self.client_socket.accept()
            logging.info("Got client connection from: {}".format(address))
            client.settimeout(60)
            threading.Thread(target=self.serve_client,
                             args=(client, address)).start()

    def serve_client(self, client, address):
        logging.info("Start serving client: {}".format(address))
        while True:
            try:
                client_report_data = client.recv(8192)
                if client_report_data:
                    client_report = pickle.loads(client_report_data)
                    client_id = client_report.client_id
                    if client_report.report_type == "start":
                        self.is_listening = True
                        self.listening_time_range[0] = time.time()
                        self.active_clients.add(client_id)
                    elif client_report.report_type == "finish":
                        logging.info(
                            "Received finish log from client {}".format(client_id))
                        self.client_log[client_id] = client_report.request_log
                        self.active_clients.remove(client_id)
                        if len(self.active_clients) == 0:
                            self.listening_time_range[1] = time.time()
                            self.generate_log()
                            self.is_listening = False
                    else:
                        raise TypeError("Unsupported client report type: {}".format(
                            client_report.report_type))
                    reply_message = "Report from {} with type '{}' received".format(
                        client_id, client_report.report_type)
                    client.send(reply_message.encode())
                else:
                    logging.info("Client {} disconnected".format(address))
                    break
            except Exception as e:
                logging.error(traceback.format_exc())
                logging.error(e)
                client.close()
                return False

    def wait_for_server(self):
        self.server_socket.listen(self.max_connection_number)
        while True:
            server, address = self.server_socket.accept()
            logging.info("Got server connection from: {}".format(address))
            server.settimeout(60)
            threading.Thread(target=self.serve_server,
                             args=(server, address)).start()

    def serve_server(self, server, address):
        logging.info("Start serving server: {}".format(address))
        while True:
            try:
                server_report_data = server.recv(1024)
                if server_report_data:
                    server_report = pickle.loads(server_report_data)
                    server_id = server_report.server_id
                    if server_id not in self.server_log:
                        self.server_log[server_id] = []
                    self.server_log[server_id] += server_report.status_log
                    reply = "Report from server {} received".format(
                        server_id)
                    server.send(reply.encode())
                else:
                    logging.info("Server {} disconnected".format(address))
                    break
            except Exception as e:
                logging.error(e)
                server.close()
                return False

    def is_valid_time(self, timestamp):
        period = self.listening_time_range[1] - self.listening_time_range[0]
        start_time = self.listening_time_range[0] + \
            period * self.listening_time_range_factor[0]
        end_time = self.listening_time_range[0] + \
            period * self.listening_time_range_factor[1]
        return start_time <= timestamp and timestamp <= end_time

    def analysis_client_requests(self, requests):
        wait_time_list = []
        for request in requests:
            if self.is_valid_time(request.request_send_time) and self.is_valid_time(request.reply_receive_time):
                wait_time_list.append(request.get_wait_time() * 1e3)
        return ListStats(wait_time_list)
    
    def analysis_server_log(self, status_log):
        cpu_usage_list = []
        for status in status_log:
            if self.is_valid_time(status.timestamp):
                cpu_usage_list.append(status.cpu_usage)
        return ListStats(cpu_usage_list)

    def generate_log(self):
        all_requests = []
        for client_id, requests in self.client_log.items():
            stats = self.analysis_client_requests(requests)
            stats.name = "{} request wait time".format(client_id)
            all_requests += requests
            print(stats.get_info())
        stats = self.analysis_client_requests(all_requests)
        stats.name = "All request wait time"
        print(stats.get_info(),"\n")

        all_status_logs = []
        for server_id, status_log in self.server_log.items():
            stats = self.analysis_server_log(status_log)
            stats.name = "Server {} cpu usage".format(server_id)
            all_status_logs += status_log
            print(stats.get_info())
        stats = self.analysis_server_log(all_status_logs)
        stats.name = "All server cpu usage"
        print(stats.get_info())
        
        print("----------------")
        self.reset()
    
    def reset(self):
        self.is_listening = False
        self.listening_time_range = [0., 0.]
        self.active_clients = set()
        self.client_log = {}
        self.server_log = {}

    def run(self):
        threading.Thread(target=self.wait_for_server).start()
        self.wait_for_client()


if __name__ == '__main__':
    set_up_log()
    monitor = Monitor()
    monitor.run()
