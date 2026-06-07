# README for setting up the development environment for mcintosh-rs232
cd mcintosh_rs232

python3 -m venv .venv
source venv/bin/activate
pip install --upgrade pip
pip install -r setup/requirements.txt


# install editable package for development

pip install -e .

python -m mcintosh_rs232 /dev/serial0

