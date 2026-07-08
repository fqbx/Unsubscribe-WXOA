"""Random human-like delay utilities."""

from __future__ import annotations

import random
import time
from typing import Callable, Optional, Tuple


def human_delay(
    min_seconds: float = 1.5,
    max_seconds: float = 3.0,
    should_stop: Optional[Callable[[], bool]] = None,
    pause_check: Optional[Callable[[], bool]] = None,
) -> None:
    """Sleep for a random duration within the given range.

    Optionally checks stop/pause callbacks in small increments so the caller
    can abort or wait out a pause without blocking the full delay.
    """
    duration = random.uniform(min_seconds, max_seconds)
    elapsed = 0.0
    step = 0.1

    while elapsed < duration:
        if should_stop and should_stop():
            return
        if pause_check and pause_check():
            time.sleep(step)
            continue

        remaining = duration - elapsed
        sleep_for = min(step, remaining)
        time.sleep(sleep_for)
        elapsed += sleep_for


def delay_range_from_config(config: dict) -> Tuple[float, float]:
    """Extract (min, max) delay seconds from a config dict."""
    delays = config.get("delays", {})
    return (
        float(delays.get("min_seconds", 1.5)),
        float(delays.get("max_seconds", 3.0)),
    )
