"""Pure-logic smoke tests — no Telegram, no network. Run with: pytest tests/test_validators.py"""
import keyboards as kb
from validators import normalize_url


def test_full_urls_pass_through():
    assert normalize_url("https://example.com") == "https://example.com"
    assert normalize_url("http://example.com/x?y=1") == "http://example.com/x?y=1"
    assert normalize_url("tg://resolve?domain=foo") == "tg://resolve?domain=foo"


def test_bare_domain_and_tme_get_https():
    assert normalize_url("example.com") == "https://example.com"
    assert normalize_url("t.me/yourchannel") == "https://t.me/yourchannel"


def test_at_handle_becomes_tme_link():
    assert normalize_url("@yourchannel") == "https://t.me/yourchannel"


def test_junk_is_rejected():
    assert normalize_url("") is None
    assert normalize_url("   ") is None
    assert normalize_url("hello world.com") is None  # space
    assert normalize_url("plaintext") is None        # no dot, no scheme


def test_four_colors_offered():
    assert set(kb.COLORS) == {"default", "primary", "success", "danger"}


def test_post_buttons_one_per_row_with_styles():
    markup = kb.post_buttons([
        {"text": "Open", "url": "https://x.com", "color": "success"},
        {"text": "Join", "url": "https://t.me/y", "color": "default"},
    ])
    rows = markup.inline_keyboard
    assert len(rows) == 2 and all(len(r) == 1 for r in rows)  # single column
    assert rows[0][0].text == "Open" and rows[0][0].url == "https://x.com"
    assert rows[0][0].style == "success"
    assert rows[1][0].style is None  # default = no style field


def test_post_buttons_single():
    markup = kb.post_buttons([{"text": "Go", "url": "https://x.com", "color": "primary"}])
    assert len(markup.inline_keyboard) == 1
    assert markup.inline_keyboard[0][0].style == "primary"
