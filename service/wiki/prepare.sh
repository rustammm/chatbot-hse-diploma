#!/bin/bash -e
# ubuntu 16

sudo apt update -y
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update -y
sudo apt install python3.7 -y
sudo apt-get install python3.7-dev -y
sudo apt-get install git -y
sudo apt-get install python3-pip -y

export LC_ALL="en_US.UTF-8"
export LC_CTYPE="en_US.UTF-8"
sudo dpkg-reconfigure locales
sudo apt-get install python3.7-venv -y

python3.7 -m pip install virtualenv -q

python3.7 -m venv env
source env/bin/activate

pip install deeppavlov==0.14.1 Flask==1.0.2

python -m deeppavlov install kbqa_cq_rus -d

