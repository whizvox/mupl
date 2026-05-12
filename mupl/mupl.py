from argparse import ArgumentParser
from pathlib import Path

from platformdirs import PlatformDirs

import mupl.menu.selectplaylist
from mupl.config import Configuration
from mupl.context import MuplContext
from mupl.logger import enable_file_logging, logger
from mupl.playlist import Playlists
from mupl.song import SongDatabase
from mupl.ui import MenuManager


class Arguments:
    datadir: Path | None = None


def main():
    parser = ArgumentParser()
    parser.add_argument("-d", "--dir", type=Path, help="Location of the data directory (defaults to system default)")
    args = parser.parse_args(namespace=Arguments())
    if args.datadir is not None:
        data_path = Path(args.datadir)
    else:
        dirs = PlatformDirs("mupl", "whizvox")
        data_path = dirs.user_data_path
    logger.info(f"Data directory set to {data_path}")
    if not data_path.exists():
        data_path.mkdir(parents=True)
    enable_file_logging(Path(data_path, "log.txt"))
    songdb = SongDatabase(Path(data_path, "songs.json"))
    songdb.load()
    playlists = Playlists(Path(data_path, "playlists.json"))
    playlists.load()
    config = Configuration(Path(data_path, "config.json"))
    config.load()
    manager = MenuManager(MuplContext(songdb, playlists, config))
    manager.queue_next_menu(lambda: mupl.menu.selectplaylist.PlaylistSelectionMenu(manager))
    manager.run()


if __name__ == "__main__":
    main()
