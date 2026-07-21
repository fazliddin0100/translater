"""Shared text-unit model for extract → translate → write-back."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextUnit:
    """One extractable/translatable piece of document text."""

    uid: str
    text: str
    kind: str  # "docx_para" | "pdf_span"
    meta: dict[str, Any] = field(default_factory=dict)
    translated: str = ""
