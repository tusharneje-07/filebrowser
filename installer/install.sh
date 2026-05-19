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
# Check for existing venv or create
if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
fi
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install flask werkzeug Pillow pystray

echo -e "${BLUE}==>${NC} Creating executable..."
# This version ensures the script runs with the USER'S full environment
cat <<EOF2 > "$BIN_DIR/$APP_NAME"
#!/usr/bin/env bash
# FileBrowser Command Wrapper

# Sync environment if running from a script/hook
if [ -z "\$DBUS_SESSION_BUS_ADDRESS" ]; then
    # Attempt to find the session bus if not set
    export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/\$(id -u)/bus"
fi

# Ensure we are in the right directory
cd "$INSTALL_DIR"

# Launch the application
# We use the full path to the venv python to ensure correct library loading
"$INSTALL_DIR/venv/bin/python3" "$INSTALL_DIR/tray_server.py" "\$@"
EOF2
chmod +x "$BIN_DIR/$APP_NAME"

echo -e "${GREEN}==> Installation complete!${NC}"
