import os, sys, threading, socket, time, signal, platform, json, subprocess
import tkinter as tk
from pathlib import Path
from PIL import Image, ImageDraw
from flask import Flask, jsonify, request, send_file
from werkzeug.serving import make_server

try:
    import pystray
except:
    pystray = None

# --- Configuration ---
PORT = 17650
LOCK_PORT = 17651
CONFIG_DIR = Path.home() / ".config" / "filebrowser"
DB_FILE = CONFIG_DIR / "paths_db.json"
SHOW_LOGS = False


def load_db():
    if not CONFIG_DIR.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not DB_FILE.exists():
        return {"roots": [], "port": 17650, "show_logs": False}
    try:
        with open(DB_FILE, "r") as f:
            data = json.load(f)
            # Ensure defaults exist
            if "port" not in data:
                data["port"] = 17650
            if "show_logs" not in data:
                data["show_logs"] = False
            return data
    except:
        return {"roots": [], "port": 17650, "show_logs": False}

    try:
        with open(DB_FILE, "r") as f:
            data = json.load(f)
            # Ensure defaults exist
            if "port" not in data:
                data["port"] = 17650
            if "show_logs" not in data:
                data["show_logs"] = False
            return data
    except:
        return {"roots": [], "port": 17650, "show_logs": False}


def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)


# Global port state
db_data = load_db()
PORT = db_data.get("port", 17650)
SHOW_LOGS = db_data.get("show_logs", False)


# --- Clean existing ---
def cleanup():
    # Use global PORT
    try:
        if platform.system() != "Windows":
            # Kill processes on both ports
            cmd = f"lsof -t -i:{PORT},:{LOCK_PORT}"
            try:
                pids = (
                    subprocess.check_output(cmd.split(), stderr=subprocess.DEVNULL)
                    .decode()
                    .split()
                )
                for pid in pids:
                    if int(pid) != os.getpid():
                        os.kill(int(pid), signal.SIGKILL)
            except subprocess.CalledProcessError:
                pass
        else:
            pass
    except:
        pass


# --- Server Logic ---
app = Flask(__name__)

# Suppress flask logs if SHOW_LOGS is False
import logging

if not SHOW_LOGS:
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)


@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/roots")
def get_roots():
    return jsonify(load_db())


@app.route("/api/browse")
def browse():
    root_id = request.args.get("root")
    rel_path = request.args.get("path", "")

    db = load_db()
    root = next((r for r in db["roots"] if r["id"] == root_id), None)
    if not root:
        return jsonify({"error": "Root not found"}), 404

    base_path = Path(root["path"])
    target_path = (base_path / rel_path).resolve()

    if not str(target_path).startswith(str(base_path)):
        return jsonify({"error": "Access denied"}), 403

    if not target_path.exists():
        return jsonify({"error": "Path not found"}), 404

    entries = []
    try:
        for item in target_path.iterdir():
            if item.name.startswith("."):
                continue
            try:
                stat = item.stat()
                entries.append(
                    {
                        "name": item.name,
                        "type": "directory" if item.is_dir() else "file",
                        "size": stat.st_size,
                        "relative_path": str(item.relative_to(base_path)),
                        "full_path": str(item),
                    }
                )
            except:
                continue
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(
        {
            "current_path": rel_path,
            "entries": sorted(
                entries, key=lambda x: (x["type"] != "directory", x["name"].lower())
            ),
        }
    )


@app.route("/api/preview")
def preview():
    root_id = request.args.get("root")
    rel_path = request.args.get("path", "")

    db = load_db()
    root = next((r for r in db["roots"] if r["id"] == root_id), None)
    if not root:
        return "Root not found", 404

    file_path = (Path(root["path"]) / rel_path).resolve()
    if not file_path.is_file():
        return "Not a file", 400

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(10000)  # First 10k chars
        return jsonify({"content": content})
    except Exception as e:
        return str(e), 500


@app.route("/api/download")
def download():
    root_id = request.args.get("root")
    rel_path = request.args.get("path", "")

    db = load_db()
    root = next((r for r in db["roots"] if r["id"] == root_id), None)
    if not root:
        return "Root not found", 404

    file_path = (Path(root["path"]) / rel_path).resolve()
    if not file_path.is_file():
        return "Not a file", 400

    return send_file(file_path)


def run_server():
    srv = make_server("127.0.0.1", PORT, app)
    srv.serve_forever()


# --- Uninstaller ---
def uninstall():
    print("Uninstalling File Browser...")
    app_name = "filebrowser"
    bin_dir = Path.home() / ".local" / "bin"
    install_dir = Path.home() / ".local" / "share" / app_name
    desktop_file = (
        Path.home() / ".local" / "share" / "applications" / "filebrowser.desktop"
    )

    # Kill any running instance
    cleanup()

    # Remove binary
    bin_file = bin_dir / app_name
    if bin_file.exists():
        bin_file.unlink()
        print(f"Removed {bin_file}")

    # Remove desktop shortcut
    if desktop_file.exists():
        desktop_file.unlink()
        print(f"Removed {desktop_file}")

    # Remove the installation directory (code only)
    if install_dir.exists():
        import shutil

        shutil.rmtree(install_dir)
        print(f"Removed installation directory: {install_dir}")

    print("\nNOTE: Your configuration and roots in ~/.config/filebrowser were kept.")
    print("To remove them, run: rm -rf ~/.config/filebrowser")
    print("Uninstallation complete.")
    sys.exit(0)


