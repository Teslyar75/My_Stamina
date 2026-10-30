"""Документы пилота: формат .stdoc, список, автосохранение, экспорт.

.stdoc — обычный zip: ``document.json`` (заголовок, время, сегменты текста и
картинок) и папка ``images/`` с оригиналами снимков. Открыть можно любым
архиватором — документы пилота не заперты в программе.
Модуль без Tk — его проверяют тесты.
"""
from __future__ import annotations

import html
import io
import json
import os
import time
import zipfile
from pathlib import Path

SUFFIX = ".stdoc"
FORMAT = 1
DOC_JSON = "document.json"
DIR_NAME = "documents"


def docs_dir() -> Path:
    """Папка документов активного пилота (без реестра — общий корень данных)."""
    from stamina import pilots
    d = Path(pilots.active_dir()) / DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


class Document:
    """Документ в памяти: заголовок и сегменты ``{"t": текст}`` / ``{"img": имя, "w": ширина}``."""

    def __init__(self, title: str = "", segments: list | None = None, images: dict | None = None,
                 created: float | None = None, modified: float | None = None,
                 path: Path | None = None) -> None:
        self.title = title
        self.segments = list(segments or [])
        self.images: dict[str, bytes] = dict(images or {})   # имя → PNG/JPEG-байты
        self.created = created or time.time()
        self.modified = modified or self.created
        self.path = path

    @property
    def text(self) -> str:
        return "".join(s.get("t", "") for s in self.segments)

    def add_image(self, data: bytes, ext: str = ".png") -> str:
        n = len(self.images) + 1
        while f"images/{n}{ext}" in self.images:
            n += 1
        name = f"images/{n}{ext}"
        self.images[name] = data
        return name

    def display_title(self) -> str:
        if self.title.strip():
            return self.title.strip()
        first = next((ln.strip() for ln in self.text.splitlines() if ln.strip()), "")
        return first[:60]


def _safe_name(title: str) -> str:
    keep = "".join(ch if ch.isalnum() or ch in " -_" else " " for ch in title).strip()
    return " ".join(keep.split())[:48] or "doc"


def new_path(title: str = "") -> Path:
    d = docs_dir()
    base = time.strftime("%Y-%m-%d_%H%M%S") + "_" + _safe_name(title)
    p = d / f"{base}{SUFFIX}"
    i = 2
    while p.exists():
        p = d / f"{base}_{i}{SUFFIX}"
        i += 1
    return p


def save(doc: Document, path: Path | None = None) -> Path:
    """Атомарная запись: во временный файл, затем replace — сбой не портит документ."""
    path = Path(path or doc.path or new_path(doc.title))
    doc.modified = time.time()
    used = {s["img"] for s in doc.segments if "img" in s}
    meta = {"format": FORMAT, "title": doc.title, "created": doc.created,
            "modified": doc.modified, "segments": doc.segments}
    tmp = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(DOC_JSON, json.dumps(meta, ensure_ascii=False, indent=1))
        for name, data in doc.images.items():
            if name in used:
                z.writestr(name, data, compress_type=zipfile.ZIP_STORED)
    os.replace(tmp, path)
    doc.path = path
    return path


def load(path: Path) -> Document:
    path = Path(path)
    with zipfile.ZipFile(path) as z:
        meta = json.loads(z.read(DOC_JSON).decode("utf-8"))
        images = {n: z.read(n) for n in z.namelist() if n.startswith("images/") and not n.endswith("/")}
    segs = [s for s in meta.get("segments") or [] if isinstance(s, dict) and ("t" in s or "img" in s)]
    return Document(str(meta.get("title") or ""), segs, images, meta.get("created"),
                    meta.get("modified"), path)


def peek(path: Path) -> dict:
    """Карточка для списка без чтения картинок: заголовок, время, начало текста."""
    try:
        with zipfile.ZipFile(path) as z:
            meta = json.loads(z.read(DOC_JSON).decode("utf-8"))
    except (OSError, zipfile.BadZipFile, KeyError, ValueError):
        return {"path": Path(path), "title": Path(path).stem, "modified": 0.0, "snippet": "", "broken": True}
    doc = Document(str(meta.get("title") or ""), meta.get("segments") or [])
    text = " ".join(doc.text.split())
    pics = sum(1 for s in doc.segments if "img" in s)
    return {"path": Path(path), "title": doc.display_title(), "modified": float(meta.get("modified") or 0),
            "snippet": text[:120], "words": len(text.split()), "images": pics, "broken": False}


