"""PDF translate-in-place with approximate layout preservation (beta)."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import fitz  # PyMuPDF

ProgressCb = Callable[[int, int, str], None]

# Prefer Windows fonts with Latin Extended (Uzbek o', g', etc.)
_FONT_CANDIDATES = [
    Path(r"C:\Windows\Fonts\arial.ttf"),
    Path(r"C:\Windows\Fonts\segoeui.ttf"),
    Path(r"C:\Windows\Fonts\calibri.ttf"),
    Path(r"C:\Windows\Fonts\times.ttf"),
]


def _pick_font() -> str | None:
    for p in _FONT_CANDIDATES:
        if p.exists():
            return str(p)
    return None


def _fit_fontsize(page: fitz.Page, rect: fitz.Rect, text: str, fontfile: str | None, start: float) -> float:
    """Shrink font until text fits into the original bbox."""
    size = max(4.0, float(start))
    while size >= 4.0:
        kwargs = {
            "fontsize": size,
            "align": fitz.TEXT_ALIGN_LEFT,
        }
        if fontfile:
            kwargs["fontfile"] = fontfile
        else:
            kwargs["fontname"] = "helv"
        # insert_textbox returns leftover unused area; negative means overflow
        # Use a dry-run via text length estimate: try insert on a copy is expensive,
        # so approximate with character width.
        avg_char = size * 0.5
        max_chars = max(1, int((rect.width * max(1, int(rect.height / (size * 1.2)))) / avg_char))
        if len(text) <= max_chars * 1.15:
            return size
        size -= 0.5
    return 4.0


def collect_pdf_texts(path: Path | str) -> list[str]:
    doc = fitz.open(str(path))
    texts: list[str] = []
    try:
        for page in doc:
            data = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            for block in data.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        t = (span.get("text") or "").strip()
                        if t:
                            texts.append(t)
    finally:
        doc.close()
    return texts


def translate_pdf(
    input_path: Path | str,
    output_path: Path | str,
    translate_fn: Callable[[list[str]], list[str]],
    progress: ProgressCb | None = None,
) -> Path:
    """
    Replace text spans in-place.

    Limitations (beta): complex multi-column / vector text / scanned pages
    may not preserve layout perfectly. Scanned PDFs need OCR (not included).
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fontfile = _pick_font()
    doc = fitz.open(str(input_path))

    spans_meta: list[dict] = []
    sources: list[str] = []

    for page_index, page in enumerate(doc):
        data = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text") or ""
                    if not text.strip():
                        continue
                    bbox = fitz.Rect(span["bbox"])
                    spans_meta.append(
                        {
                            "page": page_index,
                            "bbox": bbox,
                            "size": float(span.get("size") or 11),
                            "color": span.get("color", 0),
                            "origin": span.get("origin"),
                            "text": text,
                        }
                    )
                    sources.append(text)

    total = len(sources)
    if progress:
        progress(0, max(total, 1), "PDF matnlar tarjima qilinmoqda…")

    translated: list[str] = []
    if sources:
        batch_size = 16
        for start in range(0, len(sources), batch_size):
            chunk = sources[start : start + batch_size]
            translated.extend(translate_fn(chunk))
            if progress:
                progress(min(start + len(chunk), total), total, "PDF tarjima…")

    # Redact original text, then write translations
    by_page: dict[int, list[tuple[dict, str]]] = {}
    for meta, new_text in zip(spans_meta, translated):
        by_page.setdefault(meta["page"], []).append((meta, new_text))

    for page_index, items in by_page.items():
        page = doc[page_index]
        for meta, _new in items:
            page.add_redact_annot(meta["bbox"], fill=(1, 1, 1))
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

        for meta, new_text in items:
            if not new_text.strip():
                continue
            rect = fitz.Rect(meta["bbox"])
            # Slightly expand vertically for longer translations
            rect.y1 = max(rect.y1, rect.y0 + meta["size"] * 1.35)
            fontsize = _fit_fontsize(page, rect, new_text, fontfile, meta["size"])
            color = meta["color"]
            if isinstance(color, int):
                r = ((color >> 16) & 255) / 255.0
                g = ((color >> 8) & 255) / 255.0
                b = (color & 255) / 255.0
                text_color = (r, g, b)
            else:
                text_color = (0, 0, 0)

            kwargs = {
                "fontsize": fontsize,
                "color": text_color,
                "align": fitz.TEXT_ALIGN_LEFT,
            }
            if fontfile:
                kwargs["fontfile"] = fontfile
            else:
                kwargs["fontname"] = "helv"

            leftover = page.insert_textbox(rect, new_text, **kwargs)
            if leftover < 0:
                # Still overflowing — shrink more aggressively
                for fs in [fontsize - 1, fontsize - 2, max(4.0, fontsize * 0.7)]:
                    if fs < 4:
                        break
                    kwargs["fontsize"] = fs
                    leftover = page.insert_textbox(rect, new_text, **kwargs)
                    if leftover >= 0:
                        break

        if progress:
            progress(page_index + 1, len(doc), f"PDF sahifa {page_index + 1}/{len(doc)}")

    doc.save(str(output_path), garbage=4, deflate=True)
    doc.close()
    if progress:
        progress(total, max(total, 1), "PDF saqlandi")
    return output_path
