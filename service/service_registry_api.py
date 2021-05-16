import time
import sys

import flask
import json

import argparse
from flask import request, jsonify, Response
from threading import Lock

app = flask.Flask(__name__)
app.config["DEBUG"] = True


class AvailableServices:
    def __init__(self, lifetime = 60 * 60 * 10):
        self.__lock = Lock()
        self.__lifetime = lifetime
        self.__services = {}
        self.__services_update_time = {}

    def update_service_conf(self, service_conf):
        url = service_conf['url']
        with self.__lock:
            self.__services[url] = service_conf
            self.__services_update_time[url] = time.time()

    def get(self):
        services = []
        with self.__lock:
            for url, service_conf in self.__services.items():
                update_time = self.__services_update_time.get(url, 0)
                if time.time() - update_time > self.__lifetime:
                    continue
                services.append(service_conf)
        return services


AVAILABLE_SERVICES = AvailableServices()

@app.route('/get', methods=['GET'])
def get_api():
    try:
        app.logger.debug('New get request')
        services = AVAILABLE_SERVICES.get()
        app.logger.debug('Got get result: %s', str(services))
        return json.dumps(services, ensure_ascii=False)
    except Exception as e:
        app.logger.exception('Got exception during /get: %s', repr(e))
        return json.dumps({'error': repr(e)}, ensure_ascii=False)


@app.route('/register', methods=['POST'])
def register_api():
    req = request.json
    app.logger.debug('New register request: %s', req)
    try:
        AVAILABLE_SERVICES.update_service_conf(req)
        app.logger.debug('Successful register for request: %s', req)
        return json.dumps(req, ensure_ascii=False)
    except Exception as e:
        app.logger.exception('Exception during register for request: %s, exception: %s', req, repr(e))
        return json.dumps({'error': repr(e)}, ensure_ascii=False)


def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    sys.exit(1)


@app.route('/shutdown', methods=['GET'])
def shutdown():
    shutdown_server()
    return 'Server shutting down...'


def main():
    parser = argparse.ArgumentParser('Entry point for chat-bot')
    parser.add_argument('--port', help='port')
    args = parser.parse_args()

    app.run(host='0.0.0.0', port=args.port, threaded=True)


if __name__ == '__main__':
    main()
