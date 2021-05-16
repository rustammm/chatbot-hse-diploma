#!/bin/bash -e

source env/bin/activate

python ../main_api.py --port 50000 --config-path config.json