from __future__ import annotations

import json
import os
import platform
import subprocess
import threading
import tempfile
import sys
import socket
import time
import signal
from pathlib import Path
from typing import Any
from datetime import datetime

# --- Constants & Config ---
BASE_DIR = Path(__file__).resolve().parent
FILES_DIR = BASE_DIR / "SharedFiles"
FILES_DIR.mkdir(parents=True, exist_ok=True)
PATHS_DB_FILE = BASE_DIR / "paths_db.json"
RUNTIME_CONFIG_FILE = BASE_DIR / "runtime_config.json"

DEFAULT_RUNTIME_CONFIG = {"host": "127.0.0.1", "port": 17650}
LOCK_PORT = 17651 # Port for instance detection

def get_lock_owner_pid():
    """Finds the PID of the process holding the lock port."""
    try:
        if platform.system() == "Windows":
            output = subprocess.check_output(f'netstat -ano | findstr :{LOCK_PORT}', shell=True).decode()
            for line in output.splitlines():
                if "LISTENING" in line:
                    return int(line.strip().split()[-1])
        else: # Linux/Mac
            output = subprocess.check_output(f'lsof -i tcp:{LOCK_PORT} -t', shell=True).decode()
            return int(output.strip().splitlines()[0])
    except:
        return None

def kill_existing_instance():
    """Kills any existing instance of the app."""
    pid = get_lock_owner_pid()
    if pid and pid != os.getpid():
        print(f"Killing existing instance (PID: {pid})...")
        try:
            if platform.system() == "Windows":
                subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True)
            else:
                os.kill(pid, signal.SIGTERM)
            time.sleep(1) # Wait for port release
        except:
            pass

# Create global lock socket
lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

def acquire_lock():
    try:
        lock_socket.bind(('127.0.0.1', LOCK_PORT))
        lock_socket.listen(1)
        return True
    except socket.error:
        return False

# --- Platform Fixes ---
if platform.system().lower() == "linux":
    os.environ.setdefault("PYSTRAY_BACKEND", "appindicator")

# --- Dependencies ---
try:
    import pystray
except ImportError:
    pystray = None

import tkinter as tk
from PIL import Image, ImageDraw
from tkinter import filedialog, messagebox, ttk
from flask import Flask, jsonify, request
from werkzeug.serving import make_server

# --- Flask App ---
app = Flask(__name__)

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

@app.route("/health")
def health(): return jsonify({"status": "ok"})

# --- UI Application ---
class FileBrowserApp:
    def __init__(self):
        kill_existing_instance()
        if not acquire_lock():
            print("Failed to acquire lock. Exiting.")
            sys.exit(1)

        self.root = tk.Tk()
        self.root.title("File Browser")
        self.root.geometry("450x300")
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        
        # Start Flask
        self._start_server()
        
        self._build_ui()
        self._init_tray()

    def _start_server(self):
        self.srv = make_server("127.0.0.1", 17650, app)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def _build_ui(self):
        style = ttk.Style()
        style.configure("TLabel", font=("Nunito", 10))
        
        f = ttk.Frame(self.root, padding=30)
        f.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(f, text="FileBrowser Server", font=("Nunito", 16, "bold")).pack(pady=(0, 10))
        ttk.Label(f, text="Server is active at http://127.0.0.1:17650", foreground="green").pack(pady=5)
        
        btn_f = ttk.Frame(f)
        btn_f.pack(pady=20)
        ttk.Button(btn_f, text="Hide to Tray", command=self.hide_to_tray).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_f, text="Quit", command=self.quit_app).pack(side=tk.LEFT, padx=5)

    def _create_icon_img(self):
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((4, 4, 60, 60), radius=12, fill=(59, 130, 246))
        return img

    def _init_tray(self):
        if pystray:
            self.tray = pystray.Icon("filebrowser", self._create_icon_img(), "FileBrowser", menu=pystray.Menu(
                pystray.MenuItem("Show Window", self.show_window),
                pystray.MenuItem("Exit", self.quit_app)
            ))
            threading.Thread(target=self.tray.run, daemon=True).start()

    def show_window(self, *_):
        self.root.after(0, self.root.deiconify)

    def hide_to_tray(self):
        self.root.withdraw()

    def quit_app(self, *_):
        if hasattr(self, 'srv'): self.srv.shutdown()
        if hasattr(self, 'tray'): self.tray.stop()
        lock_socket.close()
        self.root.destroy()
        sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "uninstall":
        kill_existing_instance()
        print("Uninstalling..."); sys.exit(0)
    
    try:
        app_inst = FileBrowserApp()
        app_inst.root.mainloop()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
