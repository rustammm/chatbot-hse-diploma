import copy
import time
import sys
import threading

import flask
import json
import random
import requests
import argparse
from collections import defaultdict, deque
from flask import request, Response
from threading import Thread, Lock

from client import ServiceRegistryClient


app = flask.Flask(__name__)
app.config["DEBUG"] = True


class ThreadWithReturnValue(Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs={}):
        Thread.__init__(self, group, target, name, args, kwargs)
        self._return = None

    def run(self):
        try:
            if self._target:
                self._return = self._target(*self._args, **self._kwargs)
        finally:
            del self._target, self._args, self._kwargs

    def get_return(self):
        return self._return


class UserQuoatas:
    def __init__(self):
        self.__max_in_flight = 0
        self.__max_in_flight_for_uid = 0

        self.__in_flight_for_uid = {}
        self.__in_flight = 0

        self.__lock = Lock()

    def on_request(self, uid):
        with self.__lock:
            if self.__in_flight > self.__max_in_flight + 1:
                return False
            q = self.__in_flight_for_uid.get(uid, 0)
            if q > self.__max_in_flight + 1:
                return False
            self.__in_flight_for_uid[uid] = q + 1
        return True

    def on_request_finished(self, uid):
        with self.__lock:
            q = self.__in_flight_for_uid.get(uid, 0)
            if q == 0:
                raise Exception('called on_request_finished on unknown uid {}'.format(uid))
            self.__in_flight_for_uid[uid] = q - 1

    def update(self, quota_conf):
        with self.__lock:
            self.__max_in_flight = quota_conf['max_in_flight']
            self.__max_in_flight_for_uid = quota_conf['max_in_flight_for_uid']



class Services:
    def __init__(self):
        self.__lock = Lock()
        self.__services_list = []

    def get_services(self):
        with self.__lock:
            services_list = self.__services_list

        services = []
        for service_list in services_list.values():
            services.append(random.choice(service_list))
        return services

    def update(self, services_conf):
        services_conf = sorted(services_conf, key=lambda s: s['url'])
        services_list = defaultdict(list)
        for s in services_conf:
            services_list[s['name']] += [s]
        with self.__lock:
            self.__services_list = services_list


class ChatHistory:
    def __init__(self, max_length=10):
        self.__history = defaultdict(lambda : deque(maxlen=max_length))
        self.__lock = threading.Lock()

    def get_history(self, uid, max_length):
        if not max_length:
            return

        with self.__lock:
            history = list(self.__history[uid])
        if max_length > len(history):
            return history
        return history[-max_length:]

    def add_history(self, uid, text):
        with self.__lock:
            self.__history[uid].append(text)


USER_QUOTAS = UserQuoatas()
SERVICES = Services()
CHAT_HISTORY = ChatHistory()


def fetch(url, data, timeout):
    started = time.time()
    try:
        app.logger.debug('Starting {} with data {}'.format(url, data))
        r = requests.post(url, json=data, timeout=timeout)
        finished = time.time()
        app.logger.debug('Got for {} with data {} result {}, elapsed {}'.format(url, data, r.content, finished - started))
        return r.json()
    except Exception as e:
        finished = time.time()
        app.logger.exception('Got for {} with data {} exception {}, elapsed {}'.format(url, data, repr(e), finished - started))
        return {'ok': False, 'error': repr(e)}


def fetch_all(data, uid):
    threads = []
    services = SERVICES.get_services()
    for service in services:
        url = service['url']
        timeout = service['timeout']
        history_len = service['history_len']
        thread_name = "{}_for_{}".format(service['name'], uid)
        data = copy.deepcopy(data)
        data['history'] = []
        if history_len:
            data['history'] = CHAT_HISTORY.get_history(uid, history_len)
        kw = {'url': url, 'data': data, 'timeout': timeout}
        threads.append(ThreadWithReturnValue(target=fetch, name=thread_name, kwargs=kw))

    for t in threads:
        t.start()

    results = []
    for i, t in enumerate(threads):
        t.join(timeout=services[i]['timeout'])
        result = t.get_return()
        if result is not None:
            result['priority'] = services[i]['priority']
        results.append(result)

    return results


def postprocess(results):
    result = {}
    for x in results:
        if not x:
            continue
        if result and not x['ok']:
            continue
        if x['priority'] > result.get('priority', -1):
            result = x

    return result or {'ok': False, 'error': 'All services are unavailable'}

def fallback(uid, query):
    prepared_answers = {
        'дела':'Нормально!',
        'делаешь':'Даже не знаю...',
        'почему':'Вот так вот',
        'где': 'В каком-то интересном месте!',
        'когда':'Когда-то!',
        'сколько':'Об этом не рассказывают!',
        'дума':'Думать это хорошо!',
    }
    lowered = query.lower()
    ans = 'Не знаю...'
    for p in prepared_answers:
        if p in lowered:
            ans = prepared_answers[p]
    return {'from': 'fallback', 'ok': False, 'uid': uid, 'reply': ans}


@app.route('/api', methods=['POST'])
def main_api():
    req = request.json
    app.logger.debug('Got request %s', req)
    uid = req['uid']
    fallback_result = fallback(req['uid'], req['query'])
    if USER_QUOTAS.on_request(uid):
        try:
            results = fetch_all(req, uid)
            app.logger.debug('Got results, req: %s, results: %s', req, results)
            result = postprocess(results)
            if not result['ok']:
                result = fallback_result
        except Exception as e:
            app.logger.exception('Exception in main_api for request {}, exception {}'.format(req, repr(e)))
            result = fallback_result

        USER_QUOTAS.on_request_finished(uid)
        CHAT_HISTORY.add_history(uid, req['query'])
        CHAT_HISTORY.add_history(uid, result['reply'])
    else:
        return Response("", status=429)
    return json.dumps(result, ensure_ascii=False)


@app.route('/update_services', methods=['POST'])
def update_services():
    req = request.json
    SERVICES.update(req)
    return json.dumps({'updated': True}, ensure_ascii=False)


@app.route('/update_quoatas', methods=['POST'])
def update_quoatas():
    req = request.json
    USER_QUOTAS.update(req)
    return json.dumps({'updated': True}, ensure_ascii=False)


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
    parser.add_argument('--config-path', help='config path')
    parser.add_argument('--port', help='port')
    args = parser.parse_args()

    with open(args.config_path) as f:
        config = json.load(f)

    SERVICES.update(config['service_conf'])
    USER_QUOTAS.update(config['user_quoatas'])

    registry_conf = config['service_registry']
    registry = ServiceRegistryClient(registry_conf['conf'], registry_conf['url'], registry_conf['services_names'], SERVICES.update)
    registry.start()

    app.run(host='0.0.0.0', port=args.port, threaded=True)


if __name__ == '__main__':
    main()

