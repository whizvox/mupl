import argparse
import glob
import json
import pathlib
import random
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from time import sleep

import readchar
from readchar import readkey
from rpaudio import AudioSink
from tinytag import TinyTag

from mupl.console import console
from mupl.playlist import Playlists
from mupl.song import SongDatabase
from mupl.util import get_name_and_extension


@dataclass
class MuplContext:
    songdb: SongDatabase
    playlists: Playlists


class Arguments:
    def __init__(self, config_file: str):
        self.config_file = config_file


class Configuration:
    def __init__(self):
        self.search_dir: Path | None = None
        self.formats = ["mp3", "ogg", "flac", "wav"]
        self.output_file = "../song.txt"
        self.output_song_format = "{artist} — {title}    "
        self.output_noplay_format = "Not playing    "
        self.volume = 100
        self.shuffle = True
        self.loop = True

    def to_json(self) -> dict:
        return {
            "search_dir": self.search_dir,
            "formats": self.formats,
            "output_file": self.output_file,
            "output_song_format": self.output_song_format,
            "output_noplay_format": self.output_noplay_format,
            "volume": self.volume,
            "shuffle": self.shuffle,
            "loop": self.loop,
        }


def load_config_from_json(obj: dict) -> Configuration:
    config = Configuration()
    config.search_dir = obj["search_dir"]
    config.output_file = obj["output_file"]
    config.output_song_format = obj["output_song_format"]
    config.output_noplay_format = obj["output_noplay_format"]
    config.volume = obj["volume"]
    config.shuffle = obj["shuffle"]
    config.loop = obj["loop"]
    return config


class MusicPlayerState:
    def __init__(self, config: Configuration):
        self.config = config
        self.music_files: list[Path] = []
        self.current_music_file: Path | None = None
        self.should_stop = False
        self.should_skip = False
        self.toggle_pause = False
        self.paused = False
        self.playing = False
        self.song_info: str | None = None

    def refresh_music_files(self):
        self.music_files.clear()
        if "*" in self.config.formats:
            for file in glob.glob(str(pathlib.Path(self.config.search_dir, "**/*")), recursive=True):
                self.music_files.append(Path(file))
        else:
            for file in glob.glob(str(pathlib.Path(self.config.search_dir, "**/*")), recursive=True):
                name, ext = get_name_and_extension(pathlib.Path(file).name)
                if ext in self.config.formats:
                    self.music_files.append(Path(file))
        if self.config.shuffle:
            random.shuffle(self.music_files)

    def update_console(self):
        console.clear(home=True)
        console.print("[bold]~~~ Running [red]mupl v0.1[/red] ~~~[/bold]")
        console.print(
            "Controls: [bold green][Q][/bold green] Quit | [bold green][S][/bold green] Skip | [bold green][P][/bold green] Pause")
        console.print(
            f"{' ' * 10}[bold green][Up][/bold green] +Volume | [bold green][Down][/bold green] -Volume | [bold green][PgUp][/bold green] Max Volume | [bold green][PgDown][/bold green] Min Volume")
        console.print(f"Volume: [bold blue]{self.config.volume}[/bold blue]")
        if self.song_info is None:
            console.print("On standby")
        else:
            console.print(
                f"Currently {'paused' if self.paused else 'playing'}: [blue]{self.song_info}[/blue]")


def handle_music_playing(state: MusicPlayerState):
    if len(state.music_files) == 0:
        console.print("No music files")
        return

    def stop_is_playing():
        state.playing = False

    state.current_music_file = state.music_files.pop()
    while not state.should_stop:
        handler = AudioSink(callback=stop_is_playing).load_audio(str(state.current_music_file))
        handler.set_volume(state.config.volume / 100)
        handler.play()
        state.playing = True
        tag = TinyTag.get(state.current_music_file)
        state.song_info = f"{tag.artist} - {tag.title} ({state.current_music_file})"
        with open(state.config.output_file, "w", encoding="utf-8") as f:
            f.write(state.config.output_song_format.format(artist=tag.artist, title=tag.title, album=tag.album))
        state.update_console()
        prev_volume = state.config.volume
        while state.playing:
            sleep(0.2)
            if state.toggle_pause:
                state.toggle_pause = False
                state.paused = not state.paused
                if state.paused:
                    handler.pause()
                else:
                    handler.play()
                state.update_console()
            if prev_volume != state.config.volume:
                prev_volume = state.config.volume
                handler.set_volume(state.config.volume / 100)
                state.update_console()
            if state.should_stop or state.should_skip:
                handler.stop()
        if not state.should_stop:
            if len(state.music_files) == 0:
                if state.config.loop:
                    state.refresh_music_files()
                    if len(state.music_files) == 0:
                        console.print(
                            f"[red]No music files found in [bold]{state.config.search_dir}[/bold] with the following formats: [bold]{', '.join(state.config.formats)}[/bold][/red]")
                        state.should_stop = True
                    else:
                        state.current_music_file = state.music_files.pop()
                        state.should_skip = False
                else:
                    state.should_stop = True
            else:
                state.current_music_file = state.music_files.pop()
                state.should_skip = False
    console.print("Stopping music playing thread")


