import argparse
import logging
import statistics
import pickle
import socket
import time
import traceback
import threading
import traceback


CPU_RESOURCE = 100  # In percentage
CPU_IDLE_USAGE = 0  # In percentage
MAX_CONNECTION_NUMBER = 100
MONITOR_IP = "127.0.2.1"
MONITOR_CLIENT_PORT = 6000
MONITOR_SERVER_PORT = 6001
LOG_START_PERCENTILE = 0.3
LOG_END_PERCENTILE = 0.7
REPORT_FILE_PATH = '/tmp/server_status/report.txt'


def get_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('-log', '--loglevel', default='warning',
                        help='Provide logging level. Example --loglevel debug, default=warning')
    parser.add_argument('--monitor_ip', default=MONITOR_IP)
    parser.add_argument('--monitor_client_port', default=MONITOR_CLIENT_PORT, type=int)
    parser.add_argument('--monitor_server_port', default=MONITOR_SERVER_PORT, type=int)
    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel.upper(), filename="/tmp/server_status/monitor.log", filemode='w')
    return args


class ListStats():
    def __init__(self, nums, name=""):
        self.name = name
        if len(nums) < 2:
            nums = [0, 0]
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
    def __init__(self, args):
        self.reset()
        self.read_argument(args)
        self.max_connection_number = MAX_CONNECTION_NUMBER

        self.client_address = (self.ip, self.client_port)
        self.client_socket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)  # Use Internet, TCP
        self.client_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.client_socket.bind(self.client_address)

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
        self.active_client_num = 0
        self.count_lock = threading.Lock()
        self.client_log = {}
        self.server_log = {}


        self.results = []

    def read_argument(self, args):
        self.ip = args.monitor_ip
        self.client_port = args.monitor_client_port
        self.server_port = args.monitor_server_port

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
        self.client_in()
        while True:
            try:
                client_report_data = client.recv(8192)
                if client_report_data:
                    request = pickle.loads(client_report_data)
                    client_id = request.client_id
                    logging.debug("Receive report from {}, report id: {}".format(client_id, request.request_id))
                    if client_id not in self.client_log:
                        self.client_log[client_id] = []
                    self.client_log[client_id].append(request)
                    reply_message = "Report from {} with id '{}' received".format(
                        client_id, request.request_id)
                    client.send(reply_message.encode())
                else:
                    logging.info("Client {} disconnected.".format(address))
                    break
            except Exception as e:
                logging.error(traceback.format_exc())
                logging.error(e)
                client.close()
                return False
        self.client_out()

    def client_in(self):
        logging.info("Got new client, current num:{}".format(self.active_client_num+1))
        if self.active_client_num == 0:
            self.is_listening = True
            self.listening_time_range[0] = time.time()
        self.count_lock.acquire()
        self.active_client_num += 1
        self.count_lock.release()

    def client_out(self):
        try:
            self.count_lock.acquire()
            self.active_client_num -= 1
            self.count_lock.release()
            logging.info("Client out current client:{}".format(self.active_client_num))
            if self.active_client_num == 0:
                self.listening_time_range[1] = time.time()
                self.generate_log()
        except:
            logging.error(traceback.format_exc())

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
                    logging.debug("Server report from {}".format(server_id))
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
        start_time, end_time = self.get_valid_period()
        return start_time <= timestamp and timestamp <= end_time

    def get_valid_period(self):
        period = self.listening_time_range[1] - self.listening_time_range[0]
        start_time = self.listening_time_range[0] + \
            period * self.listening_time_range_factor[0]
        end_time = self.listening_time_range[0] + \
            period * self.listening_time_range_factor[1]
        return start_time, end_time

    def analysis_client_requests(self, requests, name=""):
        wait_time_list = []
        for request in requests:
            if self.is_valid_time(request.request_send_time) and self.is_valid_time(request.reply_receive_time):
                wait_time_list.append(request.get_wait_time() * 1e3)
        stats = ListStats(wait_time_list, name)
        print(stats.get_info())
        self.results.append(stats.get_info())
        return stats

    def analysis_server_log(self, status_log, name=""):
        cpu_usage_list = []
        for status in status_log:
            if self.is_valid_time(status.timestamp):
                cpu_usage_list.append(status.cpu_usage)
        stats = ListStats(cpu_usage_list, name)
        print(stats.get_info())
        self.results.append(stats.get_info())
        return stats

    def analysis_effciency(self, all_request):
        total_cpu_time = 0.
        request_num = 0
        wait_time_list = []
        cpu_usage_list = []
        time_usage_list = []
        for request in all_request:
            if self.is_valid_time(request.request_send_time) and self.is_valid_time(request.reply_receive_time):
                total_cpu_time += request.cpu_usage * 1e-2 * request.time_usage
                request_num += 1
                wait_time_list.append(request.get_wait_time() * 1e3)
                cpu_usage_list.append(request.cpu_usage)
                time_usage_list.append(request.time_usage)
        wait_time_stats = ListStats(
            wait_time_list, "All request wait time (ms)")
        cpu_usage_stats = ListStats(
            cpu_usage_list, "All request CPU usage (%)")
        time_usage_stats = ListStats(
            time_usage_list, "All request time usage (ms)")
        for stats in (wait_time_stats, cpu_usage_stats, time_usage_stats):
            print(stats.get_info())
            self.results.append(stats.get_info())
        server_num = len(self.server_log)
        client_num = len(self.client_log)
        theory_process_time = total_cpu_time / max(server_num, 1)
        start_time, end_time = self.get_valid_period()
        actual_process_time = (end_time - start_time) * 1e3
        efficency = (theory_process_time / actual_process_time) * 1e2
        info = "Total request num={}, client num={}, server num={}, theory cpu process time={:.2f}ms, actual process time={:.2f}ms, efficiency={:.2f}%".format(
            request_num, client_num, server_num, theory_process_time, actual_process_time, efficency)
        print(info)
        self.results.append(info)
        return (wait_time_stats, cpu_usage_stats, time_usage_stats)

    def generate_log(self):
        try:
            all_requests = []
            for client_id, requests in self.client_log.items():
                self.analysis_client_requests(
                    requests, "{} request wait time (ms)".format(client_id))
                all_requests += requests
            print()
            self.results.append('')

            all_status_logs = []
            for server_id, status_log in self.server_log.items():
                self.analysis_server_log(
                    status_log, "Server {} cpu usage".format(server_id))
                all_status_logs += status_log
            self.analysis_server_log(all_status_logs, "All server cpu usage")
            print()
            self.results.append('')

            self.analysis_effciency(all_requests)

            print("----------------")
            with open(REPORT_FILE_PATH, 'w') as f:
                for line in self.results:
                    f.write(f"{line}\n")
        except:
            logging.error(traceback.format_exc())

    def reset(self):
        self.is_listening = False
        self.listening_time_range = [0., 0.]
        self.active_client_num = 0
        self.client_log = {}
        self.server_log = {}
        
        self.results = []

    def run(self):
        threading.Thread(target=self.wait_for_server).start()
        self.wait_for_client()


if __name__ == '__main__':
    args = get_arguments()
    monitor = Monitor(args)
    monitor.run()
