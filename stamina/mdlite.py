"""Маленький Markdown без зависимостей — для редактора документов и экспорта.

Документ хранится как обычный текст в разметке Markdown (то, что набрал
пилот). Редактор подсвечивает разметку «вживую», а экспорт (HTML, PDF, DOCX)
превращает её в настоящее форматирование. Поддерживается то, что есть
в шпаргалке: **жирный**, *курсив*, <u>подчёркнутый</u>, `код`, [ссылка](адрес),
# заголовок, ## подзаголовок, - список, 1. список, > цитата,
==выделение==, - [ ] задача / - [x] сделано, таблицы | a | b |.
"""
from __future__ import annotations

import html
import re

INLINE = [
    ("code", re.compile(r"`([^`\n]+)`")),
    ("b", re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")),
    ("u", re.compile(r"<u>(.+?)</u>")),
    ("hl", re.compile(r"==(?=\S)(.+?)(?<=\S)==")),
    ("i", re.compile(r"(?<![*\w])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![*\w])|(?<!\w)_(?=\S)(.+?)(?<=\S)_(?!\w)")),
    ("link", re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")),
]
BLOCKS = [
    ("h2", re.compile(r"^(##\s+)")),
    ("h1", re.compile(r"^(#\s+)")),
    ("task", re.compile(r"^(\s*[-*+]\s+\[[ xXхХ]\]\s+)")),
    ("li", re.compile(r"^(\s*(?:[-*+•]|\d+[.)])\s+)")),
    ("quote", re.compile(r"^(>\s?)")),
]


TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEP = re.compile(r"^\s*\|(\s*:?-{2,}:?\s*\|)+\s*$")


def task_done(line: str) -> bool | None:
    """Строка-задача: True — отмечена («- [x]»), False — нет, None — не задача."""
    m = re.match(r"^\s*[-*+]\s+\[([ xXхХ])\]\s+", line)
    return None if m is None else m.group(1) != " "


def table_cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def block_of(line: str) -> tuple[str, int]:
    """Тип строки и длина её маркера: ("h1", 2) для «# Заголовок»; строка таблицы — ("row", 0)."""
    if TABLE_ROW.match(line):
        return "row", 0
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
    """Текст → [(тип блока, runs)]; тип: p, h1, h2, li, task, quote, row.
    Строка таблицы — ячейки через « │ » (линия-разделитель «|---|» пропускается)."""
    res = []
    for line in text.split("\n"):
        kind, n = block_of(line)
        if kind == "row":
            if TABLE_SEP.match(line):
                continue
            rs: list = []
            for k, cell in enumerate(table_cells(line)):
                if k:
                    rs.append((" │ ", frozenset(), ""))
                rs.extend(runs(cell))
            res.append(("row", rs))
            continue
        body = line[n:]
        if kind == "li":
            body = "• " + body
        elif kind == "task":
            body = ("☑ " if task_done(line) else "☐ ") + body
        res.append((kind, runs(body)))
    return res


def headings(text: str) -> list[tuple[int, int, str]]:
    """Оглавление: [(номер строки с 1, уровень 1/2, текст без разметки)]."""
    out = []
    for k, line in enumerate(text.split("\n"), 1):
        kind, n = block_of(line)
        if kind in ("h1", "h2"):
            title = "".join(r[0] for r in runs(line[n:])).strip()
            if title:
                out.append((k, 1 if kind == "h1" else 2, title))
    return out


def run_html(rs) -> str:
    parts = []
    for text, st, url in rs:
        s = html.escape(text)
        for tag, h in (("code", "code"), ("b", "b"), ("i", "i"), ("u", "u"), ("hl", "mark")):
            if tag in st:
                s = f"<{h}>{s}</{h}>"
        if url:
            s = f'<a href="{html.escape(url, quote=True)}">{s}</a>'
        parts.append(s)
    return "".join(parts)


def _slug(text: str, used: set) -> str:
    base = re.sub(r"[^\w]+", "-", text.lower()).strip("-") or "h"
    slug, k = base, 2
    while slug in used:
        slug, k = f"{base}-{k}", k + 1
    used.add(slug)
    return slug


def to_html(text: str, toc: bool = False) -> str:
    """HTML: настоящие списки <ul>/<ol>, задачи с галочками, таблицы, якоря у заголовков.
    toc=True — оглавление сверху (если заголовков хотя бы 3)."""
    out: list[str] = []
    lines = text.split("\n")
    used: set = set()
    heads: list[tuple[int, str, str]] = []
    k = 0
    open_list = None

    def close_list():
        nonlocal open_list
        if open_list:
            out.append("</ol>" if open_list == "ol" else "</ul>")
            open_list = None

    while k < len(lines):
        line = lines[k]
        kind, n = block_of(line)
        if kind == "row":
            close_list()
            rows = []
            while k < len(lines) and block_of(lines[k])[0] == "row":
                rows.append(lines[k])
                k += 1
            head = len(rows) > 1 and TABLE_SEP.match(rows[1])
            body = [r for r in rows if not TABLE_SEP.match(r)]
            html_rows = []
            for i, r in enumerate(body):
                cell = "th" if head and i == 0 else "td"
                html_rows.append("<tr>" + "".join(f"<{cell}>{run_html(runs(c))}</{cell}>"
                                                  for c in table_cells(r)) + "</tr>")
            out.append("<table>" + "".join(html_rows) + "</table>")
            continue
        k += 1
        if kind in ("li", "task"):
            ordered = kind == "li" and re.match(r"\s*\d", line) is not None
            want = "tasks" if kind == "task" else ("ol" if ordered else "ul")
            if open_list != want:
                close_list()
                out.append(f"<{want}>" if kind == "li" else '<ul class="tasks">')
                open_list = want
            inner = run_html(runs(line[n:]))
            if kind == "task":
                chk = " checked" if task_done(line) else ""
                inner = f'<input type="checkbox" disabled{chk}> {inner}'
            out.append(f"<li>{inner}</li>")
            continue
        close_list()
        inner = run_html(runs(line[n:])) or "&nbsp;"
        if kind in ("h1", "h2"):
            slug = _slug("".join(r[0] for r in runs(line[n:])), used)
            heads.append((1 if kind == "h1" else 2, slug, inner))
            out.append(f'<{kind} id="{slug}">{inner}</{kind}>')
        elif kind == "quote":
            out.append(f"<blockquote>{inner}</blockquote>")
        else:
            out.append(f"<p>{inner}</p>")
    close_list()
    if toc and len(heads) >= 3:
        items = "".join(f'<li class="l{lv}"><a href="#{sl}">{h}</a></li>' for lv, sl, h in heads)
        out.insert(0, f'<nav class="toc"><ul>{items}</ul></nav>')
    return "\n".join(out)


def plain(text: str) -> str:
    """Текст без разметки (для TXT)."""
    return "\n".join("".join(r[0] for r in rs) for _k, rs in paragraphs(text))
