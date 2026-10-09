"""Импорт PDF в библиотеку текстов: извлечь текст (pypdf, чистый Python) и привести его в порядок.

Чистка: лигатуры (ﬁ → fi), мягкие переносы, слова с переносом на конце строки (сло-/во → слово),
номера страниц, повторяющиеся колонтитулы (одинаковые первые/последние строки на многих страницах),
склейка строк в абзацы. Скан без текстового слоя распознаётся (почти нет текста на страницу) —
тогда вернётся scanned=True и пустой текст: такой PDF нужно сначала распознать (OCR) другой программой.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

LIGATURES = {"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl",
             "\ufb05": "st", "\ufb06": "st", "\u00ad": "", "\u200b": "", "\ufeff": "",
             "\u00a0": " ", "\u2009": " ", "\u202f": " "}
_LIG_RE = re.compile("|".join(map(re.escape, LIGATURES)))
PAGE_NUM = re.compile(r"^\s*(?:[-–—]\s*)?(?:(?:стр\.?|с\.|page|p\.|seite|сторінка)\s*)?\d{1,4}"
                      r"(?:\s*(?:/|of|из|von|з)\s*\d{1,4})?(?:\s*[-–—])?\s*$", re.I)
SCANNED_CHARS_PER_PAGE = 25
SENT_END = tuple(".!?…:;»\"”)")
PAGE_BREAK = "\x00page"


class PdfError(Exception):
    pass


@dataclass
class PdfResult:
    text: str
    total_pages: int
    first: int
    last: int
    scanned: bool = False
    raw_chars: int = 0
    removed: dict = field(default_factory=dict)


def available() -> bool:
    try:
        import pypdf  # noqa: F401
    except ImportError:
        return False
    return True


def page_count(path: str | Path) -> int:
    import pypdf
    try:
        return len(pypdf.PdfReader(str(path)).pages)
    except Exception as exc:  # pypdf бросает разные исключения на битых файлах
        raise PdfError(str(exc)) from exc


def extract_pages(path: str | Path, first: int = 1, last: int | None = None) -> tuple[list[str], int]:
    """Сырые тексты страниц first..last (с 1, включительно). → (страницы, всего страниц)."""
    import pypdf
    try:
        reader = pypdf.PdfReader(str(path))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:
                raise PdfError("PDF защищён паролем") from exc
        total = len(reader.pages)
        last = total if not last else min(last, total)
        first = max(1, min(first, last or 1))
        pages = []
        for i in range(first - 1, last):
            try:
                pages.append(reader.pages[i].extract_text() or "")
            except Exception:
                pages.append("")
        return pages, total
    except PdfError:
        raise
    except Exception as exc:
        raise PdfError(str(exc)) from exc


def fix_chars(s: str) -> str:
    s = _LIG_RE.sub(lambda m: LIGATURES[m.group(0)], s)
    s = s.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    return re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", s)       # управляющие символы вместо номеров страниц


def _norm(line: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\d+", "", line.lower())).strip()     # номер страницы не в счёт


def strip_headers(pages: list[list[str]], context: list[list[str]] | None = None
                  ) -> tuple[list[list[str]], int, int]:
    """Убрать номера страниц и колонтитулы. → (страницы, номеров, колонтитулов).
    context — соседние страницы файла: по ним видно колонтитулы, даже если выбрана одна страница."""
    nums = heads = 0
    cleaned = []
    for lines in pages:
        keep = []
        for i, ln in enumerate(lines):
            edge = i < 3 or i >= len(lines) - 3
            if edge and PAGE_NUM.match(ln):
                nums += 1
                continue
            keep.append(ln)
        cleaned.append(keep)
    sample = cleaned + [[x for x in pg if not PAGE_NUM.match(x)] for pg in (context or [])]
    if len(sample) >= 3:
        cnt = Counter()
        for lines in sample:
            edge = {_norm(x) for x in lines[:2] + lines[-2:] if x.strip()}
            cnt.update(edge)
        limit = max(2, len(sample) * 0.4)
        rep = {k for k, v in cnt.items() if v >= limit and len(k) < 120}
        if rep:
            out = []
            for lines in cleaned:
                keep = []
                for i, ln in enumerate(lines):
                    edge = i < 2 or i >= len(lines) - 2
                    if edge and _norm(ln) in rep:
                        heads += 1
                        continue
                    keep.append(ln)
                out.append(keep)
            cleaned = out
    return cleaned, nums, heads


def to_paragraphs(lines: list[str]) -> str:
    """Склеить строки в абзацы: перенос со слогом убрать, короткая строка с точкой — конец абзаца."""
    lines = [re.sub(r"[ ]{2,}", " ", ln.rstrip()) for ln in lines]
    lengths = [len(x.strip()) for x in lines if len(x.strip()) > 20]
    width = statistics.median(lengths) if lengths else 60
    paras, cur = [], ""
    for raw in lines:
        if raw == PAGE_BREAK:                                   # граница страниц: абзац продолжается,
            continue                                      # если строка не закончена
        ln = raw.strip()
        if not ln:
            if cur:
                paras.append(cur)
                cur = ""
            continue
        indent = raw[:1] == " "          # pypdf отмечает красную строку пробелом
        starts_dialogue = ln[:1] in "—–-•" and not cur.endswith("-")
        if cur and (indent or starts_dialogue):
            paras.append(cur)
            cur = ""
        heading = (not cur and len(ln) < width * 0.7 and ln[:1].isupper()
                   and not ln.endswith(SENT_END + (",", "-")) and len(ln.split()) <= 8)
        if heading:
            paras.append(ln)                                  # заголовок — отдельной строкой
            continue
        if not cur:
            cur = ln
        elif re.search(r"[^\W\d_] ?[-\u00ad]$", cur) and ln[:1].islower():
            cur = re.sub(r" ?[-\u00ad]$", "", cur) + ln                  # сло- / во → слово (и «сло -»)
        else:
            cur = cur + " " + ln
        if ln.endswith(SENT_END) and len(ln) < width * 0.75:
            paras.append(cur)
            cur = ""
    if cur:
        paras.append(cur)
    return "\n\n".join(p.strip() for p in paras if p.strip())


def clean_pages(raw_pages: list[str], context: list[str] | None = None) -> tuple[str, dict]:
    pages = [fix_chars(p).split("\n") for p in raw_pages]
    ctx = [fix_chars(p).split("\n") for p in (context or [])]
    pages, nums, heads = strip_headers(pages, ctx)
    # конец страницы посреди предложения — строки страниц просто идут подряд
    lines: list[str] = []
    for pg in pages:
        while pg and not pg[0].strip():
            pg = pg[1:]
        while pg and not pg[-1].strip():
            pg = pg[:-1]
        if lines:
            lines.append(PAGE_BREAK)
        lines.extend(pg)
    text = to_paragraphs(lines)
    return text, {"page_numbers": nums, "headers": heads}


def load(path: str | Path, first: int = 1, last: int | None = None) -> PdfResult:
    pages, total = extract_pages(path, first, last)
    raw_chars = sum(len(p.strip()) for p in pages)
    f = max(1, first)
    lst = f + len(pages) - 1
    if not pages or raw_chars / max(1, len(pages)) < SCANNED_CHARS_PER_PAGE:
        return PdfResult("", total, f, lst, scanned=True, raw_chars=raw_chars)
    context: list[str] = []
    if len(pages) < 6 and total > len(pages):              # мало страниц — соседи для поиска колонтитулов
        a, b = max(1, f - 3), min(total, lst + 3)
        extra, _ = extract_pages(path, a, b)
        context = [p for i, p in enumerate(extra, a) if not f <= i <= lst]
    text, removed = clean_pages(pages, context)
    return PdfResult(text, total, f, lst, raw_chars=raw_chars, removed=removed)