def handle_user_input(state: MusicPlayerState):
    while not state.should_stop:
        key = readkey()
        if key == "q":
            state.should_stop = True
        elif key == "s":
            state.should_skip = True
        elif key == "p":
            state.toggle_pause = True
        elif key == readchar.key.DOWN:
            state.config.volume = max(state.config.volume - 5, 5)
        elif key == readchar.key.UP:
            state.config.volume = min(state.config.volume + 5, 100)
        elif key == readchar.key.PAGE_DOWN:
            state.config.volume = 5
        elif key == readchar.key.PAGE_UP:
            state.config.volume = 100
    console.print("Stopping user input thread")


def run(config: Configuration):
    state = MusicPlayerState(config)
    state.refresh_music_files()
    if len(state.music_files) == 0:
        console.print(
            f"[red]No music files found in [bold]{config.search_dir}[/bold] with the following formats: [bold]{', '.join(config.formats)}[/bold][/red]")
        return
    t1 = Thread(target=handle_music_playing, args=(state,))
    t2 = Thread(target=handle_user_input, args=(state,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", help="Location of the configuration file", type=pathlib.Path,
                        default="muplcfg.json")
    parser.add_argument("-g", "--generate", help="Generate a default configuration file", action="store_true")
    parser.add_argument("-i", "--info", help="Print information regarding the configuration file", action="store_true")
    args = vars(parser.parse_args())
    if args["generate"]:
        path = Path("../muplcfg.json")
        config = Configuration()
        with open(path, "w") as fp:
            json.dump(config.to_json(), fp, indent=4)
        console.print(f"Written default configuration file to [blue]{path.absolute()}[/blue]")
    if args["generate"] or args["info"]:
        if args["generate"]:
            console.print()
        console.print("[bold]~~~ The [red]mupl[/red] Configuration File ~~~[/bold]")
        console.print(
            "- [blue bold]search_dir[/blue bold] [red](required)[/red]: Directory containing music files; will recursively search all sub-directories")
        console.print("- [blue bold]formats[/blue bold]: All file extensions to match")
        console.print("- [blue bold]output_file[/blue bold]: File to write song information to")
        console.print(
            "- [blue bold]output_song_format[/blue bold]: Format of what will be written in the output file when a song is playing")
        console.print(
            f"{' ' * 22}Available variables: [yellow]artist[/yellow], [yellow]title[/yellow], [yellow]artist[/yellow]")
        console.print(
            "- [blue bold]output_noplay_format[/blue bold]: What will be written in the output file when a song is not playing")
        console.print("- [blue bold]volume[/blue bold]: Volume of the player; ranges from 1-100")
        console.print("- [blue bold]shuffle[/blue bold]: Whether to shuffle the list of songs before playing")
        console.print("- [blue bold]loop[/blue bold]: Whether to loop once the playlist has finished")
        if args["generate"]:
            console.print()
            console.print("[italic]You can view this information with [/italic][red bold]--info[/red bold]")
    else:
        path = Path(args["config"])
        config: Configuration | None = None
        try:
            with open(path, "r") as fp:
                config = load_config_from_json(json.load(fp))
        except FileNotFoundError:
            console.print(f"[red]Could not find configuration file at [blue]{path}[/blue][/red]")
            console.print("[red]If you didn't specify one, try generating one with [bold]--generate[/bold][/red]")
        except:
            console.print(f"[red]Could not read from configuration file at [blue]{path}[/blue][/red]")
            console.print_exception()
        if config is not None:
            if config.search_dir is None:
                console.print("[red]Make sure to specify the [bold]search_dir[/bold] in the configuration file![/red]")
            else:
                run(config)


if __name__ == "__main__":
    main()
