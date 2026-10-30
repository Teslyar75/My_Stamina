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
# Текст документа — Markdown (stamina/mdlite.py): в .md он уходит как есть,
# в HTML/PDF/DOCX — настоящим форматированием, в TXT — без разметки.
def _mime(name: str) -> str:
    return "image/jpeg" if name.lower().endswith((".jpg", ".jpeg")) else "image/png"


def export_txt(doc: Document, path: Path) -> Path:
    from stamina import mdlite
    head = (doc.title.strip() + "\n\n") if doc.title.strip() else ""
    Path(path).write_text(head + mdlite.plain(doc.text), encoding="utf-8")
    return Path(path)


def export_md(doc: Document, path: Path) -> Path:
    """Markdown; снимки — файлами в папке «<имя>_files» рядом."""
    path = Path(path)
    files = path.with_name(path.stem + "_files")
    parts = [f"# {doc.title.strip()}\n\n"] if doc.title.strip() else []
    for s in doc.segments:
        if "t" in s:
            parts.append(s["t"])
        elif s.get("img") in doc.images:
            files.mkdir(parents=True, exist_ok=True)
            name = Path(s["img"]).name
            (files / name).write_bytes(doc.images[s["img"]])
            parts.append(f"![]({files.name}/{name})")
    path.write_text("".join(parts), encoding="utf-8")
    return path


def import_md(path: Path) -> Document:
    """Документ из .md: первый «# заголовок» — название, ![](файл) — снимки."""
    import re
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig")
    title = path.stem
    m = re.match(r"\s*#\s+(.+?)\s*(?:\n+|$)", text)
    if m:
        title, text = m.group(1), text[m.end():]
    doc = Document(title)
    pos = 0
    for im in re.finditer(r"!\[[^\]]*\]\(([^)\s]+)\)", text):
        if im.start() > pos:
            doc.segments.append({"t": text[pos:im.start()]})
        src = (path.parent / im.group(1))
        if src.is_file():
            name = doc.add_image(src.read_bytes(), src.suffix.lower() or ".png")
            doc.segments.append({"img": name, "w": 0})
        else:
            doc.segments.append({"t": im.group(0)})
        pos = im.end()
    if pos < len(text):
        doc.segments.append({"t": text[pos:]})
    return doc


def export_html(doc: Document, path: Path) -> Path:
    """HTML с картинками внутри (data URI) — один файл, открывается где угодно."""
    import base64
    from stamina import mdlite
    parts = [f"<h1>{html.escape(doc.title)}</h1>"] if doc.title.strip() else []
    for s in doc.segments:
        if "t" in s:
            parts.append(mdlite.to_html(s["t"]))
        elif s.get("img") in doc.images:
            b64 = base64.b64encode(doc.images[s["img"]]).decode("ascii")
            w = int(s.get("w") or 0)
            style = f' style="width:{w}px;max-width:100%"' if w else ' style="max-width:100%"'
            parts.append(f'<img src="data:{_mime(s["img"])};base64,{b64}"{style}>')
    body = "\n".join(parts)
    page = ("<!doctype html><html><head><meta charset=\"utf-8\">"
            f"<title>{html.escape(doc.display_title())}</title>"
            "<style>blockquote{border-left:3px solid #aaa;margin:0;padding-left:1em;color:#555}"
            "code{background:#eee;padding:0 .2em}p{margin:.2em 0}</style></head>"
            f"<body style=\"font-family:sans-serif;max-width:900px;margin:2em auto\">{body}</body></html>")
    Path(path).write_text(page, encoding="utf-8")
    return Path(path)


def image_bytes(img, fmt: str = "PNG") -> bytes:
    """PIL.Image → байты (снимок из буфера или с экрана)."""
    buf = io.BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


# -- DOCX (руками: zip + WordprocessingML, без зависимостей) ---------------------
def _img_size(data: bytes, w_px: int) -> tuple[int, int]:
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as im:
            w = int(w_px or im.width)
            w = min(w, 620)
            return w, max(1, round(im.height * w / im.width))
    except Exception:  # noqa: BLE001
        return (w_px or 400), (w_px or 400) * 3 // 4


