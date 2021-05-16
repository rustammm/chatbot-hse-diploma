import time
import socket
import logging
import requests
import threading


def get_local_ip():
    """**UNUSED**
    Source: https://stackoverflow.com/a/166589

    Returns:
        str: Local IP
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip


class ServiceRegistryClient:
    def __init__(
            self, current_service_conf, service_registry_url,
            services_names=None, callback=None, timeout=5, update_period=180, register_period=60, logger=None):

        self.__service_registry_url = service_registry_url
        self.__services_names = services_names
        self.__callback = callback
        self.__timeout = timeout
        self.__update_period = update_period
        self.__current_service_conf = current_service_conf
        if self.__current_service_conf:
            self.__current_service_conf['url'] = self.__current_service_conf['url'].replace('{ip}', get_local_ip())
        self.__register_period = register_period
        self.__logger = logger or logging.getLogger('ServiceRegistryClient')

        self.__reg_thread = threading.Thread(target=self.try_register_service_loop, name='try_register_service_loop')
        self.__reg_thread.daemon = True

        if self.__services_names and self.__callback:
            self.__update_thread = threading.Thread(target=self.try_update_services_loop, name='try_update_services_loop')
            self.__update_thread.daemon = True

    def start(self):
        self.__reg_thread.start()
        if self.__services_names and self.__callback:
            self.__update_thread.start()

    def update_services(self):
        r = requests.get(self.__service_registry_url + '/get', timeout=self.__timeout).json()
        services = [s for s in r if s['name'] in self.__services_names]
        self.__callback(services)

    def try_update_services(self):
        try:
            self.update_services()
        except Exception as e:
            self.__logger.exception('Exception while updating services {}', repr(e))

    def try_update_services_loop(self):
        while True:
            self.try_update_services()
            time.sleep(self.__update_period)

    def register_service(self):
        requests.post(self.__service_registry_url + '/register', json=self.__current_service_conf, timeout=self.__timeout)

    def try_register_service(self):
        try:
            self.register_service()
        except Exception as e:
            self.__logger.exception('Exception while service register {}', repr(e))

    def try_register_service_loop(self):
        while True:
            self.try_register_service()
            time.sleep(self.__register_period)
