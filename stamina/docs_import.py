"""«ОТКРЫТЬ» — загрузить документ с компьютера на борт.

Форматы: .txt, .md, .docx (со снимками, без внешних библиотек — читаем XML
внутри zip), .stdoc. Открытый файл становится документом в списке; у документа
запоминается исходник (``doc.source``), и для .txt/.md/.docx его можно
сохранить обратно в тот же файл. Последние открытые файлы — в настройках.
"""
from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from stamina import docs

KINDS = (".txt", ".md", ".markdown", ".docx", ".stdoc")
WRITE_BACK = {".txt": "txt", ".md": "md", ".markdown": "md", ".docx": "docx"}
RECENT_KEY = "docs_recent_files"
RECENT_MAX = 12

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def supported(path) -> bool:
    return Path(path).suffix.lower() in KINDS


def can_write_back(doc) -> bool:
    src = getattr(doc, "source", None)
    return bool(src) and Path(src).suffix.lower() in WRITE_BACK


def import_txt(path: Path) -> docs.Document:
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp1251"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", "replace")
    return docs.Document(Path(path).stem, [{"t": text.replace("\r\n", "\n")}])


def _run_text(r) -> str:
    out = []
    for el in r:
        if el.tag == W + "t":
            out.append(el.text or "")
        elif el.tag == W + "tab":
            out.append("\t")
        elif el.tag in (W + "br", W + "cr"):
            out.append("\n")
    return "".join(out)


def _flag(rpr, name) -> bool:
    if rpr is None:
        return False
    el = rpr.find(W + name)
    return el is not None and el.get(W + "val", "true") not in ("0", "false", "none")


def import_docx(path: Path) -> docs.Document:
    """Абзацы, заголовки (Heading/Title/«Заголовок»), списки, жирный/курсив, снимки."""
    path = Path(path)
    doc = docs.Document(path.stem)
    with zipfile.ZipFile(path) as z:
        body = ET.fromstring(z.read("word/document.xml")).find(W + "body")
        rels = {}
        try:
            for r in ET.fromstring(z.read("word/_rels/document.xml.rels")).iter(REL + "Relationship"):
                rels[r.get("Id")] = r.get("Target", "")
        except KeyError:
            pass
        styles = {}
        try:
            for st in ET.fromstring(z.read("word/styles.xml")).iter(W + "style"):
                nm = st.find(W + "name")
                styles[st.get(W + "styleId")] = (nm.get(W + "val") if nm is not None else "") or ""
        except KeyError:
            pass
        buf: list[str] = []

        def flush():
            if buf:
                doc.segments.append({"t": "".join(buf)})
                buf.clear()

        paras = [p for p in body.iter(W + "p")] if body is not None else []
        for p in paras:
            ppr = p.find(W + "pPr")
            sid = ""
            if ppr is not None and ppr.find(W + "pStyle") is not None:
                sid = ppr.find(W + "pStyle").get(W + "val", "")
            name = (styles.get(sid) or sid).lower()
            m = re.search(r"(?:heading|заголовок)\s*(\d)", name)
            prefix = ""
            if m:
                prefix = "#" * max(1, min(6, int(m.group(1)))) + " "
            elif name in ("title", "название"):
                prefix = "# "
            elif ppr is not None and ppr.find(W + "numPr") is not None or "list" in name:
                prefix = "- "
            elif "quote" in name or "цитата" in name:
                prefix = "> "
            line = []
            for r in p.iter(W + "r"):
                blips = list(r.iter(A + "blip"))
                for b in blips:
                    target = rels.get(b.get(R + "embed"), "")
                    member = "word/" + target.lstrip("/").removeprefix("word/") if target else ""
                    if member in z.namelist():
                        buf.append(prefix + "".join(line))
                        line, prefix = [], ""
                        flush()
                        ext = Path(member).suffix.lower() or ".png"
                        nm = doc.add_image(z.read(member), ".jpg" if ext == ".jpeg" else ext)
                        doc.segments.append({"img": nm, "w": 0})
                t = _run_text(r)
                if not t:
                    continue
                rpr = r.find(W + "rPr")
                b, i = _flag(rpr, "b"), _flag(rpr, "i")
                if (b or i) and t.strip() and not m:
                    mark = "***" if b and i else "**" if b else "*"
                    lead, core, tail = re.match(r"(\s*)(.*?)(\s*)$", t, re.S).groups()
                    t = f"{lead}{mark}{core}{mark}{tail}"
                line.append(t)
            txt = "".join(line)
            bm = re.match(r"\s*[•·▪◦]\s+", txt)
            if bm:                                   # маркер списка набран текстом
                prefix, txt = (prefix if prefix.startswith("-") else "- "), txt[bm.end():]
            buf.append(prefix + txt + "\n")
        flush()
    if doc.segments and "t" in doc.segments[-1]:
        doc.segments[-1]["t"] = doc.segments[-1]["t"].rstrip("\n") + "\n"
    first = next((s for s in doc.segments if "t" in s), None)
    if first is not None:
        mm = re.match(r"#\s+(.+?)\n+", first["t"])
        if mm:
            doc.title, first["t"] = mm.group(1).strip(), first["t"][mm.end():]
    return doc


def import_file(path) -> docs.Document:
    """Файл с диска → новый документ на борту (ещё не сохранён)."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".stdoc":
        d = docs.load(path)
        d.path = None                       # копия на борту, оригинал не трогаем
    elif ext in (".md", ".markdown"):
        d = docs.import_md(path)
    elif ext == ".docx":
        d = import_docx(path)
    elif ext == ".txt":
        d = import_txt(path)
    else:
        raise ValueError(ext)
    d.source = str(path)
    return d


def write_back(doc) -> Path:
    """Сохранить документ обратно в исходный файл (.txt/.md/.docx)."""
    src = Path(doc.source)
    kind = WRITE_BACK[src.suffix.lower()]
    fn = {"txt": docs.export_txt, "md": docs.export_md, "docx": docs.export_docx}[kind]
    return fn(doc, src)


# -- последние файлы --------------------------------------------------------------
def recent(settings) -> list[str]:
    items = (settings or {}).get(RECENT_KEY) or []
    return [p for p in items if isinstance(p, str)]


def remember(settings, path) -> None:
    if settings is None:
        return
    p = str(Path(path))
    items = [x for x in recent(settings) if x != p]
    settings[RECENT_KEY] = ([p] + items)[:RECENT_MAX]
