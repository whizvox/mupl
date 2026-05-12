import random
import time
from threading import Thread

import readchar
import wcwidth
from rich.console import Console, ConsoleOptions
from rich.text import Text
from rpaudio import AudioSink

import mupl.menu.selectplaylist
from mupl.logger import logger
from mupl.playlist import Playlist
from mupl.song import SongData
from mupl.ui import KeyControls, KeyControl, Menu, MenuManager
from mupl.util import format_duration


class PlayerMenu(Menu):
    def __init__(self, manager: MenuManager, playlist: Playlist):
        super().__init__(manager, f"Playing from [red]{playlist.name}[/red]", KeyControls([
            # KeyControl(":left_arrow:/:right_arrow:", "Skip 5 Seconds"),
            KeyControl(":down_arrow:/:up_arrow:", "Change Volume"),
            KeyControl("s", "Skip to Next Song"),
            KeyControl("p", "Pause"),
            KeyControl("x", "Exit"),
            KeyControl("c", "Hide Controls")
        ]))
        self.playlist = playlist
        self.sink: AudioSink | None = None
        self.current_song: SongData | None = None
        self.remaining_songs: list[int] = []
        self.volume = manager.mupl.config.volume
        self.paused = False
        self._position = 0
        self.shutdown = False
        self.playback_thread = Thread(target=self.playback_loop, name="PlaybackLoopThread")
        self.playback_thread.start()
        self.reload()

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
            self.current_song = self.playlist.songs[self.remaining_songs.pop(0)]
            self.sink = AudioSink().load_audio(str(self.current_song.path))
            self.sink.set_volume(self.volume / 100)
            self.sink.play()
            if self.manager.mupl.config.output_to_file:
                try:
                    with open(self.manager.mupl.config.output_file, "w+", encoding="utf-8") as fp:
                        fp.write(self.manager.mupl.config.output_file_format.format(
                            title=self.current_song.meta.title,
                            album=self.current_song.meta.album,
                            albumartist=self.current_song.meta.albumartist,
                            compartist=self.current_song.meta.get_comp_artist(),
                            track=self.current_song.meta.track,
                            year=self.current_song.meta.year
                        ))
                except IOError as e:
                    logger.error(f"Could not write to output file at {self.manager.mupl.config.output_file}:\n{e}")

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

    def handle_key(self, ch: str):
        if ch == "s":
            self.stop_current_song()
        elif ch == readchar.key.UP:
            if self.sink is not None:
                self.volume = min(self.volume + 5, 100)
                self.manager.mupl.config.volume = self.volume
                self.manager.mupl.config.save()
        elif ch == readchar.key.DOWN:
            if self.sink is not None:
                self.volume = max(self.volume - 5, 0)
                self.manager.mupl.config.volume = self.volume
                self.manager.mupl.config.save()
        elif ch == readchar.key.PAGE_UP:
            if self.sink is not None:
                self.volume = 100
                self.manager.mupl.config.volume = self.volume
                self.manager.mupl.config.save()
        elif ch == readchar.key.PAGE_DOWN:
            if self.sink is not None:
                self.volume = 5
                self.manager.mupl.config.volume = self.volume
                self.manager.mupl.config.save()
        elif ch == "p":
            self.toggle_paused()
        # elif ch == readchar.key.LEFT:
        #     if self.sink is not None:
        #         self.sink.try_seek(max(self.sink.get_pos() - 5, 0))
        # elif ch == readchar.key.RIGHT:
        #     if self.sink is not None:
        #         self.sink.try_seek(min(self.sink.get_pos() + 5, self.current_song.meta.duration))
        elif ch == "x":
            self.shutdown = True
            self.stop_current_song()
            self.manager.queue_next_menu(lambda: mupl.menu.selectplaylist.PlaylistSelectionMenu(self.manager))

    def on_destroy(self):
        self.shutdown = True
        self.stop_current_song()
        self.playback_thread.join()

    def render(self, console: Console, options: ConsoleOptions):
        yield Text()
        if self.current_song is not None:
            meta = self.current_song.meta
            yield console.render_str(f"  Title: {meta.title}")
            yield console.render_str(f" Artist: {meta.get_comp_artist()}")
            yield console.render_str(f"  Album: {meta.album}")
            yield console.render_str(f"\nVolume: {self.volume}% ")
            total_time = meta.duration
            curr_time = self._position
            time_right = f"{format_duration(int(curr_time))}/{format_duration(int(total_time))}"
            bar_width = options.max_width - wcwidth.width(time_right) - 3
            bar_fill = min(int((curr_time / total_time) * bar_width) + 1, bar_width)
            yield console.render_str(
                f"{':pause_button:' if self.paused else ':play_button:'} [yellow]{"━" * bar_fill}[/yellow]{"━" * (bar_width - bar_fill)} {time_right}")
        else:
            yield console.render_str("[i]Waiting...[/i]")
