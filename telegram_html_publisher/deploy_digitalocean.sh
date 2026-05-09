#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/telegram-html-publisher"
SERVICE_NAME="telegram-html-publisher"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash deploy_digitalocean.sh" >&2
  exit 1
fi

mkdir -p "$APP_DIR"
cp publisher.py "$APP_DIR/publisher.py"

if [[ ! -f "$APP_DIR/.env" ]]; then
  cp .env.example "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo "Created $APP_DIR/.env. Edit it before starting the service."
fi

cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<UNIT
[Unit]
Description=Kerwin Telegram HTML Publisher
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${PYTHON_BIN} ${APP_DIR}/publisher.py
Restart=always
RestartSec=8
User=root

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo "Installed ${SERVICE_NAME}."
echo "Next:"
echo "  nano ${APP_DIR}/.env"
echo "  systemctl restart ${SERVICE_NAME}"
echo "  journalctl -u ${SERVICE_NAME} -f"
