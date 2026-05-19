#!/bin/bash
set -e

APP_NAME="filebrowser"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
BIN_DIR="$HOME/.local/bin"
REPO_URL="https://github.com/tusharneje-07/file_browser.git"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${BLUE}==>${NC} Installing ${GREEN}$APP_NAME${NC}..."

mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

if [ -d "$INSTALL_DIR/.git" ]; then
    echo -e "${BLUE}==>${NC} Updating existing installation..."
    cd "$INSTALL_DIR" && git pull
else
    echo -e "${BLUE}==>${NC} Downloading application code..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

echo -e "${BLUE}==>${NC} Setting up Python environment..."
if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
fi
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install flask werkzeug Pillow pystray

echo -e "${BLUE}==>${NC} Creating executable..."
cat <<EOF2 > "$BIN_DIR/$APP_NAME"
#!/usr/bin/env bash
# FileBrowser Command Wrapper

# Sync environment to ensure tray icon works
export DISPLAY="\${DISPLAY:-:0}"
if [ -z "\$DBUS_SESSION_BUS_ADDRESS" ]; then
    export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/\$(id -u)/bus"
fi

# Run in background to prevent terminal lock
nohup "$INSTALL_DIR/venv/bin/python3" "$INSTALL_DIR/tray_server.py" "\$@" > /dev/null 2>&1 &
echo "FileBrowser started in background. Check your system tray."
EOF2
chmod +x "$BIN_DIR/$APP_NAME"

echo -e "${GREEN}==> Installation complete!${NC}"
