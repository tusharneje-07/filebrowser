#!/bin/bash
# Universal entry point for curl | bash
# Usage: curl -fsSL https://raw.githubusercontent.com/tusharneje-07/file_browser/main/installer/setup.sh | bash

OS="$(uname)"
case "$OS" in
    Linux*|Darwin*)
        echo "Detected $OS. Starting installation from GitHub..."
        bash <(curl -fsSL https://raw.githubusercontent.com/tusharneje-07/file_browser/main/installer/install.sh)
        ;;
    *)
        echo "Unsupported OS: $OS"
        echo "For Windows, please run the PowerShell installer found in the repository."
        exit 1
        ;;
esac
