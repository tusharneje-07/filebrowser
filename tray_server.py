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
DB_FILE = Path(__file__).parent / "paths_db.json"


def load_db():
    if not DB_FILE.exists():
        return {"roots": []}
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except:
        return {"roots": []}


def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)


# --- Clean existing ---
def cleanup():
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
                        print(f"Killing existing process {pid}")
                        os.kill(int(pid), signal.SIGKILL)
            except subprocess.CalledProcessError:
                pass  # No processes found
        else:
            # Simple Windows port clear (netstat + taskkill if needed)
            pass
    except Exception as e:
        print(f"Cleanup error: {e}")


# --- Server Logic ---
app = Flask(__name__)


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

    # Remove binary
    bin_file = bin_dir / app_name
    if bin_file.exists():
        bin_file.unlink()
        print(f"Removed {bin_file}")

    # Kill any running instance
    cleanup()

    print(
        f"Please manually remove the installation directory if desired: {install_dir}"
    )
    print("Uninstallation complete.")
    sys.exit(0)


# --- GUI / Tray ---
def create_image():
    # Final polished icon with transparency
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    # Background circle
    dc.ellipse((4, 4, 60, 60), fill=(37, 99, 235))
    # Inner document shape
    dc.rectangle((18, 18, 46, 46), fill="white")
    # Small blue lines to simulate text/folder
    dc.line((24, 28, 40, 28), fill=(37, 99, 235), width=2)
    dc.line((24, 34, 40, 34), fill=(37, 99, 235), width=2)
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
                create_image(),
                "File Browser",
                menu=pystray.Menu(
                    pystray.MenuItem("Manage Roots", self.show_roots),
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
        root.title("Manage Roots")
        root.geometry("400x300")
        root.configure(bg="#f6f7fb")

        # Font
        font_main = ("Nunito", 10)
        font_bold = ("Nunito", 11, "bold")

        frame = tk.Frame(root, bg="#f6f7fb", padx=10, pady=10)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Configured Roots", font=font_bold, bg="#f6f7fb").pack(
            anchor="w"
        )

        listbox = tk.Listbox(frame, font=font_main, height=8)
        listbox.pack(fill="both", expand=True, pady=5)

        def refresh():
            listbox.delete(0, tk.END)
            db = load_db()
            for r in db["roots"]:
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
        btn_frame.pack(fill="x", pady=5)

        tk.Button(
            btn_frame, text="Add", command=add_root, font=font_main, width=10
        ).pack(side="left", padx=2)
        tk.Button(
            btn_frame, text="Remove", command=remove_root, font=font_main, width=10
        ).pack(side="left", padx=2)
        tk.Button(
            btn_frame, text="Close", command=root.destroy, font=font_main, width=10
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
