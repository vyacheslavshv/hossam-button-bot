from __future__ import annotations

from sqlalchemy import select

from db import session_scope
from models import Channel


async def upsert_channel(
    *,
    chat_id: int,
    title: str,
    type_: str,
    added_by: int,
    can_post: bool,
    can_pin: bool,
    active: bool = True,
) -> None:
    async with session_scope() as s:
        ch = await s.get(Channel, chat_id)
        if ch is None:
            ch = Channel(chat_id=chat_id)
            s.add(ch)
        if title:
            ch.title = title
        if type_:
            ch.type = type_
        if added_by:
            ch.added_by = added_by
        ch.can_post = can_post
        ch.can_pin = can_pin
        ch.active = active


async def deactivate_channel(chat_id: int) -> None:
    async with session_scope() as s:
        ch = await s.get(Channel, chat_id)
        if ch is not None:
            ch.active = False


async def list_channels(added_by: int) -> list[Channel]:
    """Active chats the given user added the bot to where the bot can post."""
    async with session_scope() as s:
        res = await s.execute(
            select(Channel)
            .where(
                Channel.added_by == added_by,
                Channel.active.is_(True),
                Channel.can_post.is_(True),
            )
            .order_by(Channel.title)
        )
        return list(res.scalars().all())


async def get_channel(chat_id: int) -> Channel | None:
    async with session_scope() as s:
        return await s.get(Channel, chat_id)
