#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="powerscope-daemon"
SERVICE_TEMPLATE="deploy/systemd/powerscope-daemon.service"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
USER_NAME="${SUDO_USER:-$USER}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo ./scripts/linux/install-daemon.sh" >&2
  exit 1
fi

if [[ ! -f "${ROOT_DIR}/${SERVICE_TEMPLATE}" ]]; then
  echo "Service template not found: ${ROOT_DIR}/${SERVICE_TEMPLATE}" >&2
  exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl not found. This script requires a systemd-based Linux environment." >&2
  exit 1
fi

if [[ "$(ps -p 1 -o comm=)" != "systemd" ]]; then
  cat >&2 <<'EOF'
PID 1 is not systemd.
Run this installer on a Linux environment where systemd is PID 1.
EOF
  exit 1
fi

VENV_DIR="${ROOT_DIR}/.venv"
if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  cat >&2 <<EOF
Python virtualenv missing at ${VENV_DIR}.
Create it first as ${USER_NAME}:
  cd ${ROOT_DIR}
  python3 -m venv .venv
  . .venv/bin/activate
  pip install -e .
EOF
  exit 1
fi

sed "s/%i/${USER_NAME}/g; s#%r#${ROOT_DIR}#g" "${ROOT_DIR}/${SERVICE_TEMPLATE}" > "${SERVICE_FILE}"

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

echo "Installed and started ${SERVICE_NAME}"
systemctl --no-pager --full status "${SERVICE_NAME}" | sed -n '1,20p'

echo
echo "Useful commands:"
echo "  sudo systemctl restart ${SERVICE_NAME}"
echo "  systemctl status ${SERVICE_NAME}"
echo "  journalctl -u ${SERVICE_NAME} -f"
