#!/usr/bin/env python3
"""
Helper script to update tlm version across all relevant files.
Usage: python scripts/bump_version.py <version>
"""

import sys
import re
from pathlib import Path

def bump_version(new_version: str):
    root = Path(__file__).parent.parent
    
    # 1. VERSION (Dev line)
    v_path = root / "VERSION"
    if v_path.is_file():
        text = v_path.read_text(encoding="utf-8")
        # Matches "Dev  0.2.0.dev8" -> "Dev  <new_version>"
        new_text = re.sub(r"(Dev\s+)\S+", rf"\g<1>{new_version}", text)
        v_path.write_text(new_text, encoding="utf-8")
        print(f"Updated VERSION (Dev line) -> {new_version}")

    # 2. pyproject.toml
    pyp_path = root / "pyproject.toml"
    if pyp_path.is_file():
        text = pyp_path.read_text(encoding="utf-8")
        # Matches 'version = "0.2.0.dev8"' -> 'version = "<new_version>"'
        new_text = re.sub(r'(version\s*=\s*")\S+(")', rf"\g<1>{new_version}\g<2>", text)
        pyp_path.write_text(new_text, encoding="utf-8")
        print(f"Updated pyproject.toml -> {new_version}")

    # 3. requirements.txt (comment)
    req_path = root / "requirements.txt"
    if req_path.is_file():
        text = req_path.read_text(encoding="utf-8")
        # Matches "(0.2.0.dev8 dev train" -> "(<new_version> dev train"
        new_text = re.sub(r"(\()\S+(\s+dev train)", rf"\g<1>{new_version}\g<2>", text)
        req_path.write_text(new_text, encoding="utf-8")
        print(f"Updated requirements.txt comment -> {new_version}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/bump_version.py <version>")
        sys.exit(1)
    
    bump_version(sys.argv[1])
