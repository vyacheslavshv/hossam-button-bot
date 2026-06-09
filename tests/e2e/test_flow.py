"""End-to-end: build a post (photo / text / document) with one or more buttons and
publish it into a real channel/group. The bot does NOT pin.

Owner = @vyatg (tg_client). The bot must be running with the test token.

NOTE: these were synced to the multi-button / no-pin flow but not re-run in that
session — run the bot + `pytest tests/e2e` to execute them.
"""
import asyncio

from telethon.tl.functions.channels import (
    CreateChannelRequest,
    DeleteChannelRequest,
    InviteToChannelRequest,
)
from telethon.tl.types import MessageEntityBold

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


async def _finish_one_button(tg_client, bot, color_prompt, color_label, channel_title):
    """Click a color, then 'Done' on the add-another step, and return the channel picker."""
    await find_button(color_prompt, color_label).click()
    more = await wait_for_msg_with_button(tg_client, bot, "Add another", after_id=color_prompt.id)
    await find_button(more, "Done").click()
    return await wait_for_msg_with_button(tg_client, bot, channel_title, after_id=more.id)


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


async def test_photo_post_published(
    tg_client, test_bot_username, test_channel, sample_photo, _wait_for_bot
):
    bot = await tg_client.get_entity(test_bot_username)

    await send_and_wait(tg_client, bot, "/new")
    label_prompt = await send_file_and_wait(tg_client, bot, sample_photo)
    assert "button" in label_prompt.message.lower(), label_prompt.message

    url_prompt = await send_and_wait(tg_client, bot, "Open Website")
    assert "link" in url_prompt.message.lower(), url_prompt.message

    color_prompt = await send_and_wait(tg_client, bot, "https://example.com")
    assert "color" in color_prompt.message.lower(), color_prompt.message

    picker = await _finish_one_button(tg_client, bot, color_prompt, "Green", CHANNEL_TITLE)
    after = await latest_msg_id(tg_client, bot)
    await find_button(picker, CHANNEL_TITLE).click()
    confirm = await wait_for_reply(tg_client, bot, after)
    assert "Published" in confirm.message, confirm.message

    posts = await tg_client.get_messages(test_channel, limit=5)
    post = next((m for m in posts if m.buttons), None)
    assert post is not None, "no message with a button in the channel"
    btns = [b for row in post.buttons for b in row]
    assert len(btns) == 1, f"expected exactly one button, got {len(btns)}"
    # Telegram may append a trailing slash to a bare-domain url
    assert btns[0].url.rstrip("/") == "https://example.com", btns[0].url
    assert post.photo is not None, "published post should carry the photo"


async def test_text_post_published(tg_client, test_bot_username, test_channel, _wait_for_bot):
    bot = await tg_client.get_entity(test_bot_username)

    await send_and_wait(tg_client, bot, "/new")
    await send_and_wait(tg_client, bot, "Hello channel world")   # content (text)
    await send_and_wait(tg_client, bot, "Join")                  # label
    color_prompt = await send_and_wait(tg_client, bot, "t.me/durov")  # link

    picker = await _finish_one_button(tg_client, bot, color_prompt, "Blue", CHANNEL_TITLE)
    after = await latest_msg_id(tg_client, bot)
    await find_button(picker, CHANNEL_TITLE).click()
    confirm = await wait_for_reply(tg_client, bot, after)
    assert "Published" in confirm.message, confirm.message

    posts = await tg_client.get_messages(test_channel, limit=5)
    assert any("Hello channel world" in (m.message or "") for m in posts), [m.message for m in posts]


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
    assert "button" in label_prompt.message.lower(), label_prompt.message

    await send_and_wait(tg_client, bot, "Shop now")
    color_prompt = await send_and_wait(tg_client, bot, "https://example.com")
    picker = await _finish_one_button(tg_client, bot, color_prompt, "Red", CHANNEL_TITLE)
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
    assert "button" in label_prompt.message.lower(), label_prompt.message

    await send_and_wait(tg_client, bot, "Download")
    color_prompt = await send_and_wait(tg_client, bot, "https://example.com/file")
    picker = await _finish_one_button(tg_client, bot, color_prompt, "Default", CHANNEL_TITLE)
    after = await latest_msg_id(tg_client, bot)
    await find_button(picker, CHANNEL_TITLE).click()
    confirm = await wait_for_reply(tg_client, bot, after)
    assert "Published" in confirm.message, confirm.message

    posts = await tg_client.get_messages(test_channel, limit=8)
    post = next((m for m in posts if m.document and m.buttons), None)
    assert post is not None, "document post not found in channel"
    assert len([b for row in post.buttons for b in row]) == 1


