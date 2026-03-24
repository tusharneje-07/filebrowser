#!/usr/bin/env bash
set -euo pipefail

APP_NAME="file-browser"
INSTALL_ROOT="${HOME}/.local/share/${APP_NAME}"
BIN_DIR="${HOME}/.local/bin"
SYSTEMD_DIR="${HOME}/.config/systemd/user"
DESKTOP_DIR="${HOME}/.local/share/applications"

systemctl --user disable --now file-browser.service >/dev/null 2>&1 || true
rm -f "${SYSTEMD_DIR}/file-browser.service"
systemctl --user daemon-reload || true

rm -f "${BIN_DIR}/file-browser" "${BIN_DIR}/file-browser-service"
rm -f "${DESKTOP_DIR}/file-browser.desktop"
rm -rf "${INSTALL_ROOT}"

echo "File Browser removed from user environment."
