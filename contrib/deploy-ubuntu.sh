# WARNING: THIS IS NOT A COMPLETE SCRIPT. Think of this as
# a bunch of handy notes that are not quite complete yet.
# Most of this assumes Ubuntu 22.04, running as a non-root user.

# Set these accordingly for your environment:
export CORIOLIS_DOMAIN="example.com"
export USERMEDIA_DOMAIN="usermedia.$CORIOLIS_DOMAIN"
export CERTBOT_EMAIL="lets-encrypt-notification-mail@example.com"
export TIMEZONE="Europe/Warsaw"

# This path is referenced in systemd units and nginx configs.
# Changing it is not yet supported - do so as your own risk.
export INSTALL_DIR="/app"

# The correct system TZ is required for Coriolis timestamp
# correctness. Check if it differs from the selected TZ:
timedatectl show | grep "Timezone=$TIMEZONE"
if [[ $? -ne 0 ]]; then
  # Set and reboot to apply changes to cron, etc.
  sudo timedatectl set-timezone "$TIMEZONE"
  sudo reboot
fi

# Less spam:
sudo pro config set apt_news=false

# Python 3.10 (in 22.04), PostgreSQL, psycopg2 deps.
# Enables unatteded security upgrades as well.
sudo apt-get -y update && sudo apt-get -y upgrade && sudo apt-get -y install \
  python-is-python3 python3-full python3-pip python3-dev \
  nginx certbot python3-certbot-nginx \
  postgresql libpq-dev redis \
  unattended-upgrades \
  docker.io gcc gettext

# Make sure our users can call Docker:
sudo gpasswd -a ubuntu docker
sudo gpasswd -a www-data docker

# Installing Poetry from repos gives you 1.1 (too old).
# Installing from pip causes it to get very confused.
# Just use the nasty install script...
curl -sSL https://install.python-poetry.org | python3 -
echo "export PATH=\"/home/ubuntu/.local/bin:\$PATH\"" > ~/.bashrc
source ~/.bashrc

sudo mkdir "$INSTALL_DIR"
sudo chown $USER:$USER "$INSTALL_DIR"

git clone https://github.com/DragoonAethis/Coriolis "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Make sure all dirs required for nginx etc exist:
mkdir -p "$INSTALL_DIR/public" "$INSTALL_DIR/media"
ln -s "$INSTALL_DIR/static" "$INSTALL_DIR/public/static"

# Configure the virtualenv:
poetry config virtualenvs.in-project true
poetry install

# Configure the app:
cp .env.dist .env
nano .env  # Edit accordingly.

# Set up the database:
# Run from: sudo -u postgres psql
CREATE DATABASE coriolis;
CREATE USER coriolis WITH LOGIN;
GRANT ALL ON DATABASE coriolis TO coriolis;
ALTER USER coriolis WITH PASSWORD 'nice-try-m8';

# We're also using Redis - its defaults listen on the port we want
# for localhost only, so we don't have to mess with its config much.
# It's also systemctl enabled out of the box - as is PostgreSQL.

# Finish database setup, generate resources:
poetry run python manage.py migrate
poetry run python manage.py collectstatic
poetry run python manage.py compilemessages

# Make sure we have at least one superuser:
poetry run python manage.py createsuperuser

# Make upgrades less annoying:
git config --global --add safe.directory /app

# Let nginx/gunicorn own all app files:
sudo chown -R www-data:www-data "$INSTALL_DIR"

# Configure HTTPS certificates and keys:
# You need to do this once before messing with nginx below.
# Once this is configured, the shipped configs have valid
# rules to let certbot autorenew take the wheel.
sudo certbot run -d "$CORIOLIS_DOMAIN,$USERMEDIA_DOMAIN" --nginx --agree-tos -m "$CERTBOT_EMAIL"

# systemd units:
sudo cp "$INSTALL_DIR/contrib/coriolis.socket" "/etc/systemd/system/coriolis.socket"
sudo cp "$INSTALL_DIR/contrib/coriolis.service" "/etc/systemd/system/coriolis.service"
sudo cp "$INSTALL_DIR/contrib/coriolis-dramatiq.service" "/etc/systemd/system/coriolis-dramatiq.service"

# nginx configs:
cat "$INSTALL_DIR/contrib/coriolis.nginx.conf" |
  sed "s/usermedia.example.com/$USERMEDIA_DOMAIN/g" |
  sed "s/example.com/$CORIOLIS_DOMAIN/g" |
  sudo tee /etc/nginx/sites-available/coriolis

sudo ln -s /etc/nginx/sites-available/coriolis /etc/nginx/sites-enabled/coriolis
sudo rm /etc/nginx/sites-enabled/default

# Set up the ticket renderer container image:
docker build -t r2023-renderer:latest /app/contrib/ticket-renderer

# Start the app:
sudo systemctl daemon-reload
sudo systemctl enable coriolis.socket --now
sudo systemctl enable coriolis-dramatiq.service --now
sudo systemctl restart nginx

# And off we go!
