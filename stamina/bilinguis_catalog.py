"""Каталог двуязычных PD-книг bilinguis.com (приоритет EN→RU / EN→UK).

Сайт заявляет общественное достояние (США); тексты с Wikisource.
Структура: /book/{slug}/{lang_a}/{lang_b}/cN/ — две колонки col-xs-6 lang=…
"""
from __future__ import annotations

from stamina.i18n import t as _t

import html as html_lib
import re
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import Any

BASE = "http://bilinguis.com"
UA = "StarTyping/My_Stamina (educational; +https://github.com/Teslyar75/My_Stamina)"
TIMEOUT = 25
PAUSE_S = 0.35  # вежливо к серверу при скачивании глав

# Кураторская полка: slug → мета + доступные пары (проверено по оглавлению сайта).
# lang коды как на bilinguis (uk = українська).
BILINGUIS_BOOKS: list[dict[str, Any]] = [
    {
        "slug": "alice",
        "title": "Alice's Adventures in Wonderland",
        "author": "Lewis Carroll",
        "pairs": (("en", "ru"), ("en", "uk"), ("ru", "en"), ("uk", "en")),
    },
    {
        "slug": "tomsawyer",
        "title": "The Adventures of Tom Sawyer",
        "author": "Mark Twain",
        "pairs": (("en", "ru"), ("ru", "en")),
    },
    {
        "slug": "baskerville",
        "title": "The Hound of the Baskervilles",
        "author": "Arthur Conan Doyle",
        "pairs": (("en", "ru"), ("en", "uk"), ("ru", "en"), ("uk", "en")),
    },
    {
        "slug": "metamorphosis",
        "title": "The Metamorphosis",
        "author": "Franz Kafka",
        "pairs": (("en", "ru"), ("en", "uk"), ("ru", "en"), ("uk", "en")),
    },
]


class BilinguisError(Exception):
    pass


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
    except urllib.error.HTTPError as exc:
        raise BilinguisError(_t("Сервер bilinguis ответил ошибкой {0}").format(exc.code)) from exc
    except urllib.error.URLError as exc:
        raise BilinguisError(_t("Нет связи с bilinguis.com (нужен интернет).")) from exc
    except TimeoutError as exc:
        raise BilinguisError(_t("Таймаут при обращении к bilinguis.com.")) from exc
    for enc in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def normalize_lang(code: str) -> str:
    c = (code or "").strip().lower().replace("_", "-")
    if c in ("ua", "ukr"):
        return "uk"
    if c in ("zh-tw", "zh_tw"):
        return "zh_tw"
    return c


def list_bilingual_pairs(*, lang_a: str = "en", lang_b: str = "ru") -> dict:
    """Список книг bilinguis для пары языков (без сети, из кураторской полки)."""
    la, lb = normalize_lang(lang_a), normalize_lang(lang_b)
    if la == lb:
        return {
            "count": 0, "next": None, "previous": None, "results": [],
            "query": _t("bilinguis · {0}→{1}").format(la.upper(), lb.upper()),
            "bilingual": True, "source": "bilinguis",
        }
    results: list[dict] = []
    for book in BILINGUIS_BOOKS:
        pairs = {(normalize_lang(a), normalize_lang(b)) for a, b in book.get("pairs") or ()}
        if (la, lb) not in pairs:
            continue
        results.append({
            "id": f"bilinguis:{book['slug']}:{la}:{lb}",
            "slug": book["slug"],
            "title": book["title"],
            "author": book.get("author") or "",
            "languages": [la],
            "lang_a": la,
            "lang_b": lb,
            "download_count": 0,
            "text_url": f"{BASE}/book/{book['slug']}/{la}/{lb}/",
            "cover_url": None,
            "has_cover": False,
            "source": "bilinguis",
            "source_label": "bilinguis.com",
            "page_url": f"{BASE}/book/{book['slug']}/{la}/{lb}/",
            "bilingual": True,
            "translation": {
                "id": f"bilinguis:{book['slug']}:{lb}",
                "title": book["title"],
                "author": book.get("author") or "",
                "languages": [lb],
                "text_url": f"{BASE}/book/{book['slug']}/{la}/{lb}/",
                "page_url": f"{BASE}/book/{book['slug']}/{la}/{lb}/",
                "source": "bilinguis",
            },
        })
    return {
        "count": len(results),
        "next": None,
        "previous": None,
        "results": results,
        "query": _t("bilinguis · {0}→{1}").format(la.upper(), lb.upper()),
        "bilingual": True,
        "source": "bilinguis",
    }


