"""«ПРОСМОТР» документа: готовая страница без разметки, только чтение.

Цвета и шрифты — из темы пульта (theme.*, docs_format.doc_font), поэтому
просмотр выглядит своим в любом скине: «лист» — цвет полей ввода BG2,
текст — TEXT, ссылки — CYAN. Колесо — общий wheel_router.bind_scroll
(Windows, X11 и Tk 9 одинаково). Esc — закрыть.
"""
from __future__ import annotations

import io
import tkinter as tk

from stamina import mdlite, theme, wheel_router
from stamina.adapt import make_vscroll
from stamina.docs_format import doc_font
from stamina.hud import HudButton
from stamina.i18n import t as _t
from stamina.theme import px


def setup_tags(txt: tk.Text, base: int = 12) -> None:
    """Теги готового текста (без маркеров) — общие для просмотра и печати на экран."""
    panel = theme.BG2
    txt.tag_configure("title", font=doc_font(base + 8, "bold"), spacing3=px(14))
    txt.tag_configure("h1", font=doc_font(base + 5, "bold"), spacing1=px(10), spacing3=px(6))
    txt.tag_configure("h2", font=doc_font(base + 2, "bold"), spacing1=px(8), spacing3=px(4))
    txt.tag_configure("b", font=doc_font(base, "bold"))
    txt.tag_configure("i", font=doc_font(base, "italic"))
    txt.tag_configure("bi", font=doc_font(base, "bold italic"))
    txt.tag_configure("u", underline=True)
    txt.tag_configure("code", font=theme.font(base - 1, mono=True),
                      background=theme.blend(theme.CYAN, panel, 0.12))
    txt.tag_configure("link", foreground=theme.CYAN, underline=True)
    txt.tag_configure("quote", foreground=theme.MUTED, lmargin1=px(22), lmargin2=px(22),
                      font=doc_font(base, "italic"))
    txt.tag_configure("li", lmargin1=px(10), lmargin2=px(24))
    for tg in ("b", "i", "bi", "code"):
        txt.tag_raise(tg)


def insert_markdown(txt: tk.Text, text: str) -> None:
    """Markdown → текст с тегами (маркеры убраны)."""
    paras = mdlite.paragraphs(text)
    for n, (kind, rs) in enumerate(paras):
        for t, st, _url in rs:
            tags = [kind] + [x for x in st]
            if "b" in st and "i" in st:
                tags.append("bi")
            txt.insert(tk.END, t, tuple(tags))
        if n < len(paras) - 1:
            txt.insert(tk.END, "\n", (kind,))


class DocPreview(tk.Toplevel):
    """Полноэкранный просмотр: «лист» по центру, только чтение. Esc — закрыть."""

    def __init__(self, master, doc, widths: dict) -> None:
        bg, page_bg = theme.BG, theme.BG2
        super().__init__(master, bg=bg)
        self.title(doc.display_title() or _t("ПРОСМОТР"))
        try:
            self.attributes("-fullscreen", True)
        except tk.TclError:
            try:
                self.state("zoomed")
            except tk.TclError:
                pass
        self._photos: list = []
        bar = tk.Frame(self, bg=bg)
        bar.pack(fill=tk.X, padx=px(14), pady=px(6))
        tk.Label(bar, text=_t("ПРОСМОТР · Esc — закрыть"), bg=bg, fg=theme.MUTED,
                 font=theme.font(9)).pack(side=tk.LEFT)
        HudButton(bar, "✕", self.destroy, height=28, width=36, font_size=10).pack(side=tk.RIGHT)
        page = tk.Frame(self, bg=page_bg, highlightthickness=1, highlightbackground=theme.LINE)
        page.pack(fill=tk.Y, expand=True, pady=(0, px(14)))
        sb = make_vscroll(page)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        txt = self.txt = tk.Text(page, wrap=tk.WORD, width=78, bg=page_bg, fg=theme.TEXT, relief=tk.FLAT,
                                 bd=0, font=doc_font(12), padx=px(48), pady=px(36), spacing1=2, spacing3=4,
                                 highlightthickness=0, cursor="arrow", yscrollcommand=sb.set,
                                 selectbackground=theme.blend(theme.CYAN, page_bg, 0.45))
        txt.pack(side=tk.LEFT, fill=tk.Y)
        sb.config(command=txt.yview)
        setup_tags(txt)
        if doc.title.strip():
            txt.insert(tk.END, doc.title.strip() + "\n", "title")
        try:
            from PIL import Image, ImageTk
        except Exception:  # noqa: BLE001
            Image = None
        for seg in doc.segments:
            if "t" in seg:
                insert_markdown(txt, seg["t"])
            elif Image is not None and seg.get("img") in doc.images:
                im = Image.open(io.BytesIO(doc.images[seg["img"]]))
                logical = int(widths.get(seg["img"]) or seg.get("w") or 0)
                w = px(logical) if logical else im.width
                if w < im.width:
                    im = im.resize((w, max(1, round(im.height * w / im.width))), Image.LANCZOS)
                ph = ImageTk.PhotoImage(im, master=self)
                self._photos.append(ph)
                txt.image_create(tk.END, image=ph, pady=4)
        txt.config(state=tk.DISABLED)
        self.bind("<Escape>", lambda _e: self.destroy())
        for w in (txt, self, page):
            wheel_router.bind_scroll(w, lambda d: txt.yview_scroll(d * 3, "units"))
        self.focus_set()
