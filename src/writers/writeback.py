"""Write translated text units back as editable Word (.docx)."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from src.utils.units import TextUnit


def _iter_paragraphs(doc: Document):
    for p in doc.paragraphs:
        yield p
    for table in doc.tables:
        yield from _iter_table_paragraphs(table)
    for section in doc.sections:
        for p in section.header.paragraphs:
            yield p
        for table in section.header.tables:
            yield from _iter_table_paragraphs(table)
        for p in section.footer.paragraphs:
            yield p
        for table in section.footer.tables:
            yield from _iter_table_paragraphs(table)


def _iter_table_paragraphs(table: Table):
    for row in table.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                yield p
            for nested in cell.tables:
                yield from _iter_table_paragraphs(nested)


def _paragraph_text(paragraph: Paragraph) -> str:
    return "".join(run.text for run in paragraph.runs)


def _set_paragraph_text(paragraph: Paragraph, new_text: str) -> None:
    runs = paragraph.runs
    if not runs:
        if new_text:
            paragraph.add_run(new_text)
        return
    target_idx = 0
    for i, run in enumerate(runs):
        if run.text:
            target_idx = i
            break
    runs[target_idx].text = new_text
    for i, run in enumerate(runs):
        if i != target_idx:
            run.text = ""


def write_docx(input_path: Path | str, output_path: Path | str, units: list[TextUnit]) -> Path:
    """Replace DOCX paragraph texts in document order using translated units."""
    input_path = Path(input_path)
    output_path = Path(output_path).with_suffix(".docx")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    by_index = {u.meta["index"]: u for u in units if u.kind == "docx_para"}
    doc = Document(str(input_path))

    idx = 0
    for paragraph in _iter_paragraphs(doc):
        text = _paragraph_text(paragraph)
        if not text.strip():
            continue
        unit = by_index.get(idx)
        if unit is not None:
            _set_paragraph_text(paragraph, unit.translated or unit.text)
        idx += 1

    doc.save(str(output_path))
    return output_path


def write_units_as_new_docx(output_path: Path | str, units: list[TextUnit]) -> Path:
    """Create a fresh editable Word file from translated units (used for PDF input)."""
    output_path = Path(output_path).with_suffix(".docx")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = Document()
    doc.add_heading("Tarjima natijasi", level=1)

    current_page = None
    for u in units:
        text = (u.translated or u.text or "").strip()
        if not text:
            continue
        page = u.meta.get("page")
        if page is not None and page != current_page:
            current_page = page
            if current_page > 0:
                doc.add_page_break()
            doc.add_heading(f"Sahifa {int(current_page) + 1}", level=2)
        doc.add_paragraph(text)

    doc.save(str(output_path))
    return output_path


def write_document(input_path: Path | str, output_path: Path | str, units: list[TextUnit]) -> Path:
    """
    Always write Word (.docx) for easy later editing.

    - DOCX input → format-preserving in-place replacement
    - PDF input  → new editable .docx from translated text units
    """
    path = Path(input_path)
    output_path = Path(output_path).with_suffix(".docx")
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return write_docx(path, output_path, units)
    if suffix == ".pdf":
        return write_units_as_new_docx(output_path, units)
    raise ValueError(f"Qo'llab-quvvatlanmaydigan format: {suffix}")
