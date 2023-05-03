import time

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
