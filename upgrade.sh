#!/usr/bin/env bash
set -euxo pipefail

sudo systemctl stop nginx.service coriolis.service coriolis.socket coriolis-crontab.service coriolis-dramatiq.service
sudo chown -R $USER:$USER .
git pull
poetry install
poetry run python manage.py migrate
poetry run python manage.py compilemessages
poetry run python manage.py collectstatic --no-input
sudo chown -R www-data:www-data .
sudo systemctl restart nginx.service coriolis.service coriolis.socket coriolis-crontab.service coriolis-dramatiq.service

pushd /app/contrib/ticket-renderer
./build-image.sh r2024
popd
