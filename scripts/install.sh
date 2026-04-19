#!/usr/bin/env bash
# Install tlm from GitHub (PyPI not used until published).
# Usage: TLM_GITHUB_REPO=owner/repo bash scripts/install.sh [VERSION]
# Default VERSION=0.2.0b2; git ref is v$VERSION (override with TLM_GIT_REF).
# Prefer downloading the script from a release, verify checksum, then run.
set -euo pipefail

VERSION="${1:-0.2.0b2}"
REPO="${TLM_GITHUB_REPO:-}"
GIT_REF="${TLM_GIT_REF:-v${VERSION}}"
BIN_DIR="${HOME}/.local/bin"
VENV_DIR="${HOME}/.local/share/tlm-venv"
GIT_URL="${TLM_GIT_URL:-}"

if [[ -z "$REPO" && -z "$GIT_URL" ]]; then
  echo "error: set TLM_GITHUB_REPO=owner/repo (GitHub slug) or TLM_GIT_URL to a full git URL." >&2
  echo "  example: TLM_GITHUB_REPO=myorg/tlm bash scripts/install.sh ${VERSION}" >&2
  exit 1
fi

if [[ -z "$GIT_URL" ]]; then
  GIT_URL="git+https://github.com/${REPO}.git@${GIT_REF}"
fi

ensure_path_hint() {
  case ":${PATH}:" in
    *":${BIN_DIR}:"*) return 0 ;;
  esac
  echo "Add to PATH: export PATH=\"${BIN_DIR}:\$PATH\"" >&2
}

if command -v pipx >/dev/null 2>&1; then
  pipx install "${GIT_URL}" --force
  echo "Installed tlm from ${GIT_URL} with pipx."
  ensure_path_hint
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: need python3.11+ and pipx (or python3 for venv fallback)." >&2
  exit 1
fi

mkdir -p "$(dirname "${VENV_DIR}")" "${BIN_DIR}"
python3 -m venv "${VENV_DIR}"
# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"
python -m pip install -U pip
python -m pip install "${GIT_URL}"
ln -sf "${VENV_DIR}/bin/tlm" "${BIN_DIR}/tlm"
echo "Installed from ${GIT_URL} to ${VENV_DIR}; symlink ${BIN_DIR}/tlm"
ensure_path_hint
