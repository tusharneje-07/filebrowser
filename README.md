# File Browser

This project contains:

- A Flask server (`file_server.py`) that serves files from configured roots
- A Tkinter + system-tray manager (`tray_server.py`) to control server and roots
- A Chrome side panel extension in `chrome_extension/`
- 20 demo text files inside `SharedFiles/`

## Features

- File-browser style explorer (folders + files)
- Configurable root paths from `paths_db.json`
- Click any file row to preview content
- Image preview support in the bottom dock
- Toggle button to hide/show preview pane
- Drag a file from the extension list into any website upload target
- Click `Send to site` for direct active-tab file injection fallback
- Back/forward breadcrumb navigation in the side panel

## Upload to websites from extension

1. Open a website with drag-and-drop or file-input upload
2. Keep the side panel open
3. Drag any file row from the explorer and drop it on the website upload area
4. The extension bridge converts it into a real file drop/input change event

## Run with tray app (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python tray_server.py
```

- Server starts at `http://127.0.0.1:5000`
- App starts with manager window and tray support
- If you quit/terminate tray app, server stops automatically
- Add/remove folder roots from the Tkinter manager and save to `paths_db.json`

## Optional: run Flask only

```bash
python file_server.py
```

## Load the extension in Chrome

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select folder: `chrome_extension`
5. Click the extension icon to open the side panel

If needed, update the server URL field in the panel.
