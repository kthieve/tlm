#!/usr/bin/env bash
# Install tlm from this local clone (no GitHub fetch).
# Usage: bash scripts/install.sh
# If tlm is already installed, this performs an in-place update.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="${HOME}/.local/bin"
VENV_DIR="${HOME}/.local/share/tlm-venv"

if [[ ! -f "${ROOT}/pyproject.toml" ]]; then
  echo "error: expected pyproject.toml in ${ROOT}" >&2
  exit 1
fi

ensure_path_hint() {
  case ":${PATH}:" in
    *":${BIN_DIR}:"*) return 0 ;;
  esac
  echo "Add to PATH: export PATH=\"${BIN_DIR}:\$PATH\"" >&2
}

pipx_has_tlm() {
  command -v pipx >/dev/null 2>&1 || return 1
  local line
  while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in
      tlm\ *) return 0 ;;
    esac
  done < <(pipx list --short 2>/dev/null || true)
  return 1
}

if pipx_has_tlm; then
  echo "Updating pipx app tlm from local clone: ${ROOT}" >&2
  pipx install --editable "${ROOT}" --force
  ensure_path_hint
elif command -v pipx >/dev/null 2>&1; then
  echo "Installing tlm with pipx from local clone: ${ROOT}" >&2
  pipx install --editable "${ROOT}" --force
  ensure_path_hint
else
  if ! command -v python3 >/dev/null 2>&1; then
    echo "error: need python3.11+ (or install pipx)." >&2
    exit 1
  fi

  mkdir -p "$(dirname "${VENV_DIR}")" "${BIN_DIR}"
  if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    python3 -m venv "${VENV_DIR}"
  fi

  "${VENV_DIR}/bin/pip" install -U pip
  "${VENV_DIR}/bin/pip" install -U --editable "${ROOT}"
  ln -sf "${VENV_DIR}/bin/tlm" "${BIN_DIR}/tlm"
  echo "Installed/updated tlm from local clone into ${VENV_DIR}" >&2
  ensure_path_hint
fi

if command -v tlm >/dev/null 2>&1; then
  tlm --version
else
  echo "tlm not on PATH yet; open a new shell or add ${BIN_DIR} to PATH." >&2
fi
