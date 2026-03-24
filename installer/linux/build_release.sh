#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
OUT_DIR="${PROJECT_ROOT}/dist"
STAMP="$(date +%Y%m%d-%H%M%S)"
PACKAGE_DIR="${OUT_DIR}/file-browser-linux-${STAMP}"

mkdir -p "${PACKAGE_DIR}"

rsync -a \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.ruff_cache' \
  --exclude 'dist' \
  "${PROJECT_ROOT}/" "${PACKAGE_DIR}/"

tar -czf "${OUT_DIR}/file-browser-linux-${STAMP}.tar.gz" -C "${OUT_DIR}" "file-browser-linux-${STAMP}"

echo "Release built: ${OUT_DIR}/file-browser-linux-${STAMP}.tar.gz"
