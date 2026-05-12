from math import ceil

import readchar
from rich.console import Console, ConsoleOptions
from rich.text import Text

import mupl.menu.editplaylist
import mupl.menu.player
import mupl.menu.settings
from mupl.playlist import BasicPlaylist, Playlist
from mupl.ui import KeyControls, KeyControl, Menu, MenuManager


class PlaylistSelectionMenu(Menu):
    def __init__(self, manager: MenuManager):
        super().__init__(manager, "Select a Playlist", KeyControls([
            KeyControl(":up_arrow:/:down_arrow:", "Change Selection"),
            KeyControl("e", "Edit"),
            KeyControl("n", "Create New"),
            KeyControl("s", "Open Settings Menu")
        ]))
        self.selected = 0
        self.page = 0
        self.playlists: list[BasicPlaylist] = list(map(lambda x: x[1], manager.mupl.playlists.items()))
        self.page_size = 10

    def handle_key(self, ch: str):
        if ch == readchar.key.LEFT:
            self.change_page(-1)
        elif ch == readchar.key.RIGHT:
            self.change_page(1)
        elif ch == readchar.key.UP:
            self.change_selection(-1)
        elif ch == readchar.key.DOWN:
            self.change_selection(1)
        elif ch == "e":
            self.open_edit_menu(False)
        elif ch == "n":
            self.open_edit_menu(True)
        elif ch == readchar.key.ENTER:
            playlist = self._get_selected_playlist()
            self.manager.queue_next_menu(lambda: mupl.menu.player.PlayerMenu(self.manager, playlist))
        elif ch == "s":
            self.manager.queue_next_menu(lambda: mupl.menu.settings.SettingsMenu(self.manager))
        elif ch == "x":
            self.manager.shutdown()

    def _get_selected_playlist(self) -> Playlist:
        return self.manager.mupl.playlists.get_playlist(self.manager.mupl.songdb, self.playlists[self.selected].id)

    def get_max_pages(self):
        return ceil(len(self.playlists) / self.page_size)

    def change_page(self, amount: int):
        self.page += amount
        if self.page < 0:
            self.page = 0
        elif self.page >= self.get_max_pages():
            self.page = self.get_max_pages() - 1
        self.selected = self.page * self.page_size

    def change_selection(self, amount: int):
        self.selected += amount
        if self.selected < 0:
            self.selected = 0
        elif self.selected >= len(self.playlists):
            self.selected = len(self.playlists) - 1
        self.page = self.selected // self.page_size

    def open_edit_menu(self, create_new: bool):
        if create_new:
            self.manager.queue_next_menu(lambda: mupl.menu.editplaylist.PlaylistEditorMenu(self.manager))
        else:
            playlist = self._get_selected_playlist()
            self.manager.queue_next_menu(lambda: mupl.menu.editplaylist.PlaylistEditorMenu(self.manager, playlist))

    def render(self, console: Console, options: ConsoleOptions):
        yield Text()
        self.page_size = options.max_height - 12
        if self.page_size < 1:
            self.page_size = 1
        if self.selected < self.page * self.page_size or self.selected > (self.page + 1) * self.page_size:
            self.page = self.selected // self.page_size
        if len(self.playlists) == 0:
            yield console.render_str("[i]No playlists found. Try creating one![/i]")
        else:
            yield console.render_str(
                f"Page [blue bold]{self.page + 1}[/blue bold] of [blue bold]{self.get_max_pages()}[/blue bold]")
            for i, playlist in enumerate(self.playlists):
                line = ""
                if i == self.selected:
                    line += "[blue bold]> [/blue bold][r]"
                else:
                    line += "  "
                line += playlist.name
                if i == self.selected:
                    line += "[/r]"
                txt = console.render_str(line)
                txt.no_wrap = True
                txt.overflow = "ellipsis"
                yield txt
            yield Text()
            if self.selected < len(self.playlists):
                yield console.render_str(f"[blue bold]Songs[/blue bold]: {len(self.playlists[self.selected].files)}")
