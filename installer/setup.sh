#!/bin/bash
# Usage: curl -fsSL https://raw.githubusercontent.com/tusharneje-07/file_browser/main/installer/setup.sh | bash
echo "Installer start..."
OS="$(uname)"
case "$OS" in
    Linux*|Darwin*)
        echo "Detected $OS. Starting installation..."
        bash <(curl -fsSL https://raw.githubusercontent.com/tusharneje-07/file_browser/main/installer/install.sh)
        ;;
    *)
        echo "Unsupported OS: $OS"
        exit 1
        ;;
esac
