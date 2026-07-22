# Offline EN/RU → UZ Tarjimon

Kompyuterda internetsiz ishlaydigan **inglizcha va ruscha → o'zbekcha (lotin)** tarjimon dasturi.

PDF yoki Word (`.docx`) faylni yuklaysiz — dastur matnni ajratadi, tarjima qiladi. **Standart: asl format** (PDF → PDF, rasmlar saqlanadi). Kerak bo‘lsa Word yoki PDF ni o‘zingiz tanlaysiz.

---

## Nima qila oladi?

| Imkoniyat | Holat |
| --- | --- |
| Inglizcha → o'zbekcha (lotin) | Ha |
| Ruscha → o'zbekcha (lotin) | Ha |
| Oddiy matn (terminal) | Ha |
| Word (`.docx`) — format saqlanadi | Ha |
| PDF → PDF (rasmlar saqlanadi) | Ha |
| PDF → Word (rasmlar ko‘chiriladi) | Ha (imkoni bo‘lsa) |
| Format tanlash (auto / docx / pdf) | Ha |
| Brauzer interfeysi (Streamlit) | Ha |
| GPU orqali tezlashtirish (CUDA) | Ha (sozlanganda) |
| Skaner / rasm PDF (OCR) | Yo'q (hozircha) |

---

## Natija formati

**Standart: asl format (`auto`).**

| Kirish | Chiqish (auto) | Nima uchun |
| --- | --- | --- |
| PDF | PDF | Rasmlar, chizmalar o‘rinida qoladi |
| Word | Word | Tahrirlash oson, format saqlanadi |

Sidebar / CLI da formatni o‘zgartirish mumkin:

- **Asl format** — tavsiya (PDF rasmlari yo‘qolmaydi)
- **Word (.docx)** — PDF dan Word ga o‘tkazganda sahifa rasmlari ham ko‘chirilishga uriniladi
- **PDF** — DOCX dan oddiy matnli PDF

O'zbekcha apostrof (`o'zbek`) maxsus belgilari oddiy `'` ga normallashtiriladi — `?` ko'rinishi bartaraf etiladi.

---

## Talablar

- Windows 10 / 11
- Python **3.12** (3.14 bilan PyTorch / CUDA muammoli)
- Taxminan **2–3 GB** bo'sh disk (model uchun)
- Ixtiyoriy: NVIDIA videokarta (tezlik uchun), masalan GTX 1650

Tekshirish:

```powershell
python --version
nvidia-smi
```

---

## Birinchi o'rnatish

```powershell
cd C:\d-disk\pdf-tarjimon\translator_app

# Virtual muhit
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Kutubxonalar
pip install -r requirements.txt

# Modelni yuklab, CTranslate2 int8 formatiga o'girish (bir marta)
python scripts\convert_model.py
```

### GPU (CUDA) — tezlik uchun

Videokarta bo'lsa:

```powershell
pip install nvidia-cublas-cu12 nvidia-cuda-runtime-cu12
```

Yoki [NVIDIA CUDA Toolkit 12.x](https://developer.nvidia.com/cuda-downloads) ni tizimga o'rnating.

Keyin sozlamada **Qurilma = auto** yoki **cuda** tanlang.
Agar DLL topilmasa, dastur avtomatik **CPU** ga o'tadi.

---

## Ishga tushirish

### Brauzer (tavsiya etiladi)

```powershell
cd C:\d-disk\pdf-tarjimon\translator_app
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

Ochiladi: <http://localhost:8501>

**Qanday ishlatiladi:**

1. PDF yoki Word yuklang
2. Sidebar da **Yuklab olish formati** ni tanlang (standart: Asl format)
3. **1. Matnni ko'rish** — fayldan matn chiqishini tekshiring
4. **2. Tarjima qilish** — to'liq tarjima (progress ko'rinadi)
5. **3. Natijani yuklab olish** — PDF yoki Word

### Yon panel sozlamalari

| Sozlama | Ma'nosi |
| --- | --- |
| Qurilma: `auto` | GPU bo'lsa CUDA, bo'lmasa CPU |
| Qurilma: `cuda` | Majburiy GPU (tezroq) |
| Qurilma: `cpu` | Faqat protsessor |
| Manba til | Avto / Inglizcha / Ruscha |
| Yuklab olish formati | Asl / Word / PDF (PDF da rasmlar saqlanadi) |
| Batch hajmi | Bir vaqtda nechta jumla (katta = tezroq). Default: 32 |
| Sifat / tezlik | **Tez** (`beam=1`) yoki **Yaxshiroq sifat** (`beam=4`) |

> **Deploy** tugmasi Streamlit'niki — internetga joylash uchun.
> Offline tarjimaga kerak emas.

### Terminal (CLI)

```powershell
cd C:\d-disk\pdf-tarjimon\translator_app
.\.venv\Scripts\Activate.ps1

# Oddiy matn
python main.py --text "Hello, how are you?" --source eng_Latn --device auto
python main.py --text "Привет, как дела?" --source rus_Cyrl --device auto

# Word / PDF — asl format (PDF → PDF, rasmlar saqlanadi)
python main.py --input samples\sample_en.docx --output outputs\natija.docx --device auto
python main.py --input samples\sample_en.pdf --output outputs\natija.pdf --device auto

# PDF ni majburiy Word ga (rasmlar ko‘chiriladi)
python main.py --input samples\sample_en.pdf --output outputs\natija.docx --output-format docx --device auto

# Interaktiv
python main.py --interactive --device auto
```

**Foydali argumentlar:**

- `--device auto|cuda|cpu`
- `--output-format auto|docx|pdf` (default: `auto`)
- `--batch-size 32` (default)
- `--beam-size 1` (tez) yoki `4` (sifat)
- `--source eng_Latn|rus_Cyrl|auto`

---

## Ichki ishlash tartibi

```text
Fayl (PDF yoki DOCX)
        |
        v
1) Matnni ajratish
        |
        v
