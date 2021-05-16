#!/bin/bash -e

source env/bin/activate

python ../wiki_api.py --port 50002 --config-path config.json