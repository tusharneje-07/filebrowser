#!/usr/bin/env bash
set -euo pipefail

APP_NAME="file-browser"
INSTALL_ROOT="${HOME}/.local/share/${APP_NAME}"
BIN_DIR="${HOME}/.local/bin"
SYSTEMD_DIR="${HOME}/.config/systemd/user"
DESKTOP_DIR="${HOME}/.local/share/applications"

echo "Installing File Browser to ${INSTALL_ROOT}"

mkdir -p "${INSTALL_ROOT}" "${BIN_DIR}" "${SYSTEMD_DIR}" "${DESKTOP_DIR}"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"

rsync -a --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.ruff_cache' \
  "${PROJECT_ROOT}/" "${INSTALL_ROOT}/"

python3 -m venv "${INSTALL_ROOT}/.venv"
"${INSTALL_ROOT}/.venv/bin/pip" install --upgrade pip
"${INSTALL_ROOT}/.venv/bin/pip" install -r "${INSTALL_ROOT}/requirements.txt"

cat > "${BIN_DIR}/file-browser" <<'EOF'
#!/usr/bin/env bash
exec "$HOME/.local/share/file-browser/.venv/bin/python" "$HOME/.local/share/file-browser/tray_server.py"
EOF
chmod +x "${BIN_DIR}/file-browser"

cat > "${BIN_DIR}/file-browser-service" <<'EOF'
#!/usr/bin/env bash
exec "$HOME/.local/share/file-browser/.venv/bin/python" "$HOME/.local/share/file-browser/file_browser_service.py"
EOF
chmod +x "${BIN_DIR}/file-browser-service"

cat > "${SYSTEMD_DIR}/file-browser.service" <<'EOF'
[Unit]
Description=File Browser Local Service
After=network.target

[Service]
Type=simple
ExecStart=%h/.local/bin/file-browser-service
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF

cat > "${DESKTOP_DIR}/file-browser.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=File Browser
Comment=Manage local file browser server and paths
Exec=%h/.local/bin/file-browser
Terminal=false
Categories=Utility;Development;
StartupNotify=true
EOF

systemctl --user daemon-reload

echo
echo "Install completed."
echo "Use these commands:"
echo "  file-browser                       # open tray manager"
echo "  systemctl --user enable --now file-browser.service"
echo "  systemctl --user status file-browser.service"
