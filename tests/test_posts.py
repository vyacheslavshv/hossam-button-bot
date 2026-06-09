"""Unit tests for the saved-posts keyboards + label helper — no network, no DB."""
import datetime
from types import SimpleNamespace

from aiogram.types import Chat, Message, PhotoSize

import handlers
import keyboards as kb


def _posts(n):
    return [SimpleNamespace(id=i, label=f"\U0001F4DD Post {i}") for i in range(1, n + 1)]


def test_single_page_has_no_nav_row():
    markup = kb.saved_posts_keyboard(_posts(3), page=0, total=3)
    rows = markup.inline_keyboard
    assert len(rows) == 3  # 3 posts, no nav row
    assert [rows[i][0].callback_data for i in range(3)] == ["post:open:1", "post:open:2", "post:open:3"]


def test_first_page_nav_has_next_only():
    nav = kb.saved_posts_keyboard(_posts(5), page=0, total=12).inline_keyboard[-1]  # 3 pages
    labels = [b.text for b in nav]
    assert "◀️" not in labels      # no ◀️ on page 0
    assert "▶️" in labels          # ▶️ present
    assert any("1/3" in b.text for b in nav)


def test_middle_page_has_both_and_last_has_prev_only():
    mid = kb.saved_posts_keyboard(_posts(5), page=1, total=12).inline_keyboard[-1]
    cbs = [b.callback_data for b in mid]
    assert "post:page:0" in cbs and "post:page:2" in cbs   # ◀️ and ▶️
    last = kb.saved_posts_keyboard(_posts(2), page=2, total=12).inline_keyboard[-1]
    labels = [b.text for b in last]
    assert "▶️" not in labels and "◀️" in labels


def test_detail_and_confirm_keyboards_carry_the_id():
    detail = kb.post_detail_keyboard(7)
    cbs = [b.callback_data for row in detail.inline_keyboard for b in row]
    assert {"post:pub:7", "post:del:7", "post:page:0"} <= set(cbs)
    confirm = kb.delete_confirm_keyboard(7)
    cbs2 = [b.callback_data for row in confirm.inline_keyboard for b in row]
    assert {"post:delok:7", "post:open:7"} <= set(cbs2)


def _msg(**kw):
    return Message(message_id=1, date=datetime.datetime.now(), chat=Chat(id=1, type="private"), **kw)


def test_label_text():
    label = handlers._post_label(_msg(text="Hello world"))
    assert label.startswith("\U0001F4DD") and "Hello world" in label


def test_label_photo_uses_caption():
    m = _msg(photo=[PhotoSize(file_id="f", file_unique_id="u", width=1, height=1)], caption="Sale")
    label = handlers._post_label(m)
    assert label.startswith("\U0001F4F7") and "Sale" in label


def test_label_truncates_to_40_chars():
    label = handlers._post_label(_msg(text="x" * 100))
    assert label.count("x") == 40
