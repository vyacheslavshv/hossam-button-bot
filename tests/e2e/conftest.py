"""E2E infra — drives the real bot via Telethon user accounts.

External pattern: the bot must already be running (`python main.py`) with the
same BOT_TOKEN. We only drive it from Telethon here; we do NOT spawn it (that
would double-poll the token and crash).

The `test_channel` fixture creates a throwaway broadcast channel, promotes the
bot to admin (post + pin), and deletes it on teardown. Promoting the bot also
exercises the bot's `my_chat_member` channel-tracking.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import CreateChannelRequest, DeleteChannelRequest

ROOT = Path(__file__).parent.parent.parent
load_dotenv(ROOT / ".env.test")

_REQUIRED = (
    "TELETHON_API_ID",
    "TELETHON_API_HASH",
    "TELETHON_SESSION_STRING",
    "TEST_BOT_USERNAME",
)


@pytest.fixture(scope="session", autouse=True)
def _e2e_env_gate() -> None:
    missing = [k for k in _REQUIRED if not os.environ.get(k)]
    if missing:
        pytest.skip(
            f"E2E skipped: missing env {', '.join(missing)}. "
            f"cp ~/.claude/secrets/telegram-e2e.env {ROOT}/.env.test and add "
            "TEST_BOT_USERNAME + BOT_TOKEN.",
            allow_module_level=True,
        )


@pytest_asyncio.fixture(scope="session")
async def tg_client() -> TelegramClient:
    """Primary account (@vyatg) — admin/owner role."""
    client = TelegramClient(
        StringSession(os.environ["TELETHON_SESSION_STRING"]),
        int(os.environ["TELETHON_API_ID"]),
        os.environ["TELETHON_API_HASH"],
    )
    await client.connect()
    if not await client.is_user_authorized():
        pytest.fail("TELETHON_SESSION_STRING is not authorized.")
    try:
        yield client
    finally:
        await client.disconnect()


@pytest_asyncio.fixture(scope="session")
async def tg_user_client() -> TelegramClient:
    """Secondary account (@vyapl) — plain user."""
    raw = os.environ.get("TELETHON_SESSION_STRING_2", "").strip()
    if not raw:
        pytest.skip("TELETHON_SESSION_STRING_2 not configured")
    client = TelegramClient(
        StringSession(raw),
        int(os.environ["TELETHON_API_ID"]),
        os.environ["TELETHON_API_HASH"],
    )
    await client.connect()
    if not await client.is_user_authorized():
        pytest.fail("TELETHON_SESSION_STRING_2 is not authorized.")
    try:
        yield client
    finally:
        await client.disconnect()


@pytest.fixture(scope="session")
def test_bot_username() -> str:
    return os.environ["TEST_BOT_USERNAME"]


async def _warm_peer(client: TelegramClient, username: str) -> None:
    last_err: Exception | None = None
    for _ in range(8):
        try:
            async for _ in client.iter_dialogs():
                pass
            await client.get_entity(username)
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            await asyncio.sleep(0.5)
    pytest.fail(f"Could not resolve {username}: {last_err}")


@pytest_asyncio.fixture
async def _wait_for_bot(tg_client, test_bot_username):
    await _warm_peer(tg_client, test_bot_username)


@pytest_asyncio.fixture
async def _wait_for_bot_from_user(tg_user_client, test_bot_username):
    await _warm_peer(tg_user_client, test_bot_username)


@pytest_asyncio.fixture(scope="session")
async def test_channel(tg_client, test_bot_username):
    """A throwaway broadcast channel with the bot promoted to admin (post + pin)."""
    created = await tg_client(
        CreateChannelRequest(title="ButtonBot E2E", about="e2e test", megagroup=False)
    )
    channel = created.chats[0]
    bot = await tg_client.get_entity(test_bot_username)
    await tg_client.edit_admin(
        channel,
        bot,
        is_admin=True,
        post_messages=True,
        edit_messages=True,
        delete_messages=True,
        pin_messages=True,
        change_info=True,
        invite_users=True,
        add_admins=False,
        manage_call=False,
        title="bot",
    )
    # let the bot's poller receive + store the my_chat_member update
    await asyncio.sleep(4)
    try:
        yield channel
    finally:
        try:
            await tg_client(DeleteChannelRequest(channel))
        except Exception:  # noqa: BLE001
            pass


@pytest.fixture(scope="session")
def sample_photo(tmp_path_factory) -> str:
    from PIL import Image

    path = tmp_path_factory.mktemp("media") / "post.png"
    Image.new("RGB", (480, 320), (33, 99, 200)).save(path)
    return str(path)
