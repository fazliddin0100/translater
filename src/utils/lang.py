"""Language detection helpers for EN/RU → NLLB codes."""

from __future__ import annotations

import re

from langdetect import DetectorFactory, detect, detect_langs
from langdetect.lang_detect_exception import LangDetectException

DetectorFactory.seed = 0

_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def detect_nllb_source(text: str, default: str = "eng_Latn") -> str:
    """Map free text to NLLB source code (`eng_Latn` or `rus_Cyrl`)."""
    sample = (text or "").strip()
    if not sample:
        return default

    cyr = len(_CYRILLIC_RE.findall(sample))
    lat = len(_LATIN_RE.findall(sample))
    if cyr > lat * 1.2 and cyr >= 3:
        return "rus_Cyrl"
    if lat > cyr * 1.2 and lat >= 3:
        # Still confirm with langdetect when possible
        pass

    try:
        if len(sample) < 20:
            # langdetect is unreliable on very short strings
            return "rus_Cyrl" if cyr > lat else "eng_Latn"
        lang = detect(sample)
        if lang == "ru":
            return "rus_Cyrl"
        if lang in {"en", "uz", "tr", "de", "fr", "es", "it"}:
            # Treat Latin-script unknowns as English for NLLB EN→UZ
            return "eng_Latn"
        # Prefer script heuristic
        return "rus_Cyrl" if cyr > lat else "eng_Latn"
    except LangDetectException:
        return "rus_Cyrl" if cyr > lat else default


def detect_document_source(texts: list[str], default: str = "eng_Latn") -> str:
    """Majority vote over non-empty segments."""
    votes = {"eng_Latn": 0, "rus_Cyrl": 0}
    for t in texts:
        if not (t or "").strip():
            continue
        code = detect_nllb_source(t, default=default)
        votes[code] = votes.get(code, 0) + 1
    if votes["rus_Cyrl"] > votes["eng_Latn"]:
        return "rus_Cyrl"
    if votes["eng_Latn"] > 0:
        return "eng_Latn"
    return default
