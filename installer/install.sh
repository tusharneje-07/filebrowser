#!/bin/bash
# FINAL REVISION - Matches manual execution perfectly
APP_NAME="filebrowser"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
BIN_DIR="$HOME/.local/bin"

echo "VERIFYING INSTALLATION V1.1..."
mkdir -p "$INSTALL_DIR" "$BIN_DIR"

# Download latest
cd "$INSTALL_DIR"
if [ -d ".git" ]; then
    git pull
else
    git clone https://github.com/tusharneje-07/file_browser.git .
fi

# Use the exact same python the user uses manually
PYTHON_BIN=$(which python3)
$PYTHON_BIN -m pip install --user flask werkzeug Pillow pystray || true

# Create a direct alias-like script
cat <<EOF2 > "$BIN_DIR/$APP_NAME"
#!/bin/bash
cd "$INSTALL_DIR"
exec $PYTHON_BIN tray_server.py "\$@"
EOF2
chmod +x "$BIN_DIR/$APP_NAME"

echo "DONE. PLEASE RUN: filebrowser"
