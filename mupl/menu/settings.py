from dataclasses import dataclass

import readchar
from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

import mupl.menu.selectplaylist
from mupl.ui import Menu, MenuManager, KeyControls, KeyControl, create_selection_prompt, create_input_prompt


@dataclass
class SettingsWidget:
    name: str
    description: str
    value: str


class SettingsMenu(Menu):
    def __init__(self, manager: MenuManager):
        super().__init__(manager, "mupl Settings", KeyControls([
            KeyControl(":up_arrow:/:down_arrow:", "Change Selection"),
            KeyControl("Enter", "Modify"),
        ]))
        self.config = self.manager.mupl.config
        self.selected = 0
        self.modified = False
        self.settings: list[SettingsWidget] = [
            SettingsWidget("Output to File", "Whether to output currently playing song information to a file",
                           str(self.config.output_to_file)),
            SettingsWidget("Output File", "Location of the output file", self.config.output_file),
            SettingsWidget("Output File Format",
                           "Format of the output file (keys: [green]artist[/green], [green]title[/green], [green]albumartist[/green], [green]compartist[/green], [green]track[/green], [green]year[/green]",
                           self.config.output_file_format),
            SettingsWidget("Last Search Directory",
                           "Location of the last directory where songs were searched (probably don't need to edit)",
                           self.config.last_search_dir)
        ]

    def _update_title(self):
        if self.modified:
            self.title = "mupl Settings[red bold]*[/red bold]"
        else:
            self.title = "mupl Settings"

    def _save(self):
        self.config.output_to_file = bool(self.settings[0].value)
        self.config.output_file = self.settings[1].value
        self.config.output_file_format = self.settings[2].value
        self.config.last_search_dir = self.settings[3].value
        self.config.save()
        self.modified = False
        self._update_title()

    def _handle_string_changed(self, result: str | None):
        if result is not None and result != "":
            self.settings[self.selected].value = result
            self.modified = True
        self._update_title()

    def _handle_bool_changed(self, option: int):
        if option == 0:
            self.settings[self.selected].value = "False"
            self.modified = True
        elif option == 1:
            self.settings[self.selected].value = "True"
            self.modified = True
        self._update_title()

    def _handle_unsaved_prompt(self, option: int):
        if option == 1:
            self._save()
        if option == 0 or option == 1:
            self.manager.queue_next_menu(lambda: mupl.menu.selectplaylist.PlaylistSelectionMenu(self.manager))

    def handle_key(self, ch: str):
        if ch == readchar.key.UP:
            self.selected = max(self.selected - 1, 0)
        elif ch == readchar.key.DOWN:
            self.selected = min(self.selected + 1, len(self.settings) - 1)
        elif ch == readchar.key.ENTER:
            if self.selected in (0,):
                self.queue_prompt(create_selection_prompt(self.settings[self.selected].name, ["False", "True"],
                                                          self._handle_bool_changed))
            elif self.selected in (1, 2, 3):
                self.queue_prompt(create_input_prompt(self.settings[self.selected].name, self._handle_string_changed))
        elif ch == "s":
            self._save()
        elif ch == "x":
            if self.modified:
                self.queue_prompt(create_selection_prompt("You have unsaved changes. Do you want to exit anyways?",
                                                          ["Exit without Saving", "Save and Exit"],
                                                          self._handle_unsaved_prompt))
            else:
                self._handle_unsaved_prompt(0)

    def render(self, console: Console, options: ConsoleOptions) -> RenderResult:
        yield Text()
        for i in range(max(self.selected - 1, 0), min(self.selected + (options.max_height // 3), len(self.settings))):
            setting = self.settings[i]
            if i == self.selected:
                yield console.render_str(f"[blue bold]>[/blue bold] [r]{setting.name}[/r]")
            else:
                yield console.render_str(f"[blue bold]>[/blue bold] {setting.name}")
            valuetxt = console.render_str(
                f"[blue bold]Value:[/blue bold] {'[i](nothing)[/i]' if setting.value == '' else setting.value}",
                overflow="ellipsis")
            valuetxt.no_wrap = True
            yield valuetxt
            if i == self.selected:
                yield console.render_str(f"[blue bold]Description:[/blue bold] {setting.description}")
            yield Text()
