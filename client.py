import multiprocessing
import random
import socket
import time
import pickle

from commonData import Request

REQUEST_CPU_USAGE_RANGE = [20, 40]  # In percentage
REQUEST_TIME_USAGE_RANGE = [50, 100]  # In ms
REQUEST_SIZE = 10
SERVER_IP = "127.0.1.1"
SERVER_PORT = 5000


class Client():
    def __init__(self, name="client"):
        self.server_ip = SERVER_IP
        self.server_port = SERVER_PORT
        self.server_host = socket.gethostbyname(self.server_ip)
        self.server = (self.server_host, self.server_port)
        self.socket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)  # Use Internet, TCP

        self.host = socket.gethostname()
        self.ip = socket.gethostbyname(self.host)
        self.client_id = name

        self.request_cpu_usage_range = REQUEST_CPU_USAGE_RANGE
        self.request_time_usage_range = REQUEST_TIME_USAGE_RANGE
        self.request_size = REQUEST_SIZE
        self.request_id = 0

    def send_requests(self, destination, requests):
        try:
            self.socket.connect(destination)
        except:
            print("Client {} failed to connect: {}".format(
                self.client_id, str(destination)))
            return False

        for request in requests:
            request.request_send_time = time.time()
            message = pickle.dumps(request)
            try:
                self.socket.send(message)
                print("Client {} sent {}.".format(
                    self.client_id, request.info()))
                request_done_data = self.socket.recv(1024)
                if not request_done_data:
                    raise TypeError("No reply from {} for {}".format(
                        str(destination), self.client_id))
                request_done = pickle.loads(request_done_data)
                request_done.reply_receive_time = time.time()
                print("Client {} received reply: {}, time info: {}".format(
                    self.client_id, request_done.info(), request_done.time_info()))
            except Exception as e:
                print(e)
                self.socket.close()
                return False
        self.socket.close()
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

    def run(self):
        requests = self.generate_requests()
        self.send_requests(self.server, requests)


def run_a_client(name="client"):
    client = Client(name)
    client.run()


if __name__ == '__main__':
    for i in range(10):
        name = str(chr(65+i))
        multiprocessing.Process(target=run_a_client, args=(name,)).start()
