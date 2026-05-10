import logging

logger = logging.getLogger("mupl")


def enable_file_logging():
    logging.basicConfig(filename="log.txt", level=logging.INFO, format="[%(asctime)s] [%(threadName)s] %(levelname)s: %(message)s")
