from __future__ import annotations

import signal
import threading

from werkzeug.serving import make_server

from file_server import app
from runtime_config import load_runtime_config


class ServiceRunner:
    def __init__(self):
        runtime = load_runtime_config()
        self.host = runtime["host"]
        self.port = runtime["port"]
        self._server = make_server(self.host, self.port, app)
        self._shutdown_event = threading.Event()

    def start(self) -> None:
        print(f"File Browser service listening on http://{self.host}:{self.port}")
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
        self._server.serve_forever()

    def _handle_signal(self, _signum, _frame) -> None:
        if self._shutdown_event.is_set():
            return
        self._shutdown_event.set()
        self._server.shutdown()
        self._server.server_close()


if __name__ == "__main__":
    ServiceRunner().start()
