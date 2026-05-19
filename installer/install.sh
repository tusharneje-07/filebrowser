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

# Ensure dependencies are available on system python
python3 -m pip install --user flask werkzeug Pillow pystray || true

# Create the wrapper
cat <<EOF2 > "$BIN_DIR/$APP_NAME"
#!/usr/bin/env bash
# FileBrowser Launcher
cd "$INSTALL_DIR"
exec python3 tray_server.py "\$@"
EOF2
chmod +x "$BIN_DIR/$APP_NAME"

echo "Installation complete. Run 'filebrowser' to start."
