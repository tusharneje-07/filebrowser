#!/bin/bash
# FINAL REVISION - Optimized for Linux/MacOS tray support
APP_NAME="filebrowser"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
BIN_DIR="$HOME/.local/bin"

echo "INSTALLING FILE BROWSER..."
mkdir -p "$INSTALL_DIR" "$BIN_DIR"

# Download/Sync Repo
cd "$INSTALL_DIR"
if [ -d ".git" ]; then
    git pull
else
    git clone https://github.com/tusharneje-07/file_browser.git .
fi

# Use system python but ensure dependencies
PYTHON_BIN=$(which python3)
echo "Using $PYTHON_BIN"
$PYTHON_BIN -m pip install --user flask werkzeug Pillow pystray 2>/dev/null || true

# Check for tkinter (common pitfall on Linux)
$PYTHON_BIN -c "import tkinter" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "WARNING: tkinter not found. On Ubuntu/Debian, try: sudo apt install python3-tk"
fi

# Create robust wrapper script
cat <<EOF > "$BIN_DIR/$APP_NAME"
#!/bin/bash
# Inherit current session DBUS to ensure tray icon visibility
export DBUS_SESSION_BUS_ADDRESS=\$DBUS_SESSION_BUS_ADDRESS

cd "$INSTALL_DIR"
# Run in background and disown to prevent terminal hang
exec $PYTHON_BIN tray_server.py "\$@"
EOF

chmod +x "$BIN_DIR/$APP_NAME"

# Create Desktop Entry for Linux
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    mkdir -p "$HOME/.local/share/applications"
    cat <<EOF > "$HOME/.local/share/applications/filebrowser.desktop"
[Desktop Entry]
Name=File Browser
Comment=Access local files from Chrome
Exec=$BIN_DIR/$APP_NAME
Icon=folder
Terminal=false
Type=Application
Categories=Utility;
EOF
    # Note: Using a placeholder icon since we don't have a dedicated .png icon yet
fi

# Add uninstallation hint
echo "------------------------------------------------"
echo "INSTALLATION COMPLETE!"
echo "Run the app with: $APP_NAME"
echo "Uninstall with: $APP_NAME --uninstall"
echo "------------------------------------------------"
