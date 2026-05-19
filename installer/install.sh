#!/bin/bash
set -e

APP_NAME="filebrowser"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
BIN_DIR="$HOME/.local/bin"
REPO_URL="https://github.com/tusharneje-07/file_browser.git"

echo "Installing $APP_NAME..."

mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR" && git pull
else
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

# Create venv with system-site-packages to allow access to system tray libraries (gi, appindicator)
if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv --system-site-packages "$INSTALL_DIR/venv"
fi

# Install pip dependencies
"$INSTALL_DIR/venv/bin/pip" install flask werkzeug Pillow pystray

cat <<EOF2 > "$BIN_DIR/$APP_NAME"
#!/usr/bin/env bash
# FileBrowser Launcher
cd "$INSTALL_DIR"
# Inherit all system environment variables for the tray icon
exec "$INSTALL_DIR/venv/bin/python3" "$INSTALL_DIR/tray_server.py" "\$@"
EOF2
chmod +x "$BIN_DIR/$APP_NAME"

echo "Installation complete. Run 'filebrowser' to start."
