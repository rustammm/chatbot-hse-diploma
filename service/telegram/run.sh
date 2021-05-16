#!/bin/bash -e

source env/bin/activate

python ../bot.py --telegram_token $1 --service_registry_url $2