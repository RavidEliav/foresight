"""Logging to the console (Railway deploy logs) and to logs/run_<id>.log."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

LOGGER_NAME = "foresight"
_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}" if name else LOGGER_NAME)


def setup_logging(log_dir: Path | None = None, run_id: str | None = None) -> Path | None:
    """Configure the package logger. Returns the run log file path when one is created."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter(_FORMAT)

    if not any(getattr(h, "_foresight_console", False) for h in logger.handlers):
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        console._foresight_console = True
        logger.addHandler(console)

    for handler in [h for h in logger.handlers if isinstance(h, logging.FileHandler)]:
        logger.removeHandler(handler)
        handler.close()

    if log_dir is None or run_id is None:
        return None
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"run_{run_id}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return log_file
