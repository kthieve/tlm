#!/usr/bin/env bash
# Reinstall tlm from this working tree so your PATH `tlm` matches the clone.
# Run from the repo: bash scripts/update-from-clone.sh
# Order: pipx (if `tlm` is a pipx app) → ~/.local/share/tlm-venv → ./.venv
set -euo pipefail

NO_PULL=false
for arg in "$@"; do
  case "$arg" in
    --no-pull) NO_PULL=true ;;
    -h | --help)
      echo "usage: bash scripts/update-from-clone.sh [--no-pull]"
      echo "  Updates the active install using this directory (editable install)."
      echo "  Default: git pull --ff-only in the repo, then pip/pipx install -e ."
      exit 0
      ;;
    *)
      echo "error: unknown option: $arg (try --help)" >&2
      exit 2
      ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f "${ROOT}/pyproject.toml" ]]; then
  echo "error: expected pyproject.toml in ${ROOT}" >&2
  exit 1
fi

if [[ "${NO_PULL}" != true ]] && [[ -d "${ROOT}/.git" ]]; then
  echo "git pull --ff-only in ${ROOT}" >&2
  git -C "${ROOT}" pull --ff-only
fi

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

VENV_DIR="${HOME}/.local/share/tlm-venv"
DOT_VENV="${ROOT}/.venv"

if pipx_has_tlm; then
  echo "Updating pipx app tlm from ${ROOT} (editable)…" >&2
  pipx install --editable "${ROOT}" --force
elif [[ -x "${VENV_DIR}/bin/pip" ]]; then
  echo "Updating ${VENV_DIR} from ${ROOT} (editable)…" >&2
  "${VENV_DIR}/bin/pip" install -U pip
  "${VENV_DIR}/bin/pip" install -U --editable "${ROOT}"
elif [[ -x "${DOT_VENV}/bin/pip" ]]; then
  echo "Updating ${DOT_VENV} from ${ROOT} (editable)…" >&2
  "${DOT_VENV}/bin/pip" install -U pip
  "${DOT_VENV}/bin/pip" install -U --editable "${ROOT}"
  echo "If tlm is not on PATH, use: ${DOT_VENV}/bin/tlm or activate the venv." >&2
else
  echo "error: could not find pipx (with tlm), ${VENV_DIR}/bin/pip, or ${DOT_VENV}/bin/pip." >&2
  echo "  pipx:   pipx install --editable \"${ROOT}\" --force" >&2
  echo "  venv:   python3 -m venv .venv && .venv/bin/pip install -U pip && .venv/bin/pip install -e ." >&2
  exit 1
fi

if command -v tlm >/dev/null 2>&1; then
  tlm --version
else
  echo "tlm not on PATH; open a new shell or add ~/.local/bin to PATH." >&2
fi
