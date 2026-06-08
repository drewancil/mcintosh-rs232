# README for setting up the development environment for mcintosh-rs232
cd mcintosh_rs232

python3 -m venv .venv
source venv/bin/activate
pip install --upgrade pip
pip install -r setup/requirements.txt

# install editable package for development - no need to re-run pip install -e unless major changes are made
pip install -e .

# raspberry pi serial
python -m mcintosh_rs232 /dev/serial0

# esphome serial proxy
python -m mcintosh_rs232 "esphome://192.168.4.160:6053/?port_name=mcintosh_proxy"

