import os, sys, threading, socket, time, signal, platform, json
from pathlib import Path
from PIL import Image, ImageDraw
from flask import Flask, jsonify
from werkzeug.serving import make_server

# --- Clean existing ---
PORT = 17650
LOCK = 17651

def cleanup():
    try:
        if platform.system() != "Windows":
            pids = subprocess.check_output(['lsof', '-t', f'-i:{PORT},:{LOCK}'], stderr=subprocess.DEVNULL).decode().split()
            for pid in pids:
                if int(pid) != os.getpid(): os.kill(int(pid), signal.SIGKILL)
    except: pass

import subprocess

# --- Logic ---
app = Flask(__name__)
@app.route("/health")
def health(): return jsonify({"status": "ok"})

def run_server():
    srv = make_server("127.0.0.1", PORT, app)
    srv.serve_forever()

# --- GUI ---
import tkinter as tk
try: import pystray
except: pystray = None

def create_image():
    image = Image.new("RGBA", (64, 64), (255, 255, 255, 0))
    dc = ImageDraw.Draw(image)
    dc.ellipse((4, 4, 60, 60), fill=(37, 99, 235)) # Solid Blue Circle
    dc.rectangle((20, 20, 44, 44), fill="white")
    return image

class App:
    def __init__(self):
        cleanup()
        self.root = tk.Tk()
        self.root.withdraw()
        
        # Start Server
        threading.Thread(target=run_server, daemon=True).start()
        
        # Start Tray
        if pystray:
            self.icon = pystray.Icon("filebrowser", create_image(), "File Browser", menu=pystray.Menu(
                pystray.MenuItem("Exit", self.exit_app)
            ))
            threading.Thread(target=self.icon.run, daemon=True).start()
        
        self.root.mainloop()

    def exit_app(self, *_):
        if hasattr(self, 'icon'): self.icon.stop()
        os._exit(0)

if __name__ == "__main__":
    App()
