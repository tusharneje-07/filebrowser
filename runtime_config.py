from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RUNTIME_CONFIG_FILE = BASE_DIR / "runtime_config.json"

DEFAULT_RUNTIME_CONFIG = {
    "host": "127.0.0.1",
    "port": 17650,
}


def _normalize_host(host: object) -> str:
    value = str(host or "").strip()
    return value if value else str(DEFAULT_RUNTIME_CONFIG["host"])


def _normalize_port(port: object) -> int:
    try:
        value = int(port)
    except (TypeError, ValueError):
        return int(DEFAULT_RUNTIME_CONFIG["port"])
    if value < 1024 or value > 65535:
        return int(DEFAULT_RUNTIME_CONFIG["port"])
    return value


def _sanitize(payload: dict) -> dict:
    return {
        "host": _normalize_host(payload.get("host")),
        "port": _normalize_port(payload.get("port")),
    }


def ensure_runtime_config() -> None:
    if RUNTIME_CONFIG_FILE.exists():
        return
    RUNTIME_CONFIG_FILE.write_text(
        json.dumps(DEFAULT_RUNTIME_CONFIG, indent=2), encoding="utf-8"
    )


def load_runtime_config() -> dict:
    ensure_runtime_config()
    try:
        raw = json.loads(RUNTIME_CONFIG_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Invalid config format")
    except (OSError, json.JSONDecodeError, ValueError):
        raw = dict(DEFAULT_RUNTIME_CONFIG)
    data = _sanitize(raw)
    return data


def save_runtime_config(host: str, port: int) -> dict:
    payload = _sanitize({"host": host, "port": port})
    RUNTIME_CONFIG_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
