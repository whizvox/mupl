import json
import shutil
from math import ceil
from uuid import uuid4
from glob import glob
from pathlib import Path

import readchar
import rich.markup
import tinytag
from readchar import readkey
from rich.progress import track
from rpaudio.rpaudio import AudioSink
from tinytag import TinyTag

from mupl.console import console
from mupl.logger import logger
from mupl.playlist import Playlist, load_playlist_from_dict, ActivePlaylist
from mupl.util import get_name_and_extension, find_all_files, truncate, format_duration


class KeyControl:
    def __init__(self, key, description):
        self.key = key
        self.description = description

    def get_formatted(self):
        return f"[green bold]\\[{self.key}][/green bold] {self.description}"


class KeyControls:
    def __init__(self, controls: list[KeyControl]):
        self.controls = controls

    def print_all(self):
        # result = ""
        # curr_width = 0
        # curr_col = 0
        # for control in self.controls:
        #     new_width = curr_width + control.get_plain_width()
        #     if curr_col != 0:
        #         new_width += 3
        #     if new_width > console_width:
        #         if curr_col == 0:
        #             result += truncate(control.get_formatted(), console_width) + "\n"
        #             continue
        #         curr_col = 0
        #         result += "\n"
        #         new_width -= curr_width
        #     if curr_col != 0:
        #         result += " | "
        #     result += control.get_formatted()
        #     curr_width = new_width
        #     curr_col += 1
        # console.print(result)
        for control in self.controls:
            console.print(control.get_formatted())


class PlaylistInfo:
    def __init__(self, file: Path, playlist: Playlist):
        self.file = file
        self.playlist = playlist


class PlaylistManager:
    def __init__(self, root_dir: Path):
        self.playlist_directory = Path(root_dir, "playlists")
        self.playlists: dict[str, PlaylistInfo] = {}
        self.active_playlist: ActivePlaylist | None = None

    def is_title_available(self, title: str) -> bool:
        for plinfo in self.playlists.values():
            if plinfo.playlist.title.lower() == title.lower():
                return False
        return True

    def save(self):
        for plinfo in self.playlists.values():
            with open(plinfo.file, "w", encoding="utf-8") as fp:
                json.dump(plinfo.playlist.to_json(), fp, indent=4)
                logger.info(f"Saved playlist {plinfo.playlist.title} to {plinfo.file}")

    def create_new_playlist(self, title: str) -> Playlist:
        playlist = Playlist(str(uuid4()), title, [])
        self.playlists[playlist.id] = PlaylistInfo(Path(self.playlist_directory, playlist.id + ".json"), playlist)
        return playlist

    def set_active_playlist(self, playlist: str | Playlist) -> ActivePlaylist | None:
        if type(playlist) == str:
            if playlist in self.playlists:
                playlist = self.playlists[playlist].playlist
            else:
                return None
        self.active_playlist = ActivePlaylist(playlist)
        return self.active_playlist

    def load(self) -> list[tuple[Path, Exception]]:
        self.playlists.clear()
        failed_loads: list[tuple[Path, Exception]] = []
        for file in glob(str(Path(self.playlist_directory, "*.json"))):
            try:
                with open(file, "r", encoding="utf-8") as fp:
                    playlist = load_playlist_from_dict(json.load(fp))
                    self.playlists[playlist.id] = PlaylistInfo(Path(file), playlist)
            except Exception as e:
                failed_loads.append((Path(file), e))
        return failed_loads


def show_playlist_selection_menu(plman: PlaylistManager):
    run = True
    playlist_page = 0
    while run:
        console.clear()
        console.print("[bold]~~~ Select a Playlist ~~~[/bold]")
        console.print(
            "[green bold][Right][/green bold] +Page | [green bold][Left][/green bold] -Page | [green bold][N][/green bold] New Playlist | [green bold][X][/green bold] Exit")
        console.print()
        if len(plman.playlists) == 0:
            console.print("[italic]No playlists found. Try creating one![/italic]")
        else:
            console.print(f"Page {playlist_page + 1} of {len(plman.playlists)}")
            for i, plinfo in enumerate(plman.playlists):
                console.print(f"[blue bold]{i + 1}[/blue bold] {plinfo.title}")
            console.print("")
        k = readkey()
        if k == readchar.key.LEFT:
            playlist_page = max(playlist_page - 1, 0)
        elif k == readchar.key.RIGHT:
            playlist_page = min(playlist_page + 1, len(plman.playlists) - 1)
        elif k == "n":
            show_playlist_creation_menu(plman)
        elif k == "x":
            run = False


