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

# IMPORTANT: Do not use venv if it causes tray issues. 
# We will use the system python but ensure dependencies are present.
python3 -m pip install --user flask werkzeug Pillow pystray || true

cat <<EOF2 > "$BIN_DIR/$APP_NAME"
#!/bin/bash
# Simple wrapper that mimics manual execution
cd "$INSTALL_DIR"
exec python3 tray_server.py "\$@"
EOF2
chmod +x "$BIN_DIR/$APP_NAME"

echo "Installation complete. Run 'filebrowser' to start."
