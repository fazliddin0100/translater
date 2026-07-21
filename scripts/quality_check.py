"""Run a quick quality spot-check on EN and RU sample sentences."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.translator.engine import TranslatorEngine


def load_lines(path: Path) -> list[str]:
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def run_set(engine: TranslatorEngine, path: Path, source: str, batch_size: int) -> None:
    lines = load_lines(path)
    print(f"\n=== {source} ({len(lines)} sentences) from {path.name} ===\n")
    translations = engine.translate_batch(lines, source_lang=source, batch_size=batch_size)
    for src, dst in zip(lines, translations):
        print(f"SRC: {src}")
        print(f"UZ:  {dst}")
        print("-" * 60)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()

    samples = ROOT / "samples"
    engine = TranslatorEngine(device=args.device)
    print(f"[engine] device={engine.device} compute_type={engine.compute_type}")

    run_set(engine, samples / "quality_en.txt", "eng_Latn", args.batch_size)
    run_set(engine, samples / "quality_ru.txt", "rus_Cyrl", args.batch_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
