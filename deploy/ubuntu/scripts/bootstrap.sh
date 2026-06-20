#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/root/projects/asb}"
BRANCH="${BRANCH:-deploy}"
REPO_URL="${REPO_URL:-https://github.com/SerenePawn/Arma-Statistics-Bot.git}"
DOMAIN="${DOMAIN:-re-arma-bot.online}"

export DEBIAN_FRONTEND=noninteractive

echo "==> System packages"
apt-get update
apt-get install -y curl git postgresql postgresql-contrib nginx certbot python3-certbot-nginx

echo "==> Directories"
mkdir -p /root/projects /var/log/arma-stat-counter /var/lib/arma-stat-counter/ocaps /var/www/html

echo "==> Project code"
if [[ ! -d "$APP_DIR/.git" ]]; then
  git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"
chmod +x deploy/ubuntu/scripts/*.sh

if [[ ! -f "$APP_DIR/config.ini" ]]; then
  cp "$APP_DIR/config.ini.example" "$APP_DIR/config.ini"
  chmod 600 "$APP_DIR/config.ini"
  echo "WARNING: created $APP_DIR/config.ini from example — fill secrets before production use" >&2
fi

echo "==> PostgreSQL role/database"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='arma_stat_counter'" | grep -q 1; then
  DB_PASS="$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)"
  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
CREATE USER arma_stat_counter WITH PASSWORD '${DB_PASS}';
CREATE DATABASE arma_stat_counter OWNER arma_stat_counter;
SQL
  python3 - <<PY
from configparser import ConfigParser
from pathlib import Path

path = Path("${APP_DIR}/config.ini")
config = ConfigParser()
config.read(path)
if not config.has_section("DATABASE"):
    config.add_section("DATABASE")
config.set("DATABASE", "PSQL_PATH", "postgres://arma_stat_counter:${DB_PASS}@127.0.0.1:5432/arma_stat_counter")
with path.open("w") as fd:
    config.write(fd)
print("Updated PSQL_PATH in config.ini")
PY
fi

echo "==> systemd units"
INSTALL_SYSTEMD_UNITS=1 bash "$APP_DIR/deploy/ubuntu/scripts/deploy.sh"

if [[ ! -f "/etc/nginx/sites-enabled/arma-stat-counter.conf" ]]; then
  echo "==> nginx HTTP config"
  sed "s/example.com/${DOMAIN}/g" \
    "$APP_DIR/deploy/ubuntu/nginx/arma-stat-counter.http.conf.example" \
    > /etc/nginx/sites-available/arma-stat-counter.conf
  ln -sf /etc/nginx/sites-available/arma-stat-counter.conf /etc/nginx/sites-enabled/arma-stat-counter.conf
  nginx -t
  systemctl enable --now nginx
  systemctl reload nginx
fi

if [[ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
  echo "==> certbot (requires DNS ${DOMAIN} -> this server)"
  certbot certonly --webroot -w /var/www/html -d "$DOMAIN" --non-interactive --agree-tos -m admin@${DOMAIN} || true
fi

if [[ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
  sed "s/example.com/${DOMAIN}/g" \
    "$APP_DIR/deploy/ubuntu/nginx/arma-stat-counter.conf.example" \
    > /etc/nginx/sites-available/arma-stat-counter.conf
  nginx -t && systemctl reload nginx
fi

{
  echo "deployed_at=$(date -Is)"
  echo "hostname=$(hostname)"
  echo "public_ip=$(curl -fsS --max-time 5 ifconfig.me || echo unknown)"
  echo "app_dir=${APP_DIR}"
  echo "python=$(${APP_DIR}/.venv/bin/python --version 2>&1)"
  echo "bot=$(systemctl is-active arma-stat-counter-bot)"
  echo "web=$(systemctl is-active arma-stat-counter-web)"
  echo "health=$(curl -fsS --max-time 10 http://127.0.0.1:8000/health || echo failed)"
} | tee /root/DEPLOY_STATUS.txt

echo "Bootstrap complete. Status: /root/DEPLOY_STATUS.txt"
