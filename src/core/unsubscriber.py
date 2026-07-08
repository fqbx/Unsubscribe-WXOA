"""Unfollow one official account via long-press on the 公众号 list page.

Prerequisite: user has manually opened WeChat 公众号 list page.

Flow:
  1. Long-press first row.
  2. Tap floating「不再关注」popup (geometry near long-press point).
  3. Tap「不再关注」on the center confirmation dialog (coordinate rect).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import uiautomator2 as u2

from src.selectors import wechat as sel
from src.utils.coordinates import ConfirmDialogCoords, FirstItemRect
from src.utils.delays import human_delay
from src.utils.logger import get_logger

logger = get_logger()


@dataclass
class TouchPoint:
    x: int
    y: int
    name: str = ""


class Unsubscriber:
    """Unfollow one official account on the 公众号 list page."""

    def __init__(
        self,
        device: u2.Device,
        first_item: FirstItemRect,
        confirm_dialog: ConfirmDialogCoords,
        max_retries: int = 3,
        click_timeout: float = 5.0,
        long_press_duration: float = 1.5,
        popup_width: int = 160,
        popup_height: int = 72,
        should_stop: Optional[Callable[[], bool]] = None,
        pause_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.d = device
        self.first_item = first_item
        self.confirm_dialog = confirm_dialog
        self.max_retries = max_retries
        self.click_timeout = click_timeout
        self.long_press_duration = long_press_duration
        self.popup_width = popup_width
        self.popup_height = popup_height
        self.should_stop = should_stop or (lambda: False)
        self.pause_check = pause_check or (lambda: False)

    def _click_text_variants(
        self, texts: List[str], timeout: Optional[float] = None
    ) -> bool:
        timeout = timeout or self.click_timeout
        for text in texts:
            if self.should_stop():
                return False
            obj = self.d(text=text)
            if obj.wait(timeout=timeout):
                obj.click()
                return True
        return False

    def _dismiss_popups(self) -> None:
        for text in sel.DISMISS_POPUP:
            if self.should_stop():
                return
            self.d(text=text).click_exists(timeout=0.3)

    def _long_press_at(self, x: int, y: int) -> None:
        logger.info(f"Long-press at ({x}, {y}) for {self.long_press_duration}s")
        self.d.long_click(x, y, self.long_press_duration)

    def _first_item_position(self) -> TouchPoint:
        w, h = self.d.window_size()
        x, y = self.first_item.center_on_screen(w, h)
        bounds = self.first_item.scaled_bounds(w, h)
        logger.info(
            f"Step1 first item: x={bounds[0]}-{bounds[2]}, "
            f"y={bounds[1]}-{bounds[3]}, center=({x}, {y})"
        )
        return TouchPoint(x, y)

    def long_press_first_account(self) -> Tuple[bool, TouchPoint]:
        self._dismiss_popups()
        touch = self._first_item_position()
        self._long_press_at(touch.x, touch.y)
        human_delay(0.8, 1.2, self.should_stop, self.pause_check)
        return True, touch

    def _popup_click_position(self, touch: TouchPoint) -> Tuple[int, int]:
        w, _ = self.d.window_size()
        mid_x = w // 2
        half_w = self.popup_width // 2
        half_h = self.popup_height // 2
        if touch.x < mid_x:
            return touch.x - half_w, touch.y - half_h
        return touch.x + half_w, touch.y - half_h

    def _click_unfollow_popup(self, touch: TouchPoint) -> bool:
        """Step 2: tap floating「不再关注」after long-press."""
        human_delay(0.3, 0.6, self.should_stop, self.pause_check)

        if self._click_text_variants(sel.UNFOLLOW_BUTTON, timeout=1):
            logger.info("Step2 popup: clicked via text")
            return True
        if self.d(textContains="不再关注").click_exists(timeout=1):
            logger.info("Step2 popup: clicked via textContains")
            return True

        click_x, click_y = self._popup_click_position(touch)
        self.d.click(click_x, click_y)
        logger.info(f"Step2 popup: tap at ({click_x}, {click_y})")
        return True

    def _click_confirm_dialog(self) -> bool:
        """Step 3: tap「不再关注」on center confirmation dialog."""
        human_delay(0.6, 1.0, self.should_stop, self.pause_check)

        w, h = self.d.window_size()
        btn = self.confirm_dialog.unfollow_button
        dialog = self.confirm_dialog.dialog

        dialog_bounds = dialog.scaled_bounds(w, h)
        btn_bounds = btn.scaled_bounds(w, h)
        click_x, click_y = btn.center_on_screen(w, h)

        logger.info(
            f"Step3 confirm dialog bounds: x={dialog_bounds[0]}-{dialog_bounds[2]}, "
            f"y={dialog_bounds[1]}-{dialog_bounds[3]} "
            f"(ratios {dialog.as_ratios()})"
        )
        logger.info(
            f"Step3 unfollow button bounds: x={btn_bounds[0]}-{btn_bounds[2]}, "
            f"y={btn_bounds[1]}-{btn_bounds[3]} "
            f"(ratios {btn.as_ratios()})"
        )
        logger.info(f"Step3 tap confirm「不再关注」at ({click_x}, {click_y})")

        if self._click_text_variants(sel.CONFIRM_UNFOLLOW, timeout=1):
            return True

        self.d.click(click_x, click_y)
        return True

    def unsubscribe_one(self, touch: TouchPoint) -> bool:
        if not self._click_unfollow_popup(touch):
            logger.warning("Step2 popup failed")
            return False

        if not self._click_confirm_dialog():
            logger.warning("Step3 confirm dialog failed")
            return False

        human_delay(0.8, 1.5, self.should_stop, self.pause_check)
        return True

    def unsubscribe_with_retry(self) -> Tuple[bool, str]:
        pressed, touch = self.long_press_first_account()
        if not pressed:
            return False, "list_empty"

        for attempt in range(1, self.max_retries + 1):
            if self.should_stop():
                return False, "stopped"

            logger.info(f"Unfollow attempt {attempt}/{self.max_retries}")
            if self.unsubscribe_one(touch):
                logger.info("Unfollow success")
                self._dismiss_popups()
                return True, "ok"

            logger.warning(f"Unfollow failed (attempt {attempt}/{self.max_retries})")
            human_delay(1.0, 2.0, self.should_stop, self.pause_check)

            if attempt < self.max_retries:
                pressed, touch = self.long_press_first_account()
                if not pressed:
                    break

        self._dismiss_popups()
        return False, "failed"
