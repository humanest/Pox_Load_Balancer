import collections
import multiprocessing
import random
import socket
import time


CPU_RESOURCE = 100  # In percentage
CPU_IDLE_USAGE = 0  # In percentage
MAX_CONNECTION_NUMBER = 100
SERVER_IP = "127.0.1.1"
SERVER_PORT = 5000


class Request():
    def __init__(self, client, cpu_usage, time_usage, request_id):
        self.client = client
        self.cpu_usage = cpu_usage
        self.time_usage = time_usage
        self.request_id = request_id


class Server():
    def __init__(self):
        self.host = socket.gethostname()
        self.ip = socket.gethostbyname(self.host)
        self.port = SERVER_PORT
        self.address = (self.ip, self.port)
        self.socket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)  # Use Internet, TCP
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.address)

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
            print("Got connection from: {}".format(address))
            client.settimeout(60)
            multiprocessing.Process(target=self.serve_client,
                                    args=(client, address)).start()

    def serve_client(self, client, address):
        print("Start serving client: {}".format(address))
        while True:
            try:
                request_data = client.recv(1024).decode()
                if request_data:
                    request_info = str(request_data).split(",")
                    cpu_usage = int(request_info[0])
                    time_usage = int(request_info[1])
                    request_id = request_info[2]
                    print("Got request id: {}, added to queue".format(request_id))
                    request = Request(client, cpu_usage, time_usage, request_id)
                    self.request_queue.put(request)
                else:
                    raise NameError('Client disconnected')
            except Exception as e:
                print("ERROR:", e)
                client.close()
                return False

    def handle_request(self, request):
        print("Handling request {}...".format(request.request_id))
        time_in_sec = float(request.time_usage) * 1e-3
        time.sleep(time_in_sec)
        reply = "Request {} finished!".format(request.request_id)
        request.client.send(reply.encode())
        with self.cpu_usage.get_lock():
            self.cpu_usage.value -= request.cpu_usage
        print("Request {} finished, reply sent, current cpu usage: {}%".format(request.request_id, self.cpu_usage.value))
        with self.cpu_condition:
            self.cpu_condition.notify_all()

    def handle_request_in_queue(self):
        print("Start handling request in queue")
        while True:
            request = self.request_queue.get()
            while self.cpu_usage.value + request.cpu_usage > self.max_cpu_resource:
                print("Insufficient cpu usage: {}%".format(self.cpu_usage.value))
                with self.cpu_condition:
                    self.cpu_condition.wait()
            print("Ready to handle request id: {}, current cpu usage: {}%".format(request.request_id, self.cpu_usage.value))
            with self.cpu_usage.get_lock():
                self.cpu_usage.value += request.cpu_usage
            multiprocessing.Process(target=self.handle_request,
                                    args=(request,)).start()

    def run(self):
        multiprocessing.Process(target=self.handle_request_in_queue).start()
        self.wait_for_client()


if __name__ == '__main__':
    server = Server()
    server.run()
