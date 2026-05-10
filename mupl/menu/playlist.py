from math import ceil
from pathlib import Path

import readchar
import rich.markup
import tinytag
from readchar import readkey
from rich.control import Control
from rich.panel import Panel
from rich.progress import track
from rich.prompt import Prompt
from rpaudio.rpaudio import AudioSink
from tinytag import TinyTag

from mupl.console import console
from mupl.logger import logger, enable_file_logging
from mupl.menu.player import show_player_menu
from mupl.mupl import MuplContext
from mupl.playlist import Playlists, Playlist, BasicPlaylist
from mupl.song import SongDatabase, SongMetadata, create_metadata_from_tag
from mupl.ui import KeyControls, KeyControl
from mupl.util import get_name_and_extension, find_all_files, format_duration


def show_playlist_selection_menu(mupl: MuplContext):
    run = True
    selected = 0
    page = 0
    playlists: list[BasicPlaylist] = []
    for playlist_id, info in mupl.playlists.items():
        playlists.append(info)
    show_controls = False
    controls = KeyControls([
        KeyControl(":up_arrow:/:down_arrow:", "Change Selection"),
        KeyControl("e", "Edit"),
        KeyControl("n", "Create New"),
        KeyControl("x", "Exit"),
        KeyControl("c", "Hide Controls")
    ])
    controls2 = KeyControls([KeyControl("c", "Show Controls")])

    while run:
        page_size = console.height - 12
        if page_size < 1:
            page_size = 1
        console.clear()
        console.show_cursor(False)
        console.print("[bold]~~~ Select a Playlist ~~~[/bold]", justify="center")
        console.print()
        if len(playlists) == 0:
            console.print("[i]No playlists found. Try creating one![/i]")
        else:
            console.print(
                f"Page [blue bold]{page + 1}[/blue bold] of [blue bold]{ceil(len(playlists) / page_size)}[/blue bold]")
            for i, playlist in enumerate(playlists):
                line = ""
                if i == selected:
                    line += "[blue bold]> [/blue bold][r]"
                else:
                    line += "  "
                line += playlist.name
                if i == selected:
                    line += "[/r]"
                console.print(line, no_wrap=True, overflow="ellipsis")
            console.print()
            if selected < len(playlists):
                console.print(f"[blue bold]Songs[/blue bold]: {len(playlists[selected].files)}")
        if show_controls:
            console.print(controls)
        else:
            console.print(controls2)
        k = readkey()
        if k == readchar.key.LEFT:
            page = max(page - 1, 0)
            selected = page_size * page
        elif k == readchar.key.RIGHT:
            page = min(page + 1, ceil(len(playlists) - 1))
            selected = page_size * page
        elif k == readchar.key.UP:
            selected = max(selected - 1, 0)
        elif k == readchar.key.DOWN:
            selected = min(selected + 1, len(playlists) - 1)
        elif k == "e":
            playlist = mupl.playlists.get_playlist(mupl.songdb, playlists[selected].id)
            show_playlist_edit_menu(mupl, playlist)
        elif k == "n":
            show_playlist_edit_menu(mupl)
        elif k == "c":
            show_controls = not show_controls
        elif k == readchar.key.ENTER:
            playlist = mupl.playlists.get_playlist(mupl.songdb, playlists[selected].id)
            show_player_menu(playlist)
        elif k == "x":
            run = False


