import argparse
import logging
import socket
import traceback

from collections import OrderedDict


class Request():
    def __init__(self, client_id, request_id, cpu_usage, time_usage):
        self.client_id = client_id
        self.request_id = request_id
        self.cpu_usage = cpu_usage
        self.time_usage = time_usage

        self.id = "{}-{}".format(client_id, request_id)
        self.request_send_time = 0.
        self.request_receive_time = 0.
        self.request_process_time = 0.
        self.reply_send_time = 0.
        self.reply_receive_time = 0.

    def info(self):
        return "Request(ID:{}, CPU Usage:{}, Time Usage:{})".format(self.id, self.cpu_usage, self.time_usage)

    def time_info(self):
        time_info = OrderedDict()
        time_info["request_deliver_duration"] = self.request_receive_time - \
            self.request_send_time
        time_info["request_wait_duration"] = self.request_process_time - \
            self.request_receive_time
        time_info["request_process_duration"] = self.reply_send_time - \
            self.request_process_time
        time_info["reply_deliver_duration"] = self.reply_receive_time - \
            self.reply_send_time
        time_info["total_duration"] = self.reply_receive_time - \
            self.request_send_time
        output = ""
        for key, value in time_info.items():
            output += "{}:{}ms; ".format(key, int(value * 1e3))
        return output


class ClientReport():
    def __init__(self, client_id, report_type, request_log):
        self.client_id = client_id
        self.report_type = report_type
        self.request_log = request_log


class ServerStatus():
    def __init__(self, cpu_usage, is_idle, is_unavailable, timestamp):
        self.cpu_usage = cpu_usage
        self.is_idle = is_idle
        self.is_unavailable = is_unavailable
        self.timestamp = timestamp


class ServerReport():
    def __init__(self, server_id, status_log):
        self.server_id = server_id
        self.status_log = status_log


class SenderSocket():
    def __init__(self, dst_ip, dst_port, socket_name=""):
        self.dst_ip = dst_ip
        self.dst_port = dst_port
        self.name = socket_name
        self.dst_host = socket.gethostbyname(self.dst_ip)
        self.dst = (self.dst_host, self.dst_port)
        self.socket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)  # Use Internet, TCP
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.is_connected = False

    def connect(self):
        if self.is_connected:
            self.close()
        try:
            self.socket.connect(self.dst)
            self.is_connected = True
        except:
            logging.error("{} failed to connect: {}".format(
                self.name, str(self.dst)))
            logging.error(traceback.format_exc())
            return False
        return True

    def close(self):
        self.socket.close()
        self.socket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)  # Use Internet, TCP
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.is_connected = False

    def send(self, message):
        try:
            self.socket.send(message)
            logging.debug("{} sent message to {}.".format(
                self.name, self.dst))
        except:
            logging.error(traceback.format_exc())
            return False
        return True
    
    def receive(self):
        try:
            reply = self.socket.recv(1024)
            if not reply:
                raise TypeError("{} receive no reply from {}".format(
                    self.name, self.dst))
            return reply
        except:
            logging.error(traceback.fƒormat_exc())
            return
        
    def send_and_receive(self, message):
        self.send(message)
        reply = self.receive()
        if reply:
            try:
                logging.debug("{} receive reply {} from {}.".format(
                    self.name, reply.decode(), self.dst))
            except (UnicodeDecodeError, AttributeError):
                logging.debug("{} receive non-unicode reply from {}.".format(
                    self.name, self.dst))
        return reply


def set_up_log():
    parser = argparse.ArgumentParser()
    parser.add_argument('-log',
                        '--loglevel',
                        default='warning',
                        help='Provide logging level. Example --loglevel debug, default=warning')
    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel.upper())