def list_docs() -> list[dict]:
    """Документы пилота: свежие сверху."""
    items = [peek(p) for p in docs_dir().glob(f"*{SUFFIX}")]
    return sorted(items, key=lambda d: d["modified"], reverse=True)


def remove_to_trash(path: Path) -> Path:
    """«Удалить» — переложить в корзину documents/.trash (вернуть можно руками)."""
    path = Path(path)
    trash = path.parent / ".trash"
    trash.mkdir(exist_ok=True)
    dest = trash / path.name
    os.replace(path, dest)
    return dest


# -- экспорт ---------------------------------------------------------------------
def export_txt(doc: Document, path: Path) -> Path:
    head = (doc.title.strip() + "\n\n") if doc.title.strip() else ""
    Path(path).write_text(head + doc.text, encoding="utf-8")
    return Path(path)


def export_html(doc: Document, path: Path) -> Path:
    """HTML с картинками внутри (data URI) — один файл, открывается где угодно."""
    import base64
    parts = [f"<h1>{html.escape(doc.title)}</h1>"] if doc.title.strip() else []
    for s in doc.segments:
        if "t" in s:
            parts.append(html.escape(s["t"]).replace("\n", "<br>\n"))
        elif s.get("img") in doc.images:
            mime = "image/jpeg" if s["img"].lower().endswith((".jpg", ".jpeg")) else "image/png"
            b64 = base64.b64encode(doc.images[s["img"]]).decode("ascii")
            w = int(s.get("w") or 0)
            style = f' style="width:{w}px;max-width:100%"' if w else ' style="max-width:100%"'
            parts.append(f'<img src="data:{mime};base64,{b64}"{style}>')
    body = "\n".join(parts)
    page = ("<!doctype html><html><head><meta charset=\"utf-8\">"
            f"<title>{html.escape(doc.display_title())}</title></head>"
            f"<body style=\"font-family:sans-serif;max-width:900px;margin:2em auto\">{body}</body></html>")
    Path(path).write_text(page, encoding="utf-8")
    return Path(path)


def image_bytes(img, fmt: str = "PNG") -> bytes:
    """PIL.Image → байты (снимок из буфера или с экрана)."""
    buf = io.BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


# -- PDF (fpdf2: чистый Python, бесплатный; кириллица — системный TTF) ----------
FONT_CANDIDATES = (
    r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\tahoma.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial Unicode.ttf",
)
PX_TO_MM = 25.4 / 96


def pdf_available() -> bool:
    try:
        import fpdf  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def find_font() -> Path | None:
    return next((Path(p) for p in FONT_CANDIDATES if Path(p).is_file()), None)


def export_pdf(doc: Document, path: Path, font: Path | None = None) -> Path:
    """PDF A4: заголовок, текст (кириллица через TTF), картинки в своём размере."""
    from fpdf import FPDF
    font = font or find_font()
    if font is None:
        raise RuntimeError("нет TTF-шрифта с кириллицей")
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=15)
    pdf.set_margins(18, 18, 18)
    pdf.add_font("doc", "", str(font))
    pdf.set_title(doc.display_title())
    pdf.add_page()
    if doc.title.strip():
        pdf.set_font("doc", size=18)
        pdf.multi_cell(0, 9, doc.title.strip())
        pdf.ln(3)
    pdf.set_font("doc", size=11.5)
    width = pdf.w - pdf.l_margin - pdf.r_margin
    for s in doc.segments:
        if "t" in s:
            text = s["t"]
            if text:
                pdf.multi_cell(0, 6, text)
        elif s.get("img") in doc.images:
            data = doc.images[s["img"]]
            try:
                from PIL import Image
                with Image.open(io.BytesIO(data)) as im:
                    w_px = int(s.get("w") or im.width)
                    w_mm = min(width, w_px * PX_TO_MM)
                    h_mm = w_mm * im.height / im.width
            except Exception:  # noqa: BLE001
                continue
            if pdf.get_y() + h_mm > pdf.h - pdf.b_margin:
                pdf.add_page()
            pdf.image(io.BytesIO(data), w=w_mm, h=h_mm)
            pdf.ln(2)
    pdf.output(str(path))
    return Path(path)
