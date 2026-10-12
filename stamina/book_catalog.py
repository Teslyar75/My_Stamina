"""Поиск и загрузка книг из открытых источников (Project Gutenberg через Gutendex).

Только тексты общественного достояния. Не пиратские каталоги и не платные магазины.
API: https://gutendex.com/  · каталог: https://www.gutenberg.org/
"""
from __future__ import annotations

from stamina.i18n import t as _t

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

GUTENDEX = "https://gutendex.com/books/"
UA = "StarTyping/My_Stamina (educational; +https://github.com/Teslyar75/My_Stamina)"
TIMEOUT = 25
MAX_BYTES = 8 * 1024 * 1024  # защита от слишком больших файлов
MAX_COVER_BYTES = 2 * 1024 * 1024

# Уровни CEFR. Gutenberg не маркирует CEFR — ниже подборка PD-книг
# «примерно под уровень» + topic-fallback. Коммерческие graded readers (Oxford и т.п.) —
# под копирайтом, в открытый каталог не входят.
CEFR_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
CEFR_PAGE = 16

# EN: Project Gutenberg id → ориентир для изучающих
CEFR_IDS_EN: dict[str, list[int]] = {
    "A1": [21, 113, 2591, 55, 301, 500, 14838, 1597],
    "A2": [16, 11, 12, 46, 74, 35, 514, 47],
    "B1": [120, 215, 76, 1661, 244, 2852, 308, 42],
    "B2": [84, 1342, 1260, 174, 98, 345, 1400, 25344],
    "C1": [2701, 36, 64317, 766, 730, 996, 4217, 25305],
    "C2": [4300, 1727, 1497, 1232, 2600, 1399, 6130, 28054],
}

# Если ids закончились / другой язык — topic Gutendex (bookshelf/subject)
CEFR_TOPICS: dict[str, str] = {
    "A1": "children",
    "A2": "juvenile",
    "B1": "adventure",
    "B2": "fiction",
    "C1": "literature",
    "C2": "philosophy",
}


class BookCatalogError(Exception):
    pass


def cefr_levels() -> tuple[str, ...]:
    return CEFR_LEVELS


def covers_dir() -> Path:
    from stamina.storage import DATA_DIR
    d = DATA_DIR / "cache" / "covers"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        raise BookCatalogError(_t("Сервер ответил ошибкой {0}").format(exc.code)) from exc
    except urllib.error.URLError as exc:
        raise BookCatalogError(_t("Нет связи с каталогом книг (нужен интернет).")) from exc
    except (TimeoutError, json.JSONDecodeError, UnicodeError) as exc:
        raise BookCatalogError(_t("Не удалось прочитать ответ каталога.")) from exc


