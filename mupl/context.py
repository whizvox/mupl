from dataclasses import dataclass

from mupl.config import Configuration
from mupl.playlist import Playlists
from mupl.song import SongDatabase


@dataclass
class MuplContext:
    songdb: SongDatabase
    playlists: Playlists
    config: Configuration