def show_playlist_creation_menu(plman: PlaylistManager):
    title = "New Playlist"
    title_suffix = 1
    while not plman.is_title_available(title):
        title_suffix += 1
        title = f"New Playlist {title_suffix}"
    songs: dict[Path, TinyTag] = {}
    files: list[tuple[Path, TinyTag]] = []
    current_dir: Path | None = None
    prompt_change_dir = False
    prompt_rename = False
    selected_file = 0
    playing_file = -1
    page = 0
    sink: AudioSink | None = None
    PAGE_SIZE = 10

    def _filter_audio_files(path: Path) -> bool:
        name, ext = get_name_and_extension(path.name)
        return ext in ("mp3", "flac", "ogg", "wav")

    def refresh_files():
        files.clear()
        all_files = find_all_files(current_dir, file_filter=_filter_audio_files)
        for path in track(all_files, "Searching files..."):
            try:
                tag = TinyTag.get(path)
                files.append((path, tag))
            except tinytag.ParseError as e:
                logger.warning(f"Could not parse metadata from {path}:")
                logger.warning(e)

    run = True
    controls = KeyControls([
        KeyControl("Space", "Add/Remove"),
        KeyControl("Up/Down", "Change Selection"),
        KeyControl("Left/Right", "-/+ Page"),
        KeyControl("a", "Select All"),
        KeyControl("A", "Unselect All"),
        KeyControl("s", "Search Directory"),
        KeyControl("r", "Refresh Files"),
        KeyControl("n", "Rename Playlist"),
        KeyControl("Enter", "Play Track"),
        KeyControl("x", "Exit"),
        KeyControl("c", "Hide Controls"),
    ])
    controls2 = KeyControls([
        KeyControl("c", "Show Controls")
    ])
    show_controls = False
    while run:
        console.width = shutil.get_terminal_size().columns
        console.clear()
        console.print(f"[bold]~~~ Editing Playlist [/bold][red]{title}[/red][bold] ~~~[/bold]", justify="center")
        if show_controls:
            controls.print_all()
        else:
            controls2.print_all()
        console.print()
        if prompt_change_dir:
            prompt_change_dir = False
            new_current_dir = Path(console.input("Search in Directory > "))
            if not new_current_dir.exists():
                console.print("[red]Directory does not exist[/red]")
                console.input("Continue>")
            elif not new_current_dir.is_dir():
                console.print("[red]Not a directory[/red]")
                console.input("Continue>")
            else:
                current_dir = new_current_dir
                refresh_files()
                if sink is not None:
                    sink.stop()
                    sink = None
                selected_file = 0
                playing_file = -1
                page = 0
        elif prompt_rename:
            prompt_rename = False
            new_title = console.input("New Playlist Name > ")
            if plman.is_title_available(new_title):
                title = new_title
            else:
                console.print("[red]That name is already taken by another playlist![/red]")
                console.input("Continue>")
        else:
            if current_dir is None:
                console.print("[italic]No search directory specified[/italic]")
            else:
                console.print(f"Listing music files in [blue]{current_dir}[/blue]")
                if len(files) == 0:
                    console.print("[italic]No music files found.[/italic]")
                else:
                    console.print(
                        f"Viewing page [blue bold]{page + 1}[/blue bold]/[blue bold]{ceil(len(files) / PAGE_SIZE)}[/blue bold]")
                    for i in range(page * PAGE_SIZE, (page + 1) * PAGE_SIZE):
                        if i < len(files):
                            row = "\\["
                            if files[i][0] in songs:
                                row += "[green bold]X[/green bold]] "
                            else:
                                row += " ] "
                            if i == playing_file:
                                row += "[yellow]"
                            if i == selected_file:
                                row += "[reverse]"
                            row += rich.markup.escape(str(files[i][1].artist)) + " - " + rich.markup.escape(
                                str(files[i][1].title))
                            if i == selected_file:
                                row += "[/reverse]"
                            if i == playing_file:
                                row += "[/yellow]"
                            console.print(row, no_wrap=True, overflow="ellipsis")
                    console.print()
                    if selected_file < len(files):
                        console.print("Song Metadata:")
                        selected = files[selected_file]
                        console.print(
                            f"[blue]Album[/blue]: {rich.markup.escape(str(selected[1].album))}", no_wrap=True,
                            overflow="ellipsis")
                        console.print(
                            f"[blue]Duration[/blue]: {format_duration(int(selected[1].duration)).ljust(5)} [blue]Track No.[/blue]: {str(selected[1].track).ljust(5)} [blue]Year[/blue]: {selected[1].year}")
                        console.print(
                            f"[blue]File[/blue]: {rich.markup.escape(str(selected[0].relative_to(current_dir)))}")
            k = readkey()
            if k == "c":
                show_controls = not show_controls
            elif k == readchar.key.SPACE:
                if files[selected_file][0] not in songs:
                    songs[files[selected_file][0]] = files[selected_file][1]
                else:
                    songs.pop(files[selected_file][0])
            elif k == readchar.key.UP:
                selected_file -= 1
                if selected_file < 0:
                    selected_file = 0
                page = selected_file // PAGE_SIZE
            elif k == readchar.key.DOWN:
                selected_file += 1
                if selected_file >= len(files):
                    selected_file = len(files) - 1
                page = selected_file // PAGE_SIZE
            elif k == readchar.key.LEFT:
                page = max(page - 1, 0)
                selected_file = page * PAGE_SIZE
            elif k == readchar.key.RIGHT:
                page = min(page + 1, ceil(len(files) / PAGE_SIZE))
                selected_file = page * PAGE_SIZE
            elif k == readchar.key.PAGE_UP:
                page = 0
                selected_file = 0
            elif k == readchar.key.PAGE_DOWN:
                page = ceil(len(files) / PAGE_SIZE) - 1
                selected_file = page * PAGE_SIZE
            elif k == "a":
                for file in files:
                    if file[0] not in songs:
                        songs[file[0]] = file[1]
            elif k == "A":
                for file in files:
                    if file[0] in songs:
                        songs.pop(file[0])
            elif k == "s":
                prompt_change_dir = True
            elif k == "r":
                refresh_files()
                if sink is not None:
                    sink.stop()
                    sink = None
                selected_file = 0
                playing_file = -1
                page = 0
            elif k == "n":
                prompt_rename = True
            elif k == readchar.key.ENTER:
                if playing_file == selected_file:
                    if sink is not None:
                        sink.stop()
                    playing_file = -1
                else:
                    playing_file = selected_file
                    if sink is not None:
                        sink.stop()
                    sink = AudioSink()
                    sink.load_audio(str(files[playing_file][0]))
                    sink.play()
            elif k == "x":
                run = False
    if sink is not None:
        sink.stop()


if __name__ == "__main__":
    show_playlist_selection_menu(PlaylistManager(Path(".")))
