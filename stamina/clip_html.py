"""Вставка с оформлением: HTML из буфера обмена → Markdown документа.

Браузеры и Word кладут в буфер вместе с текстом ещё и HTML. Мы берём его и переводим
в тот же Markdown, что пишется в редакторе: жирный, курсив, подчёркнутый, заголовки,
списки, цитаты, код, ссылки, таблицы. Картинки из HTML не тянем (это внешние адреса) —
снимок вставляется отдельно, как и раньше.

Откуда HTML:
* Windows — формат буфера «HTML Format» (CF_HTML) через ctypes, без сторонних пакетов;
* Linux — ``wl-paste`` (Wayland) или ``xclip`` (X11), тип ``text/html``;
* нигде нет — ``None``, редактор вставляет обычный текст.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser

_BLOCK = {"p", "div", "section", "article", "header", "footer", "main", "figure", "tr", "table",
          "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "blockquote", "pre", "hr", "dl", "dt", "dd"}
_SKIP = {"script", "style", "head", "title", "meta", "template", "noscript", "svg"}
_INLINE_MARK = {"b": "**", "strong": "**", "i": "*", "em": "*", "cite": "*", "code": "`", "kbd": "`"}


class _ToMarkdown(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []        # готовые строки
        self.cur: list[str] = []          # текущая строка
        self.prefix = ""                  # маркер блока для текущей строки («# », «- », «> »)
        self.lists: list[list] = []       # стек списков: ["ul"|"ol", номер]
        self.quote = 0
        self.skip = 0
        self.pre = 0
        self.href: list[str | None] = []
        self.link_start: list[int] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.table: list[list[str]] = []
        self.u = 0

    # -- служебное
    def _flush(self, blank: bool = False) -> None:
        text = "".join(self.cur)
        if not self.pre:
            text = re.sub(r"[ \t\r\n\f\v]+", " ", text).strip()
        if text:
            q = "> " * self.quote
            self.lines.append(q + self.prefix + text)
        self.cur, self.prefix = [], ""
        if blank and self.lines and self.lines[-1] != "":
            self.lines.append("")

    def _out(self, s: str) -> None:
        if self.cell is not None:
            self.cell.append(s)
        else:
            self.cur.append(s)

    # -- разбор
    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        a = dict(attrs)
        style = (a.get("style") or "").replace(" ", "").lower()
        if tag in ("td", "th") and self.row is not None:
            self.cell = []
            return
        if tag == "tr":
            self.row = []
            return
        if tag == "table":
            self._flush(blank=True)
            self.table = []
            return
        if tag in _BLOCK and self.cell is None:
            self._flush(blank=tag in ("p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "blockquote",
                                      "pre", "hr") and not self.lists)
        if tag in ("h1",):
            self.prefix = "# "
        elif tag in ("h2", "h3", "h4", "h5", "h6"):
            self.prefix = "## "
        elif tag in ("ul", "ol"):
            self.lists.append([tag, 0])
        elif tag == "li":
            indent = "  " * max(0, len(self.lists) - 1)
            if self.lists and self.lists[-1][0] == "ol":
                self.lists[-1][1] += 1
                self.prefix = f"{indent}{self.lists[-1][1]}. "
            else:
                self.prefix = indent + "- "
        elif tag == "blockquote":
            self.quote += 1
        elif tag == "pre":
            self.pre += 1
        elif tag == "br":
            if self.cell is not None:
                self.cell.append(" ")
            else:
                self._flush()
        elif tag == "hr":
            self.lines += ["---", ""]
        elif tag in _INLINE_MARK and not self.pre:
            self._out(_INLINE_MARK[tag])
        elif tag == "u" or (tag == "span" and "text-decoration:underline" in style):
            self._out("<u>")
            self.u += 1
            self.href.append("u")  # маркер для закрытия span
            return
        elif tag == "a":
            self.href.append(a.get("href"))
            self._out("[")
            return
        if tag == "span":
            bold = "font-weight:bold" in style or "font-weight:700" in style
            ital = "font-style:italic" in style
            mark = ("**" if bold else "") + ("*" if ital else "")
            self.href.append(("span", mark))
            if mark:
                self._out(mark)

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag in ("td", "th") and self.cell is not None:
            txt = re.sub(r"\s+", " ", "".join(self.cell)).strip().replace("|", "\\|")
            (self.row if self.row is not None else []).append(txt)
            self.cell = None
            return
        if tag == "tr" and self.row is not None:
            if any(c for c in self.row):
                self.table.append(self.row)
            self.row = None
            return
        if tag == "table":
            self._emit_table()
            return
        if tag in _INLINE_MARK and not self.pre:
            self._close_mark(_INLINE_MARK[tag])
        elif tag == "u":
            if self.href and self.href[-1] == "u":
                self.href.pop()
            self._out("</u>")
            self.u = max(0, self.u - 1)
        elif tag == "a":
            href = self.href.pop() if self.href else None
            self._out(f"]({href})" if isinstance(href, str) and href else "]")
            if not (isinstance(href, str) and href):
                self._unwrap_link()
        elif tag == "span":
            top = self.href.pop() if self.href else None
            if top == "u":
                self._out("</u>")
            elif isinstance(top, tuple) and top[1]:
                self._close_mark(top[1][::-1])
        if tag in _BLOCK and self.cell is None:
            if tag in ("ul", "ol") and self.lists:
                self.lists.pop()
            if tag == "blockquote":
                self._flush(blank=True)
                self.quote = max(0, self.quote - 1)
                return
            if tag == "pre":
                self._flush(blank=True)
                self.pre = max(0, self.pre - 1)
                return
            self._flush(blank=tag in ("p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol") and not self.lists)

    def _close_mark(self, mark: str) -> None:
        """Закрыть «**»/«*»/«`»: пустой тег — без маркеров, пробел в конце — за маркер
        (иначе «**жирный **» Markdown не узнает)."""
        buf = self.cell if self.cell is not None else self.cur
        s = "".join(buf)
        if s.endswith(mark):
            buf[:] = [s[:-len(mark)]]
            return
        body = s.rstrip()
        buf[:] = [body + mark + s[len(body):]]

    def _unwrap_link(self) -> None:
        """Ссылка без адреса: «[текст]» → «текст»."""
        buf = self.cell if self.cell is not None else self.cur
        s = "".join(buf)
        k = s.rfind("[")
        if k >= 0 and s.endswith("]"):
            s = s[:k] + s[k + 1:-1]
        buf[:] = [s]

    def handle_data(self, data):
        if self.skip:
            return
        self._out(data)

    def _emit_table(self) -> None:
        rows, self.table = self.table, []
        if not rows:
            return
        n = max(len(r) for r in rows)
        rows = [r + [""] * (n - len(r)) for r in rows]
        self.lines.append("| " + " | ".join(rows[0]) + " |")
        self.lines.append("|" + "|".join(["---"] * n) + "|")
        for r in rows[1:]:
            self.lines.append("| " + " | ".join(r) + " |")
        self.lines.append("")

    def result(self) -> str:
        self._flush()
        out: list[str] = []
        for ln in self.lines:
            if ln == "" and (not out or out[-1] == ""):
                continue
            out.append(ln.rstrip())
        while out and out[-1] == "":
            out.pop()
        return "\n".join(out)


def to_markdown(html: str) -> str:
    """HTML-фрагмент → Markdown редактора (без картинок)."""
    p = _ToMarkdown()
    p.feed(html or "")
    p.close()
    return p.result()


def cf_html_fragment(raw: bytes | str) -> str:
    """Вырезать фрагмент из Windows CF_HTML (заголовок с StartFragment/EndFragment)."""
    data = raw.encode("utf-8", "replace") if isinstance(raw, str) else bytes(raw)
    data = data.split(b"\0", 1)[0]
    m1 = re.search(rb"StartFragment:(\d+)", data)
    m2 = re.search(rb"EndFragment:(\d+)", data)
    if m1 and m2:
        a, b = int(m1.group(1)), int(m2.group(1))
        if 0 <= a < b <= len(data):
            return data[a:b].decode("utf-8", "replace")
    text = data.decode("utf-8", "replace")
    m = re.search(r"<!--StartFragment-->(.*)<!--EndFragment-->", text, re.S)
    if m:
        return m.group(1)
    k = text.find("<")
    return text[k:] if k >= 0 else ""


def _windows_html() -> str | None:
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.RegisterClipboardFormatW.restype = wintypes.UINT
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalSize.restype = ctypes.c_size_t
    kernel32.GlobalSize.argtypes = [wintypes.HANDLE]
    fmt = user32.RegisterClipboardFormatW("HTML Format")
    if not fmt or not user32.IsClipboardFormatAvailable(fmt):
        return None
    if not user32.OpenClipboard(None):
        return None
    try:
        h = user32.GetClipboardData(fmt)
        if not h:
            return None
        ptr = kernel32.GlobalLock(h)
        if not ptr:
            return None
        try:
            raw = ctypes.string_at(ptr, kernel32.GlobalSize(h))
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()
    return cf_html_fragment(raw)


def _run(cmd: list[str]) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=2, check=False)  # noqa: S603
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0 or not r.stdout:
        return None
    return r.stdout.decode("utf-8", "replace")


def _unix_html() -> str | None:
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste"):
        types = _run(["wl-paste", "--list-types"]) or ""
        if "text/html" in types.split():
            return _run(["wl-paste", "--no-newline", "--type", "text/html"])
    if os.environ.get("DISPLAY") and shutil.which("xclip"):
        targets = _run(["xclip", "-selection", "clipboard", "-o", "-t", "TARGETS"]) or ""
        if "text/html" in targets.split():
            return _run(["xclip", "-selection", "clipboard", "-o", "-t", "text/html"])
    return None


def clipboard_html() -> str | None:
    """HTML из буфера обмена или None (нет HTML, нет утилиты, ошибка) — тогда вставляем текст."""
    try:
        if sys.platform.startswith("win"):
            return _windows_html()
        if sys.platform == "darwin":
            return None
        return _unix_html()
    except Exception:  # noqa: BLE001 — буфер обмена чужой, его сбой не должен ломать вставку
        return None


def clipboard_markdown() -> str | None:
    html = clipboard_html()
    if not html or "<" not in html:
        return None
    md = to_markdown(html)
    return md or None
