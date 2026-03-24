from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, make_response, request, send_file
from werkzeug.utils import secure_filename

from runtime_config import load_runtime_config

BASE_DIR = Path(__file__).resolve().parent
FILES_DIR = BASE_DIR / "SharedFiles"
FILES_DIR.mkdir(parents=True, exist_ok=True)
PATHS_DB_FILE = BASE_DIR / "paths_db.json"

DEFAULT_ROOTS = [
    {
        "id": "file_browser_root",
        "label": "Shared Files",
        "path": str(FILES_DIR.resolve()),
    }
]

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
    if cleaned in {"", ".", "/"}:
        return ""
    return cleaned.strip("/")


def _ensure_paths_db() -> None:
    if PATHS_DB_FILE.exists():
        return
    PATHS_DB_FILE.write_text(
        json.dumps({"roots": DEFAULT_ROOTS}, indent=2), encoding="utf-8"
    )


def _load_roots():
    _ensure_paths_db()
    try:
        payload = json.loads(PATHS_DB_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {"roots": DEFAULT_ROOTS}

    roots = []
    seen_ids = set()
    for entry in payload.get("roots", []):
        root_id = str(entry.get("id", "")).strip()
        label = str(entry.get("label", "")).strip()
        raw_path = str(entry.get("path", "")).strip()
        if not root_id or not label or not raw_path:
            continue
        if root_id in seen_ids:
            continue

        root_path = Path(raw_path).expanduser().resolve()
        if not root_path.exists() or not root_path.is_dir():
            continue

        roots.append({"id": root_id, "label": label, "path": root_path})
        seen_ids.add(root_id)

    if roots:
        return roots

    fallback_path = FILES_DIR.resolve()
    return [{"id": "file_browser_root", "label": "Shared Files", "path": fallback_path}]


def _get_root(root_id: str):
    for entry in _load_roots():
        if entry["id"] == root_id:
            return entry
    return None


def _resolve_in_root(root_path: Path, raw_relative_path: str) -> Path:
    relative_path = _normalize_rel_path(raw_relative_path)
    target = (root_path / relative_path).resolve()
    root_resolved = root_path.resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("Invalid path") from exc
    return target


def _safe_upload_name(filename: str) -> str:
    cleaned = secure_filename(filename)
    if not cleaned:
        raise ValueError("Invalid file name")
    return cleaned


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/roots")
def list_roots():
    roots = [
        {
            "id": entry["id"],
            "label": entry["label"],
            "path": str(entry["path"].resolve()),
        }
        for entry in _load_roots()
    ]
    return jsonify({"roots": roots})


@app.get("/api/browse")
def browse_files():
    root_id = request.args.get("root", "file_browser_root")
    current_path = request.args.get("path", "")

    root = _get_root(root_id)
    if not root:
        return jsonify({"error": "Invalid root id"}), 400

    try:
        current_dir = _resolve_in_root(root["path"], current_path)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not current_dir.exists() or not current_dir.is_dir():
        return jsonify({"error": "Directory not found"}), 404

    root_resolved = root["path"].resolve()
    try:
        relative_dir = current_dir.relative_to(root_resolved)
        relative_dir_str = (
            "" if str(relative_dir) == "." else str(relative_dir).replace("\\", "/")
        )
    except ValueError:
        relative_dir_str = ""

    parent_path = ""
    if relative_dir_str:
        parent_path = str(Path(relative_dir_str).parent).replace("\\", "/")
        if parent_path == ".":
            parent_path = ""

    entries = []
    for item in sorted(
        current_dir.iterdir(), key=lambda x: (x.is_file(), x.name.lower())
    ):
        stat = item.stat()
        rel_item = str(item.relative_to(root_resolved)).replace("\\", "/")
        entries.append(
            {
                "name": item.name,
                "relative_path": rel_item,
                "full_path": str(item.resolve()),
                "type": "directory" if item.is_dir() else "file",
                "size": 0 if item.is_dir() else stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        )

    return jsonify(
        {
            "root": {
                "id": root["id"],
                "label": root["label"],
                "path": str(root_resolved),
            },
            "current_path": relative_dir_str,
            "parent_path": parent_path,
            "entries": entries,
        }
    )


@app.get("/api/preview")
def preview_file():
    root_id = request.args.get("root", "file_browser_root")
    file_path = request.args.get("path", "")
    if not file_path:
        return jsonify({"error": "Missing 'path' query parameter"}), 400

    root = _get_root(root_id)
    if not root:
        return jsonify({"error": "Invalid root id"}), 400

    try:
        target = _resolve_in_root(root["path"], file_path)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not target.exists() or not target.is_file():
        return jsonify({"error": "File not found"}), 404

    content = target.read_text(encoding="utf-8", errors="replace")
    return jsonify(
        {
            "name": target.name,
            "full_path": str(target.resolve()),
            "content": content,
        }
    )


@app.get("/api/download")
def download_file():
    root_id = request.args.get("root", "file_browser_root")
    file_path = request.args.get("path", "")
    if not file_path:
        return jsonify({"error": "Missing 'path' query parameter"}), 400

    root = _get_root(root_id)
    if not root:
        return jsonify({"error": "Invalid root id"}), 400

    try:
        target = _resolve_in_root(root["path"], file_path)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not target.exists() or not target.is_file():
        return jsonify({"error": "File not found"}), 404

    return send_file(target, as_attachment=False, download_name=target.name)


@app.post("/api/upload")
def upload_files():
    root_id = request.form.get("root", "file_browser_root")
    current_path = request.form.get("path", "")

    root = _get_root(root_id)
    if not root:
        return jsonify({"error": "Invalid root id"}), 400

    try:
        target_dir = _resolve_in_root(root["path"], current_path)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not target_dir.exists() or not target_dir.is_dir():
        return jsonify({"error": "Target directory not found"}), 404

    incoming = request.files.getlist("files")
    if not incoming:
        return jsonify({"error": "No files uploaded"}), 400

    uploaded = []
    for file_storage in incoming:
        try:
            filename = _safe_upload_name(file_storage.filename or "")
        except ValueError:
            continue

        target = target_dir / filename

        final_target = target
        counter = 1
        while final_target.exists():
            final_target = target.with_stem(f"{target.stem}_{counter}")
            counter += 1

        file_storage.save(final_target)
        uploaded.append(final_target.name)

    if not uploaded:
        return jsonify({"error": "No valid files to upload"}), 400

    return jsonify({"uploaded": uploaded}), 201


if __name__ == "__main__":
    runtime = load_runtime_config()
    app.run(host=runtime["host"], port=runtime["port"], debug=False)
