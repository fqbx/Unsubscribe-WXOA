"""Automation controller with state machine, batch loop, and error handling."""

from __future__ import annotations

import enum
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from src.core.adb_manager import ADBManager
from src.core.unsubscriber import Unsubscriber
from src.utils.coordinates import ConfirmDialogCoords, FirstItemRect
from src.utils.delays import human_delay
from src.utils.logger import get_logger

logger = get_logger()


class ControllerState(enum.Enum):
    IDLE = "IDLE"
    CONNECTING = "CONNECTING"
    NAVIGATING = "NAVIGATING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


@dataclass
class BatchProgress:
    total: int = 0
    current: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    current_account: str = ""
    message: str = ""


@dataclass
class ControllerConfig:
    delay_min: float = 1.5
    delay_max: float = 3.0
    max_count: int = 30
    max_retries: int = 3
    consecutive_fail_limit: int = 5
    click_timeout: float = 5.0
    screenshots_enabled: bool = True
    screenshot_dir: str = "logs/screenshots"
    long_press_duration: float = 1.5
    popup_width: int = 160
    popup_height: int = 72
    first_item: Optional[FirstItemRect] = None
    confirm_dialog: Optional[ConfirmDialogCoords] = None

    @classmethod
    def from_dict(cls, data: dict) -> "ControllerConfig":
        delays = data.get("delays", {})
        batch = data.get("batch", {})
        screenshots = data.get("screenshots", {})
        unfollow = data.get("unfollow", {})
        first_item = FirstItemRect.from_dict(data.get("first_item", {}))
        confirm_dialog = ConfirmDialogCoords.from_dict(data.get("confirm_dialog", {}))
        return cls(
            delay_min=float(delays.get("min_seconds", 1.5)),
            delay_max=float(delays.get("max_seconds", 3.0)),
            max_count=int(batch.get("max_count", 30)),
            max_retries=int(batch.get("max_retries", 3)),
            consecutive_fail_limit=int(batch.get("consecutive_fail_limit", 5)),
            click_timeout=float(delays.get("click_timeout", 5)),
            screenshots_enabled=bool(screenshots.get("enabled", True)),
            screenshot_dir=str(screenshots.get("directory", "logs/screenshots")),
            long_press_duration=float(unfollow.get("long_press_duration", 1.5)),
            popup_width=int(unfollow.get("popup_width", 160)),
            popup_height=int(unfollow.get("popup_height", 72)),
            first_item=first_item,
            confirm_dialog=confirm_dialog,
        )


@dataclass
class ControllerCallbacks:
    on_state_change: Optional[Callable[[ControllerState, str], None]] = None
    on_progress: Optional[Callable[[BatchProgress], None]] = None
    on_log: Optional[Callable[[str], None]] = None


