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


class BookCatalogError(Exception):
    pass


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
