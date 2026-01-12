#!/usr/bin/env bash
set -euxo pipefail

sudo systemctl stop nginx.service coriolis.service coriolis.socket coriolis-crontab.service coriolis-dramatiq.service
sudo chown -R $USER:$USER .
git pull
uv sync
uv run manage.py migrate
uv run manage.py compilemessages
uv run manage.py collectstatic --no-input
sudo chown -R www-data:www-data .
sudo systemctl restart nginx.service coriolis.service coriolis-crontab.service coriolis-dramatiq.service
