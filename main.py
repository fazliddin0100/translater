"""CLI entry point: text or DOCX/PDF → Uzbek (Latin)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline import translate_document  # noqa: E402
from src.translator.engine import (  # noqa: E402
    DEFAULT_MODEL_DIR,
    DEFAULT_TARGET,
    SUPPORTED_SOURCES,
    TranslatorEngine,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline EN/RU → UZ translator (text, DOCX, PDF)",
    )
    parser.add_argument("--text", "-t", help="Plain text to translate")
    parser.add_argument(
        "--input",
        "-in",
        type=Path,
        help="Input .docx or .pdf file",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output path for translated document",
    )
    parser.add_argument(
        "--source",
        "-s",
        default="auto",
        help="Source language: eng_Latn, rus_Cyrl, or auto (default)",
    )
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument(
        "--beam-size",
        type=int,
        default=1,
        help="1 = tez (greedy), 4 = sifatliroq lekin sekin",
    )
    parser.add_argument(
        "--output-format",
        choices=["auto", "docx", "pdf"],
        default="auto",
        help="auto = asl format (PDF rasmlari saqlanadi); docx/pdf = majburiy format",
    )
    parser.add_argument("--interactive", "-i", action="store_true")
    parser.add_argument(
        "--file",
        "-f",
        type=Path,
        help="Translate each non-empty line from a UTF-8 text file",
    )
    return parser


def _resolve_source(raw: str) -> str | None:
    if raw in (None, "", "auto"):
        return None
    if raw not in SUPPORTED_SOURCES:
        raise SystemExit(f"Noto'g'ri --source: {raw}. eng_Latn | rus_Cyrl | auto")
    return raw


def run_interactive(engine: TranslatorEngine, source: str | None, target: str) -> None:
    print(f"Interactive mode (source={source or 'auto'} → {target}). Empty line to quit.")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            break
        from src.utils.lang import detect_nllb_source

        src = source or detect_nllb_source(line)
        print(engine.translate(line, source_lang=src, target_lang=target))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = _resolve_source(args.source)

    engine = TranslatorEngine(
        model_dir=args.model_dir,
        device=args.device,
        compute_type=args.compute_type,
        beam_size=args.beam_size,
        default_batch_size=args.batch_size,
    )
    print(f"[engine] device={engine.device} compute_type={engine.compute_type}")

    if args.interactive:
        run_interactive(engine, source, args.target)
        return 0

    if args.input:
        def progress(done: int, total: int, msg: str) -> None:
            print(f"[{done}/{total}] {msg}")

        out, _units = translate_document(
            args.input,
            args.output,
            engine=engine,
            source_lang=source if source else "auto",
            target_lang=args.target,
            device=args.device,
            batch_size=args.batch_size,
            output_format=args.output_format,
            progress=progress,
        )
        print(f"Saqlandi: {out}")
        return 0

    if args.file:
        from src.utils.lang import detect_nllb_source

        lines = [
            line.rstrip("\n")
            for line in args.file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        src = source or detect_nllb_source(" ".join(lines[:5]))
        for src_line, dst in zip(
            lines,
            engine.translate_batch(
                lines, source_lang=src, target_lang=args.target, batch_size=args.batch_size
            ),
        ):
            print(f"{src_line}\t→\t{dst}")
        return 0

    if args.text:
        from src.utils.lang import detect_nllb_source

        src = source or detect_nllb_source(args.text)
        print(engine.translate(args.text, source_lang=src, target_lang=args.target))
        return 0

    build_parser().print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
