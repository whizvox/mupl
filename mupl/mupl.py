from dataclasses import dataclass
from pathlib import Path

from mupl.logger import enable_file_logging
from mupl.menu.selectplaylist import PlaylistSelectionMenu
from mupl.playlist import Playlists
from mupl.song import SongDatabase
from mupl.ui import MenuManager


@dataclass
class MuplContext:
    songdb: SongDatabase
    playlists: Playlists


if __name__ == "__main__":
    enable_file_logging()
    songdb = SongDatabase(Path("songs.json"))
    songdb.load()
    playlists = Playlists(Path("playlists.json"))
    playlists.load()
    manager = MenuManager(MuplContext(songdb, playlists))
    manager.queue_next_menu(lambda: PlaylistSelectionMenu(manager))
    manager.run()
