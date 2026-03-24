# File Browser

Production-ready local file browser product for Linux:

- Flask-based file server (`file_server.py`)
- Linux tray manager with Tkinter (`tray_server.py`)
- Chrome side panel extension (`chrome_extension/`)
- Configurable roots database (`paths_db.json`)
- Runtime network config (`runtime_config.json`)
- Optional user-level systemd service (`file_browser_service.py`)

## Default Runtime

- Host: `127.0.0.1`
- Port: `17650` (high port to avoid common conflicts)

Update host/port from the tray app under **Runtime Settings**.

## Chrome Extension

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select `chrome_extension`
5. Open side panel from extension icon

## Dev Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python tray_server.py
```

## Linux Installer (Product Mode)

Install for current user:

```bash
./installer/linux/install.sh
```

This installs:

- App files at `~/.local/share/file-browser`
- Launch commands:
  - `file-browser` (tray manager)
  - `file-browser-service` (headless service)
- User systemd unit: `file-browser.service`
- Desktop launcher entry

Enable service startup:

```bash
systemctl --user enable --now file-browser.service
```

Check status:

```bash
systemctl --user status file-browser.service
```

## Build Linux Release Archive

```bash
./installer/linux/build_release.sh
```

Tarball is created in `dist/`.

## Uninstall

```bash
./installer/linux/uninstall.sh
```
