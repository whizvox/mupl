import json
from pathlib import Path

_CONFIG_VERSION = 1


class Configuration:
    _path: Path
    output_to_file: bool = False
    output_file: str = "song.txt"
    output_file_format: str = "{compartist} - {title}"
    last_search_dir: str = ""

    def __init__(self, path: Path):
        self._path = path

    def to_json(self):
        return {
            "__config_version__": _CONFIG_VERSION,
            "output_to_file": self.output_to_file,
            "output_file": self.output_file,
            "output_file_format": self.output_file_format,
            "last_search_dir": self.last_search_dir
        }

    def load(self):
        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as fp:
                obj = json.load(fp)
                self.output_to_file = obj["output_to_file"]
                self.output_file = obj["output_file"]
                self.output_file_format = obj["output_file_format"]
                self.last_search_dir = obj["last_search_dir"]
        else:
            self.save()

    def save(self):
        with open(self._path, "w+", encoding="utf-8") as fp:
            json.dump(self.to_json(), fp, indent=4)
