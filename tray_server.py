from __future__ import annotations

import json
import os
import platform
import subprocess
import threading
import tempfile
import sys
from pathlib import Path
from typing import Any
from datetime import datetime

# Environment setup for Linux appindicators
if platform.system().lower() == "linux":
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
            from gi.repository import AppIndicator3  # type: ignore
        from gi.repository import GLib, Gtk
        HAS_GI_APPINDICATOR = True
    except Exception:
        HAS_GI_APPINDICATOR = False
        AppIndicator3 = None
        GLib = None
        Gtk = None
else:
    HAS_GI_APPINDICATOR = False
    AppIndicator3 = None
    GLib = None
    Gtk = None

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

DEFAULT_RUNTIME_CONFIG = {
    "host": "127.0.0.1",
    "port": 17650,
}

DEFAULT_ROOTS = [
    {
        "id": "file_browser_root",
        "label": "Shared Files",
        "path": str(FILES_DIR.resolve()),
    }
]

# --- Runtime Config Management ---
def load_runtime_config() -> dict:
    if not RUNTIME_CONFIG_FILE.exists():
        RUNTIME_CONFIG_FILE.write_text(json.dumps(DEFAULT_RUNTIME_CONFIG, indent=2), encoding="utf-8")
        return dict(DEFAULT_RUNTIME_CONFIG)
    try:
        raw = json.loads(RUNTIME_CONFIG_FILE.read_text(encoding="utf-8"))
        return {
            "host": str(raw.get("host", DEFAULT_RUNTIME_CONFIG["host"])),
            "port": int(raw.get("port", DEFAULT_RUNTIME_CONFIG["port"]))
        }
    except Exception:
        return dict(DEFAULT_RUNTIME_CONFIG)

def save_runtime_config(host: str, port: int):
    RUNTIME_CONFIG_FILE.write_text(json.dumps({"host": host, "port": port}, indent=2), encoding="utf-8")

# --- Flask App Implementation ---
app = Flask(__name__)

