"""Inline keyboards + the four button colors.

Telegram Bot API 9.4 added a `style` field to InlineKeyboardButton with three
named values — primary (blue), success (green), danger (red). Omitting the field
renders the standard "default" look, which is visually distinct from primary.
We expose all four as button colors the user can pick from.
"""
from __future__ import annotations

from collections.abc import Iterable

from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# key -> (label shown in the picker, style sent to Telegram)
COLORS: dict[str, dict] = {
    "default": {"label": "⬜️ Default", "style": None},
    "primary": {"label": "🔵 Blue", "style": ButtonStyle.PRIMARY},
    "success": {"label": "🟢 Green", "style": ButtonStyle.SUCCESS},
    "danger": {"label": "🔴 Red", "style": ButtonStyle.DANGER},
}


def menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="➕ Create post", callback_data="new")]]
    )


def color_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=COLORS["primary"]["label"], callback_data="color:primary"),
                InlineKeyboardButton(text=COLORS["success"]["label"], callback_data="color:success"),
            ],
            [
                InlineKeyboardButton(text=COLORS["danger"]["label"], callback_data="color:danger"),
                InlineKeyboardButton(text=COLORS["default"]["label"], callback_data="color:default"),
            ],
        ]
    )


def more_keyboard() -> InlineKeyboardMarkup:
    """After a button is added: add another, or finish and publish."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add another button", callback_data="addbtn")],
            [InlineKeyboardButton(text="✅ Done — choose channel", callback_data="done")],
        ]
    )


def post_buttons(buttons: list[dict]) -> InlineKeyboardMarkup:
    """The buttons that go on the published post — one per row (single column).

    Each item is {"text": str, "url": str, "color": <COLORS key>}.
    """
    rows = []
    for b in buttons:
        style = COLORS.get(b.get("color", "default"), COLORS["default"])["style"]
        rows.append([InlineKeyboardButton(text=b["text"], url=b["url"], style=style)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def channels_keyboard(channels: Iterable) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=(c.title or str(c.chat_id))[:60], callback_data=f"pub:{c.chat_id}")]
        for c in channels
    ]
    rows.append([InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
