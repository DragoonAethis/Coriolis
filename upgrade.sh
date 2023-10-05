#!/usr/bin/env bash
set -euxo pipefail

sudo systemctl stop coriolis
sudo systemctl stop coriolis-crontab
sudo systemctl stop coriolis-dramatiq
sudo chown -R $USER:$USER .
git pull
poetry install
poetry run python manage.py migrate
poetry run python manage.py compilemessages
poetry run python manage.py collectstatic --no-input
sudo chown -R www-data:www-data .
sudo systemctl restart coriolis
sudo systemctl restart coriolis-dramatiq
sudo systemctl restart coriolis-crontab
docker build -t r2023-renderer:latest /app/contrib/ticket-renderer
