from math import ceil
from pathlib import Path

import readchar
import rich.markup
import tinytag
from rich.console import Console, ConsoleOptions, RenderResult
from rich.progress import track
from rich.text import Text
from rpaudio.rpaudio import AudioSink
from tinytag import TinyTag

import mupl.menu.selectplaylist
from mupl.logger import logger
from mupl.playlist import Playlist
from mupl.song import SongMetadata, create_metadata_from_tag
from mupl.ui import KeyControls, KeyControl, Menu, MenuManager, create_input_prompt, create_alert_prompt
from mupl.util import find_all_files, format_duration, filter_audio_files


class PlaylistEditorMenu(Menu):
    def __init__(self, manager: MenuManager, editing_playlist: Playlist | None = None):
        super().__init__(manager, "Editing Playlist", KeyControls([
            KeyControl(" ", "Add/Remove", readchar.key.SPACE),
            KeyControl(":up_arrow:/:down_arrow:", "Change Selection"),
            KeyControl(":left_arrow:/:right_arrow:", "Change Page"),
            KeyControl("a", "Select All"),
            KeyControl("A", "Unselect All"),
            KeyControl("s", "Search Directory"),
            KeyControl("r", "Refresh Files"),
            KeyControl("n", "Rename"),
            KeyControl("Enter", "Play Track"),
            KeyControl("S", "Save"),
        ]))
        self.mupl = manager.mupl
        self.songs: dict[Path, SongMetadata] = {}
        if editing_playlist is None:
            playlist_name = "New Playlist"
            name_suffix = 1
            while not self.mupl.playlists.is_name_available(playlist_name):
                name_suffix += 1
                playlist_name = f"New Playlist {name_suffix}"
            self.playlist = self.mupl.playlists.create_playlist(playlist_name)
        else:
            self.playlist = editing_playlist
            for data in self.playlist.songs:
                self.songs[data.path] = data.meta
        self._update_title()
        self.files: list[tuple[Path, SongMetadata]] = []
        self.current_dir: Path | None = None
        self.prompt_change_dir = False
        self.prompt_rename = False
        self.selected_file = 0
        self.playing_file = -1
        self.page = 0
        self.sink: AudioSink | None = None
        self.page_size = 10

    def get_max_pages(self):
        return ceil(len(self.files) / self.page_size)

    def refresh_files(self):
        self.files.clear()
        all_files = find_all_files(self.current_dir, file_filter=filter_audio_files)
        for path in track(all_files, "Searching files..."):
            try:
                tag = TinyTag.get(path)
                self.files.append((path, create_metadata_from_tag(tag)))
            except tinytag.ParseError as e:
                logger.warning(f"Could not parse metadata from {path}:")
                logger.warning(e)

    def change_selection(self, amount: int):
        self.selected_file += amount
        if self.selected_file < 0:
            self.selected_file = 0
        elif self.selected_file >= len(self.files):
            self.selected_file = len(self.files) - 1
        self.page = self.selected_file // self.page_size

    def change_page(self, amount: int):
        self.page += amount
        if self.page < 0:
            self.page = 0
        elif self.page >= self.get_max_pages():
            self.page = self.get_max_pages() - 1
        self.selected_file = self.page * self.page_size

    def on_destroy(self):
        if self.sink is not None:
            self.sink.stop()

    def _update_title(self):
        self.title = f"Editing Playlist [red]{self.playlist.name}[/red]"

    def _on_search_dir_set(self, new_search_dir: str | None):
        if new_search_dir is not None and new_search_dir != "":
            path = Path(new_search_dir)
            if not path.exists():
                self.queue_prompt(create_alert_prompt("Directory does not exist."))
            elif not path.is_dir():
                self.queue_prompt(create_alert_prompt("Not a directory."))
            else:
                if self.sink is not None:
                    self.sink.stop()
                    self.sink = None
                self.current_dir = path
                self.refresh_files()
                self.selected_file = 0
                self.playing_file = -1
                self.page = 0

    def _on_rename(self, new_name: str | None):
        if new_name is not None and new_name != "":
            conflict = False
            for playlist_id, playlist in self.manager.mupl.playlists.items():
                if playlist_id != self.playlist and playlist.name == new_name:
                    conflict = True
                    break
            if conflict:
                self.queue_prompt(create_alert_prompt("That name is already taken."))
            else:
                self.playlist.name = new_name
                self._update_title()

    def handle_key(self, ch: str):
        if ch == readchar.key.SPACE:
            if self.files[self.selected_file][0] not in self.songs:
                self.songs[self.files[self.selected_file][0]] = self.files[self.selected_file][1]
            else:
                self.songs.pop(self.files[self.selected_file][0])
        elif ch == readchar.key.UP:
            self.change_selection(-1)
        elif ch == readchar.key.DOWN:
            self.change_selection(1)
        elif ch == readchar.key.LEFT:
            self.change_page(-1)
        elif ch == readchar.key.RIGHT:
            self.change_page(1)
        elif ch == readchar.key.PAGE_UP:
            self.change_page(-100)
        elif ch == readchar.key.PAGE_DOWN:
            self.change_page(100)
        elif ch == "a":
            for data in self.files:
                if data[0] not in self.songs:
                    self.songs[data[0]] = data[1]
        elif ch == "A":
            for data in self.files:
                if data[0] in self.songs:
                    self.songs.pop(data[0])
        elif ch == "s":
            self.queue_prompt(create_input_prompt("Set Search Directory to:", self._on_search_dir_set))
        elif ch == "r":
            if self.current_dir is not None:
                self.refresh_files()
                if self.sink is not None:
                    self.sink.stop()
                    self.sink = None
                self.playing_file = -1
                self.selected_file = 0
                self.page = 0
        elif ch == "n":
            self.queue_prompt(create_input_prompt("Rename Playlist to:", self._on_rename))
        elif ch == readchar.key.ENTER:
            if self.playing_file == self.selected_file:
                if self.sink is not None:
                    self.sink.stop()
                self.playing_file = -1
            else:
                self.playing_file = self.selected_file
                if self.sink is not None:
                    self.sink.stop()
                self.sink = AudioSink()
                self.sink.load_audio(str(self.files[self.playing_file][0]))
                self.sink.play()
        elif ch == "S":
            self.playlist.songs.clear()
            for path in self.songs:
                data = self.mupl.songdb.add_song(path, self.songs[path])
                self.playlist.songs.append(data)
            self.mupl.playlists.sync(self.playlist)
            self.mupl.songdb.save()
            self.mupl.playlists.save()
            self.queue_prompt(create_alert_prompt("Successfully saved playlist.", "Info"))
        elif ch == "x":
            self.manager.queue_next_menu(lambda: mupl.menu.selectplaylist.PlaylistSelectionMenu(self.manager))

    def render(self, console: Console, options: ConsoleOptions) -> RenderResult:
        self.page_size = console.height - 12
        if self.page_size < 1:
            self.page_size = 1
        yield Text()
        if self.current_dir is None:
            yield console.render_str("[i]No search directory specified[/i]")
        else:
            yield console.render_str(f"Listing music files in [blue]{self.current_dir}[/blue]")
            if len(self.files) == 0:
                yield console.render_str("[italic]No music files found.[/italic]")
            else:
                yield console.render_str(
                    f"Viewing page [blue bold]{self.page + 1}[/blue bold]/[blue bold]{self.get_max_pages()}[/blue bold]")
                for i in range(self.page * self.page_size, (self.page + 1) * self.page_size):
                    if i < len(self.files):
                        song = self.files[i]
                        row = "\\["
                        if song[0] in self.songs:
                            row += "[green bold]X[/green bold]] "
                        else:
                            row += " ] "
                        if i == self.playing_file:
                            style = "yellow on "
                        elif i == self.selected_file:
                            style = "black on "
                        else:
                            style = "default on"
                        if i == self.selected_file:
                            style += "white"
                        else:
                            style += "default"
                        row += f"[{style}]"
                        if song[1].albumartist is not None and song[1].albumartist not in song[1].artist:
                            row += rich.markup.escape(str(song[1].artist)) + " (" + rich.markup.escape(
                                str(song[1].albumartist)) + ")"
                        else:
                            row += rich.markup.escape(str(song[1].artist))
                        row += " - " + rich.markup.escape(str(song[1].title))
                        row += f"[/{style}]"
                        txt = console.render_str(row, overflow="ellipsis")
                        txt.no_wrap = True
                        yield txt
                yield Text()
                if self.selected_file < len(self.files):
                    yield console.render_str("Song Metadata:")
                    selected = self.files[self.selected_file]
                    txt = console.render_str(
                        f"[blue]Album[/blue]: {rich.markup.escape(str(selected[1].album))}", overflow="ellipsis")
                    txt.no_wrap = True
                    yield txt
                    yield console.render_str(
                        f"[blue]Duration[/blue]: {format_duration(int(selected[1].duration)).ljust(5)} [blue]Track No.[/blue]: {str(selected[1].track).ljust(5)} [blue]Year[/blue]: {selected[1].year}")
                    yield console.render_str(
                        f"[blue]File[/blue]: {rich.markup.escape(str(selected[0].relative_to(self.current_dir)))}")
