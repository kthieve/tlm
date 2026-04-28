"""Rough USD per 1K tokens (input, output). Unknown models -> (None, None)."""

from __future__ import annotations

# Values are approximate; override via PR when pricing changes.
# DeepSeek: https://api-docs.deepseek.com/quick_start/pricing/ (per 1M in docs → /1000 here)
TABLE: dict[str, tuple[float | None, float | None]] = {
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.0025, 0.01),
    "deepseek-chat": (0.00014, 0.00028),  # legacy; maps to v4-flash non-thinking
    "deepseek-reasoner": (0.00014, 0.00028),  # legacy; maps to v4-flash thinking
    "deepseek-v4-flash": (0.00014, 0.00028),
    "deepseek-v4-pro": (0.00174, 0.00348),  # list price; promos may differ
    "openai/gpt-4o-mini": (0.00015, 0.0006),
}


def estimate_cost_usd(model: str, in_tokens: int, out_tokens: int) -> float | None:
    key = model.split("/")[-1]
    row = TABLE.get(model) or TABLE.get(key)
    if not row or row[0] is None or row[1] is None:
        return None
    pin, pout = row
    return (in_tokens / 1000.0) * pin + (out_tokens / 1000.0) * pout
