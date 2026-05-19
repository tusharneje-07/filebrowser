from __future__ import annotations
import json, os, platform, subprocess, threading, sys, socket, time, signal
from pathlib import Path
from datetime import datetime

# --- Constants ---
BASE_DIR = Path(__file__).resolve().parent
PATHS_DB_FILE = BASE_DIR / "paths_db.json"
FLASK_PORT = 17650
LOCK_PORT = 17651 

# --- Process Control ---
def get_pids_for_port(port):
    try:
        output = subprocess.check_output(['lsof', '-t', f'-i:{port}'], stderr=subprocess.DEVNULL).decode()
        return {int(p) for p in output.splitlines() if p.strip()}
    except: return set()

def kill_existing_instance():
    targets = (get_pids_for_port(FLASK_PORT) | get_pids_for_port(LOCK_PORT)) - {os.getpid()}
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

# --- App Logic ---
from flask import Flask, jsonify, request
from werkzeug.serving import make_server
app = Flask(__name__)
@app.after_request
def add_cors(r): r.headers["Access-Control-Allow-Origin"] = "*"; return r
@app.route("/health")
def health(): return jsonify({"status": "ok"})
@app.route("/api/roots")
def roots():
    if not PATHS_DB_FILE.exists(): return jsonify({"roots": []})
    return jsonify(json.loads(PATHS_DB_FILE.read_text()))

# --- GUI ---
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
        self.root.geometry("500x400")
        self.root.withdraw()
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self._start_server()
        self._init_tray()
        self._build_ui()

    def _start_server(self):
        self.srv = make_server("127.0.0.1", FLASK_PORT, app)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def _init_tray(self):
        if not pystray: return
        # Bright Blue Icon for visibility
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((4, 4, 60, 60), radius=10, fill=(37, 99, 235, 255))
        d.rectangle((15, 25, 49, 45), outline="white", width=3) # Simple folder shape
        
        self.tray = pystray.Icon("filebrowser", img, "FileBrowser", menu=pystray.Menu(
            pystray.MenuItem("Open Manager", self.show),
            pystray.MenuItem("Exit", self.quit)
        ))
        threading.Thread(target=self.tray.run, daemon=True).start()

    def _build_ui(self):
        f = ttk.Frame(self.root, padding=20)
        f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(f, text="FileBrowser Server", font=("Nunito", 14, "bold")).pack(pady=10)
        ttk.Label(f, text=f"Running at http://127.0.0.1:{FLASK_PORT}", foreground="green").pack()
        ttk.Button(f, text="Hide to Tray", command=self.hide).pack(pady=20)
        ttk.Button(f, text="Exit App", command=self.quit).pack()

    def show(self, *_): self.root.after(0, lambda: (self.root.deiconify(), self.root.lift()))
    def hide(self, *_): self.root.withdraw()
    def quit(self, *_):
        if hasattr(self, 'srv'): self.srv.shutdown()
        if hasattr(self, 'tray'): self.tray.stop()
        if lock_socket: lock_socket.close()
        self.root.destroy()
        os._exit(0)

if __name__ == "__main__":
    FileBrowserApp().root.mainloop()