2) Barcha bo'laklarni NLLB bilan tarjima qilish
        |
        v
3) Tanlangan formatga yozish (auto = asl; PDF da rasmlar qoladi)
        |
        v
Natija: *_uz.pdf yoki *_uz.docx
```

### Model

- **Nomi:** `facebook/nllb-200-distilled-600M`
- **Format:** CTranslate2 **int8**
- **Maqsad til:** `uzn_Latn` (o'zbek lotin)
- **Manba tillar:** `eng_Latn`, `rus_Cyrl`

Katta model (`3.3B`) sifatni biroz oshirishi mumkin, lekin 4 GB videokartada og'ir.

---

## Tezlikni oshirish

1. **Greedy decoding** (`beam_size=1`) — `beam=4` dan bir necha baravar tez
2. **Katta batch** (default 32) — GPU/CPU ni to'liqroq yuklaydi
3. **int8** kvantlash — kam xotira, tezroq
4. **CUDA** — NVIDIA GPU da ishlash
5. **CPU** da ko'p oqimli ishlash

Agar hali sekin bo'lsa:

- Qurilmani `cuda` / `auto` qiling
- Batch ni 32–48 ga oshiring
- Sifat/tezlikni **Tez** qoldiring
- Juda katta PDF ni bo'laklarga bo'lib tarjima qiling

---

## Loyiha tuzilmasi

```text
translator_app/
├── app.py                 # Brauzer interfeysi (Streamlit)
├── main.py                # Terminal CLI
├── requirements.txt       # Python paketlar
├── README.md              # Ushbu qo'llanma
├── models/                # CT2 modeli (gitignore)
├── samples/               # Namuna fayllar
├── outputs/               # Tarjima natijalari
├── scripts/
│   ├── convert_model.py   # HF → CT2 konvertatsiya
│   └── quality_check.py   # Sifat tekshiruvi
├── src/
│   ├── pipeline.py        # extract → translate → write-back
│   ├── translator/        # NLLB + CTranslate2
│   ├── extractors/        # PDF/DOCX dan matn olish
│   ├── writers/           # PDF / Word ga yozish (rasmlar)
│   └── utils/             # Til aniqlash, normalizatsiya
└── tests/
```

---

## Cheklovlar va ogohlantirishlar

1. **Skaner PDF** — rasmdagi matn o'qilmaydi (OCR yo'q). Avval matnli PDF/DOCX qiling.
2. **PDF chiqish** — matn almashtiriladi, rasmlar joyida qoladi (`auto` / `pdf`).
3. **PDF → Word** — matn + imkoni bo‘lsa sahifa rasmlari Word ga ko‘chiriladi.
4. **DOCX** — paragraf / jadval / header / footer qo'llab-quvvatlanadi.
5. **Tarjima sifati** — NLLB-600M umumiy model; maxsus atamalar ba'zan xato chiqishi mumkin.
6. **Birinchi ishga tushirish** — model yuklash 1–2 daqiqa olishi mumkin.

---

## Muammolarni bartaraf etish

| Muammo | Yechim |
| --- | --- |
| Matn topilmadi | Skaner PDF — OCR kerak yoki DOCX ga o'tkazing |
| Tarjima tugmasi hech narsa qilmayapti | Progress / xato panelini qarang; birinchi marta model yuklanadi |
| `cublas64_12.dll` xatosi | `pip install nvidia-cublas-cu12 nvidia-cuda-runtime-cu12` yoki CPU tanlang |
| Streamlit ochilmaydi | `streamlit run app.py` ni qayta ishga tushiring; port 8501 band emasligini tekshiring |
| Python 3.14 xatosi | Python **3.12** venv ishlating |

---

## Namuna buyruqlar (sifat tekshiruvi)

```powershell
python scripts\quality_check.py --device auto
python -m tests.test_translator
```

---

## Litsenziya / model

- Dastur kodlari — loyiha egasiga tegishli.
- **NLLB-200** — Meta'ning ochiq modeli (o'z litsenziyasi bilan).
- Tarjima natijalarini muhim hujjatlarda qo'lda tekshirish tavsiya etiladi.

---

## Qisqa xulosa

1. `.venv` ni faollashtiring
2. `streamlit run app.py`
3. Fayl yuklang → format tanlang → matnni ko'ring → tarjima qiling → **PDF/Word yuklab oling**
4. Tezlik uchun: **Qurilma = auto/cuda**, **Batch = 32**, **Sifat/tezlik = Tez**
