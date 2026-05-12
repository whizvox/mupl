from dataclasses import dataclass
from typing import Callable, Optional, Any

import readchar
import wcwidth
from rich.console import Console, ConsoleOptions, RenderResult
from rich.control import Control
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from mupl.context import MuplContext


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
    action: Callable[[Any], None] | None
    reading_input: bool
    options: list[str] | None
    _buffer: str = ""
    _selected: int = 0

    def update_buffer(self, ch: str) -> tuple[bool, str | None]:
        if ch.isprintable():
            self._buffer += ch
        elif ch == readchar.key.BACKSPACE:
            if len(self._buffer) > 0:
                self._buffer = self._buffer[:-2]
        elif ch == readchar.key.ENTER:
            return True, self._buffer
        elif ch == readchar.key.ESC:
            return True, None
        return False, None

    def update_selection(self, ch: str) -> tuple[bool, int]:
        if ch == readchar.key.LEFT:
            if self._selected <= 0:
                self._selected = len(self.options) - 1
            else:
                self._selected -= 1
        elif ch == readchar.key.RIGHT:
            if self._selected >= len(self.options) - 1:
                self._selected = 0
            else:
                self._selected += 1
        elif ch == readchar.key.ENTER:
            return True, self._selected
        elif ch == readchar.key.ESC:
            return True, -1
        return False, -1

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        yield Control.move_to(0, options.max_height // 2 - (3 if self.reading_input else 4))
        if self.reading_input:
            txt = console.render_str(f"{self.message}\n?> {self._buffer}[r] [/r]")
        elif self.options is not None:
            txt = console.render_str(f"{self.message}\n")
            optionstxt = ""
            for i, option in enumerate(self.options):
                if i > 0:
                    optionstxt += " "
                if i == self._selected:
                    optionstxt += f"[r]\\[{option}][/r]"
                else:
                    optionstxt += f"\\[{option}]"
            txt.append(console.render_str(optionstxt))
        else:
            txt = console.render_str(f"{self.message}\n\n[i]Press any key to continue[/i]")
        yield Panel(txt, title=self.title, title_align="center", padding=1, expand=False)


def create_input_prompt(message: str, action: Callable[[str | None], None], title: str = "Input"):
    return Prompt(title, message, action, True, None)


def create_alert_prompt(message: str, title: str = "Alert"):
    return Prompt(title, message, None, False, None)


def create_selection_prompt(message: str, options: list[str], action: Callable[[int], None], can_cancel=True,
                            title="Select"):
    _options = options.copy()
    _action = action
    if can_cancel:
        _options.insert(0, "Cancel")

        def __action(option: int):
            if option == -1:
                action(-1)
            else:
                action(option - 1)

        _action = __action
    return Prompt(title, message, _action, False, _options)


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
        if self._menu is None:
            raise RuntimeError("Attempted to run menu manager without setting a menu first")
        mupl_console = Console(highlight=False)
        with Live(self._menu, console=mupl_console, vertical_overflow="visible") as live:
            while not self._shutdown:
                prompt = self._menu.prompt
                if prompt is not None:
                    ch = readchar.readkey()
                    if prompt.reading_input:
                        done, res = prompt.update_buffer(ch)
                        if done:
                            self._menu.remove_prompt()
                            if prompt.action is not None:
                                prompt.action(res)
                    elif prompt.options is not None:
                        done, res = prompt.update_selection(ch)
                        if done:
                            self._menu.remove_prompt()
                            if prompt.action is not None:
                                prompt.action(res)
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