async def test_two_buttons_published(tg_client, test_bot_username, test_channel, _wait_for_bot):
    # the new multi-button feature: two buttons stacked in a single column
    bot = await tg_client.get_entity(test_bot_username)
    await send_and_wait(tg_client, bot, "/new")
    await send_and_wait(tg_client, bot, "Two-button post")        # content
    await send_and_wait(tg_client, bot, "First")                  # button 1 label
    color_prompt = await send_and_wait(tg_client, bot, "https://example.com")  # button 1 link
    await find_button(color_prompt, "Green").click()
    more = await wait_for_msg_with_button(tg_client, bot, "Add another", after_id=color_prompt.id)

    await find_button(more, "Add another").click()               # add a 2nd button
    await send_and_wait(tg_client, bot, "Second")                # button 2 label
    color_prompt2 = await send_and_wait(tg_client, bot, "https://example.org")  # button 2 link
    await find_button(color_prompt2, "Red").click()
    more2 = await wait_for_msg_with_button(tg_client, bot, "Add another", after_id=color_prompt2.id)
    await find_button(more2, "Done").click()
    picker = await wait_for_msg_with_button(tg_client, bot, CHANNEL_TITLE, after_id=more2.id)

    after = await latest_msg_id(tg_client, bot)
    await find_button(picker, CHANNEL_TITLE).click()
    confirm = await wait_for_reply(tg_client, bot, after)
    assert "Published" in confirm.message, confirm.message

    posts = await tg_client.get_messages(test_channel, limit=5)
    post = next((m for m in posts if "Two-button post" in (m.message or "")), None)
    assert post is not None, [m.message for m in posts]
    # two buttons, each on its own row (single column)
    assert post.buttons is not None and len(post.buttons) == 2, post.buttons
    assert all(len(row) == 1 for row in post.buttons), "buttons should be one per row"


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
    # not when added, not after publishing. Only the published post may appear there.
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
        picker = await _finish_one_button(tg_client, bot, color_prompt, "Green", "ButtonBot Group E2E")
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


async def test_saved_post_list_publish_delete(
    tg_client, test_bot_username, test_channel, _wait_for_bot
):
    # build -> auto-saved -> appears in /list -> re-publish from the list -> delete it
    bot = await tg_client.get_entity(test_bot_username)
    marker = "SAVEME-marker-post"

    await send_and_wait(tg_client, bot, "/new")
    await send_and_wait(tg_client, bot, marker)              # content (text) -> becomes the label
    await send_and_wait(tg_client, bot, "Btn")               # button label
    color_prompt = await send_and_wait(tg_client, bot, "https://example.com")
    await find_button(color_prompt, "Blue").click()
    more = await wait_for_msg_with_button(tg_client, bot, "Add another", after_id=color_prompt.id)
    await find_button(more, "Done").click()
    await wait_for_msg_with_button(tg_client, bot, CHANNEL_TITLE, after_id=more.id)  # saved + picker

    # /list shows it
    listing = await send_and_wait(tg_client, bot, "/list")
    assert "saved posts" in listing.message.lower(), listing.message
    assert any("SAVEME" in t for t in button_texts(listing)), button_texts(listing)

    # open it -> bot sends a preview + a detail panel (Publish / Delete / Back)
    await find_button(listing, "SAVEME").click()
    detail = await wait_for_msg_with_button(tg_client, bot, "Publish", after_id=listing.id)

    # re-publish the saved post to the channel
    await find_button(detail, "Publish").click()
    picker = await wait_for_msg_with_button(tg_client, bot, CHANNEL_TITLE, after_id=detail.id)
    after = await latest_msg_id(tg_client, bot)
    await find_button(picker, CHANNEL_TITLE).click()
    confirm = await wait_for_reply(tg_client, bot, after)
    assert "Published" in confirm.message, confirm.message
    in_channel = await tg_client.get_messages(test_channel, limit=5)
    assert any(marker in (m.message or "") for m in in_channel), [m.message for m in in_channel]

    # delete it
    listing2 = await send_and_wait(tg_client, bot, "/list")
    await find_button(listing2, "SAVEME").click()
    detail2 = await wait_for_msg_with_button(tg_client, bot, "Delete", after_id=listing2.id)
    await find_button(detail2, "Delete").click()
    confirm_del = await wait_for_msg_with_button(tg_client, bot, "Yes, delete", after_id=detail2.id)
    await find_button(confirm_del, "Yes, delete").click()

    # gone from the most-recent list page
    await asyncio.sleep(1)
    listing3 = await send_and_wait(tg_client, bot, "/list")
    assert not any("SAVEME" in t for t in button_texts(listing3)), button_texts(listing3)
