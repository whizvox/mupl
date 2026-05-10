import json
import random
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4, UUID

from mupl.logger import logger
from mupl.song import SongDatabase, SongData


@dataclass
class Playlist:
    id: UUID
    name: str
    songs: list[SongData]

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "files": list(map(lambda x: str(x.id), self.songs))
        }


@dataclass
class BasicPlaylist:
    id: UUID
    name: str
    files: list[int]

    def to_json(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "files": self.files
        }


class Playlists:
    _file_path: Path
    _playlists: dict[UUID, BasicPlaylist]

    def __init__(self, dir_path: Path):
        self._file_path = dir_path
        self._playlists = {}

    def __contains__(self, item):
        return item in self._playlists

    def __len__(self):
        return len(self._playlists)

    def __iter__(self):
        yield from self._playlists

    def __getitem__(self, item: UUID) -> BasicPlaylist:
        return self._playlists[item]

    def items(self):
        return self._playlists.items()

    def to_json(self):
        return {
            "playlists": list(map(lambda x: x.to_json(), self._playlists.values()))
        }

    def is_empty(self):
        return len(self._playlists) == 0

    def is_name_available(self, name: str):
        for playlist in self._playlists.values():
            if playlist.name == name:
                return False
        return True

    def get_playlist(self, db: SongDatabase, playlist_id: UUID) -> Playlist | None:
        if playlist_id in self._playlists:
            info = self._playlists[playlist_id]
            songs: list[SongData] = []
            for file_id in info.files:
                data = db.get_song_data(file_id)
                if data is None:
                    logger.warning(f"Could not find song data with ID of {file_id}")
                else:
                    songs.append(data)
            return Playlist(playlist_id, info.name, songs)
        return None

    def create_playlist(self, name: str) -> Playlist | None:
        if self.is_name_available(name):
            info = BasicPlaylist(uuid4(), name, [])
            self._playlists[info.id] = info
            playlist = Playlist(info.id, info.name, [])
            return playlist
        return None

    def sync(self, playlist: Playlist):
        if playlist.id in self._playlists:
            info = self._playlists[playlist.id]
            info.name = playlist.name
            info.files.clear()
            for data in playlist.songs:
                info.files.append(data.id)

    def save(self):
        logger.info(f"Saving playlist information to {self._file_path}")
        with open(self._file_path, "w+", encoding="utf-8") as fp:
            json.dump(self.to_json(), fp)

    def load(self):
        logger.info(f"Loading playlist information from {self._file_path}")
        if self._file_path.exists():
            with open(self._file_path, "r", encoding="utf-8") as fp:
                self._playlists.clear()
                obj = json.load(fp)
                for playlist_obj in obj["playlists"]:
                    playlist = load_basic_playlist_from_dict(playlist_obj)
                    self._playlists[playlist.id] = playlist
        else:
            self.save()


class ActivePlaylist:
    def __init__(self, playlist: Playlist):
        self.playlist = playlist
        self.remaining_songs: list[int] = []
        self.current_song_index = -1

    def is_playing(self) -> bool:
        return self.current_song_index != -1

    def has_next(self) -> bool:
        return len(self.remaining_songs) > 0

    def get_current_song(self) -> SongData:
        return self.playlist.songs[self.current_song_index]

    def reload(self):
        self.remaining_songs.clear()
        for i in range(len(self.playlist.songs)):
            self.remaining_songs.append(i)

    def shuffle(self):
        random.shuffle(self.remaining_songs)

    def next(self) -> bool:
        if self.has_next():
            self.current_song_index = self.remaining_songs.pop()
            return True
        return False


def load_basic_playlist_from_dict(obj: dict) -> BasicPlaylist:
    return BasicPlaylist(UUID(obj["id"]), obj["name"], obj["files"])
