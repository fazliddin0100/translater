"""Normalize Uzbek Latin text so apostrophes don't become '?' in Word/PDF."""

from __future__ import annotations

import re

# Characters that often render as '?' in limited fonts / encodings
_APOSTROPHE_LIKE = str.maketrans(
    {
        "\u02bb": "'",  # ʻ  MODIFIER LETTER TURNED COMMA (common in o'zbek)
        "\u02bc": "'",  # ʼ  MODIFIER LETTER APOSTROPHE
        "\u02bd": "'",  # ʽ
        "\u2018": "'",  # ‘
        "\u2019": "'",  # ’
        "\u201b": "'",  # ‛
        "\u2032": "'",  # ′
        "\u0060": "'",  # `
        "\u00b4": "'",  # ´
        "\u02b9": "'",  # ʹ
        "\u02c8": "'",  # ˈ
        "\ufffd": "'",  # � replacement char
        "\u201c": '"',  # “
        "\u201d": '"',  # ”
        "\u201e": '"',  # „
        "\u00ab": '"',  # «
        "\u00bb": '"',  # »
        "\u2013": "-",  # –
        "\u2014": "-",  # —
        "\u00a0": " ",  # nbsp
    }
)

# Collapse weird sequences like o?zbek → o'zbek if model emitted ?
_OZ_FIX = re.compile(r"([OoGg])\?(?=[A-Za-zʻʼ'])")


def normalize_uzbek_text(text: str) -> str:
    """Make Uzbek Latin safe for Word editing (ASCII apostrophe, clean quotes)."""
    if not text:
        return text
    out = text.translate(_APOSTROPHE_LIKE)
    out = _OZ_FIX.sub(r"\1'", out)
    # Fix leftover lone ? between letters that look like apostrophe gaps: o?z → o'z
    out = re.sub(r"(?<=[A-Za-z])\?(?=[A-Za-z])", "'", out)
    return out
