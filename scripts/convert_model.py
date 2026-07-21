"""Download NLLB-200 distilled-600M and convert to CTranslate2 int8."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_MODEL_ID = "facebook/nllb-200-distilled-600M"
DEFAULT_OUTPUT_NAME = "nllb-200-distilled-600M-int8"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def convert(
    model_id: str = DEFAULT_MODEL_ID,
    output_dir: Path | None = None,
    quantization: str = "int8",
    force: bool = False,
) -> Path:
    root = project_root()
    out = output_dir or (root / "models" / DEFAULT_OUTPUT_NAME)
    out = out.resolve()

    if out.exists() and any(out.iterdir()) and not force:
        print(f"Model already present at {out} (use --force to reconvert)")
        return out

    if out.exists() and force:
        shutil.rmtree(out)

    out.parent.mkdir(parents=True, exist_ok=True)

    # Prefer the installed console script; fall back to python -m
    converter = Path(sys.executable).with_name("ct2-transformers-converter.exe")
    if converter.exists():
        cmd = [str(converter)]
    else:
        cmd = [sys.executable, "-m", "ctranslate2.converters.transformers"]

    cmd.extend(
        [
            "--model",
            model_id,
            "--output_dir",
            str(out),
            "--quantization",
            quantization,
            "--force",
            "--copy_files",
            "tokenizer.json",
            "sentencepiece.bpe.model",
            "tokenizer_config.json",
            "special_tokens_map.json",
        ]
    )
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"Converted model saved to {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert NLLB to CTranslate2")
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Destination directory for CT2 model",
    )
    parser.add_argument(
        "--quantization",
        default="int8",
        choices=["int8", "int8_float32", "int8_float16", "float16", "float32"],
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    convert(
        model_id=args.model_id,
        output_dir=args.output_dir,
        quantization=args.quantization,
        force=args.force,
    )


if __name__ == "__main__":
    main()
