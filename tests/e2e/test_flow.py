"""End-to-end: build a post (photo + text) with one colored button, publish it
into a real channel, and confirm it's posted with a single button and pinned.

Owner = @vyatg (tg_client). The bot must be running with the test token.
"""
import asyncio

from telethon.tl.functions.channels import (
    CreateChannelRequest,
    DeleteChannelRequest,
    InviteToChannelRequest,
)
from telethon.tl.types import InputMessagesFilterPinned, MessageEntityBold

from tests.e2e._helpers import (
    button_texts,
    find_button,
    latest_msg_id,
    send_and_wait,
    send_file_and_wait,
    wait_for_msg_with_button,
    wait_for_reply,
)

CHANNEL_TITLE = "ButtonBot E2E"


async def test_start_shows_menu(tg_client, test_bot_username, _wait_for_bot):
    bot = await tg_client.get_entity(test_bot_username)
    home = await send_and_wait(tg_client, bot, "/start")
    assert "Post Builder" in home.message, home.message
    assert any("Create post" in t for t in button_texts(home)), button_texts(home)


async def test_bot_replies_to_any_user(tg_user_client, test_bot_username, _wait_for_bot_from_user):
    # the bot answers everyone (no admin gate) — a random message gets the menu
    bot = await tg_user_client.get_entity(test_bot_username)
    r = await send_and_wait(tg_user_client, bot, "hey there")
    assert any("Create post" in t for t in button_texts(r)), r.message


async def test_album_is_rejected(tg_client, test_bot_username, sample_photo, _wait_for_bot):
    bot = await tg_client.get_entity(test_bot_username)
    await send_and_wait(tg_client, bot, "/new")
    # send two photos as an album -> bot should refuse and stay on step 1
    sent = await tg_client.send_file(bot, [sample_photo, sample_photo])
    last = sent[-1] if isinstance(sent, list) else sent
    reply = await wait_for_reply(tg_client, bot, last.id)
    assert "album" in reply.message.lower(), reply.message
    await send_and_wait(tg_client, bot, "/cancel")


async def test_photo_post_published_and_pinned(
    tg_client, test_bot_username, test_channel, sample_photo, _wait_for_bot
):
    bot = await tg_client.get_entity(test_bot_username)

    await send_and_wait(tg_client, bot, "/new")
    label_prompt = await send_file_and_wait(tg_client, bot, sample_photo)
    assert "Button label" in label_prompt.message, label_prompt.message

    url_prompt = await send_and_wait(tg_client, bot, "Open Website")
    assert "Button link" in url_prompt.message, url_prompt.message

    color_prompt = await send_and_wait(tg_client, bot, "https://example.com")
    assert "color" in color_prompt.message.lower(), color_prompt.message

    # pick green -> bot pushes a preview AND a channel picker
    await find_button(color_prompt, "Green").click()
    picker = await wait_for_msg_with_button(tg_client, bot, CHANNEL_TITLE, after_id=color_prompt.id)

    after = await latest_msg_id(tg_client, bot)
    await find_button(picker, CHANNEL_TITLE).click()
    confirm = await wait_for_reply(tg_client, bot, after)
    assert "Published" in confirm.message and "pinned" in confirm.message.lower(), confirm.message

    posts = await tg_client.get_messages(test_channel, limit=5)
    post = next((m for m in posts if m.buttons), None)
    assert post is not None, "no message with a button in the channel"
    btns = [b for row in post.buttons for b in row]
    assert len(btns) == 1, f"expected exactly one button, got {len(btns)}"
    # Telegram may append a trailing slash to a bare-domain url
    assert btns[0].url.rstrip("/") == "https://example.com", btns[0].url
    assert post.photo is not None, "published post should carry the photo"

    pinned = await tg_client.get_messages(test_channel, limit=1, filter=InputMessagesFilterPinned())
    assert pinned and pinned[0].id == post.id, "the published post should be pinned"


async def test_text_post_published(tg_client, test_bot_username, test_channel, _wait_for_bot):
    bot = await tg_client.get_entity(test_bot_username)

    await send_and_wait(tg_client, bot, "/new")
    await send_and_wait(tg_client, bot, "Hello pinned world")   # content (text)
    await send_and_wait(tg_client, bot, "Join")                 # label
    color_prompt = await send_and_wait(tg_client, bot, "t.me/durov")  # link

    await find_button(color_prompt, "Blue").click()
    picker = await wait_for_msg_with_button(tg_client, bot, CHANNEL_TITLE, after_id=color_prompt.id)

    after = await latest_msg_id(tg_client, bot)
    await find_button(picker, CHANNEL_TITLE).click()
    confirm = await wait_for_reply(tg_client, bot, after)
    assert "Published" in confirm.message, confirm.message

    posts = await tg_client.get_messages(test_channel, limit=5)
    assert any("Hello pinned world" in (m.message or "") for m in posts), [m.message for m in posts]


