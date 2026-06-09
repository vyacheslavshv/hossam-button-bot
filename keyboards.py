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


def post_button(text: str, url: str, color: str) -> InlineKeyboardMarkup:
    """The single big button that goes on the published post."""
    style = COLORS.get(color, COLORS["default"])["style"]
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, url=url, style=style)]]
    )


def channels_keyboard(channels: Iterable) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=(c.title or str(c.chat_id))[:60], callback_data=f"pub:{c.chat_id}")]
        for c in channels
    ]
    rows.append([InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
