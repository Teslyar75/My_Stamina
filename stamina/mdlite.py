"""Маленький Markdown без зависимостей — для редактора документов и экспорта.

Документ хранится как обычный текст в разметке Markdown (то, что набрал
пилот). Редактор подсвечивает разметку «вживую», а экспорт (HTML, PDF, DOCX)
превращает её в настоящее форматирование. Поддерживается то, что есть
в шпаргалке: **жирный**, *курсив*, <u>подчёркнутый</u>, `код`, [ссылка](адрес),
# заголовок, ## подзаголовок, - список, 1. список, > цитата.
"""
from __future__ import annotations

import html
import re

INLINE = [
    ("code", re.compile(r"`([^`\n]+)`")),
    ("b", re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")),
    ("u", re.compile(r"<u>(.+?)</u>")),
    ("i", re.compile(r"(?<![*\w])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![*\w])|(?<!\w)_(?=\S)(.+?)(?<=\S)_(?!\w)")),
    ("link", re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")),
]
BLOCKS = [
    ("h2", re.compile(r"^(##\s+)")),
    ("h1", re.compile(r"^(#\s+)")),
    ("li", re.compile(r"^(\s*(?:[-*+•]|\d+[.)])\s+)")),
    ("quote", re.compile(r"^(>\s?)")),
]


def block_of(line: str) -> tuple[str, int]:
    """Тип строки и длина её маркера: ("h1", 2) для «# Заголовок»."""
    for name, rx in BLOCKS:
        m = rx.match(line)
        if m:
            return name, len(m.group(1))
    return "p", 0


def inline_spans(line: str) -> list[tuple[str, int, int, list[tuple[int, int]]]]:
    """Отрезки разметки в строке: (стиль, начало, конец, [отрезки маркеров])."""
    out: list = []
    taken: list[tuple[int, int]] = []

    def free(a, b):
        return all(b <= x or a >= y for x, y in taken)

    for name, rx in INLINE:
        for m in rx.finditer(line):
            a, b = m.span()
            if not free(a, b):
                continue
            g = 1 if m.group(1) is not None else 2
            ia, ib = m.span(g)
            marks = [(a, ia), (ib, b)]
            out.append((name, a, b, marks))
            if name == "code":
                taken.append((a, b))
    return out


def runs(line: str) -> list[tuple[str, frozenset, str]]:
    """Строка без маркеров → [(текст, стили, ссылка)] для экспорта."""
    spans = inline_spans(line)
    hidden = [False] * len(line)
    styles: list[set] = [set() for _ in line]
    href: list[str] = [""] * len(line)
    for name, a, b, marks in spans:
        for x, y in marks:
            for k in range(x, y):
                hidden[k] = True
        for k in range(a, b):
            styles[k].add(name)
        if name == "link":
            url = re.match(r"\[[^\]]*\]\(([^)]*)\)", line[a:b])
            for k in range(a, b):
                href[k] = url.group(1) if url else ""
    out: list = []
    for k, ch in enumerate(line):
        if hidden[k]:
            continue
        key = (frozenset(styles[k]), href[k])
        if out and (out[-1][1], out[-1][2]) == key:
            out[-1] = (out[-1][0] + ch, key[0], key[1])
        else:
            out.append((ch, key[0], key[1]))
    return out


def paragraphs(text: str) -> list[tuple[str, list]]:
    """Текст → [(тип блока, runs)]; тип: p, h1, h2, li, quote."""
    res = []
    for line in text.split("\n"):
        kind, n = block_of(line)
        body = line[n:]
        if kind == "li":
            body = "• " + body
        res.append((kind, runs(body)))
    return res


def run_html(rs) -> str:
    parts = []
    for text, st, url in rs:
        s = html.escape(text)
        for tag, h in (("code", "code"), ("b", "b"), ("i", "i"), ("u", "u")):
            if tag in st:
                s = f"<{h}>{s}</{h}>"
        if url:
            s = f'<a href="{html.escape(url, quote=True)}">{s}</a>'
        parts.append(s)
    return "".join(parts)


def to_html(text: str) -> str:
    tag = {"h1": "h1", "h2": "h2", "quote": "blockquote", "li": "p", "p": "p"}
    out = []
    for kind, rs in paragraphs(text):
        out.append(f"<{tag[kind]}>{run_html(rs) or '&nbsp;'}</{tag[kind]}>")
    return "\n".join(out)


def plain(text: str) -> str:
    """Текст без разметки (для TXT)."""
    return "\n".join("".join(r[0] for r in rs) for _k, rs in paragraphs(text))