async def test_formatted_caption_is_preserved(
    tg_client, test_bot_username, test_channel, sample_photo, _wait_for_bot
):
    # a photo with a bold caption -> the published post must keep the caption AND its formatting
    bot = await tg_client.get_entity(test_bot_username)
    await send_and_wait(tg_client, bot, "/new")
    sent = await tg_client.send_file(
        bot, sample_photo, caption="**Big sale** today", parse_mode="md"
    )
    label_prompt = await wait_for_reply(tg_client, bot, sent.id)
    assert "Button label" in label_prompt.message, label_prompt.message

    await send_and_wait(tg_client, bot, "Shop now")
    color_prompt = await send_and_wait(tg_client, bot, "https://example.com")
    await find_button(color_prompt, "Red").click()
    picker = await wait_for_msg_with_button(tg_client, bot, CHANNEL_TITLE, after_id=color_prompt.id)
    after = await latest_msg_id(tg_client, bot)
    await find_button(picker, CHANNEL_TITLE).click()
    confirm = await wait_for_reply(tg_client, bot, after)
    assert "Published" in confirm.message, confirm.message

    posts = await tg_client.get_messages(test_channel, limit=6)
    post = next((m for m in posts if m.photo and "Big sale" in (m.message or "")), None)
    assert post is not None, [m.message for m in posts]
    assert "Big sale today" in post.message
    assert any(isinstance(e, MessageEntityBold) for e in (post.entities or [])), \
        "bold formatting in the caption was lost"


async def test_document_post_published(
    tg_client, test_bot_username, test_channel, sample_photo, _wait_for_bot
):
    # an arbitrary file (sent as a document) -> a post is "anything", not only photo/text
    bot = await tg_client.get_entity(test_bot_username)
    await send_and_wait(tg_client, bot, "/new")
    sent = await tg_client.send_file(bot, sample_photo, force_document=True)
    label_prompt = await wait_for_reply(tg_client, bot, sent.id)
    assert "Button label" in label_prompt.message, label_prompt.message

    await send_and_wait(tg_client, bot, "Download")
    color_prompt = await send_and_wait(tg_client, bot, "https://example.com/file")
    await find_button(color_prompt, "Default").click()  # the no-style color
    picker = await wait_for_msg_with_button(tg_client, bot, CHANNEL_TITLE, after_id=color_prompt.id)
    after = await latest_msg_id(tg_client, bot)
    await find_button(picker, CHANNEL_TITLE).click()
    confirm = await wait_for_reply(tg_client, bot, after)
    assert "Published" in confirm.message, confirm.message

    posts = await tg_client.get_messages(test_channel, limit=8)
    post = next((m for m in posts if m.document and m.buttons), None)
    assert post is not None, "document post not found in channel"
    assert len([b for row in post.buttons for b in row]) == 1


async def test_dm_sent_to_adder_not_the_chat(tg_client, test_bot_username, _wait_for_bot):
    # adding the bot as admin must notify the adder *in DM*, never in the chat
    bot = await tg_client.get_entity(test_bot_username)
    created = await tg_client(
        CreateChannelRequest(title="ButtonBot DM E2E", about="e2e", megagroup=False)
    )
    ch = created.chats[0]
    try:
        before = await latest_msg_id(tg_client, bot)
        await tg_client.edit_admin(
            ch, bot, is_admin=True, post_messages=True, pin_messages=True,
            change_info=True, invite_users=True, delete_messages=True,
            add_admins=False, manage_call=False, title="bot",
        )
        dm = await wait_for_reply(tg_client, bot, before, timeout=25)
        assert "admin in" in dm.message.lower() and "ButtonBot DM E2E" in dm.message, dm.message
    finally:
        await tg_client(DeleteChannelRequest(ch))


async def test_group_gets_only_the_post_no_fallback_spam(
    tg_client, test_bot_username, sample_photo, _wait_for_bot
):
    # regression: the bot must NOT post "build a post" / any UI text into a group,
    # not when added, not after pinning. Only the published post may appear there.
    bot = await tg_client.get_entity(test_bot_username)
    created = await tg_client(
        CreateChannelRequest(title="ButtonBot Group E2E", about="e2e", megagroup=True)
    )
    group = created.chats[0]
    try:
        await tg_client(InviteToChannelRequest(group, [bot]))
        await tg_client.edit_admin(
            group, bot, is_admin=True, post_messages=True, pin_messages=True,
            delete_messages=True, invite_users=True, change_info=True,
            add_admins=False, manage_call=False, title="bot",
        )
        await asyncio.sleep(4)  # let my_chat_member land in the bot

        await send_and_wait(tg_client, bot, "/new")
        await send_file_and_wait(tg_client, bot, sample_photo)
        await send_and_wait(tg_client, bot, "Open")
        color_prompt = await send_and_wait(tg_client, bot, "https://example.com")
        await find_button(color_prompt, "Green").click()
        picker = await wait_for_msg_with_button(
            tg_client, bot, "ButtonBot Group E2E", after_id=color_prompt.id
        )
        after = await latest_msg_id(tg_client, bot)
        await find_button(picker, "ButtonBot Group E2E").click()
        confirm = await wait_for_reply(tg_client, bot, after)
        assert "Published" in confirm.message, confirm.message

        await asyncio.sleep(2)
        bot_posts = 0
        async for m in tg_client.iter_messages(group, limit=25):
            assert "build a post" not in (m.message or "").lower(), \
                f"bot spammed the group: {m.message!r}"
            if m.buttons:
                bot_posts += 1
        assert bot_posts == 1, f"expected exactly 1 bot post in the group, got {bot_posts}"
    finally:
        await tg_client(DeleteChannelRequest(group))