def show_playlist_edit_menu(mupl: MuplContext, editing_playlist: Playlist | None = None):
    songs: dict[Path, SongMetadata] = {}
    if editing_playlist is None:
        playlist_name = "New Playlist"
        name_suffix = 1
        while not mupl.playlists.is_name_available(playlist_name):
            name_suffix += 1
            playlist_name = f"New Playlist {name_suffix}"
        playlist = mupl.playlists.create_playlist(playlist_name)
    else:
        playlist = editing_playlist
        for data in playlist.songs:
            songs[data.path] = data.meta

    files: list[tuple[Path, SongMetadata]] = []
    current_dir: Path | None = None
    prompt_change_dir = False
    prompt_rename = False
    selected_file = 0
    playing_file = -1
    page = 0
    sink: AudioSink | None = None

    def _filter_audio_files(path: Path) -> bool:
        name, ext = get_name_and_extension(path.name)
        return ext in ("mp3", "flac", "ogg", "wav")

    def refresh_files():
        files.clear()
        all_files = find_all_files(current_dir, file_filter=_filter_audio_files)
        for path in track(all_files, "Searching files..."):
            try:
                tag = TinyTag.get(path)
                files.append((path, create_metadata_from_tag(tag)))
            except tinytag.ParseError as e:
                logger.warning(f"Could not parse metadata from {path}:")
                logger.warning(e)

    run = True
    controls = KeyControls([
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
        KeyControl("x", "Exit"),
        KeyControl("c", "Hide Controls"),
    ])
    controls2 = KeyControls([
        KeyControl("c", "Show Controls")
    ])
    show_controls = False
    while run:
        page_size = console.height - 12
        if page_size < 1:
            page_size = 1
        console.clear()
        console.print(f"[bold]~~~ Editing Playlist [/bold][red]{playlist.name}[/red][bold] ~~~[/bold]",
                      justify="center")
        console.print()
        if prompt_change_dir:
            prompt_change_dir = False
            console.show_cursor(True)
            new_current_dir_str = Prompt.ask("Search in Directory")
            if new_current_dir_str != "":
                new_current_dir = Path(new_current_dir_str)
                console.show_cursor(False)
                if not new_current_dir.exists():
                    console.print(Control.move_to(0, console.height // 2 - 4),
                                  Panel("Directory does not exist.\n\n[i]Press any key to continue.[/i]", title="Alert",
                                        padding=1), end="",
                                  justify="center")
                    readchar.readkey()
                elif not new_current_dir.is_dir():
                    console.print(Control.move_to(0, console.height // 2 - 4),
                                  Panel("Not a directory.\n\n[i]Press any key to continue.[/i]", title="Alert",
                                        padding=1),
                                  justify="center", end="")
                    readchar.readkey()
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
            console.show_cursor(True)
            new_name = Prompt.ask("New Playlist Name")
            console.show_cursor(False)
            if mupl.playlists.is_name_available(new_name):
                playlist.name = new_name
            else:
                console.print(Control.move_to(0, console.height // 2 - 4),
                              Panel(
                                  "That name is already taken by another playlist.\n\n[i]Press any key to continue.[/i]",
                                  title="Alert", padding=1),
                              end="", justify="center")
                readchar.readkey()
        else:
            if current_dir is None:
                console.print("[italic]No search directory specified[/italic]")
            else:
                console.print(f"Listing music files in [blue]{current_dir}[/blue]")
                if len(files) == 0:
                    console.print("[italic]No music files found.[/italic]")
                else:
                    console.print(
                        f"Viewing page [blue bold]{page + 1}[/blue bold]/[blue bold]{ceil(len(files) / page_size)}[/blue bold]")
                    for i in range(page * page_size, (page + 1) * page_size):
                        if i < len(files):
                            row = "\\["
                            if files[i][0] in songs:
                                row += "[green bold]X[/green bold]] "
                            else:
                                row += " ] "
                            if i == playing_file:
                                style = "yellow on "
                            elif i == selected_file:
                                style = "black on "
                            else:
                                style = "default on"
                            if i == selected_file:
                                style += "white"
                            else:
                                style += "default"
                            row += f"[{style}]"
                            if files[i][1].albumartist is not None and files[i][1].albumartist not in files[i][
                                1].artist:
                                row += rich.markup.escape(str(files[i][1].artist)) + " (" + rich.markup.escape(
                                    str(files[i][1].albumartist)) + ")"
                            else:
                                row += rich.markup.escape(str(files[i][1].artist))
                            row += " - " + rich.markup.escape(str(files[i][1].title))
                            row += f"[/{style}]"
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
            if show_controls:
                console.print(controls, end="")
            else:
                console.print(controls2, end="")
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
                page = selected_file // page_size
            elif k == readchar.key.DOWN:
                selected_file += 1
                if selected_file >= len(files):
                    selected_file = len(files) - 1
                page = selected_file // page_size
            elif k == readchar.key.LEFT:
                page = max(page - 1, 0)
                selected_file = page * page_size
            elif k == readchar.key.RIGHT:
                page = min(page + 1, ceil(len(files) / page_size))
                selected_file = page * page_size
            elif k == readchar.key.PAGE_UP:
                page = 0
                selected_file = 0
            elif k == readchar.key.PAGE_DOWN:
                page = ceil(len(files) / page_size) - 1
                selected_file = page * page_size
            elif k == "a":
                for data in files:
                    if data[0] not in songs:
                        songs[data[0]] = data[1]
            elif k == "A":
                for data in files:
                    if data[0] in songs:
                        songs.pop(data[0])
            elif k == "s":
                prompt_change_dir = True
            elif k == "r":
                if current_dir is not None:
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
            elif k == "S":
                playlist.songs.clear()
                for path in songs:
                    data = mupl.songdb.add_song(path, songs[path])
                    playlist.songs.append(data)
                mupl.playlists.sync(playlist)
                mupl.songdb.save()
                mupl.playlists.save()
                panel = Panel("Successfully saved playlist.\n\n[i]Press any key to continue.[/i]", title="Success",
                              padding=1)
                console.print(Control.move_to(0, console.height // 2 - 4), panel, end="", justify="center")
                readchar.readkey()
            elif k == "x":
                run = False
    if sink is not None:
        sink.stop()


def main():
    enable_file_logging()
    songdb = SongDatabase(Path("songs.json"))
    songdb.load()
    playlists = Playlists(Path("playlists.json"))
    playlists.load()
    console.set_window_title("mupl v0.1")
    show_playlist_selection_menu(MuplContext(songdb, playlists))


if __name__ == "__main__":
    main()
