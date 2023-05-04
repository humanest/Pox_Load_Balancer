import argparse
import logging
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
                client_report_data = client.recv(1024)
                if client_report_data:
                    client_report = pickle.loads(client_report_data)
                    client_id = client_report.client_id
                    if client_report.report_type == "start":
                        self.is_listening = True
                        self.active_clients.add(client_id)
                    elif client_report.report_type == "finish":
                        logging.info("Received finish log from client {}".format(client_id))
                        self.client_log[client_id] = client_report.request_log
                        self.active_clients.remove(client_id)
                        if len(self.active_clients) == 0:
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

    def generate_log(self):
        print(self.client_log, self.server_log)

    def run(self):
        threading.Thread(target=self.wait_for_server).start()
        self.wait_for_client()


if __name__ == '__main__':
    set_up_log()
    monitor = Monitor()
    monitor.run()
