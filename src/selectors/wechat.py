"""Text/XPath selectors used by the unfollow popup flow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class TextSelectors:
    unfollow_button: List[str] = field(
        default_factory=lambda: ["不再关注", "Unfollow"]
    )
    confirm_unfollow: List[str] = field(
        default_factory=lambda: ["不再关注", "确定", "确认", "OK", "Unfollow"]
    )
    dismiss_popup: List[str] = field(
        default_factory=lambda: [
            "取消", "知道了", "暂不", "以后再说", "Close", "Cancel",
        ]
    )


@dataclass(frozen=True)
class XPathSelectors:
    menu_unfollow: str = (
        '//*[@text="不再关注"]'
        ' | //*[@text="Unfollow"]'
        ' | //*[@textContains="不再关注"]'
    )


TEXT = TextSelectors()
XPATH = XPathSelectors()
UNFOLLOW_BUTTON = TEXT.unfollow_button
CONFIRM_UNFOLLOW = TEXT.confirm_unfollow
DISMISS_POPUP = TEXT.dismiss_popup
