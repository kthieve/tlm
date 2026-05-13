from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Static, DataTable, Button
from tlm.safety.permissions import PermissionsFile


class PermissionsView(Static):
    def __init__(self, perms: PermissionsFile, **kwargs):
        super().__init__(**kwargs)
        self.perms = perms

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Access Permissions (Global)", classes="section-title")
            yield DataTable(id="perms_table")
            with Horizontal():
                yield Button("Add Path", id="btn_add_path")
                yield Button("Remove Selected", id="btn_remove_path", variant="error")

    def on_mount(self) -> None:
        table = self.query_one("#perms_table", DataTable)
        table.add_columns("Type", "Path/Pattern")
        self.refresh_table()

    def refresh_table(self) -> None:
        table = self.query_one("#perms_table", DataTable)
        table.clear()
        for p in self.perms.allow_paths:
            table.add_row("Allow (RW)", p)
        for p in self.perms.read_paths:
            table.add_row("Read (RO)", p)
        for p in self.perms.deny_paths:
            table.add_row("Deny", p)
        for p in self.perms.escape_grants:
            table.add_row("Escape Grant", p)

    # TODO: Implement on_button_pressed to handle add/remove with modals
    # For now, this is a visual upgrade.
    # Adding modals in Textual requires push_screen.
