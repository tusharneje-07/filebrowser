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

# --- Helper Functions ---
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
        for pid in targets:
            try:
                if platform.system() == "Windows":
                    subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True)
                else:
                    os.kill(pid, signal.SIGKILL)
            except Exception: pass
        time.sleep(1)

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

def load_runtime_config() -> dict:
    if not RUNTIME_CONFIG_FILE.exists():
        return {"host": "127.0.0.1", "port": FLASK_PORT}
    try:
        return json.loads(RUNTIME_CONFIG_FILE.read_text())
    except: return {"host": "127.0.0.1", "port": FLASK_PORT}

def save_runtime_config(host: str, port: int):
    RUNTIME_CONFIG_FILE.write_text(json.dumps({"host": host, "port": port}, indent=2))

def load_paths() -> list[dict]:
    if not PATHS_DB_FILE.exists():
        default = {"roots": [{"id": "root", "label": "Shared Files", "path": str(FILES_DIR.resolve())}]}
        PATHS_DB_FILE.write_text(json.dumps(default, indent=2))
        return default["roots"]
    try:
        return json.loads(PATHS_DB_FILE.read_text()).get("roots", [])
    except: return []

def save_paths(roots: list[dict]):
    PATHS_DB_FILE.write_text(json.dumps({"roots": roots}, indent=2))

# --- Flask App ---
from flask import Flask, jsonify, request
from werkzeug.serving import make_server

app = Flask(__name__)

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

@app.route("/health")
def health(): return jsonify({"status": "ok"})

@app.route("/api/roots")
def list_roots(): return jsonify({"roots": load_paths()})

# --- GUI Application ---
import tkinter as tk
from PIL import Image, ImageDraw
from tkinter import filedialog, messagebox, ttk

# Platform Fixes for Tray
if platform.system().lower() == "linux":
    # TRY ALL BACKENDS if appindicator fails
    os.environ.setdefault("PYSTRAY_BACKEND", "appindicator")

try: import pystray
except ImportError: pystray = None

class FileBrowserApp:
    def __init__(self):
        kill_existing_instance()
        if not acquire_lock(): sys.exit(1)

        self.root = tk.Tk()
        self.root.title("File Browser Manager")
        self.root.geometry("640x480")
        
        # Withdraw the window so it starts hidden
        self.root.withdraw()
        
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        
        self.paths = load_paths()
        self._start_server()
        self._build_ui()
        self._init_tray()

    def _start_server(self):
        conf = load_runtime_config()
        self.srv = make_server(conf["host"], conf["port"], app)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def _build_ui(self):
        style = ttk.Style()
        style.configure(".", font=("Nunito", 10))
        
        main_f = ttk.Frame(self.root, padding=20)
        main_f.pack(fill=tk.BOTH, expand=True)

        header = ttk.Label(main_f, text="FileBrowser Server Manager", font=("Nunito", 16, "bold"))
        header.pack(pady=(0, 10), anchor=tk.W)

        config_f = ttk.LabelFrame(main_f, text=" Server Settings ", padding=10)
        config_f.pack(fill=tk.X, pady=10)
        
        conf = load_runtime_config()
        ttk.Label(config_f, text="Host:").grid(row=0, column=0, padx=5, sticky=tk.W)
        self.host_var = tk.StringVar(value=conf["host"])
        ttk.Entry(config_f, textvariable=self.host_var).grid(row=0, column=1, padx=5, sticky=tk.EW)
        
        ttk.Label(config_f, text="Port:").grid(row=0, column=2, padx=5, sticky=tk.W)
        self.port_var = tk.StringVar(value=str(conf["port"]))
        ttk.Entry(config_f, textvariable=self.port_var, width=8).grid(row=0, column=3, padx=5, sticky=tk.W)
        
        ttk.Button(config_f, text="Save & Restart", command=self.update_server).grid(row=0, column=4, padx=5)
        config_f.columnconfigure(1, weight=1)

        path_f = ttk.LabelFrame(main_f, text=" Shared Directories ", padding=10)
        path_f.pack(fill=tk.BOTH, expand=True)
        
        self.lb = tk.Listbox(path_f, font=("Nunito", 10), border=0, highlightthickness=1)
        self.lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(path_f, command=self.lb.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.lb.config(yscrollcommand=sb.set)
        
        self.refresh_listbox()

        btn_f = ttk.Frame(main_f)
        btn_f.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_f, text="Add Folder", command=self.add_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="Remove Selected", command=self.remove_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="Hide to Tray", command=self.hide_to_tray).pack(side=tk.RIGHT, padx=2)
        ttk.Button(btn_f, text="Exit", command=self.quit_app).pack(side=tk.RIGHT, padx=2)

    def update_server(self):
        h, p = self.host_var.get(), int(self.port_var.get())
        save_runtime_config(h, p)
        messagebox.showinfo("Restart Needed", "Please restart the application to apply server changes.")

    def refresh_listbox(self):
        self.lb.delete(0, tk.END)
        for r in self.paths: self.lb.insert(tk.END, f"{r['label']} -> {r['path']}")

    def add_folder(self):
        d = filedialog.askdirectory()
        if d:
            p = str(Path(d).resolve())
            self.paths.append({"id": f"id_{int(time.time())}", "label": Path(p).name, "path": p})
            save_paths(self.paths)
            self.refresh_listbox()

    def remove_selected(self):
        sel = self.lb.curselection()
        if sel:
            self.paths = [r for i, r in enumerate(self.paths) if i not in sel]
            save_paths(self.paths)
            self.refresh_listbox()

    def _init_tray(self):
        if pystray:
            img = Image.new("RGBA", (64, 64), (15, 23, 42, 255))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle((4, 4, 60, 60), radius=12, fill=(59, 130, 246))
            
            # Start pystray in its own thread
            self.tray = pystray.Icon("filebrowser", img, "FileBrowser", menu=pystray.Menu(
                pystray.MenuItem("Open Manager", self.show_window, default=True),
                pystray.MenuItem("Exit", self.quit_app)
            ))
            # Use non-daemon thread for pystray to prevent it from being reaped
            # but keep a reference to it.
            self.tray_thread = threading.Thread(target=self.tray.run)
            self.tray_thread.start()

    def show_window(self, *_): self.root.after(0, lambda: (self.root.deiconify(), self.root.lift(), self.root.focus_force()))
    def hide_to_tray(self): self.root.withdraw()
    def quit_app(self, *_):
        if hasattr(self, 'srv'): self.srv.shutdown()
        if hasattr(self, 'tray'): self.tray.stop()
        if lock_socket: lock_socket.close()
        self.root.destroy()
        os._exit(0)

if __name__ == "__main__":
    # Ensure a display is available for Tkinter
    if platform.system() != "Windows" and not os.environ.get("DISPLAY"):
         print("Error: No display found. This application requires a GUI environment.")
         sys.exit(1)
    
    app_inst = FileBrowserApp()
    app_inst.root.mainloop()
