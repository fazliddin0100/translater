"""NLLB translation engine backed by CTranslate2 (speed-tuned)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Sequence

import ctranslate2
from transformers import AutoTokenizer

from src.utils.normalize import normalize_uzbek_text

DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[2] / "models" / "nllb-200-distilled-600M-int8"
DEFAULT_TOKENIZER_ID = "facebook/nllb-200-distilled-600M"
DEFAULT_TARGET = "uzn_Latn"
SUPPORTED_SOURCES = ("eng_Latn", "rus_Cyrl")

# Speed defaults: greedy decoding is much faster than beam=4
DEFAULT_BEAM_SIZE = 1
DEFAULT_BATCH_SIZE = 32


def _prepend_nvidia_dll_paths() -> None:
    """Add pip-installed NVIDIA CUDA DLL directories to PATH (Windows)."""
    try:
        import nvidia  # type: ignore
    except ImportError:
        return

    root = Path(nvidia.__file__).resolve().parent
    dll_dirs: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_dir():
            continue
        if p.name.lower() == "bin" or any(p.glob("cublas64_*.dll")):
            dll_dirs.append(p)
    dll_dirs = list(dict.fromkeys(dll_dirs))
    if not dll_dirs:
        return
    prefix = os.pathsep.join(str(p) for p in dll_dirs)
    os.environ["PATH"] = prefix + os.pathsep + os.environ.get("PATH", "")
    if hasattr(os, "add_dll_directory"):
        for p in dll_dirs:
            try:
                os.add_dll_directory(str(p))
            except OSError:
                pass


def cuda_ready() -> bool:
    """True if CT2 sees a GPU and cublas can be resolved (best-effort)."""
    try:
        if ctranslate2.get_cuda_device_count() < 1:
            return False
    except Exception:
        return False
    _prepend_nvidia_dll_paths()
    return True


def _load_translator(
    model_dir: Path,
    device: str,
    compute_type: str,
    inter_threads: int,
    intra_threads: int,
) -> tuple[ctranslate2.Translator, str, str]:
    """Try CUDA first; fall back to CPU if CUDA libs fail at load time."""
    if device == "auto":
        device = "cuda" if cuda_ready() else "cpu"

    if device == "cuda":
        try:
            cuda_count = ctranslate2.get_cuda_device_count()
        except Exception:
            cuda_count = 0
        if cuda_count < 1:
            device = "cpu"
            compute_type = "int8"
        else:
            _prepend_nvidia_dll_paths()
            try:
                translator = ctranslate2.Translator(
                    str(model_dir),
                    device="cuda",
                    compute_type=compute_type,
                    inter_threads=max(1, inter_threads),
                    intra_threads=max(1, intra_threads),
                )
                return translator, "cuda", compute_type
            except RuntimeError as exc:
                msg = str(exc).lower()
                if "cublas" in msg or "cuda" in msg or "dll" in msg:
                    device = "cpu"
                    compute_type = "int8"
                else:
                    raise

    # CPU: use more threads for throughput
    if device == "cpu":
        cpu_count = os.cpu_count() or 4
        inter_threads = max(inter_threads, min(4, cpu_count))
        intra_threads = max(intra_threads, max(2, cpu_count // 2))

    translator = ctranslate2.Translator(
        str(model_dir),
        device=device,
        compute_type=compute_type,
        inter_threads=inter_threads,
        intra_threads=intra_threads,
    )
    return translator, device, compute_type


class TranslatorEngine:
    """Load a CT2 NLLB model and translate EN/RU sentences to Uzbek Latin."""

    def __init__(
        self,
        model_dir: Path | str | None = None,
        tokenizer_id: str = DEFAULT_TOKENIZER_ID,
        device: str = "auto",
        compute_type: str = "int8",
        inter_threads: int = 1,
        intra_threads: int = 4,
        beam_size: int = DEFAULT_BEAM_SIZE,
        default_batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self.model_dir = Path(model_dir) if model_dir else DEFAULT_MODEL_DIR
        if not self.model_dir.exists():
            raise FileNotFoundError(
                f"CT2 model not found at {self.model_dir}. "
                "Run: python scripts/convert_model.py"
            )

        self.beam_size = beam_size
        self.default_batch_size = default_batch_size
        self.translator, self.device, self.compute_type = _load_translator(
            self.model_dir,
            device=device,
            compute_type=compute_type,
            inter_threads=inter_threads,
            intra_threads=intra_threads,
        )

        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_id, use_fast=True)

    def translate(
        self,
        text: str,
        source_lang: str = "eng_Latn",
        target_lang: str = DEFAULT_TARGET,
        max_decoding_length: int = 256,
        beam_size: int | None = None,
    ) -> str:
        results = self.translate_batch(
            [text],
            source_lang=source_lang,
            target_lang=target_lang,
            max_decoding_length=max_decoding_length,
            beam_size=beam_size,
        )
        return results[0]

    def translate_batch(
        self,
        texts: Sequence[str],
        source_lang: str = "eng_Latn",
        target_lang: str = DEFAULT_TARGET,
        max_decoding_length: int = 256,
        beam_size: int | None = None,
        batch_size: int | None = None,
    ) -> list[str]:
        if source_lang not in SUPPORTED_SOURCES:
            raise ValueError(
                f"Unsupported source_lang={source_lang!r}. "
                f"Use one of: {', '.join(SUPPORTED_SOURCES)}"
            )

        beam = self.beam_size if beam_size is None else beam_size
        bsz = self.default_batch_size if batch_size is None else batch_size

        cleaned = [t.strip() for t in texts]
        if not cleaned:
            return []

        self.tokenizer.src_lang = source_lang
        source_tokens: list[list[str]] = []
        for text in cleaned:
            if not text:
                source_tokens.append([])
                continue
            encoded = self.tokenizer(text, truncation=True, max_length=512)
            tokens = self.tokenizer.convert_ids_to_tokens(encoded["input_ids"])
            source_tokens.append(tokens)

        non_empty_indices = [i for i, toks in enumerate(source_tokens) if toks]
        non_empty_tokens = [source_tokens[i] for i in non_empty_indices]

        translated: list[str] = [""] * len(cleaned)
        if not non_empty_tokens:
            return translated

        try:
            results = self._run_batch(
                non_empty_tokens,
                target_lang=target_lang,
                max_decoding_length=max_decoding_length,
                beam_size=beam,
                batch_size=bsz,
            )
        except RuntimeError as exc:
            msg = str(exc).lower()
            if self.device == "cuda" and ("cublas" in msg or "dll" in msg or "cuda" in msg):
                self.translator, self.device, self.compute_type = _load_translator(
                    self.model_dir,
                    device="cpu",
                    compute_type="int8",
                    inter_threads=1,
                    intra_threads=4,
                )
                results = self._run_batch(
                    non_empty_tokens,
                    target_lang=target_lang,
                    max_decoding_length=max_decoding_length,
                    beam_size=beam,
                    batch_size=bsz,
                )
            else:
                raise

        for idx, result in zip(non_empty_indices, results):
            hyp_tokens = result.hypotheses[0]
            if hyp_tokens and hyp_tokens[0].startswith(("eng_", "rus_", "uzn_", "__")):
                hyp_tokens = hyp_tokens[1:]
            translated[idx] = normalize_uzbek_text(
                self.tokenizer.convert_tokens_to_string(hyp_tokens).strip()
            )

        return translated

    def _run_batch(
        self,
        source_tokens: list[list[str]],
        target_lang: str,
        max_decoding_length: int,
        beam_size: int,
        batch_size: int,
    ):
        target_prefix = [[target_lang]] * len(source_tokens)
        return self.translator.translate_batch(
            source_tokens,
            target_prefix=target_prefix,
            beam_size=beam_size,
            max_decoding_length=max_decoding_length,
            batch_type="examples",
            max_batch_size=batch_size,
            return_scores=False,
        )

    def translate_many(
        self,
        texts: Iterable[str],
        source_lang: str = "eng_Latn",
        target_lang: str = DEFAULT_TARGET,
        **kwargs,
    ) -> list[str]:
        return self.translate_batch(
            list(texts), source_lang=source_lang, target_lang=target_lang, **kwargs
        )
