#!/usr/bin/env bash
# deploy-appssh.sh - script to deploy

# deploy the python app and configuration library
echo -e "\n-------- Deploying python application and configuration -------"

rsync -am \
    --info=name \
    --delete \
    --exclude='__pycache__/' \
    --exclude='.mypy_cache/' \
    --exclude='.pytest_cache/' \
    --exclude='.ruff_cache/' \
    --exclude='.venv/' \
    --exclude='.vscode/' \
    --exclude='.git/' \
    --exclude='.gitignore' \
    --exclude='.DS_Store' \
    --exclude='*.log*' \
    --exclude='.pylintrc' \
    --exclude='*.code-workspace' \
    --exclude='backup/' \
    --exclude='images/' \
    --exclude='*.jpg' \
    --exclude='reference_material/' \
    --exclude='setup/' \
    '/Users/andrew/Development/denon-rs232/' \
    sagebrush@mac2mqtt.crampedcell.com:/home/sagebrush/mcintosh

#echo "Deployment complete - please restart the server to apply changes"
echo

