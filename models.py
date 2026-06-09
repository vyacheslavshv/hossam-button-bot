from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Channel(Base):
    """A channel/group the bot can publish to.

    Telegram bots cannot enumerate the chats they belong to, so we persist every
    chat where the bot is made an admin. Rows are created/updated from
    `my_chat_member` updates and from the manual "forward a message / send the
    @username" fallback. `added_by` scopes the publish picker to the user who
    actually added the bot, so a stranger who finds the bot can't post into
    someone else's channel.
    """

    __tablename__ = "channels"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String, default="")
    type: Mapped[str] = mapped_column(String, default="")  # channel / supergroup / group
    added_by: Mapped[int] = mapped_column(BigInteger, default=0, index=True)
    can_post: Mapped[bool] = mapped_column(Boolean, default=True)
    can_pin: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Post(Base):
    """A saved post the user built. We don't store the media itself — just a
    reference to the user's original message in their private chat with the bot
    (which they keep), plus the buttons. Re-publishing copies from that message.
    """

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    content_chat_id: Mapped[int] = mapped_column(BigInteger)
    content_message_id: Mapped[int] = mapped_column(BigInteger)
    buttons_json: Mapped[str] = mapped_column(Text, default="[]")
    label: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