def export_docx(doc: Document, path: Path) -> Path:
    """Word .docx: заголовки, жирный/курсив/подчёркнутый, код, ссылки, списки, цитаты, снимки."""
    from xml.sax.saxutils import escape
    from stamina import mdlite
    EMU = 9525
    rels, body, media = [], [], {}

    def run(text, st=frozenset()):
        rpr = ""
        if "b" in st:
            rpr += "<w:b/>"
        if "i" in st:
            rpr += "<w:i/>"
        if "u" in st or "link" in st:
            rpr += '<w:u w:val="single"/>'
        if "link" in st:
            rpr += '<w:color w:val="1F5FBF"/>'
        if "code" in st:
            rpr += '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:shd w:val="clear" w:fill="EEEEEE"/>'
        rpr = f"<w:rPr>{rpr}</w:rPr>" if rpr else ""
        return f'<w:r>{rpr}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'

    def para(kind, rs):
        style = {"h1": "Heading1", "h2": "Heading2", "quote": "Quote", "li": "ListParagraph"}.get(kind)
        ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        return f"<w:p>{ppr}{''.join(run(t, st) for t, st, _u in rs)}</w:p>"

    if doc.title.strip():
        body.append(f'<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr>{run(doc.title.strip())}</w:p>')
    for s in doc.segments:
        if "t" in s:
            text = s["t"]
            if text.endswith("\n"):
                text = text[:-1]
            if text:
                body.extend(para(k, rs) for k, rs in mdlite.paragraphs(text))
        elif s.get("img") in doc.images:
            n = len(media) + 1
            ext = ".jpg" if _mime(s["img"]) == "image/jpeg" else ".png"
            media[f"word/media/image{n}{ext}"] = doc.images[s["img"]]
            rid = f"rIdImg{n}"
            rels.append(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image{n}{ext}"/>')
            w, h = _img_size(doc.images[s["img"]], int(s.get("w") or 0))
            cx, cy = w * EMU, h * EMU
            body.append(
                f'<w:p><w:r><w:drawing><wp:inline><wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{n}" name="img{n}"/>'
                '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{n}" name="img{n}"/><pic:cNvPicPr/></pic:nvPicPr>'
                f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
                f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"/></pic:spPr>'
                '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')
    ns = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
          'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
          'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
          'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"')
    document = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {ns}><w:body>'
                + "".join(body) + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="0" w:footer="0" w:gutter="0"/>'
                '</w:sectPr></w:body></w:document>')

    def st(sid, name, rpr, ppr=""):
        return (f'<w:style w:type="paragraph" w:styleId="{sid}"><w:name w:val="{name}"/><w:basedOn w:val="Normal"/>'
                f'<w:pPr>{ppr}</w:pPr><w:rPr>{rpr}</w:rPr></w:style>')
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
              '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>'
              '<w:sz w:val="23"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="80" w:line="288" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
              '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
              + st("Title", "Title", '<w:b/><w:sz w:val="40"/>', '<w:spacing w:after="240"/>')
              + st("Heading1", "heading 1", '<w:b/><w:sz w:val="32"/>', '<w:keepNext/><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="0"/>')
              + st("Heading2", "heading 2", '<w:b/><w:sz w:val="27"/>', '<w:keepNext/><w:spacing w:before="200" w:after="100"/><w:outlineLvl w:val="1"/>')
              + st("Quote", "Quote", '<w:i/><w:color w:val="555555"/>', '<w:ind w:left="567"/><w:pBdr><w:left w:val="single" w:sz="12" w:space="8" w:color="AAAAAA"/></w:pBdr>')
              + st("ListParagraph", "List Paragraph", "", '<w:ind w:left="567" w:hanging="283"/>')
              + '</w:styles>')
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Default Extension="png" ContentType="image/png"/><Default Extension="jpg" ContentType="image/jpeg"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
          '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
          '</Types>')
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                 '</Relationships>')
    doc_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                + "".join(rels) + '</Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("word/document.xml", document)
        z.writestr("word/styles.xml", styles)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        for name, data in media.items():
            z.writestr(name, data)
    return Path(path)


# -- PDF (fpdf2: чистый Python, бесплатный; кириллица — системный TTF) ----------
FONT_CANDIDATES = (
    r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\tahoma.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial Unicode.ttf",
)
# начертания рядом с обычным шрифтом: arial.ttf → arialbd/ariali/arialbi
FONT_STYLES = {"arial": ("arialbd", "ariali", "arialbi"), "segoeui": ("segoeuib", "segoeuii", "segoeuiz"),
               "dejavusans": ("DejaVuSans-Bold", "DejaVuSans-Oblique", "DejaVuSans-BoldOblique")}
PX_TO_MM = 25.4 / 96


def pdf_available() -> bool:
    try:
        import fpdf  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def find_font() -> Path | None:
    return next((Path(p) for p in FONT_CANDIDATES if Path(p).is_file()), None)


def _font_variants(font: Path) -> dict:
    names = FONT_STYLES.get(font.stem.lower())
    out = {}
    if names:
        for style, stem in zip(("B", "I", "BI"), names):
            for cand in (font.with_name(stem + font.suffix), font.with_name(stem.lower() + font.suffix)):
                if cand.is_file():
                    out[style] = cand
                    break
    return out


def export_pdf(doc: Document, path: Path, font: Path | None = None) -> Path:
    """PDF A4: заголовок, текст с разметкой (кириллица через TTF), картинки в своём размере."""
    from fpdf import FPDF
    from stamina import mdlite
    font = font or find_font()
    if font is None:
        raise RuntimeError("нет TTF-шрифта с кириллицей")
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=15)
    pdf.set_margins(18, 18, 18)
    pdf.add_font("doc", "", str(font))
    have = {""}
    for style, f in _font_variants(font).items():
        pdf.add_font("doc", style, str(f))
        have.add(style)
    pdf.set_title(doc.display_title())
    pdf.add_page()
    if doc.title.strip():
        pdf.set_font("doc", "B" if "B" in have else "", size=18)
        pdf.multi_cell(0, 9, doc.title.strip())
        pdf.ln(3)
    width = pdf.w - pdf.l_margin - pdf.r_margin
    sizes = {"h1": (16, 8), "h2": (13.5, 7)}
    for s in doc.segments:
        if "t" in s:
            text = s["t"][:-1] if s["t"].endswith("\n") else s["t"]
            if not text:
                continue
            for kind, rs in mdlite.paragraphs(text):
                size, lh = sizes.get(kind, (11.5, 6))
                indent = 6 if kind in ("li", "quote") else 0
                pdf.set_x(pdf.l_margin + indent)
                if kind in ("h1", "h2"):
                    pdf.ln(2)
                for t, st, url in rs:
                    style = ("B" if ("b" in st or kind in ("h1", "h2")) else "") + ("I" if ("i" in st or kind == "quote") else "")
                    if style not in have:
                        style = style[:1] if style[:1] in have else ""
                    pdf.set_font("doc", style + ("U" if ("u" in st or url) else ""), size=size)
                    pdf.set_text_color(31, 95, 191) if url else pdf.set_text_color(0, 0, 0)
                    pdf.write(lh, t, link=url or "")
                pdf.set_text_color(0, 0, 0)
                pdf.ln(lh)
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
