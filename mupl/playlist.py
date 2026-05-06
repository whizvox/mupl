import random
from pathlib import Path


class Playlist:
    def __init__(self, playlist_id: str, title: str, files: list[Path]):
        self.id = playlist_id
        self.title = title
        self.files = files

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "files": self.files
        }


class ActivePlaylist:
    def __init__(self, playlist: Playlist):
        self.playlist = playlist
        self.remaining_songs: list[int] = []
        self.current_song_index = -1

    def is_playing(self) -> bool:
        return self.current_song_index != -1

    def has_next(self) -> bool:
        return len(self.remaining_songs) > 0

    def get_current_song_file(self) -> Path:
        return self.playlist.files[self.current_song_index]

    def reload(self):
        self.remaining_songs.clear()
        for i in range(len(self.remaining_songs)):
            self.remaining_songs.append(i)

    def shuffle(self):
        random.shuffle(self.remaining_songs)

    def next(self) -> bool:
        if self.has_next():
            self.current_song_index = self.remaining_songs.pop()
            return True
        return False


def load_playlist_from_dict(obj: dict) -> Playlist:
    return Playlist(obj["id"], obj["title"], obj["files"])
