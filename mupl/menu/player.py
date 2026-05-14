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
from mupl.util import format_duration, shuffle_slice


class PlayerMenu(Menu):
    def __init__(self, manager: MenuManager, playlist: Playlist):
        super().__init__(manager, f"Playing from [red]{playlist.name}[/red]", KeyControls([
            # KeyControl(":left_arrow:/:right_arrow:", "Skip 5 Seconds"),
            KeyControl("-/+", "Change Volume"),
            KeyControl("s", "Shuffle"),
            KeyControl("Space", "Pause"),
            KeyControl(":down_arrow:/:up_arrow:", "Change Selection"),
            KeyControl("Enter", "Skip"),
            KeyControl("x", "Exit"),
            KeyControl("c", "Hide Controls")
        ]))
        self.playlist = playlist
        self.sink: AudioSink | None = None
        self.current_song: SongData | None = None
        self.songs: list[int] = []
        self.song_index = -1
        self.volume = manager.mupl.config.volume
        self.paused = False
        self._position = 0
        self.selected = 0
        self.page_size = 10
        self.shutdown = False
        self.playback_thread = Thread(target=self.playback_loop, name="PlaybackLoopThread")
        self.playback_thread.start()
        self.reload()

    def is_playing(self):
        return self.sink is not None and self.sink.is_playing

    def get_song_display_range(self) -> tuple[int, int]:
        return self.selected, min(self.selected + self.page_size, len(self.songs) - 1)

    def reload(self):
        self.paused = False
        if self.is_playing():
            self.sink.stop()
            self.sink = None
        self.songs.clear()
        for i in range(len(self.playlist.songs)):
            self.songs.append(i)

    def shuffle(self):
        if self.is_playing() or self.paused:
            shuffle_slice(self.songs, start=self.song_index + 1)
        else:
            random.shuffle(self.songs)

    def toggle_paused(self):
        self.paused = not self.paused
        self._update_output_file()

    def stop_current_song(self):
        if self.is_playing():
            self.sink.stop()
            self.sink = None
            self._position = 0

    def _update_output_file(self):
        if self.manager.mupl.config.output_to_file:
            try:
                with open(self.manager.mupl.config.output_file, "w+", encoding="utf-8") as fp:
                    if self.paused:
                        fp.write("")
                    else:
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

    def _play_next_song(self):
        self.stop_current_song()
        self.paused = False
        if not self.shutdown and self.song_index < len(self.songs) - 1:
            self.song_index += 1
            if self.selected == self.song_index:
                self.selected += 1
            self.current_song = self.playlist.songs[self.songs[self.song_index]]
            self.sink = AudioSink().load_audio(str(self.current_song.path))
            self.sink.set_volume(self.volume / 100)
            self.sink.play()
            self._update_output_file()

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
            self.shuffle()
        elif ch == readchar.key.ENTER:
            self.song_index = self.selected - 1
            self.stop_current_song()
        elif ch == "=" or ch == "+":
            if self.sink is not None:
                self.volume = min(self.volume + 5, 100)
                self.manager.mupl.config.volume = self.volume
                self.manager.mupl.config.save()
        elif ch == "-":
            if self.sink is not None:
                self.volume = max(self.volume - 5, 0)
                self.manager.mupl.config.volume = self.volume
                self.manager.mupl.config.save()
        elif ch == readchar.key.UP:
            self.selected = max(self.selected - 1, 0)
        elif ch == readchar.key.DOWN:
            self.selected = min(self.selected + 1, len(self.songs) - 1)
        elif ch == readchar.key.SPACE:
            self.toggle_paused()
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
        self.page_size = options.max_height - 12
        yield Text()
        if self.current_song is not None:
            meta = self.current_song.meta
            titletxt = console.render_str(f"  [blue bold]Title[/blue bold]: {meta.title}", overflow="ellipsis")
            titletxt.no_wrap = True
            yield titletxt
            artisttxt = console.render_str(f" [blue bold]Artist[/blue bold]: {meta.get_comp_artist()}",
                                           overflow="ellipsis")
            artisttxt.no_wrap = True
            yield artisttxt
            albumtxt = console.render_str(f"  [blue bold]Album[/blue bold]: {meta.album}", overflow="ellipsis")
            albumtxt.no_wrap = True
            yield albumtxt
            yield console.render_str(f"\n[yellow]Volume[/yellow]: {self.volume}% ")
            total_time = meta.duration
            curr_time = self._position
            time_right = f"{format_duration(int(curr_time))}/{format_duration(int(total_time))}"
            bar_width = options.max_width - wcwidth.width(time_right) - 3
            bar_fill = min(int((curr_time / total_time) * bar_width) + 1, bar_width)
            yield console.render_str(
                f"{':pause_button:' if self.paused else ':play_button:'} [yellow]{"━" * bar_fill}[/yellow]{"━" * (bar_width - bar_fill)} {time_right}")
            yield console.render_str("\n[u]Upcoming:[/u]")
            for i in range(*self.get_song_display_range()):
                song = self.playlist.songs[self.songs[i]]
                line = str(i - self.song_index) + ". "
                if i == self.selected:
                    line += f"[r]"
                line += f"{song.meta.get_comp_artist()} - {song.meta.title}"
                if i == self.selected:
                    line += "[/r]"
                txt = console.render_str(line, overflow="ellipsis")
                txt.no_wrap = True
                yield txt
        else:
            yield console.render_str("[i]Waiting...[/i]")
