#!/usr/bin/env bash
# Build a self-contained zipapp (requires shiv: pip install shiv).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p dist
python -m pip install -q shiv
python -m shiv -c tlm -o dist/tlm.pyz -p "/usr/bin/env python3" .
