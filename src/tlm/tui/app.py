from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Button, ContentSwitcher

from tlm.settings import load_settings, save_settings
from tlm.safety.permissions import load_permissions_file, save_permissions_file
from tlm.tui.settings import SettingsView
from tlm.tui.permissions import PermissionsView


class TlmConfigApp(App):
    CSS = """
    Screen {
        layout: horizontal;
    }
    #sidebar {
        width: 25;
        background: $panel;
        border-right: tall $primary;
        padding: 1;
    }
    #content {
        width: 1fr;
        padding: 1;
    }
    .section-title {
        background: $accent;
        color: $text;
        padding: 1;
        margin-bottom: 1;
        text-style: bold;
    }
    .field {
        margin: 1 0;
    }
    .label {
        width: 20;
    }
    Button {
        width: 100%;
        margin-bottom: 1;
    }
    """
    TITLE = "tlm Configuration"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.settings = load_settings()
        self.perms = load_permissions_file()

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Button("Settings", id="btn_settings")
                yield Button("Permissions", id="btn_permissions")
                yield Static(expand=True)
                yield Button("Save & Exit", id="btn_save", variant="success")
                yield Button("Cancel", id="btn_cancel", variant="error")
            with ContentSwitcher(id="content", initial="settings"):
                yield SettingsView(self.settings, id="settings")
                yield PermissionsView(self.perms, id="permissions")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_settings":
            self.query_one("#content").current = "settings"
        elif event.button.id == "btn_permissions":
            self.query_one("#content").current = "permissions"
        elif event.button.id == "btn_save":
            self.save_all()
            self.exit(0)
        elif event.button.id == "btn_cancel":
            self.exit(1)

    def save_all(self) -> None:
        settings_view = self.query_one("#settings", SettingsView)
        settings_view.apply_settings()
        save_settings(self.settings)
        save_permissions_file(self.perms)


def run_tui_app() -> int:
    app = TlmConfigApp()
    return app.run()
