"""Logging structure pour Beaume."""
import logging
import logging.handlers
from beaume.config import paths


def get_logger(name: str = "beaume") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    paths.ensure_dirs()

    fh = logging.handlers.RotatingFileHandler(
        paths.LOGS / "beaume.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger
