import sys
import flask
import json
import argparse

from functools import lru_cache

from flask import request
from deeppavlov import build_model, configs

from client import ServiceRegistryClient


app = flask.Flask(__name__)
#app.config["DEBUG"] = True

#KBQA_MODEL = build_model(configs.kbqa.kbqa_cq_rus, download=True)
KBQA_MODEL = build_model(configs.kbqa.kbqa_cq_rus, load_trained=True)
CACHE_SIZE = 100000

CONFIG = None


@lru_cache(maxsize=CACHE_SIZE)
def get_wiki_answer(query):
    return KBQA_MODEL([query])[0]


@app.route('/api', methods=['POST'])
def home():
    req = request.json
    app.logger.debug('Got request: %s', req)
    query = req['query']
    uid = req['uid']

    try:
        reply = get_wiki_answer(query)
        if reply == 'Not Found':
            app.logger.debug('Got Not Fount for uid %s', uid)
            return json.dumps({'uid': uid, 'from': CONFIG['name'], 'ok': False, 'error': reply}, ensure_ascii=False)

        app.logger.debug('Reply %s for uid %s', reply, uid)
        return json.dumps({'uid': uid, 'from': CONFIG['name'], 'ok': True, 'reply': reply}, ensure_ascii=False)
    except Exception as e:
        app.logger.exception('Exception %s for uid %s', uid, repr(e))
        return json.dumps({'uid': uid, 'from': CONFIG['name'], 'ok': False, 'error': repr(e)}, ensure_ascii=False)


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

    global CONFIG
    with open(args.config_path) as f:
        CONFIG = json.load(f)

    registry_conf = CONFIG['service_registry']
    registry = ServiceRegistryClient(registry_conf['conf'], registry_conf['url'], logger=app.logger)
    registry.start()
    app.run(host='0.0.0.0', port=args.port, threaded=True)

if __name__ == '__main__':
    main()

