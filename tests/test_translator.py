"""Minimal smoke tests for TranslatorEngine (requires converted model).

Run: python -m tests.test_translator
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.translator.engine import TranslatorEngine

MODEL_DIR = ROOT / "models" / "nllb-200-distilled-600M-int8"


def main() -> int:
    if not MODEL_DIR.exists():
        print(f"SKIP: model missing at {MODEL_DIR}")
        return 0

    engine = TranslatorEngine(device="cpu")
    out = engine.translate("Hello, how are you?", source_lang="eng_Latn")
    assert out, "empty translation"
    assert "salom" in out.lower() or "qanday" in out.lower(), out

    batch = engine.translate_batch(["Good morning.", "Thank you."], source_lang="eng_Latn")
    assert len(batch) == 2 and all(batch)

    print("OK:", out)
    print("OK batch:", batch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