def _get_bytes(url: str, *, limit: int = MAX_BYTES) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = r.read(limit + 1)
    except urllib.error.HTTPError as exc:
        raise BookCatalogError(_t("Не удалось скачать (код {0}).").format(exc.code)) from exc
    except urllib.error.URLError as exc:
        raise BookCatalogError(_t("Нет связи при скачивании.")) from exc
    if len(data) > limit:
        raise BookCatalogError(_t("Файл слишком большой (лимит {0} МБ).").format(limit // (1024 * 1024)))
    return data


def _authors(item: dict) -> str:
    names = []
    for a in item.get("authors") or []:
        name = (a.get("name") or "").strip()
        if name:
            if "," in name:
                last, first = [p.strip() for p in name.split(",", 1)]
                name = f"{first} {last}".strip() if first else last
            names.append(name)
    return ", ".join(names)


def _plain_url(formats: dict) -> str | None:
    """Предпочесть UTF-8 plain text, иначе любой text/plain (не zip)."""
    if not isinstance(formats, dict):
        return None
    prefer, fallback = [], []
    for mime, url in formats.items():
        if not url or "zip" in mime.lower() or str(url).endswith(".zip"):
            continue
        ml = mime.lower()
        if "text/plain" in ml and "utf-8" in ml:
            prefer.append(url)
        elif "text/plain" in ml:
            fallback.append(url)
    return prefer[0] if prefer else (fallback[0] if fallback else None)


def _cover_url(formats: dict) -> str | None:
    if not isinstance(formats, dict):
        return None
    for mime, url in formats.items():
        if not url:
            continue
        ml = mime.lower()
        if ml.startswith("image/") or "cover" in ml or str(url).lower().endswith((".jpg", ".jpeg", ".png")):
            return url
    # Gutendex часто кладёт обложку как image/jpeg
    return formats.get("image/jpeg") or formats.get("image/png")


def _normalize_item(item: dict) -> dict[str, Any] | None:
    formats = item.get("formats") or {}
    url = _plain_url(formats)
    if not url:
        return None
    cover = _cover_url(formats)
    title = (item.get("title") or "").strip() or _t("Без названия")
    gid = int(item.get("id") or 0)
    return {
        "id": gid,
        "title": title,
        "author": _authors(item),
        "languages": list(item.get("languages") or []),
        "download_count": int(item.get("download_count") or 0),
        "text_url": url,
        "cover_url": cover,
        "has_cover": bool(cover),
        "source": "gutenberg",
        "source_label": "Project Gutenberg",
        "page_url": f"https://www.gutenberg.org/ebooks/{gid}",
    }


def _pack_page(data: dict, *, query: str = "") -> dict:
    results = []
    for item in data.get("results") or []:
        rec = _normalize_item(item)
        if rec:
            results.append(rec)
    return {
        "count": int(data.get("count") or 0),
        "next": data.get("next"),
        "previous": data.get("previous"),
        "results": results,
        "query": query,
    }


def search_books(*, title: str = "", author: str = "", query: str = "",
                 languages: str | None = None, page: int = 1) -> dict:
    """Поиск по названию и/или автору. Возвращает {results, count, next, previous}."""
    parts = []
    if author.strip():
        parts.append(author.strip())
    if title.strip():
        parts.append(title.strip())
    if not parts and query.strip():
        parts.append(query.strip())
    if not parts:
        raise BookCatalogError(_t("Введите название или автора."))

    params: dict[str, str] = {"search": " ".join(parts)}
    if languages:
        params["languages"] = languages
    if page > 1:
        params["page"] = str(page)
    data = _get_json(GUTENDEX + "?" + urllib.parse.urlencode(params))
    return _pack_page(data, query=" ".join(parts))


def list_free_books(*, page: int = 1, languages: str | None = "en") -> dict:
    """Лента свободных книг (популярные в Gutenberg)."""
    params: dict[str, str] = {"sort": "popular"}
    if languages:
        params["languages"] = languages
    if page > 1:
        params["page"] = str(page)
    data = _get_json(GUTENDEX + "?" + urllib.parse.urlencode(params))
    return _pack_page(data, query=_t("свободные книги"))


# Кураторские пары PD. Каждый id_b обязан быть на lang_b (проверяется is_language_pair + сходство названия).
# RU-пары НЕ зашиваем: у классики в Gutenberg почти нет русских текстов, ложные id давали EN→EN.
BILINGUAL_SEED: list[dict[str, Any]] = [
    {"lang_a": "en", "id_a": 5200, "lang_b": "de", "id_b": 22367},   # Metamorphosis / Verwandlung
    {"lang_a": "en", "id_a": 11, "lang_b": "de", "id_b": 19778},      # Alice
    {"lang_a": "en", "id_a": 12, "lang_b": "de", "id_b": 28881},      # Looking-Glass
    {"lang_a": "en", "id_a": 1342, "lang_b": "de", "id_b": 10765},    # Pride and Prejudice
    {"lang_a": "en", "id_a": 84, "lang_b": "de", "id_b": 10166},      # Frankenstein
    {"lang_a": "en", "id_a": 345, "lang_b": "de", "id_b": 10066},     # Dracula
    {"lang_a": "en", "id_a": 98, "lang_b": "fr", "id_b": 13951},      # Two Cities / FR
    {"lang_a": "en", "id_a": 103, "lang_b": "fr", "id_b": 46501},     # Around the World
    {"lang_a": "en", "id_a": 164, "lang_b": "fr", "id_b": 50916},     # 20 000 Leagues
    {"lang_a": "en", "id_a": 1184, "lang_b": "fr", "id_b": 17989},    # Monte Cristo
    {"lang_a": "en", "id_a": 996, "lang_b": "es", "id_b": 2000},      # Don Quixote
    {"lang_a": "en", "id_a": 500, "lang_b": "it", "id_b": 19717},     # Pinocchio
]

_TITLE_STOP = {
    "the", "a", "an", "of", "and", "in", "to", "for", "on", "by", "or", "with",
    "der", "die", "das", "und", "ein", "eine", "le", "la", "les", "des", "du",
    "el", "los", "las", "и", "в", "на", "к", "по", "из", "о",
}


def _title_tokens(s: str) -> set[str]:
    s = re.sub(r"[^\w\s]", " ", (s or "").lower(), flags=re.UNICODE)
    return {w for w in s.split() if len(w) > 2 and w not in _TITLE_STOP}


def _score_title_pair(a: str, b: str) -> float:
    ta, tb = _title_tokens(a), _title_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def _author_surname(author: str) -> str:
    author = (author or "").replace(",", " ").strip()
    if not author:
        return ""
    parts = [p for p in author.split() if p]
    return parts[-1] if parts else ""


def fetch_book(gid: int) -> dict | None:
    """Одна книга Gutenberg по id (или None)."""
    found = _fetch_by_ids([int(gid)], languages=None)
    return found[0] if found else None


def book_langs(book: dict | None) -> set[str]:
    if not book:
        return set()
    return {str(x).lower() for x in (book.get("languages") or []) if x}


def primary_lang(book: dict | None, default: str = "") -> str:
    langs = list(book_langs(book))
    raw = (book.get("languages") or []) if book else []
    if raw:
        return str(raw[0]).lower()
    return default


def is_language_pair(book_a: dict | None, book_b: dict | None, lang_b: str,
                     *, require_title_overlap: bool = True) -> bool:
    """True, если book_b — перевод на lang_b (не второй EN-текст и не чужая книга)."""
    if not book_a or not book_b:
        return False
    if int(book_a.get("id") or 0) == int(book_b.get("id") or 0):
        return False
    lb = (lang_b or "").strip().lower()
    if not lb:
        return False
    langs_b = book_langs(book_b)
    langs_a = book_langs(book_a)
    if not langs_a or not langs_b:
        return False
    # перевод ОБЯЗАН быть на запрошенном языке; primary — тоже он
    if lb not in langs_b or primary_lang(book_b) != lb:
        return False
    # оригинал не должен совпадать с языком перевода
    if primary_lang(book_a) == lb or primary_lang(book_a) == primary_lang(book_b):
        return False
    if langs_a == langs_b:
        return False
    # отсечь «Карамазовы → Secret Garden»: либо общий автор, либо похожие названия
    if require_title_overlap:
        score = _score_title_pair(book_a.get("title") or "", book_b.get("title") or "")
        sa = _author_surname(book_a.get("author") or "")
        sb = _author_surname(book_b.get("author") or "")
        same_author = bool(sa and sb and sa.lower() == sb.lower())
        if same_author:
            return True
        if score < 0.22:
            return False
    return True


def find_translation(book: dict, lang_b: str, *, min_score: float = 0.34) -> dict | None:
    """Найти PD-перевод той же книги на lang_b в Gutenberg (или None)."""
    if not book or not lang_b:
        return None
    lang_b = lang_b.strip().lower()
    langs = book_langs(book)
    if lang_b in langs:
        return None
    gid = int(book.get("id") or 0)
    for seed in BILINGUAL_SEED:
        tr = None
        if seed["id_a"] == gid and seed["lang_b"] == lang_b:
            tr = fetch_book(seed["id_b"])
        elif seed["id_b"] == gid and seed["lang_a"] == lang_b:
            tr = fetch_book(seed["id_a"])
        if tr and is_language_pair(book, tr, lang_b):
            return tr

    title = book.get("title") or ""
    surname = _author_surname(book.get("author") or "")
    queries: list[str] = []
    if surname:
        queries.append(surname)
    words = list(_title_tokens(title))[:4]
    if words:
        queries.append(" ".join(words[:3]))
    best: dict | None = None
    best_score = 0.0
    seen_q: set[str] = set()
    for q in queries:
        q = q.strip()
        if not q or q in seen_q:
            continue
        seen_q.add(q)
        try:
            page = search_books(query=q, languages=lang_b, page=1)
        except BookCatalogError:
            continue
        for cand in (page.get("results") or [])[:16]:
            if int(cand.get("id") or 0) == gid:
                continue
            if not is_language_pair(book, cand, lang_b):
                continue
            score = _score_title_pair(title, cand.get("title") or "")
            if surname and surname.lower() in (cand.get("author") or "").lower():
                score += 0.28
            if score > best_score:
                best, best_score = cand, score
    if best and best_score >= min_score:
        return best
    return None


def _attach_translation(book: dict, tr: dict, lang_b: str) -> dict | None:
    if not is_language_pair(book, tr, lang_b):
        return None
    rec = dict(book)
    rec["translation"] = tr
    rec["lang_b"] = lang_b
    rec["bilingual"] = True
    return rec


def list_bilingual_seed(*, lang_a: str = "en", lang_b: str = "ru", page: int = 1) -> dict:
    """Кураторская полка пар PD (быстрый старт каталога 2ЯЗ)."""
    lang_a = (lang_a or "en").strip().lower()
    lang_b = (lang_b or "ru").strip().lower()
    page = max(1, int(page or 1))
    seeds = [s for s in BILINGUAL_SEED if s["lang_a"] == lang_a and s["lang_b"] == lang_b]
    per = CEFR_PAGE
    chunk = seeds[(page - 1) * per: page * per]
    results: list[dict] = []
    for s in chunk:
        books = _fetch_by_ids([s["id_a"], s["id_b"]], languages=None)
        by_id = {int(b["id"]): b for b in books}
        a, b = by_id.get(s["id_a"]), by_id.get(s["id_b"])
        if a and b:
            rec = _attach_translation(a, b, lang_b)
            if rec:
                results.append(rec)
    next_url = f"biseed:{lang_a}:{lang_b}:{page + 1}" if page * per < len(seeds) else None
    return {
        "count": len(seeds),
        "next": next_url,
        "previous": None,
        "results": results,
        "query": _t("свободные · 2 языка ({0}→{1})").format(lang_a.upper(), lang_b.upper()),
        "bilingual": True,
    }


def list_bilingual_free(*, lang_a: str = "en", lang_b: str = "ru", page: int = 1,
                        popular_page: int | None = None) -> dict:
    """Кураторские пары, затем популярные lang_a с найденным PD-переводом на lang_b."""
    lang_a = (lang_a or "en").strip().lower()
    lang_b = (lang_b or "ru").strip().lower()
    page = max(1, int(page or 1))
    # page=1 — кураторская полка; popular_page — добор из ленты Gutenberg
    if popular_page is None and page == 1:
        seeded = list_bilingual_seed(lang_a=lang_a, lang_b=lang_b, page=1)
        if seeded.get("results"):
            if not seeded.get("next"):
                seeded["next"] = f"bifree:{lang_a}:{lang_b}:1"
            return seeded
        popular_page = 1
    elif popular_page is None:
        popular_page = page
    free = list_free_books(page=popular_page, languages=lang_a)
    out: list[dict] = []
    for book in free.get("results") or []:
        tr = find_translation(book, lang_b)
        if tr:
            rec = _attach_translation(book, tr, lang_b)
            if rec:
                out.append(rec)
    next_url = None
    if free.get("next"):
        next_url = f"bifree:{lang_a}:{lang_b}:{int(popular_page) + 1}"
    return {
        "count": int(free.get("count") or 0),
        "next": next_url,
        "previous": None,
        "results": out,
        "query": _t("свободные · 2 языка ({0}→{1})").format(lang_a.upper(), lang_b.upper()),
        "bilingual": True,
    }


def search_bilingual(*, title: str = "", author: str = "", lang_a: str = "en",
                     lang_b: str = "ru", page: int = 1) -> dict:
    """Поиск как обычно, в выдаче только книги с найденным PD-переводом."""
    lang_a = (lang_a or "").strip().lower() or None
    lang_b = (lang_b or "ru").strip().lower()
    packed = search_books(title=title, author=author, languages=lang_a, page=page)
    out: list[dict] = []
    for book in packed.get("results") or []:
        tr = find_translation(book, lang_b)
        if tr:
            rec = _attach_translation(book, tr, lang_b)
            if rec:
                out.append(rec)
    next_url = None
    if packed.get("next"):
        next_url = packed["next"]
    return {
        "count": int(packed.get("count") or 0),
        "next": next_url,
        "previous": packed.get("previous"),
        "results": out,
        "query": packed.get("query") or "",
        "bilingual": True,
    }


def list_bilingual_by_cefr(level: str, *, lang_a: str = "en", lang_b: str = "ru",
                           page: int = 1) -> dict:
    """CEFR-полка: только те книги уровня, для которых есть PD-перевод."""
    packed = list_by_cefr(level, page=page, languages=lang_a or "en")
    lang_b = (lang_b or "ru").strip().lower()
    out: list[dict] = []
    for book in packed.get("results") or []:
        tr = find_translation(book, lang_b)
        if tr:
            rec = _attach_translation(book, tr, lang_b)
            if rec:
                if book.get("cefr"):
                    rec["cefr"] = book["cefr"]
                out.append(rec)
    return {
        "count": int(packed.get("count") or 0),
        "next": packed.get("next"),
        "previous": packed.get("previous"),
        "results": out,
        "query": packed.get("query") or "",
        "cefr": packed.get("cefr"),
        "bilingual": True,
    }


def _fetch_by_ids(ids: list[int], *, languages: str | None) -> list[dict]:
    if not ids:
        return []
    params: dict[str, str] = {"ids": ",".join(str(i) for i in ids)}
    if languages:
        params["languages"] = languages
    data = _get_json(GUTENDEX + "?" + urllib.parse.urlencode(params))
    by_id = {}
    for item in data.get("results") or []:
        rec = _normalize_item(item)
        if rec:
            by_id[int(rec["id"])] = rec
    # сохранить порядок подборки
    return [by_id[i] for i in ids if i in by_id]


def list_by_cefr(level: str, *, page: int = 1, languages: str | None = "en") -> dict:
    """Книги по категории CEFR (A1…C2): сначала кураторская PD-полка, затем topic."""
    lv = (level or "").strip().upper()
    if lv not in CEFR_LEVELS:
        raise BookCatalogError(_t("Неизвестный уровень: {0}").format(level))
    page = max(1, int(page or 1))
    lang = (languages or "").strip().lower() or None

    ids = list(CEFR_IDS_EN.get(lv) or []) if (lang in (None, "", "en")) else []
    id_pages = max(1, (len(ids) + CEFR_PAGE - 1) // CEFR_PAGE) if ids else 0

    results: list[dict] = []
    next_url = None
    count = 0
    query = _t("уровень {0}").format(lv)

    if ids and page <= id_pages:
        chunk = ids[(page - 1) * CEFR_PAGE: page * CEFR_PAGE]
        results = _fetch_by_ids(chunk, languages=lang)
        for r in results:
            r["cefr"] = lv
        count = len(ids)
        if page < id_pages or CEFR_TOPICS.get(lv):
            next_url = f"cefr:{lv}:{page + 1}"
    else:
        topic_page = page - id_pages if ids else page
        topic = CEFR_TOPICS.get(lv) or "fiction"
        params: dict[str, str] = {"topic": topic, "sort": "popular"}
        if lang:
            params["languages"] = lang
        if topic_page > 1:
            params["page"] = str(topic_page)
        data = _get_json(GUTENDEX + "?" + urllib.parse.urlencode(params))
        packed = _pack_page(data, query=query)
        results = packed["results"]
        for r in results:
            r["cefr"] = lv
        count = int(packed.get("count") or 0) + len(ids)
        if packed.get("next"):
            next_url = f"cefr:{lv}:{page + 1}"

    return {
        "count": count,
        "next": next_url,
        "previous": None,
        "results": results,
        "query": query,
        "cefr": lv,
    }


def cover_cache_path(gutenberg_id: int) -> Path:
    return covers_dir() / f"{int(gutenberg_id)}.jpg"


def download_cover(book: dict) -> Path | None:
    """Скачать обложку в кэш. None — нет URL или ошибка."""
    url = book.get("cover_url")
    gid = int(book.get("id") or 0)
    if not url or not gid:
        return None
    path = cover_cache_path(gid)
    if path.exists() and path.stat().st_size > 0:
        return path
    try:
        data = _get_bytes(url, limit=MAX_COVER_BYTES)
    except BookCatalogError:
        return None
    if len(data) < 80:
        return None
    try:
        path.write_bytes(data)
        return path
    except OSError:
        return None


def download_text(book: dict) -> str:
    """Скачать plain text книги и убрать служебный хвост Gutenberg."""
    url = book.get("text_url")
    if not url:
        raise BookCatalogError(_t("У этой книги нет текстовой версии для скачивания."))
    raw = _get_bytes(url)
    text = None
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", "replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _strip_gutenberg_boilerplate(text).strip() + "\n"
    if len(text) < 200:
        raise BookCatalogError(_t("Скачанный файл слишком короткий — похоже, это не книга."))
    return text


def _strip_gutenberg_boilerplate(text: str) -> str:
    start = re.search(
        r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK[^*\n]*\*\*\*",
        text, re.I,
    )
    if start:
        text = text[start.end():]
    end = re.search(
        r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK",
        text, re.I,
    )
    if end:
        text = text[:end.start()]
    return text.strip()
