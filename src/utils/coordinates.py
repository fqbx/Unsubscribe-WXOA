"""Screen rectangles on a reference device, scaled to the current display."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class ScaledRect:
    """Rectangle in reference pixels (top-left origin), scaled to current screen."""

    ref_width: int = 1264
    ref_height: int = 2800
    status_bar_height: int = 135
    coordinate_origin: str = "full_screen"  # full_screen | content
    x_left: int = 0
    x_right: int = 0
    y_top: int = 0
    y_bottom: int = 0

    @classmethod
    def from_dict(cls, data: dict, defaults: dict | None = None) -> "ScaledRect":
        defaults = defaults or {}
        ref = data.get("reference_resolution", defaults.get("reference_resolution", {}))
        return cls(
            ref_width=int(ref.get("width", 1264)),
            ref_height=int(ref.get("height", 2800)),
            status_bar_height=int(data.get("status_bar_height", 135)),
            coordinate_origin=str(data.get("coordinate_origin", "full_screen")),
            x_left=int(data.get("x_left", 0)),
            x_right=int(data.get("x_right", 0)),
            y_top=int(data.get("y_top", 0)),
            y_bottom=int(data.get("y_bottom", 0)),
        )

    def _scale_x(self, x: int, screen_w: int) -> int:
        return int(x * screen_w / self.ref_width)

    def _scale_y(self, y: int, screen_h: int) -> int:
        if self.coordinate_origin == "content":
            ref_content_h = self.ref_height - self.status_bar_height
            screen_bar = int(self.status_bar_height * screen_h / self.ref_height)
            screen_content_h = screen_h - screen_bar
            y_in_content = y - self.status_bar_height
            return screen_bar + int(y_in_content * screen_content_h / ref_content_h)
        return int(y * screen_h / self.ref_height)

    def center_on_screen(self, screen_w: int, screen_h: int) -> Tuple[int, int]:
        cx = int((self._scale_x(self.x_left, screen_w) + self._scale_x(self.x_right, screen_w)) / 2)
        cy = int((self._scale_y(self.y_top, screen_h) + self._scale_y(self.y_bottom, screen_h)) / 2)
        return cx, cy

    def scaled_bounds(self, screen_w: int, screen_h: int) -> Tuple[int, int, int, int]:
        return (
            self._scale_x(self.x_left, screen_w),
            self._scale_y(self.y_top, screen_h),
            self._scale_x(self.x_right, screen_w),
            self._scale_y(self.y_bottom, screen_h),
        )

    def as_ratios(self) -> dict:
        """Relative ratios on reference resolution (for config documentation)."""
        return {
            "x_left_ratio": round(self.x_left / self.ref_width, 4),
            "x_right_ratio": round(self.x_right / self.ref_width, 4),
            "y_top_ratio": round(self.y_top / self.ref_height, 4),
            "y_bottom_ratio": round(self.y_bottom / self.ref_height, 4),
        }


@dataclass(frozen=True)
class FirstItemRect(ScaledRect):
    """First list row on the official-accounts page."""

    @classmethod
    def from_dict(cls, data: dict) -> "FirstItemRect":
        ref = data.get("reference_resolution", {})
        item = data.get("first_item", {})
        return cls(
            ref_width=int(ref.get("width", 1264)),
            ref_height=int(ref.get("height", 2800)),
            x_left=int(item.get("x_left", 0)),
            x_right=int(item.get("x_right", 1264)),
            y_top=int(item.get("y_top", 350)),
            y_bottom=int(item.get("y_bottom", 550)),
        )


@dataclass(frozen=True)
class ConfirmDialogCoords:
    """Center confirmation dialog after tapping the first「不再关注」."""

    dialog: ScaledRect
    unfollow_button: ScaledRect
    ref_width: int = 1264
    ref_height: int = 2800
    status_bar_height: int = 135
    coordinate_origin: str = "content"

    @classmethod
    def from_dict(cls, data: dict) -> "ConfirmDialogCoords":
        if not data:
            data = {
                "reference_resolution": {"width": 1264, "height": 2800},
                "status_bar_height": 135,
                "coordinate_origin": "content",
                "dialog": {
                    "x_left": 130,
                    "x_right": 1134,
                    "y_top": 1725,
                    "y_bottom": 2100,
                },
                "unfollow_button": {
                    "x_left": 632,
                    "x_right": 1134,
                    "y_top": 1536,
                    "y_bottom": 1727,
                },
            }
        ref = data.get("reference_resolution", {})
        ref_w = int(ref.get("width", 1264))
        ref_h = int(ref.get("height", 2800))
        bar = int(data.get("status_bar_height", 135))
        origin = str(data.get("coordinate_origin", "content"))
        base = {
            "reference_resolution": {"width": ref_w, "height": ref_h},
            "status_bar_height": bar,
            "coordinate_origin": origin,
        }
        dialog_data = {**base, **data.get("dialog", {})}
        button_data = {**base, **data.get("unfollow_button", {})}
        return cls(
            ref_width=ref_w,
            ref_height=ref_h,
            status_bar_height=bar,
            coordinate_origin=origin,
            dialog=ScaledRect.from_dict(dialog_data),
            unfollow_button=ScaledRect.from_dict(button_data),
        )
