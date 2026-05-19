from __future__ import annotations
import json, os, platform, subprocess, threading, sys, socket, time, signal, tempfile
from pathlib import Path
from datetime import datetime

# --- Constants ---
BASE_DIR = Path(__file__).resolve().parent
PATHS_DB_FILE = BASE_DIR / "paths_db.json"
RUNTIME_CONFIG_FILE = BASE_DIR / "runtime_config.json"
FLASK_PORT = 17650
LOCK_PORT = 17651 

# --- Process Control ---
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

# --- Config Management ---
def load_runtime_config():
    if not RUNTIME_CONFIG_FILE.exists(): return {"host": "127.0.0.1", "port": FLASK_PORT}
    try: return json.loads(RUNTIME_CONFIG_FILE.read_text())
    except: return {"host": "127.0.0.1", "port": FLASK_PORT}

def save_runtime_config(host, port):
    RUNTIME_CONFIG_FILE.write_text(json.dumps({"host": host, "port": port}, indent=2))

def load_paths():
    if not PATHS_DB_FILE.exists():
        default = {"roots": [{"id": "root", "label": "Shared Files", "path": str(BASE_DIR / "SharedFiles")}]}
        PATHS_DB_FILE.write_text(json.dumps(default, indent=2))
        return default["roots"]
    try: return json.loads(PATHS_DB_FILE.read_text()).get("roots", [])
    except: return []

def save_paths(roots):
    PATHS_DB_FILE.write_text(json.dumps({"roots": roots}, indent=2))

# --- Flask App ---
from flask import Flask, jsonify, request, send_file
from werkzeug.serving import make_server
from werkzeug.utils import secure_filename

app = Flask(__name__)
@app.after_request
def add_cors(r): r.headers["Access-Control-Allow-Origin"] = "*"; return r

@app.route("/api/roots")
def list_roots(): return jsonify({"roots": load_paths()})

@app.route("/api/browse")
def browse_files():
    root_id = request.args.get("root", "root")
    path_req = request.args.get("path", "").strip("/")
    roots = load_paths()
    root = next((r for r in roots if r["id"] == root_id), None)
    if not root: return jsonify({"error": "Invalid root"}), 400
    base = Path(root["path"])
    target = (base / path_req).resolve()
    if not str(target).startswith(str(base.resolve())): return jsonify({"error": "Forbidden"}), 403
    entries = []
    if target.exists() and target.is_dir():
        for item in sorted(target.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            stat = item.stat()
            entries.append({
                "name": item.name, "type": "directory" if item.is_dir() else "file",
                "relative_path": str(item.relative_to(base)).replace("\\", "/"),
                "size": 0 if item.is_dir() else stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
    return jsonify({"entries": entries, "current_path": path_req})

# --- GUI ---
import tkinter as tk
from PIL import Image, ImageDraw
from tkinter import filedialog, messagebox, ttk

if platform.system().lower() == "linux":
    # DO NOT force appindicator, let pystray decide
    pass

try: import pystray
except: pystray = None

class FileBrowserApp:
    def __init__(self):
        kill_existing_instance()
        if not acquire_lock(): sys.exit(1)
        
        self.root = tk.Tk()
        self.root.title("File Browser Manager")
        self.root.geometry("640x480")
        
        # Start HIDDEN by default as requested
        self.root.withdraw()
        
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        
        self.paths = load_paths()
        self._start_server()
        self._init_tray()
        self._build_ui()

    def _start_server(self):
        conf = load_runtime_config()
        self.srv = make_server(conf["host"], conf["port"], app)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def _init_tray(self):
        if not pystray: return
        img = Image.new("RGBA", (64, 64), (15, 23, 42, 255))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((4, 4, 60, 60), radius=12, fill=(59, 130, 246, 255))
        d.rectangle((20, 25, 44, 45), fill="white") # folder-ish icon
        
        self.tray = pystray.Icon("filebrowser", img, "File Browser", menu=pystray.Menu(
            pystray.MenuItem("Open Manager", self.show, default=True),
            pystray.MenuItem("Exit", self.quit)
        ))
        threading.Thread(target=self.tray.run, daemon=True).start()

    def _build_ui(self):
        style = ttk.Style()
        style.configure(".", font=("Nunito", 10))
        
        main_f = ttk.Frame(self.root, padding=20)
        main_f.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_f, text="FileBrowser Manager", font=("Nunito", 16, "bold")).pack(pady=(0, 10), anchor=tk.W)

        # Server Settings
        config_f = ttk.LabelFrame(main_f, text=" Server Settings ", padding=10)
        config_f.pack(fill=tk.X, pady=10)
        conf = load_runtime_config()
        ttk.Label(config_f, text="Host:").grid(row=0, column=0, padx=5, sticky=tk.W)
        self.host_var = tk.StringVar(value=conf["host"])
        ttk.Entry(config_f, textvariable=self.host_var).grid(row=0, column=1, padx=5, sticky=tk.EW)
        ttk.Label(config_f, text="Port:").grid(row=0, column=2, padx=5, sticky=tk.W)
        self.port_var = tk.StringVar(value=str(conf["port"]))
        ttk.Entry(config_f, textvariable=self.port_var, width=8).grid(row=0, column=3, padx=5, sticky=tk.W)
        ttk.Button(config_f, text="Save", command=self.save_conf).grid(row=0, column=4, padx=5)
        config_f.columnconfigure(1, weight=1)

        # Paths
        path_f = ttk.LabelFrame(main_f, text=" Shared Folders ", padding=10)
        path_f.pack(fill=tk.BOTH, expand=True)
        self.lb = tk.Listbox(path_f, font=("Nunito", 10), border=0, highlightthickness=1)
        self.lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(path_f, command=self.lb.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.lb.config(yscrollcommand=sb.set)
        
        self.refresh_list()

        btn_f = ttk.Frame(main_f)
        btn_f.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_f, text="Add Folder", command=self.add_dir).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="Remove", command=self.remove_dir).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="Hide to Tray", command=self.hide).pack(side=tk.RIGHT, padx=2)
        ttk.Button(btn_f, text="Exit", command=self.quit).pack(side=tk.RIGHT, padx=2)

    def save_conf(self):
        save_runtime_config(self.host_var.get(), int(self.port_var.get()))
        messagebox.showinfo("Saved", "Settings saved. Restart to apply.")

    def refresh_list(self):
        self.lb.delete(0, tk.END)
        for r in self.paths: self.lb.insert(tk.END, f"{r['label']} -> {r['path']}")

    def add_dir(self):
        d = filedialog.askdirectory()
        if d:
            p = str(Path(d).resolve())
            self.paths.append({"id": f"id_{int(time.time())}", "label": Path(p).name, "path": p})
            save_paths(self.paths)
            self.refresh_list()

    def remove_dir(self):
        sel = self.lb.curselection()
        if sel:
            self.paths = [r for i, r in enumerate(self.paths) if i not in sel]
            save_paths(self.paths)
            self.refresh_list()

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
