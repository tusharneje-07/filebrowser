# Filebrowser

Filebrowser is a high-performance, cross-platform local file server designed to bridge the gap between your local filesystem and web-based workflows. It provides a robust backend to serve local files via a RESTful API, managed through a system tray application and consumed by a specialized Chrome extension.

## Technical Architecture

The application is built on a decoupled architecture consisting of three primary components:

### 1. Backend Server (Python/Flask)
- **Core Engine**: A lightweight Flask-based REST API running on a user-configurable port (default 17650).
- **Process Management**: Implements single-instance enforcement using TCP socket locking (port 17651) and automated cleanup of orphaned processes.
- **API Endpoints**:
    - `/api/roots`: Returns configured filesystem entry points.
    - `/api/browse`: Hierarchical directory traversal with security-validated path resolution.
    - `/api/preview`: Optimized text stream preview (10KB chunks).
    - `/api/download`: Direct binary stream delivery for images, PDFs, and general files.

### 2. Desktop Interface (Tkinter/Pystray)
- **Tray Manager**: Native system tray integration for background persistence and quick access.
- **Settings GUI**: A Tkinter-based configuration interface utilizing the Nunito typography for managing file roots and server parameters.
- **Persistence**: User configuration is stored in the standard XDG configuration path (`~/.config/filebrowser/`) to ensure settings persist across application updates.

### 3. Frontend (Chrome Extension)
- **Sidepanel UI**: A modern, reactive interface for browsing local files within the browser context.
- **Bridge Layer**: A content-bridge mechanism that allows dragging and dropping local files directly into web application upload zones.

## Installation

### Linux and MacOS
Installation is handled via an automated script that configures the environment, installs dependencies, and creates a desktop entry.

```bash
curl -fsSL https://raw.githubusercontent.com/tusharneje-07/filebrowser/main/installer/setup.sh | bash
```

### Windows
Execute the following in an Administrative PowerShell session:

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/tusharneje-07/filebrowser/main/installer/install.ps1'))
```

## System Requirements
- Python 3.8+
- Flask, Werkzeug, Pillow, Pystray
- (Linux) libayatana-appindicator or libappindicator-gtk3

## Commands
- `filebrowser`: Initialize the background server and tray icon.
- `filebrowser uninstall`: Complete system cleanup (removes binary and desktop entries while preserving user configuration in `.config`).

## Configuration Paths
- Linux/MacOS: `~/.config/filebrowser/paths_db.json`
- Windows: `%LOCALAPPDATA%\filebrowser\paths_db.json`
