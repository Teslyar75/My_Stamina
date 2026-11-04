"""Лёгкая разметка ответов агента для чата Ориона (без tkinter — проверяется тестами).

Понимает: **жирный**, *курсив*, `код`, блоки кода ```…```, списки (- • 1.),
заголовки (#), цитаты (>), ссылки [текст](url) и голые https://…,
картинки ![подпись](url) — отдельной строкой-блоком (экран покажет миниатюру).
Строчную разметку разбирает общий :mod:`stamina.mdlite`.
"""
from __future__ import annotations

import re

from stamina import mdlite

_FENCE = re.compile(r"^\s*```")
_IMAGE = re.compile(r"!\[([^\]\n]*)\]\((\S+?)\)")
_URL = re.compile(r"(?<![(\[\w])(https?://[^\s<>()\]]+[^\s<>()\].,;:!?»\"'])")
_NUM = re.compile(r"^(\s*)(\d+[.)])\s+")
_BUL = re.compile(r"^(\s*)[-*+•]\s+")


def _link_bare(rs):
    out = []
    for text, styles, href in rs:
        if href or "code" in styles:
            out.append((text, styles, href))
            continue
        pos = 0
        for m in _URL.finditer(text):
            if m.start() > pos:
                out.append((text[pos:m.start()], styles, ""))
            out.append((m.group(1), frozenset(styles | {"link"}), m.group(1)))
            pos = m.end()
        if pos < len(text):
            out.append((text[pos:], styles, ""))
    return out


def inline(text: str):
    """Строка → [(текст, стили, ссылка)] (стили: b, i, u, code, link)."""
    return _link_bare(mdlite.runs(text))


def parse(text: str) -> list[tuple]:
    """Текст → блоки:

    ("code", lang, текст) · ("image", подпись, url) ·
    ("line", вид, отступ-маркер, runs) — вид: p, h1, h2, li, ol, quote.
    """
    blocks: list[tuple] = []
    code: list[str] | None = None
    lang = ""
    for line in (text or "").split("\n"):
        if code is not None:
            if _FENCE.match(line):
                blocks.append(("code", lang, "\n".join(code)))
                code = None
            else:
                code.append(line)
            continue
        if _FENCE.match(line):
            code, lang = [], line.strip()[3:].strip()
            continue
        # картинки — отдельными блоками, текст вокруг остаётся строкой
        pos = 0
        rest = []
        for m in _IMAGE.finditer(line):
            rest.append(line[pos:m.start()])
            blocks.extend(_line(" ".join(x for x in rest if x.strip())) if any(x.strip() for x in rest) else [])
            rest = []
            blocks.append(("image", m.group(1), m.group(2)))
            pos = m.end()
        tail = line[pos:]
        if pos == 0 or tail.strip():
            blocks.extend(_line(tail))
    if code is not None:                       # незакрытый блок кода — всё равно показать
        blocks.append(("code", lang, "\n".join(code)))
    return blocks


def _line(line: str) -> list[tuple]:
    m = _NUM.match(line)
    if m:
        return [("line", "ol", m.group(1) + m.group(2) + " ", inline(line[m.end():]))]
    m = _BUL.match(line)
    if m:
        return [("line", "li", m.group(1) + "• ", inline(line[m.end():]))]
    kind, n = mdlite.block_of(line)
    return [("line", kind, "", inline(line[n:]))]


def plain(text: str) -> str:
    """Текст без разметки (для озвучки): ссылки — подписью, код — как есть, картинки — молча."""
    out = []
    for b in parse(text):
        if b[0] == "code":
            out.append(b[2])
        elif b[0] == "line":
            out.append(b[2].replace("• ", "") + "".join(r[0] for r in b[3]))
    return "\n".join(out).strip()
