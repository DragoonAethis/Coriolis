#!/usr/bin/env bash
set -euo pipefail

git pull
poetry run python manage.py migrate
poetry run python manage.py compilemessages
poetry run python manage.py collectstatic --no-input
chown -R www-data:www-data .
systemctl restart coriolis
