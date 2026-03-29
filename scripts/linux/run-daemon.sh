#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing .venv/bin/python. Create venv and install package first." >&2
  exit 1
fi

DAEMON_HOST="${DAEMON_HOST:-127.0.0.1}"
DAEMON_PORT="${DAEMON_PORT:-8765}"

exec ./.venv/bin/python -m host.daemon --host "${DAEMON_HOST}" --port "${DAEMON_PORT}" "$@"
