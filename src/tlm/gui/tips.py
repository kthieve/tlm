"""Shared guidance strings and tips for the installer and onboarding wizard."""

from __future__ import annotations

# Provider cost guidance (from prices.py data)
BUDGET_PICKS = [
    (
        "DeepSeek",
        "deepseek",
        "deepseek-v4-flash",
        "~$0.14 / million tokens input",
        "Fastest, great quality",
    ),
    (
        "OpenRouter",
        "openrouter",
        "openai/gpt-4o-mini",
        "~$0.15 / million tokens input",
        "Reliable, good default",
    ),
    (
        "DeepSeek",
        "deepseek",
        "deepseek-chat",
        "~$0.14 / million tokens input",
        "Solid general use",
    ),
]

DAILY_COST_ESTIMATE = "Typical daily use costs $0.01–$0.10/day."

# Provider signup URLs
PROVIDER_SIGNUP_URLS = {
    "openrouter": "https://openrouter.ai/keys",
    "deepseek": "https://platform.deepseek.com/api_keys",
    "openai": "https://platform.openai.com/api-keys",
    "chutes": "https://chutes.ai",
    "nano-gpt": "https://nano-gpt.com/api",
}

# Feature explanations
FEATURE_TIPS = {
    "memory": (
        "Memory lets tlm remember facts across sessions.\n"
        "Example: 'I use Arch Linux with KDE' will persist.\n"
        "Safe — secrets and API keys are never stored."
    ),
    "web": (
        "Web tools let the model search DuckDuckGo and fetch\n"
        "web pages to answer your questions with current info.\n"
        "Requires the free Lightpanda headless browser.\n"
        "You can install it now or later via `tlm gui`."
    ),
    "updates": (
        "Once per day, tlm prints one line to stderr if a newer\n"
        "GitHub release exists. Nothing is auto-installed —\n"
        "you decide when to run `tlm update --yes` yourself."
    ),
    "safety_profiles": {
        "strict": "Blocks most system writes. Best for shared machines.",
        "standard": "Balanced guardrails. Recommended for most users.",
        "trusted": "Fewer restrictions. For experienced users.",
        "sandbox": "Runs commands inside bwrap/firejail isolation.",
    },
}

# Post-install quick-start commands
QUICKSTART_COMMANDS = [
    ("Ask a question", "tlm how do I check disk usage"),
    ("Write a script", "tlm write a bash script to clean apt cache"),
    ("Run a command", "tlm do what is my cpu temperature"),
]

USEFUL_COMMANDS = [
    ("tlm config", "Change settings in the terminal"),
    ("tlm gui", "Open the graphical settings panel"),
    ("tlm sessions", "Browse your chat history"),
    ("tlm providers", "See configured providers & API key status"),
    ("tlm update", "Check for and install updates"),
    ("tlm help", "Full command reference"),
    ("tlm completion bash", "Generate shell completions"),
]
