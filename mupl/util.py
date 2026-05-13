import random
from pathlib import Path
from typing import Callable, MutableSequence, Any


def _find_all_files(directory: Path, max_depth: int, file_filter: Callable[[Path], bool], current_depth: int,
                    follow_symlinks: bool, files: set[Path]):
    if current_depth > max_depth:
        return
    for file in directory.iterdir():
        if file.is_file():
            if file_filter(file):
                files.add(file)
        elif file.is_dir():
            if not file.is_symlink() or follow_symlinks:
                _find_all_files(file, max_depth, file_filter, current_depth + 1, follow_symlinks, files)


def find_all_files(directory: Path, max_depth=20, file_filter: Callable[[Path], bool] = lambda: True,
                   follow_symlinks=False) -> list[Path]:
    files: set[Path] = set()
    _find_all_files(directory, max_depth, file_filter, 0, follow_symlinks, files)
    result = list(files)
    result.sort()
    return result


def get_name_and_extension(name: str) -> tuple[str, str]:
    index = name.rfind(".")
    if index == -1:
        return name, ""
    return name[0:index], name[index + 1:]


def filter_audio_files(path: Path) -> bool:
    name, ext = get_name_and_extension(path.name)
    return ext in ("mp3", "flac", "ogg", "wav")


def truncate(s: str, max_width: int) -> str:
    if len(s) > max_width:
        return s[:max_width - 1] + "…"
    return s


def format_duration(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02}"


def shuffle_slice(seq: MutableSequence[Any], start: int = 0, end: int = -1):
    """
    Shuffle a portion of a sequence.
    :param seq: The sequence to shuffle
    :param start: The starting index (inclusive), defaults to 0
    :param end: The ending index (exclusive), defaults to the length of the sequence
    """
    if end < 0:
        end = len(seq)
    for i in range(start, end - 1):
        idx = random.randrange(i, end)
        seq[idx], seq[i] = seq[i], seq[idx]
