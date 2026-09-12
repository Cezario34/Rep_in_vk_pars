from __future__ import annotations

import logging
from logging import Logger
from pathlib import Path

DEFAULT_FORMAT = "[{asctime}] #{levelname:8} {filename} - {lineno} - {message}"
DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    name: str = "mailing",
    log_file: str | Path = "logs.log",
    level: int = logging.INFO,
) -> Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATEFMT, style="{")

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger