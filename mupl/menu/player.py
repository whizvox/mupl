import readchar
import wcwidth
from rich.console import Console, ConsoleOptions
from rich.control import Control
from rich.live import Live
from rpaudio.rpaudio import AudioSink

from mupl.console import console
from mupl.playlist import ActivePlaylist, Playlist
from mupl.song import SongData
from mupl.ui import KeyControls, KeyControl
from mupl.util import format_duration


class PlayerMenu:
    def __init__(self, playlist: Playlist):
        self.active = ActivePlaylist(playlist)
        self.sink: AudioSink | None = None
        self.controls = KeyControls([
            KeyControl(":left_arrow:/:right_arrow:", "Skip 5 Seconds"),
            KeyControl(":down_arrow:/:up_arrow:", "Change Volume"),
            KeyControl("s", "Skip to Next Song"),
            KeyControl("p", "Pause"),
            KeyControl("x", "Exit"),
            KeyControl("c", "Hide Controls")
        ])
        self.no_controls = KeyControls([
            KeyControl("c", "Show Controls")
        ])
        self.volume = 100
        self.show_controls = False
        self.current_song: SongData | None = None

    def stop_current_song(self):
        self.active.next()

    def play_song(self):
        if self.sink is not None:
            self.sink.stop()
            self.sink = None
        if self.active.has_next():
            self.current_song = self.active.get_current_song()
            self.sink = AudioSink(callback=self.stop_current_song).load_audio(str(self.current_song.path))
            self.sink.play()

    def __rich_console__(self, _console: Console, options: ConsoleOptions):
        yield Control.clear()
        yield Control.move_to(0, 0)
        yield Control.show_cursor(False)
        yield _console.render_str(f"[blue][bold]~~~ Listening to [/bold][red]{self.active.playlist.name}[/red][bold] ~~~[/blue][/bold]\n", justify="center")
        if self.current_song is not None:
            meta = self.current_song.meta
            artist = meta.artist
            if meta.albumartist is not None and meta.albumartist not in artist:
                artist += f" ({meta.albumartist})"
            yield _console.render_str(f"  Title: {meta.title}")
            yield _console.render_str(f" Artist: {artist}")
            yield _console.render_str(f"  Album: {meta.album}")
            total_time = meta.duration
            curr_time = self.sink.get_pos()
            time_right = f"{format_duration(int(curr_time))}/{format_duration(int(total_time))}"
            bar_width = options.max_width - wcwidth.width(time_right) - 1
            bar_fill = int((curr_time / total_time) * bar_width)
            yield _console.render_str(f"\n[yellow]{"━" * bar_fill}[/yellow]{"━" * (bar_width - bar_fill)} {time_right}")
        else:
            yield _console.render_str("Not playing...")
        yield self.controls if self.show_controls else self.no_controls


def show_player_menu(playlist: Playlist):
    menu = PlayerMenu(playlist)

    with Live(menu, refresh_per_second=10, console=console):
        run = True
        menu.active.reload()
        menu.active.shuffle()
        menu.active.next()
        menu.play_song()
        while run:
            ch = readchar.readkey()
            if ch == "s":
                menu.stop_current_song()
                menu.play_song()
            elif ch == readchar.key.UP:
                if menu.sink is not None:
                    menu.volume = min(menu.volume + 5, 100)
                    menu.sink.set_volume(menu.volume / 100)
            elif ch == readchar.key.DOWN:
                if menu.sink is not None:
                    menu.volume = max(menu.volume - 5, 0)
                    menu.sink.set_volume(menu.volume / 100)
            elif ch == readchar.key.PAGE_UP:
                if menu.sink is not None:
                    menu.volume = 100
                    menu.sink.set_volume(1)
            elif ch == readchar.key.PAGE_DOWN:
                if menu.sink is not None:
                    menu.volume = 5
                    menu.sink.set_volume(0.05)
            elif ch == readchar.key.LEFT:
                if menu.sink is not None:
                    menu.sink.try_seek(max(menu.sink.get_pos() - 5, 0))
            elif ch == readchar.key.RIGHT:
                if menu.sink is not None:
                    menu.sink.try_seek(min(menu.sink.get_pos() + 5, menu.current_song.meta.duration))
            elif ch == "c":
                menu.show_controls = not menu.show_controls
            elif ch == "x":
                run = False
        if menu.sink is not None:
            menu.sink.stop()
            menu.sink = None