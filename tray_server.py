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

FLASK_PORT = 17650
LOCK_PORT = 17651 

def get_pids_for_port(port):
    pids = set()
    try:
        if platform.system() == "Windows":
            output = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True).decode()
            for line in output.splitlines():
                if "LISTENING" in line:
                    parts = line.strip().split()
                    if parts: pids.add(int(parts[-1]))
        else:
            output = subprocess.check_output(['lsof', '-t', f'-i:{port}'], stderr=subprocess.DEVNULL).decode()
            for line in output.splitlines():
                if line.strip(): pids.add(int(line.strip()))
    except Exception: pass
    return pids

def kill_existing_instance():
    my_pid = os.getpid()
    targets = (get_pids_for_port(FLASK_PORT) | get_pids_for_port(LOCK_PORT)) - {my_pid}
    if targets:
        print(f"Cleaning up existing instances (PIDs: {list(targets)})...")
        for pid in targets:
            try:
                if platform.system() == "Windows":
                    subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True)
                else:
                    os.kill(pid, signal.SIGKILL)
            except Exception: pass
        time.sleep(1)

# --- Global Lock Socket ---
lock_socket = None

def acquire_lock():
    global lock_socket
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        lock_socket.bind(('127.0.0.1', LOCK_PORT))
        lock_socket.listen(1)
        return True
    except socket.error: return False

# --- Platform Fixes ---
if platform.system().lower() == "linux":
    os.environ.setdefault("PYSTRAY_BACKEND", "appindicator")

try:
    import pystray
except ImportError:
    pystray = None

import tkinter as tk
from PIL import Image, ImageDraw
from tkinter import filedialog, messagebox, ttk
from flask import Flask, jsonify, request
from werkzeug.serving import make_server

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
            print(f"CRITICAL: Port {LOCK_PORT} is blocked.")
            sys.exit(1)

        self.root = tk.Tk()
        self.root.title("File Browser")
        self.root.geometry("450x300")
        
        # Withdraw the window immediately on startup so it starts in tray
        self.root.withdraw()
        
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        
        self._start_server()
        self._build_ui()
        self._init_tray()

    def _start_server(self):
        self.srv = make_server("127.0.0.1", FLASK_PORT, app)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def _build_ui(self):
        try: self.root.option_add("*Font", "Nunito 10")
        except: pass
        f = ttk.Frame(self.root, padding=30)
        f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(f, text="FileBrowser Server", font=("Nunito", 16, "bold")).pack(pady=(0, 10))
        ttk.Label(f, text=f"Active at http://127.0.0.1:{FLASK_PORT}", foreground="#22c55e").pack(pady=5)
        btn_f = ttk.Frame(f)
        btn_f.pack(pady=20)
        ttk.Button(btn_f, text="Hide to Tray", command=self.hide_to_tray).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_f, text="Exit App", command=self.quit_app).pack(side=tk.LEFT, padx=5)

    def _create_icon_img(self):
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((4, 4, 60, 60), radius=12, fill=(59, 130, 246))
        return img

    def _init_tray(self):
        if pystray:
            self.tray = pystray.Icon("filebrowser", self._create_icon_img(), "FileBrowser", menu=pystray.Menu(
                pystray.MenuItem("Open", self.show_window, default=True),
                pystray.MenuItem("Exit", self.quit_app)
            ))
            # Start tray in a daemon thread
            threading.Thread(target=self.tray.run, daemon=True).start()

    def show_window(self, *_):
        self.root.after(0, self._force_focus)

    def _force_focus(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide_to_tray(self):
        self.root.withdraw()

    def quit_app(self, *_):
        if hasattr(self, 'srv'): self.srv.shutdown()
        if hasattr(self, 'tray'): self.tray.stop()
        if lock_socket: lock_socket.close()
        self.root.destroy()
        os._exit(0) # Force exit to prevent hanging

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "uninstall":
        kill_existing_instance()
        print("Uninstalled successfully."); sys.exit(0)
    
    app_inst = FileBrowserApp()
    app_inst.root.mainloop()
