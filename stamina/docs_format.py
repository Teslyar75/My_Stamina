"""Оформление в редакторе документов: Markdown вживую, лента кнопок, поиск, справка.

Текст документа — обычный Markdown: что набрано, то и хранится (и уходит в .md).
Редактор подсвечивает разметку сразу при наборе: **жирный** становится жирным,
«# » — заголовком, маркеры приглушены. Кнопки и Ctrl-клавиши только ставят
или снимают эти маркеры — поэтому «визуальный» вид и Markdown всегда совпадают.
Клавиши ловятся по коду клавиши (работают в любой раскладке) и только в самом
редакторе — набор текста они не ломают.
"""
from __future__ import annotations

import sys
import tkinter as tk

from stamina import mdlite, theme
from stamina.adapt import make_vscroll
from stamina.hud import HudButton
from stamina.i18n import t as _t
from stamina.theme import AMBER, CYAN, GREEN, LINE, MUTED, PANEL, TEXT, px

WIN = sys.platform.startswith("win")
# Windows virtual-key коды: одинаковы в любой раскладке (Ctrl+B и на кириллице)
VK = {66: "b", 73: "i", 85: "u", 49: "1", 50: "2", 76: "l", 81: "q", 69: "e", 75: "k",
      90: "z", 89: "y", 70: "f", 72: "h", 191: "/"}
WRAP = {"b": ("**", "**"), "i": ("*", "*"), "u": ("<u>", "</u>"), "code": ("`", "`")}
LINE_MARK = {"h1": "# ", "h2": "## ", "li": "- ", "quote": "> "}


def actions() -> list[tuple[str, str, str]]:
    """(id, надпись кнопки, клавиши) — и для ленты, и для справки."""
    return [
        ("b", "B", "Ctrl+B"), ("i", "I", "Ctrl+I"), ("u", "U", "Ctrl+U"),
        ("h1", "H1", "Ctrl+Shift+1"), ("h2", "H2", "Ctrl+Shift+2"),
        ("li", "•", "Ctrl+Shift+L"), ("quote", "❝", "Ctrl+Shift+Q"),
        ("code", "</>", "Ctrl+E"), ("link", "🔗", "Ctrl+K"),
        ("undo", "↶", "Ctrl+Z"), ("redo", "↷", "Ctrl+Y"),
        ("find", "🔍", "Ctrl+F / Ctrl+H"), ("help", "?", "Ctrl+/"),
    ]


def action_names() -> dict:
    return {"b": _t("жирный"), "i": _t("курсив"), "u": _t("подчёркнутый"),
            "h1": _t("заголовок"), "h2": _t("подзаголовок"), "li": _t("список"),
            "quote": _t("цитата"), "code": _t("код"), "link": _t("ссылка"),
            "undo": _t("отменить"), "redo": _t("вернуть"), "find": _t("найти и заменить"),
            "help": _t("эта справка (ещё раз — список документов)")}


def cheat_sheet() -> list[tuple[str, str]]:
    """Шпаргалка Markdown: (что набрать, что получится)."""
    return [("**текст**", _t("жирный")), ("*текст*", _t("курсив")), ("<u>текст</u>", _t("подчёркнутый")),
            ("# " + _t("Заголовок"), _t("заголовок")), ("## " + _t("Подзаголовок"), _t("подзаголовок")),
            ("- " + _t("пункт"), _t("список")), ("1. " + _t("пункт"), _t("нумерованный список")),
            ("> " + _t("цитата"), _t("цитата")), ("`код`", _t("код")),
            ("[" + _t("текст") + "](https://…)", _t("ссылка"))]


def doc_font(size: int = 12, style: str = "") -> tuple:
    """Шрифт текста документа: спокойный книжный, не HUD-шрифт интерфейса."""
    family = "Segoe UI" if WIN else theme.font(size)[0]
    f = (family, theme.font(size)[1])
    return f + (style,) if style else f


