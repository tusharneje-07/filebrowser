#!/bin/bash
set -e

APP_NAME="filebrowser"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
BIN_DIR="$HOME/.local/bin"
REPO_URL="https://github.com/tusharneje-07/file_browser.git"

# Text colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==>${NC} Installing ${GREEN}$APP_NAME${NC}..."

# Create directories
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

# Check for dependencies
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error:${NC} Python3 is required but not installed."
    exit 1
fi

if ! command -v git &> /dev/null; then
    echo -e "${RED}Error:${NC} git is required but not installed."
    exit 1
fi

# Clone the repository
if [ -d "$INSTALL_DIR/.git" ]; then
    echo -e "${BLUE}==>${NC} Updating existing installation..."
    cd "$INSTALL_DIR" && git pull
else
    echo -e "${BLUE}==>${NC} Downloading application code..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

# Create virtual environment
echo -e "${BLUE}==>${NC} Setting up Python environment..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install flask werkzeug Pillow pystray

# Create the binary wrapper
echo -e "${BLUE}==>${NC} Creating executable..."
cat <<EOF2 > "$BIN_DIR/$APP_NAME"
#!/bin/bash
"$INSTALL_DIR/venv/bin/python3" "$INSTALL_DIR/tray_server.py" "\$@"
EOF2
chmod +x "$BIN_DIR/$APP_NAME"

# Add BIN_DIR to PATH if not present
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    SHELL_RC=""
    if [[ "$SHELL" == */zsh ]]; then
        SHELL_RC="$HOME/.zshrc"
    elif [[ "$SHELL" == */bash ]]; then
        SHELL_RC="$HOME/.bashrc"
    fi
    
    if [ -n "$SHELL_RC" ]; then
        echo "export PATH=\"\$PATH:$BIN_DIR\"" >> "$SHELL_RC"
        echo -e "${BLUE}==>${NC} Added $BIN_DIR to your PATH in $SHELL_RC"
    fi
fi

# Desktop Entry for Linux
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo -e "${BLUE}==>${NC} Creating desktop entry..."
    mkdir -p "$HOME/.local/share/applications"
    cat <<EOF3 > "$HOME/.local/share/applications/$APP_NAME.desktop"
[Desktop Entry]
Name=File Browser
Exec=$BIN_DIR/$APP_NAME
Icon=folder
Type=Application
Categories=Utility;
Terminal=false
EOF3
fi

echo -e "${GREEN}==> Installation complete!${NC}"
echo -e "You can now run it by typing: ${BLUE}$APP_NAME${NC}"
echo -e "To uninstall, run: ${BLUE}$APP_NAME uninstall${NC}"
