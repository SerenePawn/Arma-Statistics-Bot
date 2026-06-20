#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/root/projects/asb}"
BRANCH="${BRANCH:-deploy}"

cd "$APP_DIR"

echo "==> Fetch ${BRANCH}"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

echo "==> Ensure Python 3.12"
bash deploy/ubuntu/scripts/install-python.sh

echo "==> Install Python dependencies"
bash deploy/ubuntu/scripts/install-runtime.sh

echo "==> Run migrations"
bash deploy/ubuntu/scripts/migrate.sh

echo "==> Install log commands"
bash deploy/ubuntu/scripts/install-logs.sh

if [[ "${INSTALL_SYSTEMD_UNITS:-0}" == "1" ]]; then
  echo "==> Install systemd units"
  install -m 644 "$APP_DIR/deploy/ubuntu/systemd/arma-stat-counter-bot.service.example" \
    /etc/systemd/system/arma-stat-counter-bot.service
  install -m 644 "$APP_DIR/deploy/ubuntu/systemd/arma-stat-counter-web.service.example" \
    /etc/systemd/system/arma-stat-counter-web.service
  systemctl daemon-reload
  systemctl enable arma-stat-counter-bot arma-stat-counter-web
fi

echo "==> Restart services"
systemctl restart arma-stat-counter-bot arma-stat-counter-web

echo "==> Status"
systemctl --no-pager status arma-stat-counter-bot arma-stat-counter-web

echo "==> Health check"
curl -fsS http://127.0.0.1:8000/health
echo

echo "Deploy complete."
