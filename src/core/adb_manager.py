"""ADB device detection, uiautomator2 connection, and health checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import adbutils
import uiautomator2 as u2

from src.utils.logger import get_logger

logger = get_logger()


@dataclass
class DeviceInfo:
    serial: str
    model: str
    status: str

    @property
    def display_name(self) -> str:
        return f"{self.model} ({self.serial})"


class ADBManager:
    """Manage ADB device discovery and uiautomator2 connections."""

    def __init__(self) -> None:
        self._adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
        self._device: Optional[u2.Device] = None
        self._connected_serial: Optional[str] = None

    @property
    def device(self) -> Optional[u2.Device]:
        return self._device

    @property
    def connected_serial(self) -> Optional[str]:
        return self._connected_serial

    @property
    def is_connected(self) -> bool:
        return self._device is not None

    def list_devices(self) -> List[DeviceInfo]:
        """Return all ADB devices currently visible."""
        devices: List[DeviceInfo] = []
        try:
            for dev in self._adb.device_list():
                model = "Unknown"
                try:
                    model = dev.shell("getprop ro.product.model").strip() or "Unknown"
                except Exception:
                    pass
                devices.append(
                    DeviceInfo(serial=dev.serial, model=model, status="device")
                )
        except Exception as exc:
            logger.error(f"Failed to list ADB devices: {exc}")
        return devices

    def connect(self, serial: Optional[str] = None) -> u2.Device:
        """Connect to a device via uiautomator2.

        Args:
            serial: Device serial. If None, uses the first available device.

        Raises:
            RuntimeError: If no device is found or connection fails.
        """
        devices = self.list_devices()
        if not devices:
            raise RuntimeError(
                "No ADB devices found. Ensure USB debugging is enabled and "
                "the phone is connected. Run 'adb devices' to verify."
            )

        target_serial = serial or devices[0].serial
        logger.info(f"Connecting to device {target_serial} via uiautomator2...")

        try:
            self._device = u2.connect(target_serial)
            self._connected_serial = target_serial
        except Exception as exc:
            self._device = None
            self._connected_serial = None
            raise RuntimeError(
                f"uiautomator2 connection failed: {exc}\n\n"
                "First-time setup: run 'python -m uiautomator2 init' with the "
                "phone connected to install the uiautomator agent."
            ) from exc

        logger.info(f"Connected to {target_serial}")
        return self._device

    def health_check(self) -> dict:
        """Run basic health checks on the connected device.

        Returns:
            Dict with check results: ok (bool), message (str), details (dict).
        """
        if not self._device:
            return {
                "ok": False,
                "message": "Not connected",
                "details": {},
            }

        details: dict = {}
        issues: List[str] = []

        try:
            info = self._device.info
            details["screen_on"] = info.get("screenOn", False)
            details["current_package"] = info.get("currentPackageName", "")
            if not details["screen_on"]:
                issues.append("Screen is off — unlock the phone before running.")
        except Exception as exc:
            issues.append(f"Cannot read device info: {exc}")

        try:
            self._device.shell("echo ok", timeout=5)
            details["shell_ok"] = True
        except Exception as exc:
            details["shell_ok"] = False
            issues.append(f"Shell command failed: {exc}")

        try:
            agent_alive = self._device.uiautomator.running()
            details["uiautomator_running"] = agent_alive
            if not agent_alive:
                issues.append(
                    "uiautomator agent not running. Run: python -m uiautomator2 init"
                )
        except Exception:
            details["uiautomator_running"] = None

        ok = len(issues) == 0
        message = "Device healthy" if ok else "; ".join(issues)
        return {"ok": ok, "message": message, "details": details}

    def disconnect(self) -> None:
        """Release the current connection."""
        self._device = None
        self._connected_serial = None
        logger.info("Disconnected from device")

    @staticmethod
    def init_guidance() -> str:
        """Return first-time setup instructions for the user."""
        return (
            "First-time setup:\n"
            "1. Enable Developer Options + USB debugging on your Android phone\n"
            "2. Connect via USB and accept the debugging authorization prompt\n"
            "3. Install ADB (Android Platform Tools) and add to PATH\n"
            "4. Run: python -m uiautomator2 init\n"
            "5. Keep the phone unlocked with screen on during automation\n"
            "6. Disable MIUI/Huawei USB debugging security restrictions if present"
        )