class FormatMixin:
    """Подмешивается в DocsScreen: нужны self.text, self._say, self._changed."""

    # -- лента -------------------------------------------------------------------
    def build_format_bar(self, parent) -> tk.Frame:
        bar = tk.Frame(parent, bg=PANEL)
        self.fmt_buttons: dict[str, HudButton] = {}
        for aid, label, _keys in actions():
            color = AMBER if aid == "help" else (GREEN if aid == "find" else CYAN)
            gap = px(6) if aid in ("undo", "find", "help") else px(2)
            w = 30
            b = HudButton(bar, label, lambda a=aid: self.do_action(a), height=28, width=w,
                          font_size=9, color=color)
            b.pack(side=tk.LEFT, padx=(gap if self.fmt_buttons else 0, 0))
            self.fmt_buttons[aid] = b
        return bar

    def build_find_bar(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=PANEL)
        self.find_var, self.repl_var = tk.StringVar(), tk.StringVar()

        def entry(var, w):
            e = tk.Entry(f, textvariable=var, width=w, bg=theme.BG2, fg=TEXT, insertbackground=CYAN,
                         relief=tk.FLAT, font=theme.font(10), highlightthickness=1,
                         highlightbackground=LINE, highlightcolor=CYAN)
            return e
        tk.Label(f, text=_t("Найти:"), bg=PANEL, fg=MUTED, font=theme.font(9)).pack(side=tk.LEFT)
        self.find_entry = entry(self.find_var, 16)
        self.find_entry.pack(side=tk.LEFT, padx=(px(4), px(8)), ipady=2)
        tk.Label(f, text=_t("Заменить:"), bg=PANEL, fg=MUTED, font=theme.font(9)).pack(side=tk.LEFT)
        self.repl_entry = entry(self.repl_var, 14)
        self.repl_entry.pack(side=tk.LEFT, padx=(px(4), px(8)), ipady=2)
        for label, cmd in ((_t("ДАЛЕЕ"), self.find_next), (_t("ЗАМЕНИТЬ"), self.replace_one),
                           (_t("ВСЕ"), self.replace_all), ("✕", self.close_find)):
            HudButton(f, label, cmd, height=26, font_size=8, color=MUTED if label == "✕" else CYAN,
                      width=30 if label == "✕" else None).pack(side=tk.LEFT, padx=(0, px(4)))
        self.find_entry.bind("<Return>", lambda _e: (self.find_next(), "break")[1])
        self.repl_entry.bind("<Return>", lambda _e: (self.replace_one(), "break")[1])
        for e in (self.find_entry, self.repl_entry):
            e.bind("<Escape>", lambda _e: (self.close_find(), "break")[1])
        self.find_var.trace_add("write", lambda *_a: self._mark_found())
        self.find_count = tk.Label(f, text="", bg=PANEL, fg=MUTED, font=theme.font(8))
        self.find_count.pack(side=tk.LEFT)
        self._find_bar = f
        return f

    # -- справка в левой панели ----------------------------------------------------
    def build_help_view(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=PANEL)
        sb = make_vscroll(f)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        t = tk.Text(f, wrap=tk.WORD, bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, width=26,
                    font=theme.font(9), highlightthickness=0, cursor="arrow", takefocus=0,
                    yscrollcommand=sb.set, spacing1=1, spacing3=1, padx=px(2))
        t.pack(fill=tk.BOTH, expand=True)
        sb.config(command=t.yview)
        t.tag_configure("h", font=theme.font(10, True), foreground=AMBER, spacing1=px(8), spacing3=px(3))
        t.tag_configure("k", font=theme.font(9, True), foreground=CYAN)
        t.tag_configure("m", font=theme.font(9, mono=True), foreground=GREEN)
        t.tag_configure("d", foreground=MUTED)
        t.insert(tk.END, _t("Пишите как обычно — оформление видно сразу. Окно справки не мешает: набирайте справа."), "d")
        t.insert(tk.END, "\n")
        t.insert(tk.END, _t("КНОПКИ И КЛАВИШИ") + "\n", "h")
        names = action_names()
        for aid, label, keys in actions():
            t.insert(tk.END, f"{label}  ", "k")
            t.insert(tk.END, f"{names[aid]}  ")
            t.insert(tk.END, keys + "\n", "d")
        t.insert(tk.END, _t("ШПАРГАЛКА MARKDOWN") + "\n", "h")
        for src, res in cheat_sheet():
            t.insert(tk.END, src, "m")
            t.insert(tk.END, "  → " + res + "\n", "d")
        t.insert(tk.END, _t("ФАЙЛЫ") + "\n", "h")
        t.insert(tk.END, _t("ЭКСПОРТ → .md, .docx, .html, .txt; «Открыть .md…» — взять файл Markdown. «ОТПРАВИТЬ» — письмо с файлом во вложении."), "d")
        t.config(state=tk.DISABLED)
        t.bind("<MouseWheel>", lambda e: (t.yview_scroll(-1 if e.delta > 0 else 1, "units"), "break")[1])
        self.help_text = t
        return f

    # -- подсветка ------------------------------------------------------------------
    def setup_md_tags(self) -> None:
        t = self.text
        base = 12
        t.tag_configure("md_h1", font=doc_font(base + 7, "bold"), spacing1=px(10), spacing3=px(4))
        t.tag_configure("md_h2", font=doc_font(base + 3, "bold"), spacing1=px(8), spacing3=px(2))
        t.tag_configure("md_b", font=doc_font(base, "bold"))
        t.tag_configure("md_i", font=doc_font(base, "italic"))
        t.tag_configure("md_bi", font=doc_font(base, "bold italic"))
        t.tag_configure("md_u", underline=True)
        t.tag_configure("md_code", font=theme.font(base - 1, mono=True), background=theme.blend(CYAN, theme.BG2, 0.12))
        t.tag_configure("md_link", foreground=CYAN, underline=True)
        t.tag_configure("md_quote", foreground=MUTED, lmargin1=px(18), lmargin2=px(18))
        t.tag_configure("md_li", lmargin1=px(6), lmargin2=px(22))
        t.tag_configure("md_mark", foreground=theme.blend(MUTED, theme.BG2, 0.55))
        t.tag_configure("found", background=theme.blend(AMBER, theme.BG2, 0.45))
        for tag in ("md_h1", "md_h2"):
            t.tag_raise(tag)
        for tag in ("md_b", "md_i", "md_bi", "md_code", "md_mark", "found"):
            t.tag_raise(tag)
        self._hl_job = None
        t.bind("<KeyRelease>", lambda _e: self.schedule_highlight(), add="+")
        t.bind("<Control-KeyPress>", self._on_ctrl_key, add="+")
        t.bind("<Return>", self._on_return, add="+")

    MD_TAGS = ("md_h1", "md_h2", "md_b", "md_i", "md_bi", "md_u", "md_code", "md_link",
               "md_quote", "md_li", "md_mark")

    def schedule_highlight(self) -> None:
        if getattr(self, "_hl_job", None):
            self.after_cancel(self._hl_job)
        self._hl_job = self.after(60, self.highlight)

    def highlight(self, first: int | None = None, last: int | None = None) -> None:
        self._hl_job = None
        t = self.text
        end = int(t.index("end-1c").split(".")[0])
        first, last = first or 1, min(last or end, end)
        img_lines = {int(idx.split(".")[0]) for _k, _v, idx in t.dump(f"{first}.0", f"{last}.end", image=True)}
        for tag in self.MD_TAGS:
            t.tag_remove(tag, f"{first}.0", f"{last}.end+1c")
        for ln in range(first, last + 1):
            if ln in img_lines:
                continue
            line = t.get(f"{ln}.0", f"{ln}.end")
            if not line:
                continue
            kind, n = mdlite.block_of(line)
            if kind != "p":
                t.tag_add("md_" + kind, f"{ln}.0", f"{ln}.end")
                if kind != "li":
                    t.tag_add("md_mark", f"{ln}.0", f"{ln}.{n}")
            spans = mdlite.inline_spans(line)
            bold, ital = set(), set()
            for name, a, b, marks in spans:
                t.tag_add("md_" + name, f"{ln}.{a}", f"{ln}.{b}")
                for x, y in marks:
                    t.tag_add("md_mark", f"{ln}.{x}", f"{ln}.{y}")
                (bold if name == "b" else ital if name == "i" else set()).update(range(a, b))
            both = sorted(bold & ital)
            for k in both:
                t.tag_add("md_bi", f"{ln}.{k}")
        self.update_empty_hint()

    # -- действия ----------------------------------------------------------------------
    def _on_ctrl_key(self, e):
        key = VK.get(e.keycode) if WIN else None
        if key is None:
            ks = (e.keysym or "").lower()
            key = {"exclam": "1", "at": "2", "slash": "/", "question": "/"}.get(ks, ks if len(ks) == 1 else None)
        shift = bool(e.state & 0x1)
        if shift:
            act = {"1": "h1", "2": "h2", "l": "li", "q": "quote", "z": "redo"}.get(key)
        else:
            act = {"b": "b", "i": "i", "u": "u", "e": "code", "k": "link", "z": "undo", "y": "redo",
                   "f": "find", "h": "find", "/": "help"}.get(key)
        if act is None:
            return None
        self.do_action(act, replace=(key == "h"))
        return "break"

    def do_action(self, aid: str, replace: bool = False) -> None:
        t = self.text
        if aid in WRAP:
            self.wrap_selection(*WRAP[aid])
        elif aid in LINE_MARK:
            self.toggle_line(aid)
        elif aid == "link":
            self.wrap_selection("[", "](https://)", select_tail=True)
        elif aid == "undo":
            try:
                t.edit_undo()
            except tk.TclError:
                pass
        elif aid == "redo":
            try:
                t.edit_redo()
            except tk.TclError:
                pass
        elif aid == "find":
            self.open_find(replace)
            return
        elif aid == "help":
            self.toggle_help()
            t.focus_set()
            return
        self.highlight()
        self._changed()
        t.focus_set()

    def wrap_selection(self, left: str, right: str, select_tail: bool = False) -> None:
        t = self.text
        t.edit_separator()
        try:
            a, b = t.index("sel.first"), t.index("sel.last")
        except tk.TclError:
            a = b = t.index("insert")
        inner = t.get(a, b)
        before = t.get(f"{a}-{len(left)}c", a)
        after = t.get(b, f"{b}+{len(right)}c")
        if inner and before == left and after == right:          # снять оформление
            t.delete(b, f"{b}+{len(right)}c")
            t.delete(f"{a}-{len(left)}c", a)
            return
        if inner.startswith(left) and inner.endswith(right) and len(inner) >= len(left) + len(right):
            t.delete(a, b)
            t.insert(a, inner[len(left):len(inner) - len(right)])
            return
        t.delete(a, b)
        t.insert(a, left + inner + right)
        t.tag_remove("sel", "1.0", tk.END)
        if select_tail:                                         # курсор — на адрес ссылки
            pos = t.index(f"{a}+{len(left) + len(inner) + 2}c")
            t.mark_set("insert", pos)
            t.tag_add("sel", pos, f"{pos}+8c")
        elif inner:
            t.tag_add("sel", f"{a}+{len(left)}c", f"{a}+{len(left) + len(inner)}c")
            t.mark_set("insert", f"{a}+{len(left) + len(inner) + len(right)}c")
        else:
            t.mark_set("insert", f"{a}+{len(left)}c")
        t.edit_separator()

    def toggle_line(self, kind: str) -> None:
        t = self.text
        t.edit_separator()
        try:
            l1 = int(t.index("sel.first").split(".")[0])
            l2 = int(t.index("sel.last").split(".")[0])
        except tk.TclError:
            l1 = l2 = int(t.index("insert").split(".")[0])
        lines = [t.get(f"{ln}.0", f"{ln}.end") for ln in range(l1, l2 + 1)]
        all_on = all(mdlite.block_of(s)[0] == kind for s in lines if s.strip()) and any(s.strip() for s in lines)
        for ln, s in zip(range(l1, l2 + 1), lines):
            cur, n = mdlite.block_of(s)
            if n:
                t.delete(f"{ln}.0", f"{ln}.{n}")
            if not all_on and (s.strip() or l1 == l2):
                t.insert(f"{ln}.0", LINE_MARK[kind])
        t.edit_separator()

    def _on_return(self, _e=None):
        """Enter в пункте списка продолжает список; на пустом пункте — заканчивает."""
        t = self.text
        ln = t.index("insert").split(".")[0]
        line = t.get(f"{ln}.0", f"{ln}.end")
        kind, n = mdlite.block_of(line)
        if kind not in ("li", "quote") or t.compare("insert", "!=", f"{ln}.end"):
            self.schedule_highlight()
            return None
        if not line[n:].strip():
            t.delete(f"{ln}.0", f"{ln}.end")
            self.schedule_highlight()
            return "break"
        mark = line[:n]
        import re
        num = re.match(r"(\s*)(\d+)([.)]\s+)", mark)
        if num:
            mark = f"{num.group(1)}{int(num.group(2)) + 1}{num.group(3)}"
        t.insert("insert", "\n" + mark)
        t.see("insert")
        self.schedule_highlight()
        return "break"

    # -- поиск ----------------------------------------------------------------------------
    def open_find(self, replace: bool = False) -> None:
        if not self._find_bar.winfo_ismapped():
            self._find_bar.pack(fill=tk.X, pady=(0, px(6)), before=self._editor_wrap)
        try:
            sel = self.text.get("sel.first", "sel.last")
            if sel and "\n" not in sel:
                self.find_var.set(sel)
        except tk.TclError:
            pass
        (self.repl_entry if replace else self.find_entry).focus_set()
        self._mark_found()

    def close_find(self) -> None:
        self._find_bar.pack_forget()
        self.text.tag_remove("found", "1.0", tk.END)
        self.text.focus_set()

    def _mark_found(self) -> int:
        t = self.text
        t.tag_remove("found", "1.0", tk.END)
        q = self.find_var.get()
        n = 0
        if q:
            pos = "1.0"
            while True:
                pos = t.search(q, pos, tk.END, nocase=True)
                if not pos:
                    break
                t.tag_add("found", pos, f"{pos}+{len(q)}c")
                pos = f"{pos}+{len(q)}c"
                n += 1
        self.find_count.config(text=_t("совпадений: {0}").format(n) if q else "")
        return n

    def find_next(self) -> bool:
        t = self.text
        q = self.find_var.get()
        if not q:
            return False
        pos = t.search(q, "insert+1c", tk.END, nocase=True) or t.search(q, "1.0", tk.END, nocase=True)
        if not pos:
            return False
        t.tag_remove("sel", "1.0", tk.END)
        t.tag_add("sel", pos, f"{pos}+{len(q)}c")
        t.mark_set("insert", pos)
        t.see(pos)
        return True

    def replace_one(self) -> None:
        t = self.text
        q = self.find_var.get()
        try:
            if t.get("sel.first", "sel.last").lower() == q.lower() and q:
                a = t.index("sel.first")
                t.delete("sel.first", "sel.last")
                t.insert(a, self.repl_var.get())
                t.mark_set("insert", a)
        except tk.TclError:
            pass
        self.find_next()
        self._mark_found()
        self.highlight()
        self._changed()

    def replace_all(self) -> int:
        t = self.text
        q, r = self.find_var.get(), self.repl_var.get()
        if not q:
            return 0
        n, pos = 0, "1.0"
        t.edit_separator()
        while True:
            pos = t.search(q, pos, tk.END, nocase=True)
            if not pos:
                break
            t.delete(pos, f"{pos}+{len(q)}c")
            t.insert(pos, r)
            pos = f"{pos}+{len(r)}c"
            n += 1
        t.edit_separator()
        self._mark_found()
        self.highlight()
        self._changed()
        self.find_count.config(text=_t("заменено: {0}").format(n))
        return n
