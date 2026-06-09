"""All bot logic.

Flow: /start -> Create post -> send content (text or one photo/video/file) ->
button label -> button link -> button color -> preview + pick a channel ->
the post is copied into the channel with a single big button and pinned.

The single inline button is the whole point: Telegram renders a one-button
pinned message as a large button on top of the channel/group.
"""
from __future__ import annotations

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
    "I build a channel/group post with one big button — the kind Telegram shows "
    "large on top of a pinned message.\n\n"
    "First add me as an <b>admin</b> (with <i>Post messages</i> + <i>Pin messages</i>) "
    "to your channel or group. Then tap below to build a post."
)

CONTENT_PROMPT = (
    "📝 <b>Step 1/4 — Content</b>\n\n"
    "Send the post itself: text, or a photo / video / file (with an optional caption). "
    "It will be published exactly as you send it here.\n\n"
    "<i>One photo/video per post — albums can't carry a button.</i>"
)


class PostFlow(StatesGroup):
    content = State()
    button_text = State()
    button_url = State()
    color = State()
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
            "a button can only be one message."
        )
        return
    await state.update_data(
        content_chat_id=message.chat.id,
        content_message_id=message.message_id,
    )
    await state.set_state(PostFlow.button_text)
    await message.answer(
        "🔘 <b>Step 2/4 — Button label</b>\n\n"
        "Send the text to show on the button (e.g. <code>Open Website</code> or "
        "<code>Join now</code>)."
    )


# --------------------------------------------------------------- step 2: label

@router.message(PostFlow.button_text)
async def step_button_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Please send the button label as plain text.")
        return
    await state.update_data(button_text=text[:64])
    await state.set_state(PostFlow.button_url)
    await message.answer(
        "🔗 <b>Step 3/4 — Button link</b>\n\n"
        "Send the link the button opens — a website, a bot, a channel… any "
        "<code>https://</code> or <code>t.me/</code> link (or an <code>@handle</code>)."
    )


# --------------------------------------------------------------- step 3: link

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
    await state.update_data(button_url=url)
    await state.set_state(PostFlow.color)
    await message.answer("🎨 <b>Step 4/4 — Button color</b>\n\nPick a color:", reply_markup=kb.color_keyboard())


# --------------------------------------------------------------- step 4: color

@router.callback_query(PostFlow.color, F.data.startswith("color:"))
async def step_color(cq: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    color = cq.data.split(":", 1)[1]
    if color not in kb.COLORS:
        await cq.answer()
        return
    await state.update_data(color=color)
    await cq.answer(kb.COLORS[color]["label"])
    await _preview_and_pick(cq.message, cq.from_user.id, state, bot)


@router.message(PostFlow.color)
async def step_color_text(message: Message) -> None:
    await message.answer("Pick a color using the buttons 👇", reply_markup=kb.color_keyboard())


async def _preview_and_pick(message: Message, user_id: int, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    markup = kb.post_button(data["button_text"], data["button_url"], data["color"])
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
    label = kb.COLORS[data["color"]]["label"]
    if channels:
        await message.answer(
            f"👆 <b>Preview</b> ({label} button). Where should I publish it?",
            reply_markup=kb.channels_keyboard(channels),
        )
    else:
        await message.answer(
            f"👆 <b>Preview</b> ({label} button).\n\n"
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
    markup = kb.post_button(data["button_text"], data["button_url"], data["color"])
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

    pinned = await _try_pin(bot, chat_id, sent.message_id)
    ch = await repo.get_channel(chat_id)
    title = escape((ch.title if ch else "") or "the channel")

    text = f"✅ Published to <b>{title}</b>"
    text += " and pinned it 📌." if pinned else (
        ".\n⚠️ I couldn't pin it — give me <i>Pin messages</i> permission, or pin it manually."
    )
    link = _post_link(chat_id, sent.message_id)
    if link:
        text += f"\n\n🔗 {link}"
    await message.answer(text, reply_markup=kb.menu_keyboard())
    await state.clear()


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
        # demoted / removed -> can't reliably post or pin anymore
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


async def _try_pin(bot: Bot, chat_id: int, message_id: int) -> bool:
    try:
        await bot.pin_chat_message(chat_id=chat_id, message_id=message_id, disable_notification=True)
        return True
    except TelegramBadRequest as e:
        logger.info(f"pin failed for {chat_id}: {e}")
        return False


def _post_link(chat_id: int, message_id: int) -> str | None:
    s = str(chat_id)
    if s.startswith("-100"):
        return f"https://t.me/c/{s[4:]}/{message_id}"
    return None
