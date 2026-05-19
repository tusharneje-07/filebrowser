#!/bin/bash
# Usage: curl -fsSL https://raw.githubusercontent.com/tusharneje-07/filebrowser/main/installer/setup.sh | bash
OS="$(uname)"
case "$OS" in
    Linux*|Darwin*)
        bash <(curl -fsSL https://raw.githubusercontent.com/tusharneje-07/filebrowser/main/installer/install.sh)
        ;;
    *)
        echo "Unsupported OS: $OS"
        exit 1
        ;;
esac
