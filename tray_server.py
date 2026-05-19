from __future__ import annotations

import json
import os
import platform
import subprocess
import threading
import sys
import socket
import time
import signal
from pathlib import Path
from datetime import datetime

# --- Logging for Debugging ---
LOG_FILE = Path(tempfile.gettempdir()) / "filebrowser_debug.log"
def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")

import tempfile

# --- Constants & Config ---
BASE_DIR = Path(__file__).resolve().parent
PATHS_DB_FILE = BASE_DIR / "paths_db.json"
RUNTIME_CONFIG_FILE = BASE_DIR / "runtime_config.json"
FLASK_PORT = 17650
LOCK_PORT = 17651 

def get_pids_for_port(port):
    pids = set()
    try:
        output = subprocess.check_output(['lsof', '-t', f'-i:{port}'], stderr=subprocess.DEVNULL).decode()
        for line in output.splitlines():
            if line.strip(): pids.add(int(line.strip()))
    except: pass
    return pids

def kill_existing_instance():
    my_pid = os.getpid()
    targets = (get_pids_for_port(FLASK_PORT) | get_pids_for_port(LOCK_PORT)) - {my_pid}
    for pid in targets:
        try: os.kill(pid, signal.SIGKILL)
        except: pass
    if targets: time.sleep(1)

lock_socket = None
def acquire_lock():
    global lock_socket
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        lock_socket.bind(('127.0.0.1', LOCK_PORT))
        lock_socket.listen(1)
        return True
    except: return False

def load_paths():
    if not PATHS_DB_FILE.exists(): return []
    try: return json.loads(PATHS_DB_FILE.read_text()).get("roots", [])
    except: return []

# --- Flask App ---
from flask import Flask, jsonify, request
from werkzeug.serving import make_server
app = Flask(__name__)
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

# --- GUI ---
import tkinter as tk
from PIL import Image, ImageDraw
from tkinter import filedialog, messagebox, ttk

if platform.system().lower() == "linux":
    # Hint at the backend but don't force it if it fails
    if not os.environ.get("PYSTRAY_BACKEND"):
        os.environ["PYSTRAY_BACKEND"] = "appindicator"

try: import pystray
except: pystray = None

class FileBrowserApp:
    def __init__(self):
        log("Initializing Application...")
        kill_existing_instance()
        if not acquire_lock():
            log("Failed to acquire lock.")
            sys.exit(1)

        self.root = tk.Tk()
        self.root.title("File Browser Manager")
        self.root.geometry("640x480")
        self.root.withdraw()
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        
        self.paths = load_paths()
        self._start_server()
        self._init_tray()
        self._build_ui()
        log("UI and Tray initialized.")

    def _start_server(self):
        self.srv = make_server("127.0.0.1", FLASK_PORT, app)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def _build_ui(self):
        f = ttk.Frame(self.root, padding=20)
        f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(f, text="FileBrowser Server Manager", font=("Nunito", 16, "bold")).pack(pady=10)
        ttk.Button(f, text="Hide to Tray", command=self.hide_to_tray).pack()
        ttk.Button(f, text="Exit", command=self.quit_app).pack()

    def _init_tray(self):
        if not pystray:
            log("Pystray not found.")
            return
        
        img = Image.new("RGBA", (64, 64), (15, 23, 42, 255))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((4, 4, 60, 60), radius=12, fill=(59, 130, 246, 255))
        
        self.tray = pystray.Icon("filebrowser", img, "FileBrowser", menu=pystray.Menu(
            pystray.MenuItem("Open", self.show_window),
            pystray.MenuItem("Exit", self.quit_app)
        ))
        threading.Thread(target=self.tray.run, daemon=True).start()

    def show_window(self, *_):
        self.root.after(0, lambda: (self.root.deiconify(), self.root.lift()))

    def hide_to_tray(self): self.root.withdraw()

    def quit_app(self, *_):
        if hasattr(self, 'srv'): self.srv.shutdown()
        if hasattr(self, 'tray'): self.tray.stop()
        if lock_socket: lock_socket.close()
        self.root.destroy()
        os._exit(0)

if __name__ == "__main__":
    log("Starting main...")
    app_inst = FileBrowserApp()
    app_inst.root.mainloop()
