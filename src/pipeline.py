"""Document translation: extract → translate → write-back."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.extractors.document import extract_document
from src.translator.engine import DEFAULT_TARGET, TranslatorEngine
from src.utils.lang import detect_document_source, detect_nllb_source
from src.utils.normalize import normalize_uzbek_text
from src.utils.units import TextUnit
from src.writers.writeback import write_document

ProgressCb = Callable[[int, int, str], None]


def translate_units(
    units: list[TextUnit],
    engine: TranslatorEngine,
    *,
    source_lang: str | None = None,
    target_lang: str = DEFAULT_TARGET,
    batch_size: int = 8,
    progress: ProgressCb | None = None,
) -> list[TextUnit]:
    """Translate TextUnit.text → TextUnit.translated in batches."""
    if not units:
        return units

    texts = [u.text for u in units]
    total = len(texts)
    translated: list[str] = [""] * total

    if source_lang and source_lang != "auto":
        pinned = source_lang
        groups: dict[str, list[int]] = {pinned: list(range(total))}
    else:
        groups = {}
        for i, t in enumerate(texts):
            code = detect_nllb_source(t)
            groups.setdefault(code, []).append(i)

    done = 0
    if progress:
        progress(0, total, "Matnlar tarjima qilinmoqda…")

    for code, indices in groups.items():
        for start in range(0, len(indices), batch_size):
            chunk_idx = indices[start : start + batch_size]
            chunk_txt = [texts[i] for i in chunk_idx]
            outs = engine.translate_batch(
                chunk_txt,
                source_lang=code,
                target_lang=target_lang,
                batch_size=batch_size,
                beam_size=getattr(engine, "beam_size", 1),
            )
            for i, out in zip(chunk_idx, outs):
                translated[i] = normalize_uzbek_text(out)
            done += len(chunk_idx)
            if progress:
                progress(done, total, f"Tarjima: {done}/{total}")

    for u, tr in zip(units, translated):
        u.translated = normalize_uzbek_text(tr)
    return units


def translate_document(
    input_path: Path | str,
    output_path: Path | str | None = None,
    *,
    engine: TranslatorEngine | None = None,
    source_lang: str | None = "auto",
    target_lang: str = DEFAULT_TARGET,
    device: str = "cpu",
    batch_size: int = 8,
    output_format: str = "auto",
    progress: ProgressCb | None = None,
) -> tuple[Path, list[TextUnit]]:
    """
    Full pipeline:
      1) extract text (+ positions)
      2) translate all units
      3) write back (PDF keeps images; format selectable)
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    suffix = input_path.suffix.lower()
    if suffix not in {".docx", ".pdf"}:
        raise ValueError("Faqat .docx va .pdf qo'llab-quvvatlanadi")

    fmt = (output_format or "auto").lower()
    if fmt == "auto":
        ext = suffix
    elif fmt in {"docx", "pdf"}:
        ext = f".{fmt}"
    else:
        raise ValueError("output_format: auto | docx | pdf")

    if output_path is None:
        output_path = input_path.with_name(f"{input_path.stem}_uz{ext}")
    else:
        output_path = Path(output_path).with_suffix(ext)

    if engine is None:
        if progress:
            progress(0, 1, "Model yuklanmoqda…")
        engine = TranslatorEngine(device=device)

    if progress:
        progress(0, 1, "1/3 Matn ajratilmoqda…")
    units = extract_document(input_path)
    if not units:
        raise ValueError(
            "Hujjatdan matn topilmadi. Skanerlangan PDF bo'lishi mumkin "
            "(OCR kerak) yoki fayl bo'sh."
        )

    src = source_lang
    if src in (None, "auto"):
        src = detect_document_source([u.text for u in units[:50]])

    if progress:
        progress(0, len(units), f"2/3 Tarjima ({len(units)} bo'lak)…")
    translate_units(
        units,
        engine,
        source_lang=src,
        target_lang=target_lang,
        batch_size=batch_size,
        progress=progress,
    )

    if progress:
        progress(0, 1, f"3/3 {ext} faylga yozilmoqda…")
    out = write_document(input_path, output_path, units, output_format=fmt)
    if progress:
        progress(1, 1, f"Tayyor ({out.suffix})")
    return out, units
