# WARNING: THIS IS NOT A COMPLETE SCRIPT. Think of this as
# a bunch of handy notes that are not quite complete yet.
# Most of this assumes Ubuntu 20.04.

# Python 3.9, PostgreSQL, psycopg2 deps
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
  nginx gcc gettext postgresql libpq-dev \
  certbot python3-certbot-nginx python3-pip \
  python3.9-full python3.9-venv python3.9-dev

timedatectl set-timezone Europe/Warsaw
reboot

# Poetry
pip install poetry
poetry config virtualenvs.in-project true

cd /
git clone https://github.com/DragoonAethis/Coriolis app
cd app
poetry install

# Poetry should complain about Python 3.8 being invalid and looking for 3.9.
# Because it's installed, it SHOULD pick it up: "Using python3.9 (3.9.??)"
# If not, you forgot to install 3.9 above. Don't do pyenv for now.
# If psycopg2 install fails, you forgot about gcc or dev libs.

cp .env.dist .env
nano .env

# sudo -u postgres psql
CREATE DATABASE coriolis;
CREATE USER coriolis;
ALTER USER coriolis WITH PASSWORD 'nice-try-m8';
GRANT ALL ON DATABASE coriolis TO coriolis;

# Pre-deployment
poetry shell  # loads .env
./manage.py compilemessages
./manage.py collectstatic
./manage.py migrate
exit  # the poetry shell

mkdir /app/public && cd /app/public
mkdir ../media

ln -s ../static static
ln -s ../media media

chown -R www-data:www-data /app

# BEFORE MESSING WITH NGINX, SET UP HTTPS CERTS W/ REDIRECT!
# It's a massive pain to do this right now with configs below.
certbot run -d example.com --nginx --agree-tos -m owo@whats.this

# Files
cp contrib/coriolis.service /etc/systemd/system/coriolis.service
cp contrib/coriolis.nginx.conf /etc/nginx/sites-available/coriolis
nano /etc/nginx/sites-available/coriolis  # s/example.com/your.domain/d

ln -s /etc/nginx/sites-available/coriolis /etc/nginx/sites-enabled/coriolis
rm /etc/nginx/sites-enabled/default

systemctl daemon-reload
systemctl restart nginx
systemctl enable coriolis --now

cd /app
poetry shell
./manage.py createsuperuser

# Try your domain now.
