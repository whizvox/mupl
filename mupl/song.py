import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tinytag import TinyTag

from mupl.logger import logger


@dataclass
class SongMetadata:
    title: str | None
    artist: str | None
    album: str | None
    albumartist: str | None
    year: str | None
    track: int | None
    duration: float | None

    def get_comp_artist(self) -> str | None:
        if self.artist is None:
            return None
        if self.albumartist is not None and self.albumartist not in self.artist:
            return f"{self.artist} ({self.albumartist})"
        return self.artist

    def to_json(self):
        return {
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "albumartist": self.albumartist,
            "year": self.year,
            "track": self.track,
            "duration": self.duration
        }


def create_metadata_from_tag(tag: TinyTag) -> SongMetadata:
    return SongMetadata(tag.title, tag.artist, tag.album, tag.albumartist, tag.year, tag.track, tag.duration)


def parse_metadata_from_json(obj: dict) -> SongMetadata:
    return SongMetadata(obj["title"], obj["artist"], obj["album"], obj["albumartist"], obj["year"], obj["track"],
                        obj["duration"])


@dataclass
class SongData:
    id: int
    path: Path
    meta: SongMetadata

    def to_json(self):
        return {
            "id": self.id,
            "path": str(self.path),
            "meta": self.meta.to_json()
        }


def parse_data_from_json(obj: dict) -> SongData:
    return SongData(obj["id"], Path(obj["path"]), parse_metadata_from_json(obj["meta"]))


class SongDatabase:
    _file_path: Path
    _path_to_data: dict[Path, SongData]
    _id_to_data: dict[int, SongData]
    _last_index: int

    def __init__(self, file_path: Path):
        self._file_path = file_path
        self._path_to_data = {}
        self._id_to_data = {}
        self._last_index = 0

    def _update_last_index(self):
        while self._last_index in self._id_to_data:
            self._last_index += 1

    def get_song_data(self, key: int | Path) -> SongData | None:
        if type(key) is int:
            return self._id_to_data.get(key)
        return self._path_to_data.get(key)

    def add_song(self, path: Path, meta: Optional[SongMetadata] = None) -> SongData:
        data = self.get_song_data(path)
        if data is None:
            if meta is None:
                tag = TinyTag.get(path)
                meta = create_metadata_from_tag(tag)
            self._update_last_index()
            data = SongData(self._last_index, path, meta)
            self._id_to_data[data.id] = data
            self._path_to_data[data.path] = data
        return data

    def remove_song(self, song: Path | int) -> bool:
        if type(song) is int:
            if song in self._id_to_data:
                data = self._id_to_data.pop(song)
                self._path_to_data.pop(data.path)
                return True
            return False
        elif type(song) is Path:
            if song in self._path_to_data:
                data = self._path_to_data.pop(song)
                self._id_to_data.pop(data.id)
                return True
            return False
        else:
            raise ValueError(f"Invalid type for remove_song: {type(song)}")

    def save(self):
        logger.info(f"Saving song database to {self._file_path}")
        obj = {
            "songs": list(map(lambda x: x.to_json(), self._id_to_data.values())),
            "lastid": self._last_index,
        }
        with open(self._file_path, "w+", encoding="utf-8") as fp:
            json.dump(obj, fp)

    def load(self):
        logger.info(f"Loading song database from {self._file_path}")
        self._path_to_data.clear()
        self._id_to_data.clear()
        self._last_index = 0
        if self._file_path.exists():
            with open(self._file_path, "r", encoding="utf-8") as fp:
                obj = json.load(fp)
                for song_obj in obj["songs"]:
                    data = parse_data_from_json(song_obj)
                    self._id_to_data[data.id] = data
                    self._path_to_data[data.path] = data
                self._last_index = obj["lastid"]
        else:
            self.save()
