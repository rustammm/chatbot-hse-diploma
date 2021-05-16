import sys
import flask
import json
from flask import request
import numpy as np
import torch
import argparse
from transformers import GPT2LMHeadModel, GPT2Tokenizer
from dostoevsky.tokenization import RegexTokenizer
from dostoevsky.models import FastTextSocialNetworkModel

from client import ServiceRegistryClient


TOK = None
MODEL = None
CONFIG = None

app = flask.Flask(__name__)
app.config["DEBUG"] = True

class ResultValidation:
    def __init__(self):
        tokenizer = RegexTokenizer()
        self.__model = FastTextSocialNetworkModel(tokenizer=tokenizer)
        pass

    def validate(self, text):
        try:
            return self.__model.predict([text], k=2)[0].get('negative', 0) < 0.3
        except Exception as e:
            app.logger.exception('Exception during result validation: %s', repr(e))
            return True


RESULT_VALIDATION = ResultValidation()


def get_answer(query, history):
    parts = history + [query]
    q = '- {}\n-'.format('\n- '.join(parts))
    input = TOK.encode(q, return_tensors="pt")
    out = MODEL.generate(
        input, max_length=CONFIG['max_length'], repetition_penalty=5.0,
        do_sample=True, top_k=CONFIG['top_k'], top_p=0.95, temperature=1)

    raw = TOK.decode(out[0])
    raw = raw[len(q):]
    ans = raw.split('<')[0].strip()
    return ans.replace('  ', ' ')


@app.route('/api', methods=['POST'])
def home():
    app.logger.debug('New request: %s', request)
    req = request.json
    app.logger.debug('Got request: %s', req)
    uid = req['uid']

    res = get_answer(req['query'], req['history'])
    if not RESULT_VALIDATION.validate(res):
        return json.dumps(
            {'uid': uid, 'from': CONFIG['name'], 'ok': False, 'error': 'Validation of result did not pass'},
            ensure_ascii=False)

    reply = json.dumps(res, ensure_ascii=False)
    app.logger.debug('Got answer: %s for request: %s', reply, req)
    return json.dumps({'uid': uid, 'from': CONFIG['name'], 'ok': True, 'reply': res}, ensure_ascii=False)


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
    np.random.seed(42)
    torch.manual_seed(42)

    parser = argparse.ArgumentParser('Entry point for chat-bot')
    parser.add_argument('--config-path', help='config path')
    parser.add_argument('--port', help='port')
    args = parser.parse_args()

    global TOK, MODEL, CONFIG
    with open(args.config_path) as f:
        CONFIG = json.load(f)

    TOK = GPT2Tokenizer.from_pretrained(CONFIG['model_path'])
    MODEL = GPT2LMHeadModel.from_pretrained(CONFIG['model_path'])

    registry_conf = CONFIG['service_registry']
    registry = ServiceRegistryClient(registry_conf['conf'], registry_conf['url'], logger=app.logger)
    registry.start()
    app.run(host='0.0.0.0', port=args.port, threaded=True)


if __name__ == '__main__':
    main()
