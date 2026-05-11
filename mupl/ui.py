from dataclasses import dataclass
from typing import Callable, Optional

import readchar
import wcwidth
from rich.console import Console, ConsoleOptions, RenderResult
from rich.control import Control
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from mupl.muplold import MuplContext


class KeyControl:
    def __init__(self, key_name: str, description: str, key: str | None = None,
                 action: Callable[[], None] | None = None):
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


@dataclass
class Prompt:
    title: str | None
    message: str
    action: Callable[[str | None], None] | None
    reading_input: bool
    buffer: str = ""

    def update_buffer(self, ch: str) -> bool:
        if ch.isprintable():
            self.buffer += ch
        elif ch == readchar.key.BACKSPACE:
            if len(self.buffer) > 0:
                self.buffer = self.buffer[:-2]
        elif ch == readchar.key.ENTER:
            if self.action is not None:
                self.action(self.buffer)
            return True
        elif ch == readchar.key.ESC:
            if self.action is not None:
                self.action(None)
            return True
        return False

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        yield Control.move_to(0, options.max_height // 2 - (3 if self.reading_input else 4))
        if self.reading_input:
            txt = console.render_str(f"{self.message}\n?> {self.buffer}[r] [/r]")
        else:
            txt = console.render_str(f"{self.message}\n\n[i]Press any key to continue[/i]")
        yield Panel(txt, title=self.title, title_align="center", padding=1, expand=False)


def create_input_prompt(message: str, action: Callable[[str], None], title: str = "Input"):
    return Prompt(title, message, action, True)


def create_alert_prompt(message: str, title: str = "Alert"):
    return Prompt(title, message, None, False)


class Menu:
    manager: MenuManager
    title: str
    show_controls: bool
    _controls: KeyControls | None
    _no_controls: KeyControls | None
    prompts: list[Prompt]
    prompt: Prompt | None

    def __init__(self, manager: MenuManager, title: str, controls: Optional[KeyControls] = None,
                 show_controls: bool = False, add_default_controls: bool = True):
        self.manager = manager
        self.title = title
        self._controls = controls
        if controls is not None and add_default_controls:
            self._controls.controls.append(KeyControl("x", "Exit"))
            self._controls.controls.append(KeyControl("c", "Hide Controls"))
            self._no_controls = KeyControls([
                KeyControl("c", "Show Controls")
            ])
        else:
            self._no_controls = None
        self.show_controls = show_controls
        self.prompts = []
        self.prompt = None

    def queue_prompt(self, prompt: Prompt | None):
        if self.prompt is None:
            self.prompt = prompt
        else:
            self.prompts.append(prompt)

    def remove_prompt(self):
        if len(self.prompts) > 0:
            self.prompt = self.prompts.pop(0)
        else:
            self.prompt = None

    def has_controls(self):
        return self._controls is not None

    def handle_key(self, ch: str):
        pass

    def render(self, console: Console, options: ConsoleOptions) -> RenderResult:
        pass

    def on_destroy(self):
        pass

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        yield Control.clear()
        yield Control.move_to(0, 0)
        yield Control.show_cursor(False)
        yield console.render_str(f"[blue bold]~~~ [/blue bold]{self.title} [blue bold]~~~[/blue bold]",
                                 justify="center")
        yield from self.render(console, options)
        if self.has_controls():
            if self.show_controls:
                yield self._controls
            else:
                yield self._no_controls
        if self.prompt is not None:
            yield self.prompt


class MenuManager:
    _menu: Menu | None = None
    _next_menu: Callable[[], Menu] | None = None
    _shutdown: bool = False
    mupl: MuplContext

    def __init__(self, mupl: MuplContext):
        self.mupl = mupl

    def shutdown(self):
        self._shutdown = True

    def queue_next_menu(self, menu: Callable[[], Menu]):
        if self._menu is None:
            self._menu = menu()
        else:
            self._next_menu = menu

    def run(self):
        mupl_console = Console(highlight=False)
        with Live(self._menu, console=mupl_console, vertical_overflow="visible") as live:
            while not self._shutdown:
                if self._menu.prompt is not None:
                    ch = readchar.readkey()
                    if self._menu.prompt.reading_input:
                        if self._menu.prompt.update_buffer(ch):
                            self._menu.remove_prompt()
                    else:
                        self._menu.remove_prompt()
                else:
                    ch = readchar.readkey()
                    self._menu.handle_key(ch)
                    if self._menu.has_controls() and ch == "c":
                        self._menu.show_controls = not self._menu.show_controls
                if self._next_menu is not None:
                    self._menu.on_destroy()
                    self._menu = self._next_menu()
                    self._next_menu = None
                live.update(self._menu, refresh=True)
        if self._menu is not None:
            self._menu.on_destroy()
