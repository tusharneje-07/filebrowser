# Filebrowser

Filebrowser is a specialized workflow tool designed to simplify the process of uploading and previewing local files directly within the web browser. It eliminates the need to switch between application windows or navigate complex directory structures in traditional file pickers.

## Motivation and Purpose

This application was developed to solve two primary friction points in modern web workflows:

1.  **Window Switching Inefficiency**: For users who prefer working in full-screen mode, switching to a file manager to drag and drop files is disruptive. Filebrowser integrates a file manager directly into the browser sidepanel, allowing for seamless drag-and-drop operations without ever leaving the active window.
2.  **Lack of File Previews**: Standard file pickers often fail to provide content previews for text-based formats or PDFs. This forces users to manually open files in external applications to verify their contents before uploading. Filebrowser provides instant, integrated previews for a wide variety of file types (Images, PDFs, and Text-based code/data files) directly within the browser interface.

## System Architecture

The project consists of two integrated components:

### 1. Chrome Extension (Frontend)
- **Unified UI**: Provides a modern, responsive file management interface within the browser sidepanel.
- **Instant Preview**: High-performance preview engine for verifying file contents (Images, PDF, Text) before selection.
- **Upload Integration**: Handles the selection and injection of files into designated web upload zones or active tabs.

### 2. Backend Server (Flask & Tkinter)
- **File Service**: A Flask-based server that serves local filesystem content through a secure REST API.
- **Root-Based Security**: The server only exposes files within user-defined "Root Paths" (e.g., specific projects, Volume D, or Volume E).
- **Configuration Interface**: A Tkinter-wrapped management tool for configuring root paths and custom server ports.
- **Persistence**: User settings and root configurations are stored in the local application data directory to ensure they remain available across updates.

## Installation

### Linux and MacOS
Installation is handled via an automated script that configures the environment and creates a desktop entry.

```bash
curl -fsSL https://tusharneje.in/projects/fileserver/setup.sh | bash
```

Alternatively, use the GitHub direct link:

```bash
curl -fsSL https://raw.githubusercontent.com/tusharneje-07/filebrowser/main/installer/setup.sh | bash
```

### Windows
Execute the following in an Administrative PowerShell session:

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://tusharneje.in/projects/fileserver/install.ps1'))
```

Alternatively, use the GitHub direct link:

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/tusharneje-07/filebrowser/main/installer/install.ps1'))
```

## Usage Guide

### 1. Launch the Backend
Run the following command in your terminal to start the background server and configuration interface:
```bash
filebrowser
```
Right-click the management icon in your taskbar to open **File Browser Settings**. Here you must:
- **Add Root Paths**: Add the folders you want to access (e.g., your Downloads folder or an entire Drive).
- **Configure Port**: Ensure the port matches the one set in the Chrome Extension (default is 17650).

### 2. Setting Up the Chrome Extension
Since the extension is currently in developer mode:
1. Open Chrome and go to `chrome://extensions/`.
2. Turn on **Developer mode** (top right).
3. Click **Load unpacked** and select the `chrome_extension` folder from this project.
4. Click the **Extensions puzzle icon** in Chrome and pin **File Browser**.

### 3. Integrated Workflow
Once both parts are running:
- **Open the Sidepanel**: Click the File Browser extension icon to open the file manager in your browser's sidepanel.
- **Browse & Preview**: Click on folders to navigate and click on files (Images, PDFs, Text) to see an instant preview at the bottom.
- **Drag and Drop**: Simply drag a file from the extension sidepanel directly onto any website's upload area.
- **Send to Site**: Alternatively, click the **"Send to site"** button on any file card to automatically inject it into the active page's upload field.

## Technical Details

- **Server Port**: Defaults to 17650 (configurable via settings).
- **Process Management**: Automatically handles port conflicts and enforces a single-instance execution model.
- **Data Storage**: Configuration is managed at `~/.config/filebrowser/paths_db.json` on Unix systems and the equivalent AppData path on Windows.

## Usage
- `filebrowser`: Launches the background server and management interface.
- `filebrowser uninstall`: Removes the application binary and system shortcuts while preserving your root path configurations.
