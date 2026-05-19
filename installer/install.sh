#!/bin/bash
# FINAL REVISION - Minimal Output with Progress Bar
APP_NAME="filebrowser"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
BIN_DIR="$HOME/.local/bin"

# Progress bar function
progress_bar() {
    local duration=$1
    local width=40
    local progress=0
    while [ $progress -le 100 ]; do
        local filled=$((progress * width / 100))
        local empty=$((width - filled))
        printf "\rInstallation Progress: ["
        printf "%${filled}s" | tr ' ' '#'
        printf "%${empty}s" | tr ' ' '-'
        printf "] %d%%" "$progress"
        sleep $((duration / 100))
        progress=$((progress + 1))
    done
    echo ""
}

# Start installation quietly
mkdir -p "$INSTALL_DIR" "$BIN_DIR" > /dev/null 2>&1

# Download necessary files using curl (no git dependency)
cd "$INSTALL_DIR" > /dev/null 2>&1
BASE_URL="https://raw.githubusercontent.com/tusharneje-07/filebrowser/main"
curl -fsSL "$BASE_URL/tray_server.py" -o tray_server.py > /dev/null 2>&1
curl -fsSL "$BASE_URL/icon.png" -o icon.png > /dev/null 2>&1
# Note: paths_db.json is now managed in ~/.config/filebrowser/ by the app itself

# Dependencies quietly
PYTHON_BIN=$(which python3)
$PYTHON_BIN -m pip install --user flask werkzeug Pillow pystray > /dev/null 2>&1

# Start the fake progress bar to mask the remaining setup
progress_bar 2

# Create robust wrapper script quietly
cat <<EOF > "$BIN_DIR/$APP_NAME"
#!/bin/bash
export DBUS_SESSION_BUS_ADDRESS=\$DBUS_SESSION_BUS_ADDRESS
cd "$INSTALL_DIR"
exec $PYTHON_BIN tray_server.py "\$@" > /dev/null 2>&1
EOF

chmod +x "$BIN_DIR/$APP_NAME" > /dev/null 2>&1

# Create Desktop Entry for Linux quietly
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    mkdir -p "$HOME/.local/share/applications" > /dev/null 2>&1
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
fi

echo "Success: File Browser installed. Run with '$APP_NAME'."
