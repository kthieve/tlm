from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Input, Label, Select, Checkbox, Static
from tlm.settings import UserSettings
from tlm.providers.registry import REAL_PROVIDER_IDS


class SettingsView(Static):
    def __init__(self, settings: UserSettings, **kwargs):
        super().__init__(**kwargs)
        self.settings = settings

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Main Settings", classes="section-title")

            with Horizontal(classes="field"):
                yield Label("Provider: ", classes="label")
                yield Select(
                    [(p, p) for p in ["stub"] + list(REAL_PROVIDER_IDS)],
                    value=self.settings.provider or "openrouter",
                    id="set_provider",
                )

            with Horizontal(classes="field"):
                yield Label("Default Model: ", classes="label")
                yield Input(value=self.settings.model or "", placeholder="model-id", id="set_model")

            with Horizontal(classes="field"):
                yield Label("Temperature: ", classes="label")
                yield Input(value=str(self.settings.temperature), id="set_temp")

            with Horizontal(classes="field"):
                yield Label("Timeout (s): ", classes="label")
                yield Input(value=str(self.settings.timeout), id="set_timeout")

            with Horizontal(classes="field"):
                yield Label("Safety Profile: ", classes="label")
                yield Select(
                    [
                        ("strict", "strict"),
                        ("standard", "standard"),
                        ("trusted", "trusted"),
                        ("sandbox", "sandbox"),
                    ],
                    value=self.settings.safety_profile,
                    id="set_safety",
                )

            yield Label("Memory", classes="section-title")
            yield Checkbox(
                "Enable Memory", value=self.settings.memory_enabled, id="set_mem_enabled"
            )

            # API Keys section (simplified for now)
            yield Label("API Keys (Current Provider)", classes="section-title")
            current_provider = self.settings.provider or "openrouter"
            current_key = self.settings.api_keys.get(current_provider, "")
            yield Input(
                value=current_key,
                placeholder=f"API Key for {current_provider}",
                password=True,
                id="set_api_key",
            )

    def apply_settings(self) -> None:
        self.settings.provider = self.query_one("#set_provider", Select).value
        self.settings.model = self.query_one("#set_model", Input).value or None
        try:
            self.settings.temperature = float(self.query_one("#set_temp", Input).value)
        except ValueError:
            pass
        try:
            self.settings.timeout = float(self.query_one("#set_timeout", Input).value)
        except ValueError:
            pass
        self.settings.safety_profile = self.query_one("#set_safety", Select).value
        self.settings.memory_enabled = self.query_one("#set_mem_enabled", Checkbox).value

        # Save key for current provider
        key = self.query_one("#set_api_key", Input).value
        if key:
            self.settings.api_keys[self.settings.provider] = key
        else:
            self.settings.api_keys.pop(self.settings.provider, None)
