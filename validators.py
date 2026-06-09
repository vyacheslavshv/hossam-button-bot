from __future__ import annotations

import re

# "something.tld" with no scheme and no spaces — treat as a bare domain.
_DOMAINISH = re.compile(r"^[^\s/@]+\.[^\s/]{2,}")


def normalize_url(raw: str) -> str | None:
    """Turn user input into a URL Telegram will accept for a url-button, or None.

    Accepts full URLs (http/https/tg), bare domains (example.com/x -> https://),
    t.me links, and @handles (@channel -> https://t.me/channel).
    """
    s = (raw or "").strip()
    if not s or " " in s or "\n" in s:
        return None

    low = s.lower()
    if low.startswith(("https://", "http://", "tg://")):
        return s
    if s.startswith("@") and len(s) > 1:
        return "https://t.me/" + s[1:]
    if low.startswith("t.me/") or _DOMAINISH.match(s):
        return "https://" + s
    return None
