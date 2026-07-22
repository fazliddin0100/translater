"""Streamlit UI: extract → translate → write-back with visible steps."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.extractors.document import extract_document
from src.pipeline import translate_document
from src.translator.engine import TranslatorEngine

st.set_page_config(page_title="UZ Tarjimon", page_icon="📄", layout="wide")

st.title("Offline EN/RU → UZ Tarjimon")
st.caption(
    "PDF yoki Word yuklang → tarjima. Rasmlar uchun PDF ni asl formatda yuklab oling."
)

with st.sidebar:
    st.header("Sozlamalar")
    device = st.selectbox(
        "Qurilma",
        ["auto", "cuda", "cpu"],
        index=0,
        help="auto = GPU bo‘lsa CUDA, bo‘lmasa CPU. CUDA — tezroq.",
    )
    lang_label = st.selectbox(
        "Manba til",
        ["Avto aniqlash", "Inglizcha", "Ruscha"],
        index=0,
    )
    source_map = {
        "Avto aniqlash": "auto",
        "Inglizcha": "eng_Latn",
        "Ruscha": "rus_Cyrl",
    }
    source = source_map[lang_label]
    out_fmt_label = st.selectbox(
        "Yuklab olish formati",
        [
            "Asl format (tavsiya)",
            "Word (.docx)",
            "PDF",
        ],
        index=0,
        help="PDF da rasmlar saqlanadi. Word ga o‘tkazganda rasmlar ham ko‘chirilishga uriniladi.",
    )
    out_fmt_map = {
        "Asl format (tavsiya)": "auto",
        "Word (.docx)": "docx",
        "PDF": "pdf",
    }
    output_format = out_fmt_map[out_fmt_label]
    batch_size = st.slider("Batch hajmi (katta = tezroq, ko‘proq xotira)", 8, 64, 32)
    beam_size = st.selectbox(
        "Sifat / tezlik",
        [("Tez (tavsiya)", 1), ("Yaxshiroq sifat", 4)],
        format_func=lambda x: x[0],
    )[1]
    st.info(
        "PDF skaner (rasm) bo‘lsa matn chiqmaydi. Oddiy matnli PDF/DOCX bilan sinang."
    )


@st.cache_resource(show_spinner=False)
def load_engine(device_name: str, beam: int, batch: int) -> TranslatorEngine:
    return TranslatorEngine(
        device=device_name,
        beam_size=beam,
        default_batch_size=batch,
    )


# --- session defaults ---
for key, default in {
    "result_bytes": None,
    "result_name": None,
    "result_mime": None,
    "preview_rows": None,
    "extract_count": 0,
    "last_error": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

uploaded = st.file_uploader("PDF yoki Word (.docx) yuklang", type=["docx", "pdf"])

c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    preview_btn = st.button(
        "1. Matnni ko‘rish",
        disabled=uploaded is None,
        width='stretch',
    )
with c2:
    run_btn = st.button(
        "2. Tarjima qilish",
        type="primary",
        disabled=uploaded is None,
        width='stretch',
    )
with c3:
    clear_btn = st.button("Tozalash", width='stretch')

if clear_btn:
    for k in ("result_bytes", "result_name", "result_mime", "preview_rows", "last_error"):
        st.session_state[k] = None
    st.session_state.extract_count = 0
    st.rerun()

status = st.empty()
progress_bar = st.progress(0.0, text="Kutish…")


def _on_progress(done: int, total: int, msg: str) -> None:
    total = max(total, 1)
    progress_bar.progress(min(done / total, 0.99), text=msg)
    status.info(msg)


if uploaded is not None and preview_btn:
    try:
        st.session_state.last_error = None
        suffix = Path(uploaded.name).suffix.lower()
        tmp = ROOT / "outputs" / "_upload_preview"
        tmp.mkdir(parents=True, exist_ok=True)
        in_path = tmp / uploaded.name
        in_path.write_bytes(uploaded.getvalue())

        status.info("Matn ajratilmoqda…")
        units = extract_document(in_path)
        st.session_state.extract_count = len(units)
        st.session_state.preview_rows = [
            {"#": i + 1, "Asl matn": u.text[:300]} for i, u in enumerate(units[:80])
        ]
        if not units:
            st.session_state.last_error = (
                "Matn topilmadi. Bu skaner PDF bo‘lishi mumkin yoki faylda matn yo‘q."
            )
        else:
            status.success(f"Topildi: {len(units)} ta matn bo‘lagi")
            progress_bar.progress(1.0, text="Matn ajratildi")
    except Exception as exc:  # noqa: BLE001
        st.session_state.last_error = f"{exc}\n{traceback.format_exc()}"
        status.error(str(exc))

if uploaded is not None and run_btn:
    try:
        st.session_state.last_error = None
        st.session_state.result_bytes = None
        suffix = Path(uploaded.name).suffix.lower()
        if suffix not in {".docx", ".pdf"}:
            raise ValueError("Faqat .docx yoki .pdf")

        out_dir = ROOT / "outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        in_path = out_dir / f"_upload{suffix}"
        in_path.write_bytes(uploaded.getvalue())

        # Resolve extension for filename preview
        if output_format == "auto":
            out_ext = suffix
        elif output_format == "docx":
            out_ext = ".docx"
        else:
            out_ext = ".pdf"
        out_name = f"{Path(uploaded.name).stem}_uz{out_ext}"
        out_path = out_dir / out_name

        status.info("Model yuklanmoqda (birinchi marta 1–2 daqiqa ketishi mumkin)…")
        progress_bar.progress(0.05, text="Model yuklanmoqda…")
        engine = load_engine(device, beam_size, batch_size)
        status.info(f"Qurilma: {engine.device} | compute: {engine.compute_type}")

        result_path, units = translate_document(
            in_path,
            out_path,
            engine=engine,
            source_lang=source,
            device=device,
            batch_size=batch_size,
            output_format=output_format,
            progress=_on_progress,
        )

        st.session_state.result_bytes = result_path.read_bytes()
        st.session_state.result_name = result_path.name
        if result_path.suffix.lower() == ".pdf":
            st.session_state.result_mime = "application/pdf"
        else:
            st.session_state.result_mime = (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        st.session_state.extract_count = len(units)
        st.session_state.preview_rows = [
            {
                "#": i + 1,
                "Asl matn": u.text[:200],
                "Tarjima": (u.translated or "")[:200],
            }
            for i, u in enumerate(units[:80])
        ]
        progress_bar.progress(1.0, text="Tayyor!")
        status.success(
            f"Tayyor: {len(units)} bo‘lak → {result_path.name}"
        )
    except Exception as exc:  # noqa: BLE001
        st.session_state.last_error = f"{exc}\n{traceback.format_exc()}"
        status.error(f"Xato: {exc}")
        progress_bar.progress(0.0, text="Xato")

# --- always show state ---
if st.session_state.last_error:
    with st.expander("Xato tafsiloti", expanded=True):
        st.code(st.session_state.last_error)

if st.session_state.preview_rows:
    st.subheader(f"Matn / tarjima ko‘rinishi ({st.session_state.extract_count} bo‘lak)")
    st.dataframe(st.session_state.preview_rows, width='stretch', hide_index=True)

if st.session_state.result_bytes:
    label = "3. Natijani yuklab olish"
    name = st.session_state.result_name or "tarjima_uz.bin"
    if name.lower().endswith(".pdf"):
        label = "3. PDF yuklab olish"
    elif name.lower().endswith(".docx"):
        label = "3. Word (.docx) yuklab olish"
    st.download_button(
        label=label,
        data=st.session_state.result_bytes,
        file_name=name,
        mime=st.session_state.result_mime or "application/octet-stream",
        type="primary",
        width="stretch",
    )
else:
    st.caption("Tarjima tugagach bu yerda yuklab olish tugmasi chiqadi.")
