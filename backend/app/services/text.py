"""Small text helpers shared by the topic service, the collector and the seed script."""

from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_WHITESPACE = re.compile(r"\s+")

MAX_TOPIC_NAME_LENGTH = 200
MAX_SLUG_LENGTH = 220
MAX_TITLE_LENGTH = 500


def normalize_name(name: str) -> str:
    """Lowercase, accent-stripped, whitespace-collapsed form used for topic matching."""
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _WHITESPACE.sub(" ", stripped.strip().lower())


def slugify(value: str, max_length: int = MAX_SLUG_LENGTH) -> str:
    """URL-safe slug. Returns an empty string when nothing usable remains."""
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    slug = _NON_ALNUM.sub("-", stripped.lower()).strip("-")
    return slug[:max_length].strip("-")


def truncate(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 1].rstrip() + "\u2026"


def clean_whitespace(value: str | None) -> str | None:
    """Collapse runs of whitespace; returns None for an effectively empty string."""
    if value is None:
        return None
    collapsed = _WHITESPACE.sub(" ", value).strip()
    return collapsed or None
