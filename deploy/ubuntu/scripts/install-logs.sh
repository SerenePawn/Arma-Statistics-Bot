#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/root/projects/asb}"

install -m 755 "$APP_DIR/deploy/ubuntu/scripts/logs" /usr/local/bin/logs
install -m 755 "$APP_DIR/deploy/ubuntu/scripts/logs-bot" /usr/local/bin/logs-bot
install -m 755 "$APP_DIR/deploy/ubuntu/scripts/logs-web" /usr/local/bin/logs-web
