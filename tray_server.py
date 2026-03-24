from __future__ import annotations

import json
import os
import platform
import subprocess
import threading
import tempfile
from pathlib import Path
from typing import Any

if platform.system().lower() == "linux":
    os.environ.setdefault("PYSTRAY_BACKEND", "appindicator")

try:
    import pystray
except Exception:
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
        AppIndicator3 = None  # type: ignore
        GLib = None  # type: ignore
        Gtk = None  # type: ignore
else:
    HAS_GI_APPINDICATOR = False
    AppIndicator3 = None  # type: ignore
    GLib = None  # type: ignore
    Gtk = None  # type: ignore

import tkinter as tk
from PIL import Image, ImageDraw
from tkinter import filedialog, messagebox, ttk
from werkzeug.serving import make_server

from file_server import PATHS_DB_FILE, app
from runtime_config import load_runtime_config, save_runtime_config


class FlaskServerController:
    def __init__(self):
        runtime = load_runtime_config()
        self.host = runtime["host"]
        self.port = runtime["port"]
        self._server = None
        self._thread = None
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._server is not None

    def start(self) -> None:
        with self._lock:
            if self._server is not None:
                return
            self._server = make_server(self.host, self.port, app)
            self._thread = threading.Thread(
                target=self._server.serve_forever, daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            if self._server is None:
                return
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None

    def restart(self, host: str, port: int) -> None:
        self.stop()
        self.host = host
        self.port = port
        self.start()


class PathsDB:
    def __init__(self, db_file: Path):
        self.db_file = db_file
        self._ensure_exists()

    def _ensure_exists(self) -> None:
        if self.db_file.exists():
            return
        default = {
            "roots": [
                {
                    "id": "file_browser_root",
                    "label": "Shared Files",
                    "path": str(
                        (Path(__file__).resolve().parent / "SharedFiles").resolve()
                    ),
                }
            ]
        }
        self.db_file.write_text(json.dumps(default, indent=2), encoding="utf-8")

    def load(self) -> list[dict[str, Any]]:
        self._ensure_exists()
        try:
            payload = json.loads(self.db_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return list(payload.get("roots", []))

    def save(self, roots: list[dict[str, Any]]) -> None:
        payload = {"roots": roots}
        self.db_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class TrayServerApp:
    def __init__(self):
        self.server = FlaskServerController()
        self.db = PathsDB(PATHS_DB_FILE)
        self.tray_enabled = False
        self.tray_thread = None
        self.pystray_icon = None
        self.gtk_indicator = None
        self.gtk_menu = None
        self.gtk_loop_running = False
        self.tray_icon_file = None

        self.root = tk.Tk()
        self.root.title("File Browser Server Manager")
        self.root.geometry("640x420")
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)

        self.paths: list[dict[str, Any]] = []
        self._build_ui()
        self.reload_paths()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        top_row = ttk.Frame(frame)
        top_row.pack(fill=tk.X)

        self.server_status_var = tk.StringVar(value="Server: Starting...")
        ttk.Label(
            top_row, textvariable=self.server_status_var, font=("Segoe UI", 10, "bold")
        ).pack(side=tk.LEFT)

        ttk.Label(
            frame,
            text="Manage browse paths used by Flask. Add folders with the picker and click Save Paths.",
        ).pack(fill=tk.X, pady=(8, 8))

        runtime_row = ttk.LabelFrame(frame, text="Runtime Settings", padding=10)
        runtime_row.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(runtime_row, text="Host").grid(row=0, column=0, sticky=tk.W)
        self.host_var = tk.StringVar(value=self.server.host)
        ttk.Entry(runtime_row, textvariable=self.host_var).grid(
            row=0, column=1, sticky=tk.EW, padx=(8, 8)
        )

        ttk.Label(runtime_row, text="Port").grid(row=0, column=2, sticky=tk.W)
        self.port_var = tk.StringVar(value=str(self.server.port))
        ttk.Entry(runtime_row, width=8, textvariable=self.port_var).grid(
            row=0, column=3, sticky=tk.W, padx=(8, 8)
        )

        ttk.Button(runtime_row, text="Save Runtime", command=self.save_runtime_settings).grid(
            row=0, column=4, sticky=tk.E
        )
        runtime_row.columnconfigure(1, weight=1)

        list_wrap = ttk.Frame(frame)
        list_wrap.pack(fill=tk.BOTH, expand=True)

        self.path_listbox = tk.Listbox(list_wrap, selectmode=tk.EXTENDED)
        self.path_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(
            list_wrap, orient=tk.VERTICAL, command=self.path_listbox.yview
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.path_listbox.config(yscrollcommand=scrollbar.set)

        button_row = ttk.Frame(frame)
        button_row.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_row, text="Add Folder", command=self.add_folder).pack(
            side=tk.LEFT
        )
        ttk.Button(
            button_row, text="Remove Selected", command=self.remove_selected
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(button_row, text="Save Paths", command=self.save_paths).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(button_row, text="Hide to Tray", command=self.hide_window).pack(
            side=tk.RIGHT
        )

    def _create_tray_icon(self) -> Image.Image:
        size = 64
        image = Image.new("RGBA", (size, size), (15, 23, 42, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((8, 12, 56, 52), radius=8, fill=(59, 130, 246, 255))
        draw.rectangle((8, 12, 30, 24), fill=(96, 165, 250, 255))
        return image

    def _write_tray_icon_file(self) -> str:
        if self.tray_icon_file and Path(self.tray_icon_file).exists():
            return self.tray_icon_file

        icon_path = Path(tempfile.gettempdir()) / "file-browser-tray.png"
        self._create_tray_icon().save(icon_path)
        self.tray_icon_file = str(icon_path)
        return self.tray_icon_file

    def run(self) -> None:
        self.server.start()
        self._update_server_status()
        self.show_window()
        self._start_tray_icon()
        self.root.mainloop()

    def _start_tray_icon(self) -> None:
        try:
            if platform.system().lower() == "linux" and HAS_GI_APPINDICATOR:
                self._start_linux_appindicator()
                self.tray_enabled = True
                return

            self._start_pystray()
            self.tray_enabled = True
        except Exception as exc:
            self.tray_enabled = False
            messagebox.showwarning(
                "Tray Unavailable", f"{self._tray_help_text()}\n\nError: {exc}"
            )

    def _start_pystray(self) -> None:
        if pystray is None:
            raise RuntimeError("pystray is not installed")

        ready_event = threading.Event()

        def _setup(icon: pystray.Icon) -> None:
            icon.visible = True
            ready_event.set()

        self.pystray_icon = pystray.Icon(
            "FileBrowser",
            self._create_tray_icon(),
            "File Browser Server",
            menu=pystray.Menu(
                pystray.MenuItem("Open Manager", self._menu_open_manager),
                pystray.MenuItem("Add Folder", self._menu_add_folder),
                pystray.MenuItem("Quit", self._menu_quit),
            ),
        )

        self.pystray_icon.run_detached(setup=_setup)
        if not ready_event.wait(timeout=3):
            raise RuntimeError("Tray backend did not signal readiness")

    def _start_linux_appindicator(self) -> None:
        if not HAS_GI_APPINDICATOR:
            raise RuntimeError("Linux appindicator backend unavailable")

        icon_path = self._write_tray_icon_file()
        indicator = AppIndicator3.Indicator.new(
            "FileBrowser",
            "application-x-executable",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )

        if hasattr(indicator, "set_icon_full"):
            indicator.set_icon_full(icon_path, "File Browser")
        elif hasattr(indicator, "set_icon"):
            indicator.set_icon(icon_path)

        menu = Gtk.Menu()

        item_open = Gtk.MenuItem(label="Open Manager")
        item_open.connect("activate", lambda *_: self._menu_open_manager())
        menu.append(item_open)

        item_add = Gtk.MenuItem(label="Add Folder")
        item_add.connect("activate", lambda *_: self._menu_add_folder())
        menu.append(item_add)

        item_quit = Gtk.MenuItem(label="Quit")
        item_quit.connect("activate", lambda *_: self._menu_quit())
        menu.append(item_quit)

        menu.show_all()
        indicator.set_menu(menu)
        indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        self.gtk_indicator = indicator
        self.gtk_menu = menu

        def _gtk_loop() -> None:
            self.gtk_loop_running = True
            Gtk.main()
            self.gtk_loop_running = False

        self.tray_thread = threading.Thread(target=_gtk_loop, daemon=True)
        self.tray_thread.start()

    def _stop_tray_icon(self) -> None:
        if self.pystray_icon is not None:
            try:
                self.pystray_icon.stop()
            except Exception:
                pass
            self.pystray_icon = None

        if self.gtk_loop_running and GLib is not None and Gtk is not None:
            try:
                GLib.idle_add(Gtk.main_quit)
            except Exception:
                pass

        self.gtk_indicator = None
        self.gtk_menu = None

        if self.tray_icon_file:
            try:
                Path(self.tray_icon_file).unlink(missing_ok=True)
            except Exception:
                pass
            self.tray_icon_file = None

    def _tray_help_text(self) -> str:
        base = "System tray is not available. App will run in normal window mode."
        if platform.system().lower() != "linux":
            return base

        detail = [base, "", "Fedora GNOME usually needs AppIndicator support:"]

        detail.append("1) Install extension package:")
        detail.append("   sudo dnf install gnome-shell-extension-appindicator")
        detail.append("2) Install appindicator runtime libs:")
        detail.append("   sudo dnf install libappindicator-gtk3 libdbusmenu-gtk3")
        detail.append("3) Log out and log in again")
        detail.append("4) Enable extension in Extensions app")

        if self._is_gnome_appindicator_missing():
            detail.append("5) AppIndicator extension seems disabled right now")

        return "\n".join(detail)

    def _is_gnome_appindicator_missing(self) -> bool:
        try:
            result = subprocess.run(
                ["gnome-extensions", "list", "--enabled"],
                check=False,
                capture_output=True,
                text=True,
            )
            enabled = result.stdout.lower()
        except Exception:
            return False

        return (
            "appindicatorsupport@rgcjonas.gmail.com" not in enabled
            and "kstatusnotifieritem" not in enabled
        )

    def _update_server_status(self) -> None:
        status = "Running" if self.server.is_running else "Stopped"
        self.server_status_var.set(
            f"Server: {status} (http://{self.server.host}:{self.server.port})"
        )

    def save_runtime_settings(self) -> None:
        host = self.host_var.get().strip() or "127.0.0.1"
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Port", "Port must be a number between 1024 and 65535.")
            return

        if port < 1024 or port > 65535:
            messagebox.showerror("Invalid Port", "Port must be between 1024 and 65535.")
            return

        save_runtime_config(host, port)
        self.server.restart(host, port)
        self._update_server_status()
        messagebox.showinfo("Runtime Saved", f"Server restarted on http://{host}:{port}")

    def reload_paths(self) -> None:
        self.paths = self.db.load()
        self.path_listbox.delete(0, tk.END)
        for entry in self.paths:
            label = entry.get("label", "Unnamed")
            path = entry.get("path", "")
            self.path_listbox.insert(tk.END, f"{label}  ->  {path}")

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(parent=self.root)
        if not folder:
            return

        folder_path = str(Path(folder).resolve())
        if any(str(item.get("path", "")) == folder_path for item in self.paths):
            messagebox.showinfo("Path Exists", "This folder is already in the list.")
            return

        label = Path(folder_path).name or "Folder"
        path_id = self._make_unique_id(label)
        self.paths.append({"id": path_id, "label": label, "path": folder_path})
        self.reload_paths_from_memory()

    def remove_selected(self) -> None:
        selected = set(self.path_listbox.curselection())
        if not selected:
            return
        self.paths = [
            item for idx, item in enumerate(self.paths) if idx not in selected
        ]
        self.reload_paths_from_memory()

    def save_paths(self) -> None:
        self.db.save(self.paths)
        messagebox.showinfo("Saved", "Path database saved to paths_db.json")

    def reload_paths_from_memory(self) -> None:
        self.path_listbox.delete(0, tk.END)
        for entry in self.paths:
            self.path_listbox.insert(tk.END, f"{entry['label']}  ->  {entry['path']}")

    def _make_unique_id(self, label: str) -> str:
        base = "".join(c.lower() if c.isalnum() else "_" for c in label).strip("_")
        if not base:
            base = "root"

        existing = {str(item.get("id", "")) for item in self.paths}
        candidate = base
        index = 1
        while candidate in existing:
            candidate = f"{base}_{index}"
            index += 1
        return candidate

    def hide_window(self) -> None:
        if self.tray_enabled:
            self.root.withdraw()
        else:
            self.root.iconify()

    def on_window_close(self) -> None:
        if self.tray_enabled:
            self.hide_window()
            return
        self.quit_app()

    def show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()

    def quit_app(self) -> None:
        self.server.stop()
        self._update_server_status()
        self._stop_tray_icon()
        self.root.quit()
        self.root.destroy()

    def _menu_open_manager(self, *_args) -> None:
        self.root.after(0, self.show_window)

    def _menu_add_folder(self, *_args) -> None:
        def _open_and_add():
            self.show_window()
            self.add_folder()

        self.root.after(0, _open_and_add)

    def _menu_quit(self, *_args) -> None:
        self.root.after(0, self.quit_app)


if __name__ == "__main__":
    TrayServerApp().run()