def _corsify(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        return _corsify(make_response("", 204))
    return None

@app.after_request
def add_cors_headers(response):
    return _corsify(response)

def _normalize_rel_path(raw_path: str) -> str:
    cleaned = raw_path.replace("\\", "/").strip()
    return "" if cleaned in {"", ".", "/"} else cleaned.strip("/")

def _load_roots():
    if not PATHS_DB_FILE.exists():
        PATHS_DB_FILE.write_text(json.dumps({"roots": DEFAULT_ROOTS}, indent=2), encoding="utf-8")
        return [{"id": r["id"], "label": r["label"], "path": Path(r["path"])} for r in DEFAULT_ROOTS]
    try:
        payload = json.loads(PATHS_DB_FILE.read_text(encoding="utf-8"))
        roots = []
        for entry in payload.get("roots", []):
            p = Path(entry["path"]).expanduser().resolve()
            if p.exists() and p.is_dir():
                roots.append({"id": entry["id"], "label": entry["label"], "path": p})
        return roots if roots else [{"id": r["id"], "label": r["label"], "path": Path(r["path"])} for r in DEFAULT_ROOTS]
    except Exception:
        return [{"id": r["id"], "label": r["label"], "path": Path(r["path"])} for r in DEFAULT_ROOTS]

@app.get("/health")
def health(): return jsonify({"status": "ok"})

@app.get("/api/roots")
def list_roots():
    return jsonify({"roots": [{"id": r["id"], "label": r["label"], "path": str(r["path"])} for r in _load_roots()]})

@app.get("/api/browse")
def browse_files():
    root_id = request.args.get("root", "file_browser_root")
    current_path = request.args.get("path", "")
    root = next((r for r in _load_roots() if r["id"] == root_id), None)
    if not root: return jsonify({"error": "Invalid root"}), 400
    try:
        current_dir = (root["path"] / _normalize_rel_path(current_path)).resolve()
        current_dir.relative_to(root["path"].resolve())
    except Exception: return jsonify({"error": "Invalid path"}), 400
    if not current_dir.exists() or not current_dir.is_dir(): return jsonify({"error": "Not found"}), 404
    
    rel_dir = str(current_dir.relative_to(root["path"].resolve())).replace("\\", "/")
    if rel_dir == ".": rel_dir = ""
    parent = str(Path(rel_dir).parent).replace("\\", "/") if rel_dir else ""
    if parent == ".": parent = ""

    entries = []
    for item in sorted(current_dir.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        stat = item.stat()
        entries.append({
            "name": item.name,
            "relative_path": str(item.relative_to(root["path"].resolve())).replace("\\", "/"),
            "full_path": str(item.resolve()),
            "type": "directory" if item.is_dir() else "file",
            "size": 0 if item.is_dir() else stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return jsonify({"root": {"id": root["id"], "label": root["label"], "path": str(root["path"])}, "current_path": rel_dir, "parent_path": parent, "entries": entries})

@app.get("/api/preview")
def preview_file():
    root_id = request.args.get("root", "file_browser_root")
    path = request.args.get("path", "")
    root = next((r for r in _load_roots() if r["id"] == root_id), None)
    if not root: return jsonify({"error": "Invalid root"}), 400
    try:
        target = (root["path"] / _normalize_rel_path(path)).resolve()
        target.relative_to(root["path"].resolve())
    except Exception: return jsonify({"error": "Invalid path"}), 400
    if not target.exists() or not target.is_file(): return jsonify({"error": "Not found"}), 404
    return jsonify({"name": target.name, "full_path": str(target.resolve()), "content": target.read_text(encoding="utf-8", errors="replace")})

@app.get("/api/download")
def download_file():
    root_id = request.args.get("root", "file_browser_root")
    path = request.args.get("path", "")
    root = next((r for r in _load_roots() if r["id"] == root_id), None)
    if not root: return jsonify({"error": "Invalid root"}), 400
    try:
        target = (root["path"] / _normalize_rel_path(path)).resolve()
        target.relative_to(root["path"].resolve())
    except Exception: return jsonify({"error": "Invalid path"}), 400
    return send_file(target, as_attachment=False, download_name=target.name)

@app.post("/api/upload")
def upload_files():
    root_id = request.form.get("root", "file_browser_root")
    path = request.form.get("path", "")
    root = next((r for r in _load_roots() if r["id"] == root_id), None)
    if not root: return jsonify({"error": "Invalid root"}), 400
    try:
        target_dir = (root["path"] / _normalize_rel_path(path)).resolve()
        target_dir.relative_to(root["path"].resolve())
    except Exception: return jsonify({"error": "Invalid path"}), 400
    
    uploaded = []
    for fs in request.files.getlist("files"):
        fname = secure_filename(fs.filename or "")
        if not fname: continue
        target = target_dir / fname
        while target.exists(): target = target.with_stem(f"{target.stem}_{datetime.now().timestamp()}")
        fs.save(target)
        uploaded.append(target.name)
    return jsonify({"uploaded": uploaded}), 201

# --- Server Control ---
class FlaskServerController:
    def __init__(self):
        runtime = load_runtime_config()
        self.host = runtime["host"]
        self.port = runtime["port"]
        self._server = None
        self._thread = None
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool: return self._server is not None

    def start(self) -> None:
        with self._lock:
            if self._server: return
            self._server = make_server(self.host, self.port, app)
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            if not self._server: return
            self._server.shutdown()
            self._server = None
            self._thread = None

    def restart(self, host: str, port: int) -> None:
        self.stop()
        self.host, self.port = host, port
        self.start()

# --- GUI Implementation ---
class TrayServerApp:
    def __init__(self):
        self.server = FlaskServerController()
        self.tray_enabled = False
        self.pystray_icon = None
        self.gtk_indicator = None
        self.tray_icon_file = None

        self.root = tk.Tk()
        self.root.title("File Browser Server")
        self.root.geometry("640x420")
        
        # Apply Nunito-like font if possible, else Segoe UI / Ubuntu
        self.default_font = ("Nunito", 10)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)
        self.paths: list[dict[str, Any]] = []
        self._build_ui()
        self.reload_paths()

    def _build_ui(self):
        style = ttk.Style()
        style.configure(".", font=self.default_font)
        
        frame = ttk.Frame(self.root, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(frame)
        header.pack(fill=tk.X, pady=(0, 10))
        
        self.status_var = tk.StringVar(value="Server: Starting...")
        ttk.Label(header, textvariable=self.status_var, font=("Nunito", 11, "bold")).pack(side=tk.LEFT)

        config_frame = ttk.LabelFrame(frame, text=" Server Configuration ", padding=10)
        config_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(config_frame, text="Host:").grid(row=0, column=0, padx=5, sticky=tk.W)
        self.host_var = tk.StringVar(value=self.server.host)
        ttk.Entry(config_frame, textvariable=self.host_var).grid(row=0, column=1, padx=5, sticky=tk.EW)
        
        ttk.Label(config_frame, text="Port:").grid(row=0, column=2, padx=5, sticky=tk.W)
        self.port_var = tk.StringVar(value=str(self.server.port))
        ttk.Entry(config_frame, textvariable=self.port_var, width=8).grid(row=0, column=3, padx=5, sticky=tk.W)
        
        ttk.Button(config_frame, text="Update Server", command=self.save_settings).grid(row=0, column=4, padx=5)
        config_frame.columnconfigure(1, weight=1)

        path_frame = ttk.LabelFrame(frame, text=" Shared Directories ", padding=10)
        path_frame.pack(fill=tk.BOTH, expand=True)
        
        self.lb = tk.Listbox(path_frame, font=self.default_font, border=0, highlightthickness=1)
        self.lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(path_frame, command=self.lb.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.lb.config(yscrollcommand=sb.set)

        btns = ttk.Frame(frame)
        btns.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btns, text="Add Folder", command=self.add_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Remove Selected", command=self.remove_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Hide to Tray", command=self.hide_window).pack(side=tk.RIGHT, padx=2)

    def _create_icon(self):
        img = Image.new("RGBA", (64, 64), (15, 23, 42, 255))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((8, 12, 56, 52), radius=8, fill=(59, 130, 246, 255))
        d.rectangle((8, 12, 30, 24), fill=(96, 165, 250, 255))
        return img

    def run(self):
        self.server.start()
        self._update_status()
        self._start_tray()
        self.root.mainloop()

    def _start_tray(self):
        try:
            if platform.system().lower() == "linux" and HAS_GI_APPINDICATOR:
                self._start_linux_tray()
            elif pystray:
                self.pystray_icon = pystray.Icon("FileBrowser", self._create_icon(), "File Browser", menu=pystray.Menu(
                    pystray.MenuItem("Open", self.show_window),
                    pystray.MenuItem("Quit", self.quit_app)
                ))
                self.pystray_icon.run_detached()
            self.tray_enabled = True
        except Exception: pass

    def _start_linux_tray(self):
        self.tray_icon_file = str(Path(tempfile.gettempdir()) / "fb_tray.png")
        self._create_icon().save(self.tray_icon_file)
        self.gtk_indicator = AppIndicator3.Indicator.new("FileBrowser", "application-x-executable", AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
        self.gtk_indicator.set_icon_full(self.tray_icon_file, "File Browser")
        m = Gtk.Menu()
        i1 = Gtk.MenuItem(label="Open"); i1.connect("activate", lambda _: self.show_window()); m.append(i1)
        i2 = Gtk.MenuItem(label="Quit"); i2.connect("activate", lambda _: self.quit_app()); m.append(i2)
        m.show_all()
        self.gtk_indicator.set_menu(m)
        self.gtk_indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        threading.Thread(target=Gtk.main, daemon=True).start()

    def _update_status(self):
        self.status_var.set(f"Server: Running at http://{self.server.host}:{self.server.port}")

    def save_settings(self):
        h, p = self.host_var.get(), int(self.port_var.get())
        save_runtime_config(h, p)
        self.server.restart(h, p)
        self._update_status()
        messagebox.showinfo("Success", "Server updated")

    def reload_paths(self):
        self.paths = []
        if PATHS_DB_FILE.exists():
            try: self.paths = json.loads(PATHS_DB_FILE.read_text())["roots"]
            except: pass
        self.lb.delete(0, tk.END)
        for r in self.paths: self.lb.insert(tk.END, f"{r['label']} -> {r['path']}")

    def add_folder(self):
        d = filedialog.askdirectory()
        if not d: return
        p = str(Path(d).resolve())
        if any(r["path"] == p for r in self.paths): return
        self.paths.append({"id": f"id_{len(self.paths)}", "label": Path(p).name, "path": p})
        self._save_paths()

    def remove_selected(self):
        sel = self.lb.curselection()
        if not sel: return
        self.paths = [r for i, r in enumerate(self.paths) if i not in sel]
        self._save_paths()

    def _save_paths(self):
        PATHS_DB_FILE.write_text(json.dumps({"roots": self.paths}, indent=2))
        self.reload_paths()

    def show_window(self, *_): self.root.after(0, lambda: (self.root.deiconify(), self.root.lift()))
    def hide_window(self): self.root.withdraw()
    def on_window_close(self): self.hide_window() if self.tray_enabled else self.quit_app()
    
    def quit_app(self, *_):
        self.server.stop()
        if self.pystray_icon: self.pystray_icon.stop()
        if self.gtk_indicator: Gtk.main_quit()
        self.root.quit()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "uninstall":
        # Uninstallation logic
        print("Uninstalling FileBrowser...")
        if platform.system() == "Linux":
            subprocess.run(["rm", "-rf", str(Path.home() / ".local/share/filebrowser")])
            # Remove bin link
            subprocess.run(["rm", "-f", str(Path.home() / ".local/bin/filebrowser")])
        elif platform.system() == "Darwin":
            subprocess.run(["rm", "-rf", "/Applications/FileBrowser.app"])
        print("Uninstalled successfully.")
        sys.exit(0)
    TrayServerApp().run()
