"""All bot logic.

Flow: /start -> Create post -> send content (text or one photo/video/file) ->
for each button: label -> link -> color, then "add another / done" -> the post is
saved -> preview + pick a channel. Saved posts live in /list, where they can be
re-published or deleted.

Buttons are stacked one per row (single column). The bot does NOT pin: with a
single button the user can pin the post themselves to get the large banner button.

Posts are stored as a reference to the user's original message in their private
chat with the bot (kept), plus the buttons; re-publishing copies from that message.
"""
from __future__ import annotations

import json
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    Message,
    MessageOriginChannel,
)
from loguru import logger

import keyboards as kb
import repo
from validators import normalize_url

router = Router()

# The bot is a DM-only assistant. It must never write into a group/channel except
# the published post itself, so we ignore every message that isn't from a private
# chat — group chatter AND service messages (bot added, message pinned, etc.).
router.message.filter(F.chat.type == ChatType.PRIVATE)

WELCOME = (
    "👋 <b>Post Builder</b>\n\n"
    "I build a channel/group post with one or more buttons.\n"
    "• <b>One button</b> → you can pin the post to show it as a big button on top.\n"
    "• <b>Several buttons</b> → just published to the channel/group.\n\n"
    "First add me as an <b>admin</b> (with <i>Post messages</i>) to your channel or "
    "group. Then tap below to build a post — every post you make is saved in /list."
)

CONTENT_PROMPT = (
    "📝 <b>Step 1 — Content</b>\n\n"
    "Send the post itself: text, or a photo / video / file (with an optional caption). "
    "It will be published exactly as you send it here.\n\n"
    "<i>One photo/video per post — albums can't carry buttons.</i>"
)

_KIND_ICON = {
    "photo": "📷", "video": "🎬", "animation": "🎞", "document": "📎",
    "audio": "🎵", "voice": "🎤", "video_note": "⭕", "text": "📝",
}


class PostFlow(StatesGroup):
    content = State()
    button_text = State()
    button_url = State()
    color = State()
    more = State()          # "add another button or publish?"
    choose_channel = State()


# --------------------------------------------------------------- entry / control

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(WELCOME, reply_markup=kb.menu_keyboard())


@router.message(Command("new"))
async def cmd_new(message: Message, state: FSMContext) -> None:
    await _start_flow(message, state)


