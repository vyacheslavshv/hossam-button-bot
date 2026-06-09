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


def test_post_button_is_a_single_url_button_with_style():
    markup = kb.post_button("Open", "https://x.com", "success")
    assert len(markup.inline_keyboard) == 1
    assert len(markup.inline_keyboard[0]) == 1
    btn = markup.inline_keyboard[0][0]
    assert btn.text == "Open"
    assert btn.url == "https://x.com"
    assert btn.style == "success"


def test_default_color_sends_no_style():
    btn = kb.post_button("Open", "https://x.com", "default").inline_keyboard[0][0]
    assert btn.style is None
