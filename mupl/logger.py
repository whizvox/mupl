import logging
from pathlib import Path

logger = logging.getLogger("mupl")


def enable_file_logging(path: Path):
    logging.basicConfig(filename=path, level=logging.INFO,
                        format="[%(asctime)s] [%(threadName)s] %(levelname)s: %(message)s")
