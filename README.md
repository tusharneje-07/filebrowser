# 📁 File Browser

A lightweight, professional file browser that connects your local filesystem to your browser via a Chrome extension. It features a system tray manager, customizable server settings, and high-performance file streaming.

## ✨ Features

- **System Tray Management**: Start, stop, and configure the server from a beautiful tray icon.
- **Root Management**: Easily add or remove multiple local folder "roots" via a GUI.
- **Chrome Extension Integration**: Browse, preview, and send local files directly into web upload areas or active tabs.
- **Customizable**: Configure your server port and toggle terminal logs directly from the settings.
- **Modern UI**: Clean design using the **Nunito** font for both the extension and desktop settings.
- **Atomic One-Liner Install**: Scripted installation for Linux and MacOS.

## 🚀 Installation

### 🐧 Linux & 🍎 MacOS
Run this one-liner in your terminal to install the application, setup the environment, and create a desktop entry:

```bash
curl -fsSL https://raw.githubusercontent.com/tusharneje-07/file_browser/main/installer/setup.sh | bash
```

### 🪟 Windows
1. Open **PowerShell** as Administrator.
2. Execute the following command:
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/tusharneje-07/file_browser/main/installer/install.ps1'))
```

## 🛠️ Commands

Once installed, you can use the following commands globally:

- `filebrowser`: Launches the application and starts the server in the background.
- `filebrowser uninstall`: Completely removes the application, binary, and system shortcuts (keeps your folder configurations in `~/.config/filebrowser`).

## ⚙️ Configuration

Your data and settings are stored persistently in:
- **Linux/MacOS**: `~/.config/filebrowser/paths_db.json`
- **Windows**: `%LOCALAPPDATA%\filebrowser\paths_db.json`

## 🧩 Browser Extension

1. Open Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode**.
3. Click **Load unpacked** and select the `chrome_extension` folder from this repository.
4. Open the Extension Sidepanel to start browsing your configured roots!
