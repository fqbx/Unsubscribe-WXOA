"""Logging setup using loguru."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Optional

from loguru import logger


def setup_logger(
    log_dir: str | Path = "logs",
    level: str = "INFO",
    log_callback: Optional[Callable[[str], None]] = None,
) -> None:
    """Configure loguru for file + console output and optional GUI callback."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logger.remove()

    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    )

    logger.add(
        log_path / "app_{time:YYYY-MM-DD}.log",
        level=level,
        rotation="00:00",
        retention="14 days",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    )

    if log_callback is not None:
        def _sink(message) -> None:
            record = message.record
            formatted = f"{record['time'].strftime('%H:%M:%S')} {record['message']}"
            log_callback(formatted)

        logger.add(_sink, level=level, format="{message}")


def get_logger():
    """Return the configured loguru logger."""
    return logger
