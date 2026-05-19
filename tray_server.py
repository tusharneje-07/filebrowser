from __future__ import annotations

import json
import os
import platform
import subprocess
import threading
import tempfile
import sys
import socket
from pathlib import Path
from typing import Any
from datetime import datetime

# --- Robustness: Single Instance Lock ---
LOCK_PORT = 17651 # Separate from Flask port
lock_socket = None

def is_already_running():
    global lock_socket
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', LOCK_PORT))
        return False
    except socket.error:
        return True

# --- Platform Fixes ---
if platform.system().lower() == "linux":
    # Ensure appindicator backend for GNOME/KDE
    os.environ.setdefault("PYSTRAY_BACKEND", "appindicator")

# --- Dependencies ---
try:
    import pystray
except ImportError:
    pystray = None

if platform.system().lower() == "linux":
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        try:
            gi.require_version("AyatanaAppIndicator3", "0.1")
            from gi.repository import AyatanaAppIndicator3 as AppIndicator3
        except Exception:
            gi.require_version("AppIndicator3", "0.1")
            from gi.repository import AppIndicator3
        from gi.repository import GLib, Gtk
        HAS_GI_APPINDICATOR = True
    except Exception:
        HAS_GI_APPINDICATOR = False
else:
    HAS_GI_APPINDICATOR = False

import tkinter as tk
from PIL import Image, ImageDraw
from tkinter import filedialog, messagebox, ttk
from flask import Flask, jsonify, make_response, request, send_file
from werkzeug.serving import make_server
from werkzeug.utils import secure_filename

# --- Constants & Config ---
BASE_DIR = Path(__file__).resolve().parent
FILES_DIR = BASE_DIR / "SharedFiles"
FILES_DIR.mkdir(parents=True, exist_ok=True)
PATHS_DB_FILE = BASE_DIR / "paths_db.json"
RUNTIME_CONFIG_FILE = BASE_DIR / "runtime_config.json"

DEFAULT_RUNTIME_CONFIG = {"host": "127.0.0.1", "port": 17650}
DEFAULT_ROOTS = [{"id": "root", "label": "Shared Files", "path": str(FILES_DIR.resolve())}]

def load_runtime_config():
    if not RUNTIME_CONFIG_FILE.exists():
        return dict(DEFAULT_RUNTIME_CONFIG)
    try:
        return json.loads(RUNTIME_CONFIG_FILE.read_text())
    except: return dict(DEFAULT_RUNTIME_CONFIG)

# --- Flask App ---
app = Flask(__name__)

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

@app.route("/health")
def health(): return jsonify({"status": "ok"})

@app.route("/api/roots")
def list_roots():
    if not PATHS_DB_FILE.exists(): PATHS_DB_FILE.write_text(json.dumps({"roots": DEFAULT_ROOTS}))
    return jsonify(json.loads(PATHS_DB_FILE.read_text()))

# (Simplified API handlers for brevity in this robust version)
@app.route("/api/browse")
def browse():
    root_id = request.args.get("root", "root")
    path_req = request.args.get("path", "")
    roots = json.loads(PATHS_DB_FILE.read_text())["roots"]
    root = next((r for r in roots if r["id"] == root_id), roots[0])
    base = Path(root["path"])
    target = (base / path_req.strip("/")).resolve()
    if not str(target).startswith(str(base)): return jsonify({"error": "Forbidden"}), 403
    
    entries = []
    if target.exists() and target.is_dir():
        for item in sorted(target.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            entries.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "relative_path": str(item.relative_to(base)).replace("\\", "/")
            })
    return jsonify({"entries": entries, "current_path": str(target.relative_to(base))})

# --- Server Control ---
class ServerManager:
    def __init__(self):
        conf = load_runtime_config()
        self.host, self.port = conf["host"], conf["port"]
        self._srv = None

    def start(self):
        if self._srv: return
        self._srv = make_server(self.host, self.port, app)
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()

    def stop(self):
        if self._srv: self._srv.shutdown(); self._srv = None

# --- UI Application ---
class FileBrowserApp:
    def __init__(self):
        if is_already_running():
            print("FileBrowser is already running.")
            sys.exit(0)

        self.root = tk.Tk()
        self.root.title("File Browser")
        self.root.geometry("500x400")
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        
        self.server = ServerManager()
        self.server.start()
        
        self._build_ui()
        self._init_tray()

    def _build_ui(self):
        f = ttk.Frame(self.root, padding=20)
        f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(f, text="File Browser Server", font=("Nunito", 14, "bold")).pack(pady=10)
        ttk.Label(f, text=f"Running at http://{self.server.host}:{self.server.port}").pack()
        ttk.Button(f, text="Hide to Tray", command=self.hide_to_tray).pack(pady=20)
        ttk.Button(f, text="Exit Completely", command=self.quit_app).pack()

    def _create_icon_img(self):
        img = Image.new("RGBA", (64, 64), (255, 255, 255, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((4, 4, 60, 60), radius=12, fill=(59, 130, 246))
        return img

    def _init_tray(self):
        if pystray:
            self.tray = pystray.Icon("filebrowser", self._create_icon_img(), "File Browser", menu=pystray.Menu(
                pystray.MenuItem("Show Manager", self.show_window),
                pystray.MenuItem("Exit", self.quit_app)
            ))
            threading.Thread(target=self.tray.run, daemon=True).start()

    def show_window(self, *_):
        self.root.after(0, self.root.deiconify)

    def hide_to_tray(self):
        self.root.withdraw()

    def quit_app(self, *_):
        self.server.stop()
        if hasattr(self, 'tray'): self.tray.stop()
        self.root.destroy()
        sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "uninstall":
        print("Uninstalling..."); sys.exit(0)
    FileBrowserApp().root.mainloop()
