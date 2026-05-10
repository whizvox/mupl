import random
import time
from threading import Thread

import readchar
import wcwidth
from rich.console import Console, ConsoleOptions
from rich.control import Control
from rich.live import Live
from rpaudio import AudioSink

from mupl.console import console
from mupl.logger import logger
from mupl.playlist import Playlist
from mupl.song import SongData
from mupl.ui import KeyControls, KeyControl
from mupl.util import format_duration


class PlayerMenu:
    def __init__(self, playlist: Playlist):
        self.playlist = playlist
        self.sink: AudioSink | None = None
        self.current_song: SongData | None = None
        self.remaining_songs: list[int] = []
        self.volume = 100
        self.paused = False
        self._position = 0
        self.controls = KeyControls([
            # KeyControl(":left_arrow:/:right_arrow:", "Skip 5 Seconds"),
            KeyControl(":down_arrow:/:up_arrow:", "Change Volume"),
            KeyControl("s", "Skip to Next Song"),
            KeyControl("p", "Pause"),
            KeyControl("x", "Exit"),
            KeyControl("c", "Hide Controls")
        ])
        self.no_controls = KeyControls([
            KeyControl("c", "Show Controls")
        ])
        self.show_controls = False
        self.shutdown = False

    def is_playing(self):
        return self.sink is not None and self.sink.is_playing

    def reload(self):
        self.paused = False
        if self.is_playing():
            self.sink.stop()
            self.sink = None
        self.remaining_songs.clear()
        for i in range(len(self.playlist.songs)):
            self.remaining_songs.append(i)

    def shuffle(self):
        random.shuffle(self.remaining_songs)

    def toggle_paused(self):
        self.paused = not self.paused

    def stop_current_song(self):
        if self.is_playing():
            self.sink.stop()
            self.sink = None
            self._position = 0

    def _play_next_song(self):
        self.stop_current_song()
        self.paused = False
        if not self.shutdown and len(self.remaining_songs) > 0:
            self.current_song = self.playlist.songs[self.remaining_songs.pop()]
            self.sink = AudioSink().load_audio(str(self.current_song.path))
            self.sink.set_volume(self.volume / 100)
            self.sink.play()

    def playback_loop(self):
        logger.info("Starting playback loop")
        prev_paused = self.paused
        prev_volume = self.volume
        while not self.shutdown:
            if self.is_playing():
                self._position = self.sink.get_pos()
            if prev_paused != self.paused:
                prev_paused = self.paused
                if self.sink is not None:
                    if self.paused:
                        self.sink.pause()
                    else:
                        self.sink.play()
            if prev_volume != self.volume:
                prev_volume = self.volume
                if self.sink is not None:
                    self.sink.set_volume(self.volume / 100)
            if not self.is_playing() and not self.paused:
                self._play_next_song()
            time.sleep(0.1)
        self.stop_current_song()
        logger.info("Playback loop finished")

    def __rich_console__(self, _console: Console, options: ConsoleOptions):
        yield Control.clear()
        yield Control.move_to(0, 0)
        yield Control.show_cursor(False)
        yield _console.render_str(
            f"[blue][bold]~~~ Listening to [/bold][red]{self.playlist.name}[/red][bold] ~~~[/blue][/bold]\n",
            justify="center")
        if self.current_song is not None:
            meta = self.current_song.meta
            artist = meta.artist
            if meta.albumartist is not None and meta.albumartist not in artist:
                artist += f" ({meta.albumartist})"
            yield _console.render_str(f"  Title: {meta.title}")
            yield _console.render_str(f" Artist: {artist}")
            yield _console.render_str(f"  Album: {meta.album}")
            total_time = meta.duration
            curr_time = self._position
            time_right = f"{format_duration(int(curr_time))}/{format_duration(int(total_time))}"
            bar_width = options.max_width - wcwidth.width(time_right) - 3
            bar_fill = min(int((curr_time / total_time) * bar_width) + 1, bar_width)
            yield _console.render_str(
                f"\n{':pause_button:' if self.paused else ':play_button:'} [yellow]{"━" * bar_fill}[/yellow]{"━" * (bar_width - bar_fill)} {time_right}")
        else:
            yield _console.render_str("[i]Waiting...[/i]")
        yield self.controls if self.show_controls else self.no_controls


def show_player_menu(playlist: Playlist):
    menu = PlayerMenu(playlist)

    with Live(menu, refresh_per_second=10, console=console):
        run = True
        menu.reload()
        menu.shuffle()
        playback_thread = Thread(target=menu.playback_loop, name="PlaybackLoopThread")
        playback_thread.start()
        while run:
            ch = readchar.readkey()
            if ch == "s":
                menu.stop_current_song()
            elif ch == readchar.key.UP:
                if menu.sink is not None:
                    menu.volume = min(menu.volume + 5, 100)
            elif ch == readchar.key.DOWN:
                if menu.sink is not None:
                    menu.volume = max(menu.volume - 5, 0)
            elif ch == readchar.key.PAGE_UP:
                if menu.sink is not None:
                    menu.volume = 100
            elif ch == readchar.key.PAGE_DOWN:
                if menu.sink is not None:
                    menu.volume = 5
            elif ch == "p":
                menu.toggle_paused()
            # elif ch == readchar.key.LEFT:
            #     if menu.sink is not None:
            #         menu.sink.try_seek(max(menu.sink.get_pos() - 5, 0))
            # elif ch == readchar.key.RIGHT:
            #     if menu.sink is not None:
            #         menu.sink.try_seek(min(menu.sink.get_pos() + 5, menu.current_song.meta.duration))
            elif ch == "c":
                menu.show_controls = not menu.show_controls
            elif ch == "x":
                menu.shutdown = True
                run = False
        menu.shutdown = True
        playback_thread.join()