class _ChapterParser(HTMLParser):
    """Собирает текст из <div class="col-xs-6" lang="..">."""

    def __init__(self, lang_a: str, lang_b: str) -> None:
        super().__init__(convert_charrefs=True)
        self.lang_a = lang_a
        self.lang_b = lang_b
        self.parts_a: list[str] = []
        self.parts_b: list[str] = []
        self._buf: list[str] = []
        self._capture: str | None = None  # 'a' | 'b' | None
        self._depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        ad = {k.lower(): (v or "") for k, v in attrs}
        if tag == "div" and "col-xs-6" in (ad.get("class") or ""):
            lang = normalize_lang(ad.get("lang") or "")
            if self._capture is None:
                if lang == self.lang_a:
                    self._capture, self._depth, self._buf = "a", 1, []
                    return
                if lang == self.lang_b:
                    self._capture, self._depth, self._buf = "b", 1, []
                    return
        if self._capture and tag == "div":
            self._depth += 1
        if self._capture and tag in ("br",):
            self._buf.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if not self._capture or tag != "div":
            return
        self._depth -= 1
        if self._depth <= 0:
            text = "".join(self._buf)
            text = re.sub(r"[ \t]+\n", "\n", text)
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            if text:
                if self._capture == "a":
                    self.parts_a.append(text)
                else:
                    self.parts_b.append(text)
            self._capture, self._depth, self._buf = None, 0, []

    def handle_data(self, data: str) -> None:
        if self._capture and data:
            self._buf.append(data)


def _chapter_urls(index_html: str, slug: str, la: str, lb: str) -> list[str]:
    pat = re.compile(
        rf'href=["\'](/book/{re.escape(slug)}/{re.escape(la)}/{re.escape(lb)}/c\d+/?)["\']',
        re.I,
    )
    urls: list[str] = []
    seen: set[str] = set()
    for m in pat.finditer(index_html):
        path = m.group(1)
        if not path.endswith("/"):
            path += "/"
        if path in seen:
            continue
        seen.add(path)
        urls.append(BASE + path)
    # натуральный порядок c1, c2, … c10
    def key(u: str) -> int:
        m = re.search(r"/c(\d+)/?$", u)
        return int(m.group(1)) if m else 0

    return sorted(urls, key=key)


def download_pair(book: dict) -> tuple[str, str]:
    """Скачать оригинал и перевод. Возвращает (text_a, text_b)."""
    slug = book.get("slug") or ""
    la = normalize_lang(book.get("lang_a") or "en")
    lb = normalize_lang(book.get("lang_b") or "ru")
    if not slug or la == lb:
        raise BilinguisError(_t("Некорректная пара bilinguis."))
    index_url = f"{BASE}/book/{slug}/{la}/{lb}/"
    index_html = _get(index_url)
    chapters = _chapter_urls(index_html, slug, la, lb)
    if not chapters:
        raise BilinguisError(_t("Не найдены главы книги на bilinguis.com."))
    parts_a: list[str] = []
    parts_b: list[str] = []
    for i, curl in enumerate(chapters):
        if i:
            time.sleep(PAUSE_S)
        ch_html = _get(curl)
        p = _ChapterParser(la, lb)
        p.feed(ch_html)
        block_a = "\n\n".join(p.parts_a).strip()
        block_b = "\n\n".join(p.parts_b).strip()
        if block_a:
            parts_a.append(block_a)
        if block_b:
            parts_b.append(block_b)
    text_a = "\n\n".join(parts_a).strip() + "\n"
    text_b = "\n\n".join(parts_b).strip() + "\n"
    # убрать HTML-сущности на всякий случай
    text_a = html_lib.unescape(text_a)
    text_b = html_lib.unescape(text_b)
    if len(text_a) < 200 or len(text_b) < 200:
        raise BilinguisError(_t("Скачанный текст bilinguis слишком короткий."))
    return text_a, text_b


def is_bilinguis_book(book: dict | None) -> bool:
    if not book:
        return False
    return book.get("source") == "bilinguis" or str(book.get("id") or "").startswith("bilinguis:")
