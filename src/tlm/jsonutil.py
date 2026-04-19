"""Extract a JSON object from LLM output (fences or raw)."""

from __future__ import annotations

import json
import re


def extract_json_object(text: str) -> dict:
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I)
        s = re.sub(r"\s*```$", "", s)
    s = s.strip()
    if not s.startswith("{"):
        i = s.find("{")
        j = s.rfind("}")
        if i == -1 or j == -1 or j <= i:
            raise ValueError("no JSON object found in model output")
        s = s[i : j + 1]
    return json.loads(s)