# --- GUI / Tray ---
def get_icon_image():
    icon_path = Path(__file__).parent / "icon.png"
    if icon_path.exists():
        try:
            return Image.open(icon_path)
        except:
            pass
    # Fallback to generated image
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    dc.ellipse((4, 4, 60, 60), fill=(37, 99, 235))
    dc.rectangle((18, 18, 46, 46), fill="white")
    return image


class App:
    def __init__(self):
        # Single Instance Lock
        self.lock_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.lock_sock.bind(("127.0.0.1", LOCK_PORT))
        except:
            print("Another instance is running. Exiting.")
            sys.exit(0)

        cleanup()

        # Start Server
        threading.Thread(target=run_server, daemon=True).start()

        # Tray Icon
        if pystray:
            self.icon = pystray.Icon(
                "filebrowser",
                get_icon_image(),
                "File Browser",
                menu=pystray.Menu(
                    pystray.MenuItem("File Browser Settings", self.show_roots),
                    pystray.MenuItem("Exit", self.exit_app),
                ),
            )
            self.icon.run()

        else:
            print("pystray not found, running in headless mode.")
            while True:
                time.sleep(1)

    def show_roots(self):
        # Run Tkinter in a separate thread to avoid blocking pystray
        threading.Thread(target=self._roots_window, daemon=True).start()

    def _roots_window(self):
        root = tk.Tk()
        root.title("File Browser Settings")
        root.geometry("450x480")
        root.configure(bg="#f6f7fb")

        # Font
        font_main = ("Nunito", 10)
        font_bold = ("Nunito", 11, "bold")
        font_small = ("Nunito", 9)

        frame = tk.Frame(root, bg="#f6f7fb", padx=20, pady=20)
        frame.pack(fill="both", expand=True)

        # Port Configuration
        port_frame = tk.Frame(frame, bg="#f6f7fb")
        port_frame.pack(fill="x", pady=(0, 15))

        tk.Label(port_frame, text="Server Port:", font=font_bold, bg="#f6f7fb").pack(
            side="left"
        )

        port_var = tk.StringVar(value=str(PORT))
        port_entry = tk.Entry(
            port_frame, textvariable=port_var, font=font_main, width=8
        )
        port_entry.pack(side="left", padx=10)

        def update_port():
            try:
                new_port = int(port_var.get())
                if 1024 <= new_port <= 65535:
                    db = load_db()
                    db["port"] = new_port
                    save_db(db)
                    tk.messagebox.showinfo(
                        "Success",
                        "Port updated. Please restart the application to apply.",
                    )
                else:
                    tk.messagebox.showerror(
                        "Error", "Port must be between 1024 and 65535"
                    )
            except ValueError:
                tk.messagebox.showerror("Error", "Invalid port number")

        tk.Button(port_frame, text="Update", command=update_port, font=font_small).pack(
            side="left"
        )

        # Log Configuration
        log_frame = tk.Frame(frame, bg="#f6f7fb")
        log_frame.pack(fill="x", pady=(0, 20))

        log_var = tk.BooleanVar(value=SHOW_LOGS)

        def toggle_logs():
            db = load_db()
            db["show_logs"] = log_var.get()
            save_db(db)
            tk.messagebox.showinfo("Info", "Log setting saved. Restart to apply.")

        tk.Checkbutton(
            log_frame,
            text="Show server logs in terminal",
            variable=log_var,
            command=toggle_logs,
            font=font_main,
            bg="#f6f7fb",
            activebackground="#f6f7fb",
        ).pack(side="left")

        # Roots Configuration
        tk.Label(frame, text="Configured Roots", font=font_bold, bg="#f6f7fb").pack(
            anchor="w"
        )

        listbox = tk.Listbox(
            frame,
            font=font_main,
            height=8,
            bg="white",
            relief="flat",
            highlightthickness=1,
        )
        listbox.pack(fill="both", expand=True, pady=5)

        def refresh():
            listbox.delete(0, tk.END)
            db = load_db()
            for r in db.get("roots", []):
                listbox.insert(tk.END, f"{r['label']} ({r['path']})")

        def add_root():
            from tkinter import filedialog, simpledialog

            path = filedialog.askdirectory()
            if path:
                label = simpledialog.askstring(
                    "Label",
                    "Enter a label for this root:",
                    initialvalue=Path(path).name,
                )
                if label:
                    db = load_db()
                    if "roots" not in db:
                        db["roots"] = []
                    root_id = label.lower().replace(" ", "_")
                    db["roots"].append({"id": root_id, "label": label, "path": path})
                    save_db(db)
                    refresh()

        def remove_root():
            idx = listbox.curselection()
            if idx:
                db = load_db()
                db["roots"].pop(idx[0])
                save_db(db)
                refresh()

        btn_frame = tk.Frame(frame, bg="#f6f7fb")
        btn_frame.pack(fill="x", pady=10)

        tk.Button(
            btn_frame, text="Add Root", command=add_root, font=font_main, width=12
        ).pack(side="left", padx=2)
        tk.Button(
            btn_frame, text="Remove", command=remove_root, font=font_main, width=12
        ).pack(side="left", padx=2)
        tk.Button(
            btn_frame, text="Close", command=root.destroy, font=font_main, width=12
        ).pack(side="right", padx=2)

        refresh()
        root.mainloop()

    def exit_app(self, *_):
        if hasattr(self, "icon"):
            self.icon.stop()
        os._exit(0)


if __name__ == "__main__":
    if "--uninstall" in sys.argv or "uninstall" in sys.argv:
        uninstall()
    App()