class AutomationController:
    """Orchestrate device connection, navigation, and batch unsubscribe."""

    def __init__(
        self,
        config: Optional[ControllerConfig] = None,
        callbacks: Optional[ControllerCallbacks] = None,
    ) -> None:
        self.config = config or ControllerConfig()
        self.callbacks = callbacks or ControllerCallbacks()
        self.adb = ADBManager()

        self._state = ControllerState.IDLE
        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # not paused initially
        self._worker: Optional[threading.Thread] = None
        self._progress = BatchProgress()

    @property
    def state(self) -> ControllerState:
        with self._state_lock:
            return self._state

    @property
    def progress(self) -> BatchProgress:
        return self._progress

    def _set_state(self, state: ControllerState, message: str = "") -> None:
        with self._state_lock:
            self._state = state
        logger.info(f"State -> {state.value}: {message}")
        if self.callbacks.on_state_change:
            self.callbacks.on_state_change(state, message)

    def _update_progress(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if hasattr(self._progress, key):
                setattr(self._progress, key, value)
        if self.callbacks.on_progress:
            self.callbacks.on_progress(self._progress)

    def _should_stop(self) -> bool:
        return self._stop_event.is_set()

    def _pause_check(self) -> bool:
        return not self._pause_event.is_set()

    def _wait_if_paused(self) -> None:
        while not self._pause_event.is_set():
            if self._should_stop():
                return
            time.sleep(0.1)

    def pause(self) -> None:
        if self.state == ControllerState.RUNNING:
            self._pause_event.clear()
            self._set_state(ControllerState.PAUSED, "Paused by user")

    def resume(self) -> None:
        if self.state == ControllerState.PAUSED:
            self._pause_event.set()
            self._set_state(ControllerState.RUNNING, "Resumed")

    def stop(self) -> None:
        self._stop_event.set()
        self._pause_event.set()
        if self.state in (
            ControllerState.RUNNING,
            ControllerState.PAUSED,
            ControllerState.NAVIGATING,
            ControllerState.CONNECTING,
        ):
            self._set_state(ControllerState.STOPPED, "Stopped by user")

    def emergency_stop(self) -> None:
        """Immediate stop — same as stop() but logs explicitly."""
        logger.warning("Emergency stop triggered")
        self.stop()

    def list_devices(self):
        return self.adb.list_devices()

    def connect_device(self, serial: Optional[str] = None) -> bool:
        self._set_state(ControllerState.CONNECTING, "Connecting to device...")
        try:
            self.adb.connect(serial)
            health = self.adb.health_check()
            if not health["ok"]:
                logger.warning(f"Health check issues: {health['message']}")
            self._set_state(ControllerState.IDLE, "Connected")
            return True
        except Exception as exc:
            self._set_state(ControllerState.ERROR, str(exc))
            return False

    def _save_screenshot(self, label: str) -> Optional[str]:
        if not self.config.screenshots_enabled or not self.adb.device:
            return None
        try:
            screenshot_dir = Path(self.config.screenshot_dir)
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            filename = screenshot_dir / f"{label}_{int(time.time())}.png"
            self.adb.device.screenshot(str(filename))
            logger.info(f"Screenshot saved: {filename}")
            return str(filename)
        except Exception as exc:
            logger.error(f"Screenshot failed: {exc}")
            return None

    def start_batch(
        self,
        serial: Optional[str] = None,
        max_count: Optional[int] = None,
        delay_min: Optional[float] = None,
        delay_max: Optional[float] = None,
    ) -> None:
        if self._worker and self._worker.is_alive():
            logger.warning("Batch already running")
            return

        self._stop_event.clear()
        self._pause_event.set()
        self._progress = BatchProgress(
            total=max_count or self.config.max_count,
            message="Starting...",
        )
        self._update_progress()

        self._worker = threading.Thread(
            target=self._run_batch,
            args=(serial, max_count, delay_min, delay_max),
            daemon=True,
        )
        self._worker.start()

    def _run_batch(
        self,
        serial: Optional[str],
        max_count: Optional[int],
        delay_min: Optional[float],
        delay_max: Optional[float],
    ) -> None:
        count = max_count or self.config.max_count
        d_min = delay_min if delay_min is not None else self.config.delay_min
        d_max = delay_max if delay_max is not None else self.config.delay_max

        self._update_progress(total=count)

        try:
            if not self.adb.is_connected:
                if not self.connect_device(serial):
                    return

            device = self.adb.device
            if device is None:
                self._set_state(ControllerState.ERROR, "No device connected")
                return

            unsubscriber = Unsubscriber(
                device,
                first_item=self.config.first_item or FirstItemRect(),
                confirm_dialog=self.config.confirm_dialog or ConfirmDialogCoords.from_dict({}),
                max_retries=self.config.max_retries,
                click_timeout=self.config.click_timeout,
                long_press_duration=self.config.long_press_duration,
                popup_width=self.config.popup_width,
                popup_height=self.config.popup_height,
                should_stop=self._should_stop,
                pause_check=self._pause_check,
            )

            self._set_state(
                ControllerState.RUNNING,
                "请确保手机已在公众号列表页",
            )

            if self._should_stop():
                self._set_state(ControllerState.STOPPED, "Stopped before batch")
                return

            consecutive_fails = 0

            # 批量循环：长按第一条 → 点「不再关注」（不自动导航）
            for i in range(count):
                self._wait_if_paused()
                if self._should_stop():
                    self._set_state(ControllerState.STOPPED, f"Stopped at {i}/{count}")
                    return

                self._update_progress(
                    current=i + 1,
                    message=f"取关第 {i + 1}/{count} 个",
                )

                success, name = unsubscriber.unsubscribe_with_retry()

                if name == "list_empty":
                    self._update_progress(message="List empty — batch complete")
                    break

                if success:
                    consecutive_fails = 0
                    self._update_progress(
                        success=self._progress.success + 1,
                        current_account=name,
                        message=f"Unfollowed: {name}",
                    )
                else:
                    consecutive_fails += 1
                    self._save_screenshot(f"fail_{i + 1}")
                    self._update_progress(
                        failed=self._progress.failed + 1,
                        current_account=name,
                        message=f"Failed: {name}",
                    )
                    logger.warning(
                        f"Unfollow failed for {name!r} "
                        f"(consecutive fails: {consecutive_fails})"
                    )

                    if consecutive_fails >= self.config.consecutive_fail_limit:
                        self._set_state(
                            ControllerState.PAUSED,
                            f"Paused after {consecutive_fails} consecutive failures — "
                            "check WeChat UI and selectors",
                        )
                        self._pause_event.clear()
                        self._wait_if_paused()
                        if self._should_stop():
                            self._set_state(ControllerState.STOPPED, "Stopped after pause")
                            return
                        consecutive_fails = 0
                        self._pause_event.set()
                        self._set_state(ControllerState.RUNNING, "Resumed after pause")

                human_delay(
                    d_min, d_max, self._should_stop, self._pause_check
                )

            if self._should_stop():
                self._set_state(ControllerState.STOPPED, "Stopped")
            else:
                self._set_state(
                    ControllerState.COMPLETED,
                    f"Done: {self._progress.success} success, "
                    f"{self._progress.failed} failed",
                )

        except Exception as exc:
            logger.exception(f"Batch error: {exc}")
            self._save_screenshot("error")
            self._set_state(ControllerState.ERROR, str(exc))


def load_config(config_path: str | Path = "config/default.yaml") -> ControllerConfig:
    """Load controller config from YAML file."""
    path = Path(config_path)
    if not path.exists():
        logger.warning(f"Config not found at {path}, using defaults")
        return ControllerConfig()

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return ControllerConfig.from_dict(data)


def load_full_config(config_path: str | Path = "config/default.yaml") -> dict:
    """Load raw YAML config dict."""
    path = Path(config_path)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
