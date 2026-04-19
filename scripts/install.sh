#!/usr/bin/env bash
# Install tlm via pipx, or fall back to a user venv under ~/.local/share/tlm-venv.
# Usage: curl -fsSL URL/install.sh | bash -s -- [VERSION]
# Prefer downloading the script and: bash install.sh 0.2.0b1
# (Do not pipe curl to sh unchecked; verify SHA256 from the release page when possible.)
set -euo pipefail

VERSION="${1:-0.2.0b1}"
BIN_DIR="${HOME}/.local/bin"
VENV_DIR="${HOME}/.local/share/tlm-venv"

ensure_path_hint() {
  case ":${PATH}:" in
    *":${BIN_DIR}:"*) return 0 ;;
  esac
  echo "Add to PATH: export PATH=\"${BIN_DIR}:\$PATH\"" >&2
}

if command -v pipx >/dev/null 2>&1; then
  pipx install "tlm==${VERSION}" --force
  echo "Installed tlm ${VERSION} with pipx."
  ensure_path_hint
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 and pipx not found; install python3.11+ or pipx." >&2
  exit 1
fi

mkdir -p "$(dirname "${VENV_DIR}")" "${BIN_DIR}"
python3 -m venv "${VENV_DIR}"
# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"
python -m pip install -U pip
python -m pip install "tlm==${VERSION}"
ln -sf "${VENV_DIR}/bin/tlm" "${BIN_DIR}/tlm"
echo "Installed tlm ${VERSION} to ${VENV_DIR}; symlink ${BIN_DIR}/tlm"
ensure_path_hint
