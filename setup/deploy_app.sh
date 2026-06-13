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
    --exclude='.git/' \
    --exclude='.gitignore' \
    --exclude='.DS_Store' \
    --exclude='.python-version' \
    --exclude='*.md' \
    --exclude='py.typed' \
    --exclude='pyproject.toml' \
    --exclude='LICENSE' \
    --exclude='*.log*' \
    --exclude='.pylintrc' \
    --exclude='backup/' \
    --exclude='images/' \
    --exclude='tests/' \
    --exclude='*.jpg' \
    '/Users/andrew/Development/mcintosh-rs232/' \
    sagebrush@mac2mqtt.crampedcell.com:/home/sagebrush/mcintosh-rs232

#echo "Deployment complete - please restart the server to apply changes"
echo


#--exclude='.vscode/' \
#--exclude='*.code-workspace' \
#--exclude='reference_material/' \
