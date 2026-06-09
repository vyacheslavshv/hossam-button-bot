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


POSTS_PER_PAGE = 5


def menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Create post", callback_data="new")],
            [InlineKeyboardButton(text="📋 My posts", callback_data="list")],
        ]
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


def saved_posts_keyboard(posts: Iterable, page: int, total: int) -> InlineKeyboardMarkup:
    """A page of saved posts (one per row) + prev/next nav when there's more than one page."""
    rows = [
        [InlineKeyboardButton(text=(p.label or f"Post {p.id}")[:60], callback_data=f"post:open:{p.id}")]
        for p in posts
    ]
    total_pages = max(1, (total + POSTS_PER_PAGE - 1) // POSTS_PER_PAGE)
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"post:page:{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="post:noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"post:page:{page + 1}"))
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def post_detail_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📤 Publish", callback_data=f"post:pub:{post_id}")],
            [InlineKeyboardButton(text="🗑 Delete", callback_data=f"post:del:{post_id}")],
            [InlineKeyboardButton(text="⬅️ Back to list", callback_data="post:page:0")],
        ]
    )


def delete_confirm_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Yes, delete", callback_data=f"post:delok:{post_id}")],
            [InlineKeyboardButton(text="⬅️ Cancel", callback_data=f"post:open:{post_id}")],
        ]
    )
