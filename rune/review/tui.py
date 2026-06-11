from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, ListView, ListItem, Label
from textual.containers import Horizontal


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
        self.cursor = 0
        self.selected: set[int] = set()

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            self._list = ListView(*[ListItem(Label(self._label(i))) for i in range(len(self.findings))])
            yield self._list
            self._detail = Static("", id="detail")
            yield self._detail
        yield Footer()

    def _label(self, i: int) -> str:
        mark = "[x]" if i in self.selected else "[ ]"
        return f"{mark} finding {i+1}"

    def action_next(self):
        if self.cursor < len(self.findings) - 1:
            self.cursor += 1
            self._refresh()

    def action_prev(self):
        if self.cursor > 0:
            self.cursor -= 1
            self._refresh()

    def action_toggle_select(self):
        if self.cursor in self.selected:
            self.selected.discard(self.cursor)
        else:
            self.selected.add(self.cursor)
        self._refresh()

    def action_clear_sel(self):
        self.selected.clear()
        self._refresh()

    def action_quit(self):
        self.exit()

    def _refresh(self):
        for i, item in enumerate(self._list.children):
            item.children[0].update(self._label(i))
