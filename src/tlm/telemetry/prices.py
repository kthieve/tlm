"""Rough USD per 1K tokens (input, output). Unknown models -> (None, None)."""

from __future__ import annotations

# Values are approximate; override via PR when pricing changes.
# DeepSeek: https://api-docs.deepseek.com/quick_start/pricing/ (per 1M in docs → /1000 here)
TABLE: dict[str, tuple[float | None, float | None]] = {
    # OpenAI
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.0025, 0.01),
    "gpt-4-turbo": (0.01, 0.03),
    "gpt-3.5-turbo": (0.0005, 0.0015),
    "o1": (0.015, 0.06),
    "o1-mini": (0.0011, 0.0044),
    "o1-preview": (0.015, 0.06),
    "o3-mini": (0.0011, 0.0044),
    
    # DeepSeek
    "deepseek-chat": (0.00014, 0.00028),
    "deepseek-reasoner": (0.00014, 0.00028),
    "deepseek-v4-flash": (0.00014, 0.00028),
    "deepseek-v4-pro": (0.00174, 0.00348),
    
    # Anthropic (commonly used via OpenAI-compatible proxies/routers)
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-5-haiku": (0.00025, 0.00125),
    "claude-3-opus": (0.015, 0.075),
    
    # Prefixed variants
    "openai/gpt-4o-mini": (0.00015, 0.0006),
    "openai/gpt-4o": (0.0025, 0.01),
    "anthropic/claude-3-5-sonnet": (0.003, 0.015),
}


def estimate_cost_usd(model: str, in_tokens: int, out_tokens: int) -> float | None:
    key = model.split("/")[-1]
    row = TABLE.get(model) or TABLE.get(key)
    if not row or row[0] is None or row[1] is None:
        return None
    pin, pout = row
    return (in_tokens / 1000.0) * pin + (out_tokens / 1000.0) * pout