@router.message(Command("cancel"), StateFilter("*"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Cancelled. Send /new to start over.", reply_markup=kb.menu_keyboard())


@router.message(Command("list"), StateFilter("*"))
async def cmd_list(message: Message, state: FSMContext) -> None:
    # registered with the other commands so it wins over state message handlers
    await state.clear()
    await _show_list(message, message.from_user.id, page=0, edit=False)


@router.callback_query(F.data == "new")
async def cb_new(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    await _start_flow(cq.message, state)


@router.callback_query(F.data == "cancel")
async def cb_cancel(cq: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cq.answer("Cancelled")
    await cq.message.answer("Cancelled. Send /new to start over.", reply_markup=kb.menu_keyboard())


async def _start_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(PostFlow.content)
    await message.answer(CONTENT_PROMPT)


# --------------------------------------------------------------- step 1: content

@router.message(PostFlow.content)
async def step_content(message: Message, state: FSMContext) -> None:
    if message.media_group_id:
        await message.answer(
            "That's an album. Send a <b>single</b> photo/video or text — a post with "
            "buttons can only be one message."
        )
        return
    await state.update_data(
        content_chat_id=message.chat.id,
        content_message_id=message.message_id,
        label=_post_label(message),
        buttons=[],
    )
    await state.set_state(PostFlow.button_text)
    await message.answer(
        "🔘 <b>Step 2 — Buttons</b>\n\n"
        "Send the text for the first button (e.g. <code>Open Website</code> or "
        "<code>Join now</code>)."
    )


# --------------------------------------------------------------- per-button: label

@router.message(PostFlow.button_text)
async def step_button_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Please send the button label as plain text.")
        return
    await state.update_data(cur_text=text[:64])
    await state.set_state(PostFlow.button_url)
    await message.answer(
        "🔗 Send the link this button opens — a website, a bot, a channel… any "
        "<code>https://</code> or <code>t.me/</code> link (or an <code>@handle</code>)."
    )


# --------------------------------------------------------------- per-button: link

@router.message(PostFlow.button_url)
async def step_button_url(message: Message, state: FSMContext) -> None:
    url = normalize_url(message.text or "")
    if not url:
        await message.answer(
            "That doesn't look like a valid link. Try something like "
            "<code>https://example.com</code>, <code>t.me/yourchannel</code> or "
            "<code>@yourchannel</code>."
        )
        return
    await state.update_data(cur_url=url)
    await state.set_state(PostFlow.color)
    await message.answer("🎨 Pick a color for this button:", reply_markup=kb.color_keyboard())


# --------------------------------------------------------------- per-button: color

@router.callback_query(PostFlow.color, F.data.startswith("color:"))
async def step_color(cq: CallbackQuery, state: FSMContext) -> None:
    color = cq.data.split(":", 1)[1]
    if color not in kb.COLORS:
        await cq.answer()
        return
    await cq.answer(kb.COLORS[color]["label"])
    data = await state.get_data()
    buttons = data.get("buttons", [])
    buttons.append({"text": data["cur_text"], "url": data["cur_url"], "color": color})
    await state.update_data(buttons=buttons)
    await state.set_state(PostFlow.more)
    await cq.message.answer(
        f"✅ Added <b>{escape(data['cur_text'])}</b> ({kb.COLORS[color]['label']}). "
        f"You now have <b>{len(buttons)}</b> button(s).\n\nAdd another, or publish?",
        reply_markup=kb.more_keyboard(),
    )


@router.message(PostFlow.color)
async def step_color_text(message: Message) -> None:
    await message.answer("Pick a color using the buttons 👇", reply_markup=kb.color_keyboard())


# --------------------------------------------------------------- add another / done

@router.callback_query(PostFlow.more, F.data == "addbtn")
async def cb_add_button(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    data = await state.get_data()
    n = len(data.get("buttons", [])) + 1
    await state.set_state(PostFlow.button_text)
    await cq.message.answer(f"🔘 Send the text for button #{n}:")


@router.callback_query(PostFlow.more, F.data == "done")
async def cb_done(cq: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await cq.answer()
    data = await state.get_data()
    try:
        await repo.save_post(
            user_id=cq.from_user.id,
            content_chat_id=data["content_chat_id"],
            content_message_id=data["content_message_id"],
            buttons=data["buttons"],
            label=data.get("label", ""),
        )
    except Exception as e:  # noqa: BLE001 — saving must not block publishing
        logger.warning(f"save_post failed: {e}")
    await _preview_and_pick(cq.message, cq.from_user.id, state, bot)


@router.message(PostFlow.more)
async def step_more_text(message: Message) -> None:
    await message.answer("Use the buttons below 👇", reply_markup=kb.more_keyboard())


async def _preview_and_pick(message: Message, user_id: int, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    markup = kb.post_buttons(data["buttons"])
    try:
        await bot.copy_message(
            chat_id=user_id,
            from_chat_id=data["content_chat_id"],
            message_id=data["content_message_id"],
            reply_markup=markup,
        )
    except TelegramBadRequest as e:
        logger.warning(f"preview failed: {e}")

    await state.set_state(PostFlow.choose_channel)
    channels = await repo.list_channels(user_id)
    n = len(data["buttons"])
    saved = "Saved ✅ — find it any time in /list."
    if channels:
        await message.answer(
            f"👆 <b>Preview</b> ({n} button(s)). {saved}\n\nPublish it now?",
            reply_markup=kb.channels_keyboard(channels),
        )
    else:
        await message.answer(
            f"👆 <b>Preview</b> ({n} button(s)). {saved}\n\n"
            "I'm not an admin in any of your channels yet:\n"
            "1. Add me as <b>admin</b> (with <i>Post messages</i>) to your channel/group.\n"
            "2. Then <b>forward any message</b> from it here, or send its "
            "<code>@username</code>.",
            reply_markup=kb.channels_keyboard([]),
        )


# --------------------------------------------------------------- choose channel

@router.callback_query(PostFlow.choose_channel, F.data.startswith("pub:"))
async def cb_publish(cq: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    chat_id = int(cq.data.split(":", 1)[1])
    await cq.answer()
    await _publish(cq.message, cq.from_user.id, chat_id, state, bot)


@router.message(PostFlow.choose_channel)
async def add_channel(message: Message, state: FSMContext, bot: Bot) -> None:
    """Manual fallback: forward a message from the channel, or send @username / id."""
    target = await _resolve_chat(message, bot)
    if target is None:
        await message.answer(
            "Forward a message from your channel, or send its <code>@username</code>."
        )
        return

    can_post, can_pin = await _bot_rights(bot, target.id)
    if not can_post:
        await message.answer(
            "I'm not an admin there yet (or I can't post). Add me as admin with "
            "<i>Post messages</i>, then try again."
        )
        return

    await repo.upsert_channel(
        chat_id=target.id,
        title=target.title or "",
        type_=target.type,
        added_by=message.from_user.id,
        can_post=can_post,
        can_pin=can_pin,
    )
    channels = await repo.list_channels(message.from_user.id)
    await message.answer(
        f"✅ Added <b>{escape(target.title or 'this chat')}</b>. Tap it to publish:",
        reply_markup=kb.channels_keyboard(channels),
    )


async def _publish(message: Message, user_id: int, chat_id: int, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    markup = kb.post_buttons(data["buttons"])
    try:
        sent = await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=data["content_chat_id"],
            message_id=data["content_message_id"],
            reply_markup=markup,
        )
    except TelegramBadRequest as e:
        logger.warning(f"publish to {chat_id} failed: {e}")
        await message.answer(
            "❌ Couldn't publish there. Make sure I'm an admin with <i>Post messages</i>. "
            "Send /new to try again."
        )
        await state.clear()
        return

    ch = await repo.get_channel(chat_id)
    title = escape((ch.title if ch else "") or "the channel")
    text = f"✅ Published to <b>{title}</b>."
    link = _post_link(chat_id, sent.message_id)
    if link:
        text += f"\n\n🔗 {link}"
    if len(data["buttons"]) == 1:
        text += "\n\n<i>Tip: pin it in the channel to show the button as a big banner on top.</i>"
    await message.answer(text, reply_markup=kb.menu_keyboard())
    await state.clear()


# --------------------------------------------------------------- saved posts (/list)

@router.callback_query(F.data == "list")
async def cb_open_list(cq: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cq.answer()
    await _show_list(cq.message, cq.from_user.id, page=0, edit=False)


@router.callback_query(F.data.startswith("post:page:"))
async def cb_list_page(cq: CallbackQuery) -> None:
    page = int(cq.data.split(":")[2])
    await cq.answer()
    await _show_list(cq.message, cq.from_user.id, page=page, edit=True)


async def _show_list(message: Message, user_id: int, page: int, edit: bool) -> None:
    total = await repo.count_posts(user_id)
    if total == 0:
        text = "You have no saved posts yet. Send /new to create one."
        markup = kb.menu_keyboard()
    else:
        per = kb.POSTS_PER_PAGE
        pages = (total + per - 1) // per
        page = max(0, min(page, pages - 1))
        items = await repo.list_posts(user_id, limit=per, offset=page * per)
        text = f"📋 <b>Your saved posts</b> ({total}). Tap one to open:"
        markup = kb.saved_posts_keyboard(items, page, total)

    if edit:
        try:
            await message.edit_text(text, reply_markup=markup)
            return
        except TelegramBadRequest:
            pass
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("post:open:"))
async def cb_post_open(cq: CallbackQuery, bot: Bot) -> None:
    post = await repo.get_post(int(cq.data.split(":")[2]), cq.from_user.id)
    if post is None:
        await cq.answer("Post not found", show_alert=True)
        return
    await cq.answer()
    buttons = json.loads(post.buttons_json)
    try:
        await bot.copy_message(
            chat_id=cq.from_user.id,
            from_chat_id=post.content_chat_id,
            message_id=post.content_message_id,
            reply_markup=kb.post_buttons(buttons),
        )
    except TelegramBadRequest as e:
        logger.warning(f"preview of saved post {post.id} failed: {e}")
        await cq.message.answer("⚠️ Couldn't render this saved post — the original message is gone.")
    await cq.message.answer(
        f"👆 <b>{escape(post.label or 'Post')}</b> — {len(buttons)} button(s).",
        reply_markup=kb.post_detail_keyboard(post.id),
    )


@router.callback_query(F.data.startswith("post:pub:"))
async def cb_post_publish(cq: CallbackQuery, state: FSMContext) -> None:
    post = await repo.get_post(int(cq.data.split(":")[2]), cq.from_user.id)
    if post is None:
        await cq.answer("Post not found", show_alert=True)
        return
    await cq.answer()
    await state.clear()
    await state.update_data(
        content_chat_id=post.content_chat_id,
        content_message_id=post.content_message_id,
        buttons=json.loads(post.buttons_json),
    )
    await state.set_state(PostFlow.choose_channel)
    channels = await repo.list_channels(cq.from_user.id)
    if channels:
        await cq.message.answer("Where should I publish it?", reply_markup=kb.channels_keyboard(channels))
    else:
        await cq.message.answer(
            "I'm not an admin in any of your channels yet. Add me as <b>admin</b> "
            "(with <i>Post messages</i>), then forward a message from it here or send its "
            "<code>@username</code>.",
            reply_markup=kb.channels_keyboard([]),
        )


@router.callback_query(F.data.startswith("post:delok:"))
async def cb_post_delete_ok(cq: CallbackQuery) -> None:
    ok = await repo.delete_post(int(cq.data.split(":")[2]), cq.from_user.id)
    await cq.answer("Deleted" if ok else "Not found")
    await _show_list(cq.message, cq.from_user.id, page=0, edit=False)


@router.callback_query(F.data.startswith("post:del:"))
async def cb_post_delete(cq: CallbackQuery) -> None:
    post_id = int(cq.data.split(":")[2])
    await cq.answer()
    await cq.message.answer(
        "Delete this saved post?", reply_markup=kb.delete_confirm_keyboard(post_id)
    )


# --------------------------------------------------------------- channel tracking

@router.my_chat_member()
async def on_my_chat_member(event: ChatMemberUpdated, bot: Bot) -> None:
    chat = event.chat
    if chat.type not in ("channel", "supergroup", "group"):
        return

    member = event.new_chat_member
    new_status = member.status
    old_status = event.old_chat_member.status
    who = event.from_user.id if event.from_user else 0

    if new_status not in ("administrator", "creator"):
        # demoted / removed -> can't post anymore
        await repo.deactivate_channel(chat.id)
        logger.info(f"lost rights in {chat.title!r} ({chat.id}) status={new_status}")
        return

    can_post = getattr(member, "can_post_messages", None)
    can_pin = getattr(member, "can_pin_messages", None)
    await repo.upsert_channel(
        chat_id=chat.id,
        title=chat.title or "",
        type_=chat.type,
        added_by=who,
        can_post=(can_post is not False),
        can_pin=(can_pin is not False),
        active=True,
    )
    logger.info(f"admin in {chat.title!r} ({chat.id}) status={new_status} by={who}")

    # Tell the person who added the bot — privately, never in the chat itself —
    # but only on a fresh promotion and only if they have an open DM with the bot.
    freshly_added = old_status not in ("administrator", "creator")
    if who and freshly_added:
        try:
            await bot.send_message(
                who,
                f"✅ I'm now an admin in <b>{escape(chat.title or 'your chat')}</b>.\n"
                "Send /new to build a post for it.",
                reply_markup=kb.menu_keyboard(),
            )
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            logger.info(f"can't DM {who} about {chat.id}: {e}")


# --------------------------------------------------------------- fallback

@router.message(StateFilter(None))
async def fallback(message: Message) -> None:
    await message.answer("Tap below to build a post 👇", reply_markup=kb.menu_keyboard())


@router.callback_query()
async def cb_noop(cq: CallbackQuery) -> None:
    # clears the loading spinner on any stale/unhandled button
    await cq.answer()


# --------------------------------------------------------------- helpers

def _post_label(message: Message) -> str:
    """Short, plain-text label for the saved-posts list."""
    if message.photo:
        kind = "photo"
    elif message.video:
        kind = "video"
    elif message.animation:
        kind = "animation"
    elif message.video_note:
        kind = "video_note"
    elif message.audio:
        kind = "audio"
    elif message.voice:
        kind = "voice"
    elif message.document:
        kind = "document"
    else:
        kind = "text"
    icon = _KIND_ICON.get(kind, "📄")
    plain = (message.text or message.caption or "").strip().replace("\n", " ")
    return f"{icon} {plain[:40]}" if plain else f"{icon} ({kind})"


async def _resolve_chat(message: Message, bot: Bot):
    origin = message.forward_origin
    if isinstance(origin, MessageOriginChannel):
        return origin.chat

    ref = (message.text or "").strip()
    if not ref:
        return None
    if ref.startswith("@"):
        chat_ref: str | int = ref
    elif ref.lstrip("-").isdigit():
        chat_ref = int(ref)
    else:
        chat_ref = "@" + ref
    try:
        return await bot.get_chat(chat_ref)
    except TelegramBadRequest:
        return None


async def _bot_rights(bot: Bot, chat_id: int) -> tuple[bool, bool]:
    """(can_post, can_pin) for the bot in chat_id."""
    try:
        me = await bot.me()
        member = await bot.get_chat_member(chat_id, me.id)
    except TelegramBadRequest:
        return False, False
    if member.status == "creator":
        return True, True
    if member.status == "administrator":
        # can_post_messages is only present for channels; None in groups (any admin posts)
        can_post = getattr(member, "can_post_messages", None) is not False
        can_pin = getattr(member, "can_pin_messages", None) is not False
        return can_post, can_pin
    return False, False


def _post_link(chat_id: int, message_id: int) -> str | None:
    s = str(chat_id)
    if s.startswith("-100"):
        return f"https://t.me/c/{s[4:]}/{message_id}"
    return None
