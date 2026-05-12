from dataclasses import dataclass
from typing import Any

import readchar
from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

import mupl.menu.selectplaylist
from mupl.config import Configuration
from mupl.ui import Menu, MenuManager, KeyControls, KeyControl, create_selection_prompt, create_input_prompt


class ConfigItem:
    name: str
    description: str
    value: Any
    display_value: str
    _config: Configuration
    _config_attr: str

    def __init__(self, name: str, description: str, config: Configuration, attr: str):
        if not hasattr(config, attr):
            raise RuntimeError(f"Cannot create setting widget, configuration does not have attribute: {attr}")
        self._config = config
        self._config_attr = attr
        self.name = name
        self.description = description
        self.value = self._get_config_value()
        self.display_value = str(self.value)

    def _get_config_value(self):
        return getattr(self._config, self._config_attr)

    def _on_update(self, menu: SettingsMenu, new_value: Any):
        if new_value is not None:
            self.value = new_value
            self.display_value = str(new_value)
            menu.modified = True
            menu.update_title()

    def sync_with_config(self):
        setattr(self._config, self._config_attr, self.value)

    def on_want_modify(self, menu: Menu):
        raise NotImplementedError()


@dataclass
class StringItem(ConfigItem):
    def __init__(self, name: str, description: str, config: Configuration, attr: str):
        super().__init__(name, description, config, attr)

    def on_want_modify(self, menu: SettingsMenu):
        def __on_update(new_value: str):
            self._on_update(menu, new_value)

        menu.queue_prompt(create_input_prompt(self.name, __on_update))


@dataclass
class BooleanItem(ConfigItem):
    def __init__(self, name: str, description: str, config: Configuration, attr: str):
        super().__init__(name, description, config, attr)

    def _on_update_bool(self, menu: SettingsMenu, new_value: int):
        if new_value == 0:
            self._on_update(menu, False)
        elif new_value == 1:
            self._on_update(menu, True)

    def on_want_modify(self, menu: SettingsMenu):
        def __on_update(new_value: int):
            self._on_update_bool(menu, new_value)

        menu.queue_prompt(create_selection_prompt(self.name, ["False", "True"], __on_update))


class SettingsMenu(Menu):
    def __init__(self, manager: MenuManager):
        super().__init__(manager, "mupl Settings", KeyControls([
            KeyControl(":up_arrow:/:down_arrow:", "Change Selection"),
            KeyControl("Enter", "Modify"),
        ]))
        self.config = self.manager.mupl.config
        self.selected = 0
        self.modified = False
        self.settings: list[ConfigItem] = [
            BooleanItem("Output to File", "Whether to output currently playing song information to a file", self.config,
                        "output_to_file"),
            StringItem("Output File", "Location of the output file", self.config, "output_file"),
            StringItem("Output File Format",
                       "Format of the output file (keys: [green]artist[/green], [green]title[/green], [green]albumartist[/green], [green]compartist[/green], [green]track[/green], [green]year[/green]",
                       self.config, "output_file_format"),
            StringItem("Last Search Directory",
                       "Location of the last directory where songs were searched (probably don't need to edit)",
                       self.config, "last_search_dir")
        ]

    def update_title(self):
        if self.modified:
            self.title = "mupl Settings[red bold]*[/red bold]"
        else:
            self.title = "mupl Settings"

    def _save(self):
        for item in self.settings:
            item.sync_with_config()
        self.config.save()
        self.modified = False
        self.update_title()

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
            self.settings[self.selected].on_want_modify(self)
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
                f"[blue bold]Value:[/blue bold] {'[i](nothing)[/i]' if setting.display_value == '' else setting.display_value}",
                overflow="ellipsis")
            valuetxt.no_wrap = True
            yield valuetxt
            if i == self.selected:
                yield console.render_str(f"[blue bold]Description:[/blue bold] {setting.description}")
            yield Text()
