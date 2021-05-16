#!/bin/bash -e

# pass config name to run model

source env/bin/activate

python ../model_api.py --port 50001 --config-path $1