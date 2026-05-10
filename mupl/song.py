import json
from pathlib import Path


class SongDatabase:
    file_path: Path
    _song_indices: dict[Path, int]
    _song_paths: dict[int, Path]
    _last_index: int

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self._song_indices = {}
        self._song_paths = {}
        self._last_index = 0

    def _update_last_index(self):
        while self._last_index in self._song_paths:
            self._last_index += 1

    def get_song_path(self, index: int) -> Path | None:
        return self._song_paths.get(index)

    def get_song_index(self, path: Path) -> int | None:
        return self._song_indices.get(path)

    def add_song(self, path: Path) -> int:
        index = self.get_song_index(path)
        if index is None:
            self._update_last_index()
            index = self._last_index
            self._song_indices[path] = index
            self._song_paths[index] = path
        return index

    def remove_song(self, song: Path | int) -> bool:
        if type(song) is int:
            if song in self._song_paths:
                path = self._song_paths.pop(song)
                self._song_indices.pop(path)
                return True
            return False
        elif type(song) is Path:
            if song in self._song_indices:
                index = self._song_indices.pop(song)
                self._song_paths.pop(index)
                return True
            return False
        else:
            raise ValueError(f"Invalid type for remove_song: {type(song)}")

    def save(self):
        songs: dict[int, str] = {}
        for index, file in self._song_paths.items():
            songs[index] = str(file)
        obj = {
            "songs": songs
        }
        with open(self.file_path, "w+", encoding="utf-8") as fp:
            json.dump(obj, fp)

    def load(self):
        self._song_indices.clear()
        self._song_paths.clear()
        self._last_index = 0
        with open(self.file_path, "r", encoding="utf-8") as fp:
            obj = json.load(fp)
            for index, file in obj["songs"].items():
                self._song_paths[int(index)] = Path(file)
        for index, path in self._song_paths.items():
            self._song_indices[path] = index
            if self._last_index < index:
                self._last_index = index
