"""Polling-based Telethon helpers (from the telegram-e2e skill template)."""
from __future__ import annotations

import asyncio
import time
from typing import Any

from telethon import TelegramClient
from telethon.tl.custom import Message


def find_button(message: Message, substring: str) -> Any:
    if message.buttons is None:
        raise AssertionError(
            f"message has no inline keyboard: {(message.message or '')[:80]!r}"
        )
    for row in message.buttons:
        for btn in row:
            if substring.lower() in (btn.text or "").lower():
                return btn
    available = [b.text for row in message.buttons for b in row]
    raise AssertionError(f"button containing {substring!r} not found. Available: {available}")


def button_texts(message: Message) -> list[str]:
    if message.buttons is None:
        return []
    return [b.text for row in message.buttons for b in row]


async def wait_for_reply(
    client: TelegramClient, peer: Any, after_id: int, *, timeout: float = 20.0
) -> Message:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        async for m in client.iter_messages(peer, limit=6):
            if m.id > after_id and not m.out:
                return m
        await asyncio.sleep(0.3)
    raise TimeoutError(f"no new message from peer after id {after_id} within {timeout}s")


async def send_and_wait(
    client: TelegramClient, peer: Any, text: str, *, timeout: float = 20.0
) -> Message:
    sent = await client.send_message(peer, text)
    return await wait_for_reply(client, peer, sent.id, timeout=timeout)


async def send_file_and_wait(
    client: TelegramClient, peer: Any, file: Any, *, timeout: float = 20.0
) -> Message:
    sent = await client.send_file(peer, file, force_document=False)
    return await wait_for_reply(client, peer, sent.id, timeout=timeout)


async def latest_msg_id(client: TelegramClient, peer: Any) -> int:
    async for m in client.iter_messages(peer, limit=1):
        return m.id
    return 0


async def wait_for_msg_with_button(
    client: TelegramClient, peer: Any, substring: str, *, after_id: int = 0, timeout: float = 25.0
) -> Message:
    """Wait for a message (newer than after_id) whose inline keyboard contains a
    button matching `substring`. Used when the bot pushes several messages at once
    (e.g. a preview + a channel picker) and we want a specific one."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        async for m in client.iter_messages(peer, limit=8):
            if m.id <= after_id or not m.buttons:
                continue
            for row in m.buttons:
                for b in row:
                    if substring.lower() in (b.text or "").lower():
                        return m
        await asyncio.sleep(0.3)
    raise TimeoutError(f"no message with button {substring!r} after id {after_id} within {timeout}s")
