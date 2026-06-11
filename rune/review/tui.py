from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static


class ReviewApp(App):
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("j", "next", "Next"),
        ("k", "prev", "Prev"),
        ("space", "toggle_select", "Select"),
        ("a", "apply", "Apply"),
        ("p", "preview", "Preview"),
        ("d", "dismiss", "Dismiss"),
        ("c", "clear_sel", "Clear"),
        ("o", "open_editor", "Editor"),
        ("r", "rescan", "Rescan"),
        ("slash", "filter", "Filter"),
        ("question_mark", "help", "Help"),
        ("g,g", "goto_first", "First"),
        ("G", "goto_last", "Last"),
    ]

    def __init__(self, findings: list):
        super().__init__()
        self.findings = findings

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"{len(self.findings)} findings", id="body")
        yield Footer()

    def action_quit(self):
        self.exit()
