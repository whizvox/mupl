from typing import Callable

import wcwidth
from rich.console import Console, ConsoleOptions, RenderResult, Group
from rich.control import Control
from rich.text import Text


class KeyControl:
    def __init__(self, key_name: str, description: str, key: str | None=None, action: Callable[[], None] | None=None):
        self.key_name = key_name
        self.description = description
        self.key = key
        self.action = action

    def get_markdown(self):
        return f"[green bold]\\[{self.key_name}][/green bold] {self.description}"


class KeyControls:
    def __init__(self, controls: list[KeyControl]):
        self.controls = controls

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        if len(self.controls) == 0:
            return []
        lines = []
        curr_line = Text()
        for control in self.controls:
            control_text = console.render_str(control.get_markdown())
            new_line = curr_line.copy()
            if len(curr_line) != 0:
                new_line.append(", ")
            new_line.append_text(control_text)
            if wcwidth.width(str(new_line)) > options.max_width:
                if len(curr_line) == 0:
                    new_line.no_wrap = True
                    new_line.overflow = "ellipsis"
                    lines.append(new_line)
                else:
                    lines.append(curr_line.copy().append(" " * (options.max_width - len(curr_line))))
                    curr_line = control_text.copy()
            else:
                curr_line = new_line
        lines.append(curr_line)
        lines[-1].end = ""
        lines.insert(0, Control.move_to(0, options.max_height - len(lines)))
        lines.append(Control.show_cursor(False))
        return lines
