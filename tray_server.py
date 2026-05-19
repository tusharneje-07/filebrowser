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
    """Finds all PIDs associated with a specific port using lsof or netstat."""
    pids = set()
    try:
        if platform.system() == "Windows":
            # Using findstr to get the PID column from netstat
            output = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True).decode()
            for line in output.splitlines():
                if "LISTENING" in line:
                    parts = line.strip().split()
                    if parts:
                        pids.add(int(parts[-1]))
        else: # Linux/Mac
            # lsof -t is specific and fast
            output = subprocess.check_output(['lsof', '-t', f'-i:{port}'], stderr=subprocess.DEVNULL).decode()
            for line in output.splitlines():
                if line.strip():
                    pids.add(int(line.strip()))
    except Exception:
        pass
    return pids

def kill_existing_instance():
    """Nuclear kill of anything on our ports."""
    my_pid = os.getpid()
    # Check both ports
    targets = (get_pids_for_port(FLASK_PORT) | get_pids_for_port(LOCK_PORT)) - {my_pid}
    
    if targets:
        print(f"Cleaning up existing instances (PIDs: {list(targets)})...")
        for pid in targets:
            try:
                if platform.system() == "Windows":
                    subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True)
                else:
                    os.kill(pid, signal.SIGKILL)
            except Exception:
                pass
        
        # ESSENTIAL: Wait for the OS to release the socket
        # If we don't wait, bind() will fail with "Address already in use"
        retries = 10
        while retries > 0:
            if not (get_pids_for_port(FLASK_PORT) | get_pids_for_port(LOCK_PORT)) - {my_pid}:
                break
            time.sleep(0.5)
            retries -= 1

# --- Global Lock Socket ---
lock_socket = None

def acquire_lock():
    global lock_socket
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # SO_REUSEADDR allows us to take the port even if it's in TIME_WAIT
        lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
        
        # Try to acquire lock with retries
        locked = False
        for _ in range(5):
            if acquire_lock():
                locked = True
                break
            time.sleep(1)
            
        if not locked:
            print(f"CRITICAL: Port {LOCK_PORT} is still blocked. Use 'fuser -k {LOCK_PORT}/tcp' manually.")
            sys.exit(1)

        self.root = tk.Tk()
        self.root.title("File Browser")
        self.root.geometry("450x300")
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        
        self._start_server()
        self._build_ui()
        self._init_tray()

    def _start_server(self):
        try:
            # Try to start server with retries
            started = False
            for _ in range(5):
                try:
                    self.srv = make_server("127.0.0.1", FLASK_PORT, app)
                    threading.Thread(target=self.srv.serve_forever, daemon=True).start()
                    started = True
                    break
                except socket.error:
                    time.sleep(1)
            
            if not started:
                print(f"CRITICAL: Flask Port {FLASK_PORT} is still blocked.")
                sys.exit(1)
        except Exception as e:
            print(f"Flask start failed: {e}")
            sys.exit(1)

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
        sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "uninstall":
        kill_existing_instance()
        print("Uninstalled successfully."); sys.exit(0)
    
    try:
        app_inst = FileBrowserApp()
        app_inst.root.mainloop()
    except Exception as e:
        print(f"Application Error: {e}")
        sys.exit(1)
