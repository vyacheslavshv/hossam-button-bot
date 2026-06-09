from __future__ import annotations

import json

from sqlalchemy import func, select

from db import session_scope
from models import Channel, Post


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


# --------------------------------------------------------------- saved posts

async def save_post(
    *,
    user_id: int,
    content_chat_id: int,
    content_message_id: int,
    buttons: list[dict],
    label: str,
) -> int:
    async with session_scope() as s:
        p = Post(
            user_id=user_id,
            content_chat_id=content_chat_id,
            content_message_id=content_message_id,
            buttons_json=json.dumps(buttons, ensure_ascii=False),
            label=label or "",
        )
        s.add(p)
        await s.flush()
        return p.id


async def count_posts(user_id: int) -> int:
    async with session_scope() as s:
        res = await s.execute(
            select(func.count()).select_from(Post).where(Post.user_id == user_id)
        )
        return int(res.scalar_one())


async def list_posts(user_id: int, *, limit: int, offset: int) -> list[Post]:
    async with session_scope() as s:
        res = await s.execute(
            select(Post)
            .where(Post.user_id == user_id)
            .order_by(Post.created_at.desc(), Post.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(res.scalars().all())


async def get_post(post_id: int, user_id: int) -> Post | None:
    async with session_scope() as s:
        p = await s.get(Post, post_id)
        return p if (p is not None and p.user_id == user_id) else None


async def delete_post(post_id: int, user_id: int) -> bool:
    async with session_scope() as s:
        p = await s.get(Post, post_id)
        if p is None or p.user_id != user_id:
            return False
        await s.delete(p)
        return True
