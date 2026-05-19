# FileBrowser

A modern file browser application with a tray-based server and a Chrome extension frontend.

## Installation

### Linux & MacOS
To install FileBrowser instantly, run the following command in your terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/tusharneje-07/file_browser/main/installer/setup.sh | bash
```

### Windows
1. Open PowerShell as Administrator.
2. Run the installer script:
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/tusharneje-07/file_browser/main/installer/install.ps1'))
```

## Features
- **Tray Icon Manager**: Control the server from your system tray.
- **Cross-Platform**: Works on Linux, MacOS, and Windows.
- **Chrome Extension**: Access your local files directly from your browser.
- **Nunito Font**: Clean and modern typography.

## Commands
- `filebrowser`: Start the application.
- `filebrowser uninstall`: Remove the application and all configurations.
