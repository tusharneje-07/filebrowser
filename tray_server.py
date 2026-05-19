from __future__ import annotations
import json, os, platform, subprocess, threading, sys, socket, time, signal
from pathlib import Path
from datetime import datetime

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
PATHS_DB_FILE = BASE_DIR / "paths_db.json"
RUNTIME_CONFIG_FILE = BASE_DIR / "runtime_config.json"
FLASK_PORT = 17650
LOCK_PORT = 17651 

def get_pids_for_port(port):
    try:
        output = subprocess.check_output(['lsof', '-t', f'-i:{port}'], stderr=subprocess.DEVNULL).decode()
        return {int(p) for p in output.splitlines() if p.strip()}
    except: return set()

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

# --- Persistence ---
def load_paths():
    if not PATHS_DB_FILE.exists():
        default = {"roots": [{"id": "root", "label": "Shared Files", "path": str(BASE_DIR / "SharedFiles")}]}
        PATHS_DB_FILE.write_text(json.dumps(default, indent=2))
        return default["roots"]
    try: return json.loads(PATHS_DB_FILE.read_text()).get("roots", [])
    except: return []

def save_paths(roots):
    PATHS_DB_FILE.write_text(json.dumps({"roots": roots}, indent=2))

# --- Server ---
from flask import Flask, jsonify, request
from werkzeug.serving import make_server
app = Flask(__name__)
@app.after_request
def add_cors(r): r.headers["Access-Control-Allow-Origin"] = "*"; return r
@app.route("/api/roots")
def list_roots(): return jsonify({"roots": load_paths()})

# --- UI ---
import tkinter as tk
from PIL import Image, ImageDraw
from tkinter import filedialog, messagebox, ttk

if platform.system().lower() == "linux":
    os.environ.setdefault("PYSTRAY_BACKEND", "appindicator")

try: import pystray
except: pystray = None

class FileBrowserApp:
    def __init__(self):
        kill_existing_instance()
        if not acquire_lock(): sys.exit(1)
        
        self.root = tk.Tk()
        self.root.title("File Browser Manager")
        self.root.geometry("600x450")
        self.root.withdraw() # Start hidden
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        
        self.paths = load_paths()
        self._start_server()
        self._init_tray()
        self._build_ui()

    def _start_server(self):
        self.srv = make_server("127.0.0.1", FLASK_PORT, app)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def _init_tray(self):
        if not pystray: return
        # Create a solid, high-contrast icon
        img = Image.new("RGBA", (64, 64), (15, 23, 42, 255))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((4, 4, 60, 60), radius=10, fill=(37, 99, 235, 255)) # Solid Blue
        d.rectangle((20, 20, 44, 44), fill="white") # White center square
        
        self.tray = pystray.Icon("filebrowser", img, "File Browser", menu=pystray.Menu(
            pystray.MenuItem("Open Manager", self.show, default=True),
            pystray.MenuItem("Exit", self.quit)
        ))
        # Important: No daemon thread for tray to ensure stability
        t = threading.Thread(target=self.tray.run)
        t.start()

    def _build_ui(self):
        style = ttk.Style()
        style.configure(".", font=("Nunito", 10))
        main_f = ttk.Frame(self.root, padding=20)
        main_f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(main_f, text="FileBrowser Manager", font=("Nunito", 16, "bold")).pack(pady=10, anchor=tk.W)
        
        # Path List
        self.lb = tk.Listbox(main_f, font=("Nunito", 10))
        self.lb.pack(fill=tk.BOTH, expand=True)
        for r in self.paths: self.lb.insert(tk.END, f"{r['label']} -> {r['path']}")
        
        btn_f = ttk.Frame(main_f)
        btn_f.pack(fill=tk.X, pady=10)
        ttk.Button(btn_f, text="Add Folder", command=self.add_dir).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="Hide to Tray", command=self.hide).pack(side=tk.RIGHT, padx=2)
        ttk.Button(btn_f, text="Exit", command=self.quit).pack(side=tk.RIGHT, padx=2)

    def add_dir(self):
        d = filedialog.askdirectory()
        if d:
            p = str(Path(d).resolve())
            self.paths.append({"id": f"id_{int(time.time())}", "label": Path(p).name, "path": p})
            save_paths(self.paths)
            self.lb.insert(tk.END, f"{self.paths[-1]['label']} -> {p}")

    def show(self, *_): self.root.after(0, lambda: (self.root.deiconify(), self.root.lift(), self.root.focus_force()))
    def hide(self, *_): self.root.withdraw()
    def quit(self, *_):
        if hasattr(self, 'srv'): self.srv.shutdown()
        if hasattr(self, 'tray'): self.tray.stop()
        if lock_socket: lock_socket.close()
        self.root.destroy()
        os._exit(0)

if __name__ == "__main__":
    FileBrowserApp().root.mainloop()
