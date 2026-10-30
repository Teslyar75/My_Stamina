"""Экран «ДОКУМЕНТЫ» — писать текстом и голосом, вставлять снимки, хранить.

Слева — список документов пилота (свежие сверху), справа — редактор:
заголовок, лента кнопок и сам текст. Вставка текста и снимков — общий модуль
`stamina/compose.py` (тот же, что у чата Ориона), диктовка — общий MicControl.
Каждое изменение сохраняется само (автосохранение), формат — `stamina/docs.py`.
F9 в этом отсеке — диктовка (в остальных — звук).
"""
from __future__ import annotations

from stamina.i18n import t as _t

import io
import re
import time
import tkinter as tk
from pathlib import Path

from stamina import compose, docs, docs_format, docs_tools, mailer, shots, theme
from stamina.adapt import make_vscroll
from stamina.hud import HudButton, HudPanel
from stamina.theme import AMBER, BG, CYAN, GREEN, LINE, MUTED, PANEL, TEXT, px
from stamina.voice.mic import MicControl

AUTOSAVE_MS = 1200
IMG_WIDTH = 560          # ширина вставленного снимка по умолчанию, px
SIZES = (25, 50, 75, 100)


def _label(master, text="", *, fg=None, size=10, bold=False, bg=None, **kw):
    fg = TEXT if fg is None else fg
    bg = BG if bg is None else bg
    return tk.Label(master, text=text, fg=fg, bg=bg, font=theme.font(size, bold), **kw)


class DocsScreen(docs_format.FormatMixin, docs_tools.ToolsMixin, docs_tools.ReadAloudMixin, tk.Frame):
    """Список документов и редактор с автосохранением."""

    def __init__(self, master, app) -> None:
        super().__init__(master, bg=BG)
        self.app = app
        self.doc: docs.Document | None = None
        self._photos: dict[str, object] = {}      # Tk-ссылки на картинки в тексте
        self._widths: dict[str, int] = {}
        self._save_job = None
        self._items: list[dict] = []
        self._loading = False

        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(14), pady=(px(10), px(4)))
        _label(top, _t("ДОКУМЕНТЫ"), size=16, bold=True).pack(side=tk.LEFT)
        self.status = _label(top, "", fg=MUTED, size=9)
        self.status.pack(side=tk.LEFT, padx=(px(10), px(6)))
        HudButton(top, "?", lambda: self.app.open_help(), height=32, font_size=10,
                  width=32, color=AMBER).pack(side=tk.RIGHT)
        HudButton(top, _t("В ПАПКУ"), self._open_folder, height=32, font_size=9,
                  color=CYAN).pack(side=tk.RIGHT, padx=(0, px(8)))
        self._out_group = tk.Frame(top, bg=BG)
        self._out_group.pack(side=tk.RIGHT, padx=(0, px(14)))

        body = tk.Frame(self, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=px(14), pady=(0, px(10)))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # -- список
        left = HudPanel(body, title=_t("МОИ ДОКУМЕНТЫ"))
        left.grid(row=0, column=0, sticky="nsew", padx=(0, px(10)))
        self.left_panel = left
        # левая панель — либо список документов, либо справка по оформлению (кнопка «?»)
        self.help_view = self.build_help_view(left.body)
        lb = self.list_view = tk.Frame(left.body, bg=PANEL)
        lb.pack(fill=tk.BOTH, expand=True)
        btns = tk.Frame(lb, bg=PANEL)
        btns.pack(fill=tk.X, pady=(0, px(6)))
        HudButton(btns, _t("+ НОВЫЙ"), self.new_doc, height=32, font_size=10,
                  color=GREEN).pack(side=tk.LEFT)
        self.del_btn = HudButton(btns, _t("УБРАТЬ"), self._remove, height=32, font_size=9,
                                 color=MUTED)
        self.del_btn.pack(side=tk.RIGHT)
        sb = make_vscroll(lb)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox = tk.Listbox(lb, width=24, bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0,
                                  highlightthickness=0, selectbackground=theme.blend(CYAN, PANEL, 0.55),
                                  selectforeground=TEXT, activestyle="none", font=theme.font(10),
                                  yscrollcommand=sb.set, exportselection=False)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        sb.config(command=self.listbox.yview)
        self.listbox.bind("<<ListboxSelect>>", self._on_pick)
        self.empty_hint = _label(lb, _t("Здесь появятся ваши документы.\nНажмите «+ НОВЫЙ» и пишите —\nвсё сохраняется само."),
                                 fg=MUTED, size=9, bg=PANEL, justify="left")

        # -- редактор
        right = HudPanel(body, title=_t("РЕДАКТОР"))
        right.grid(row=0, column=1, sticky="nsew")
        self.right_panel, self._body = right, body
        rb = right.body
        self.title_var = tk.StringVar()
        self.title_entry = tk.Entry(rb, textvariable=self.title_var, bg=theme.BG2, fg=TEXT,
                                    insertbackground=CYAN, relief=tk.FLAT, font=theme.font(13, True),
                                    highlightthickness=1, highlightbackground=LINE, highlightcolor=CYAN)
        self.title_entry.pack(fill=tk.X, pady=(0, px(6)), ipady=px(3))
        self.title_var.trace_add("write", lambda *_a: self._changed())
        self.build_format_bar(rb).pack(fill=tk.X, pady=(0, px(6)))

        bar = tk.Frame(rb, bg=PANEL)
        bar.pack(fill=tk.X, pady=(0, px(6)))
        # «Вставить» — над редактором; «выдать» (просмотр/PDF/отправить/экспорт) —
        # в шапке страницы, чтобы на 1024×600 редактору осталась высота.
        ins = tk.Frame(bar, bg=PANEL)
        ins.pack(side=tk.LEFT)
        out = self._out_group
        self.img_btn = HudButton(ins, _t("КАРТИНКА ▾"), self.image_menu, height=30, font_size=9,
                                 color=CYAN)
        self.img_btn.pack(side=tk.LEFT)
        store = getattr(self.app, "store", None)
        self.mic = MicControl(ins, on_text=self.insert_dictation, on_status=self._mic_status,
                              label=_t("ДИКТОВКА F9"), height=30, font_size=9,
                              settings=getattr(store, "settings", None),
                              save=getattr(store, "save_settings", None))
        self.mic.button.command = self.start_dictation
        self.mic.button.pack(side=tk.LEFT, padx=(px(6), 0))
        self.lang_btn = HudButton(ins, "RU", self.dict_lang_menu, height=30, font_size=9,
                                  width=50, color=GREEN)
        self.lang_btn.pack(side=tk.LEFT, padx=(px(2), 0))
        self.tr_btn = HudButton(ins, _t("ПЕРЕВОД ▾"), self.translate_menu, height=30, font_size=9,
                                color=CYAN)
        self.tr_btn.pack(side=tk.LEFT, padx=(px(6), 0))
        self.check_btn = HudButton(ins, _t("ПРОВЕРКА"), self.check_text, height=30, font_size=9,
                                   color=AMBER)
        self.check_btn.pack(side=tk.LEFT, padx=(px(6), 0))
        self.read_btn = HudButton(ins, _t("▶ ЧИТАТЬ"), self.read_toggle, height=30, font_size=9,
                                  color=GREEN)
        self.read_btn.pack(side=tk.LEFT, padx=(px(6), 0))
        for sym, cmd in (("■", self.read_stop), ("⏮", lambda: self.read_chapter(-1)),
                         ("⏭", lambda: self.read_chapter(1))):
            HudButton(ins, sym, cmd, height=30, font_size=9, width=30,
                      color=MUTED).pack(side=tk.LEFT, padx=(px(2), 0))
        self._focus = None      # фокус-режим O — общий ui.FocusMode, как в сканере английского
        self.btn_focus = HudButton(ins, _t("⛶ ФОКУС  O"), self.toggle_focus, height=30, font_size=9,
                                   color=AMBER)
        self.btn_focus.pack(side=tk.LEFT, padx=(px(6), 0))
        self.export_btn = HudButton(out, _t("ЭКСПОРТ"), self._export_menu, height=32, font_size=9,
                                    color=AMBER)
        self.export_btn.pack(side=tk.RIGHT)
        HudButton(out, _t("ОТПРАВИТЬ"), self.send_mail, height=32, font_size=9,
                  color=GREEN).pack(side=tk.RIGHT, padx=(0, px(6)))
        HudButton(out, "PDF", self.save_pdf, height=32, font_size=9,
                  color=AMBER).pack(side=tk.RIGHT, padx=(0, px(6)))
        HudButton(out, _t("ПРОСМОТР"), self.preview, height=32, font_size=9,
                  color=GREEN).pack(side=tk.RIGHT, padx=(0, px(6)))
        self.mic_hint = _label(rb, "", fg=MUTED, size=8, bg=PANEL, anchor="w")
        self.mic_hint.pack(side=tk.BOTTOM, fill=tk.X)
        self.build_find_bar(rb)
        wrap = self._editor_wrap = tk.Frame(rb, bg=PANEL)
        wrap.pack(fill=tk.BOTH, expand=True)
        tsb = make_vscroll(wrap)
        tsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text = tk.Text(wrap, wrap=tk.WORD, bg=theme.BG2, fg=TEXT, insertbackground=CYAN,
                            relief=tk.FLAT, font=docs_format.doc_font(12), undo=True, maxundo=-1, autoseparators=True,
                            padx=px(30), pady=px(18), highlightthickness=0, yscrollcommand=tsb.set,
                            spacing1=px(3), spacing2=px(2), spacing3=px(5))
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tsb.config(command=self.text.yview)
        self.text.bind("<<Modified>>", self._on_modified)
        self.text.bind("<<Paste>>", self._on_paste)
        self.text.bind("<Button-3>", self._image_menu)
        self.text.bind("<Double-Button-1>", self._open_image_at)
        self.setup_md_tags()
        # подсказка в пустом документе (исчезает с первой буквой)
        self.text_hint = tk.Label(self.text, text=_t("Начните писать здесь. **жирный**, *курсив*, # заголовок, - список — оформление видно сразу.\nСнимок из буфера — Ctrl+V, голос — F9, справка по кнопкам — «?»."),
                                  bg=theme.BG2, fg=MUTED, font=docs_format.doc_font(11), justify="left",
                                  anchor="nw", cursor="xterm")
        self.text_hint.bind("<Button-1>", lambda _e: self.text.focus_set())

        self.init_tools()
        self.text.tag_configure("speak", background="#1f3b4d")
        self.text.tag_lower("speak")
        self.after(160, self._tick_mic)
        self.refresh()
        self._show_doc(None)

    # -- для кокпита ------------------------------------------------------------
    def focus_input(self) -> None:
        self.refresh()
        self.text.focus_set()

    def on_key(self, e):
        """Набор принадлежит редактору; O/Щ — фокус-режим, только вне полей ввода."""
        if e.keysym == "Escape" and self._focus is not None:
            self.toggle_focus(False)
            return "break"
        from stamina.english.speech_std import is_focus_key
        w = self.focus_get()
        if is_focus_key(e) and not isinstance(w, (tk.Text, tk.Entry)):
            self.toggle_focus()
            return "break"
        return None

    # -- фокус-режим (O / Щ, Esc — выход) ----------------------------------------
    def in_focus(self) -> bool:
        return self._focus is not None

    def toggle_focus(self, on: bool | None = None) -> None:
        from stamina.english.ui import FocusMode
        on = (self._focus is None) if on is None else on
        if on and self._focus is None:
            # редактор на всё окно; если открыта справка — редактор вместе со справкой
            target = self._body if getattr(self, "_help_on", False) else self.right_panel
            self.update_idletasks()   # FocusMode прячет только отображённые grid-виджеты
            self._focus = FocusMode(target)
        elif not on and self._focus is not None:
            f, self._focus = self._focus, None
            f.restore()
        self.btn_focus.set_text(_t("✕ ФОКУС  Esc") if self._focus else _t("⛶ ФОКУС  O"))
        self.btn_focus.set_active(self._focus is not None)

    def on_leave(self) -> None:
        self.toggle_focus(False)
        self.save_now()

    def dictate(self) -> None:
        """F9 в этом отсеке: начать/закончить диктовку."""
        self.text.focus_set()
        self.start_dictation()

    # -- список ------------------------------------------------------------------
    def refresh(self) -> None:
        self._items = docs.list_docs()
        self.listbox.delete(0, tk.END)
        cur = self.doc.path if self.doc else None
        for i, it in enumerate(self._items):
            when = time.strftime("%d.%m %H:%M", time.localtime(it["modified"])) if it["modified"] else ""
            title = it["title"] or _t("Без названия")
            self.listbox.insert(tk.END, f" {title}")
            self.listbox.insert(tk.END, f"    {when}")
            self.listbox.itemconfig(tk.END, fg=MUTED, selectforeground=MUTED)
            if cur and Path(it["path"]) == Path(cur):
                self.listbox.selection_set(2 * i, 2 * i + 1)
        if self._items:
            self.empty_hint.place_forget()
        else:
            self.empty_hint.place(relx=0.04, rely=0.08)

    def _on_pick(self, _e=None) -> None:
        sel = self.listbox.curselection()
        if not sel:
            return
        k = sel[0] // 2
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(2 * k, 2 * k + 1)
        it = self._items[k]
        if self.doc and self.doc.path and Path(self.doc.path) == Path(it["path"]):
            return
        self.save_now()
        try:
            self._show_doc(docs.load(it["path"]))
        except Exception as exc:  # noqa: BLE001
            self._say(_t("Не открылся: {0}").format(exc), AMBER)

    def new_doc(self) -> None:
        self.save_now()
        self._show_doc(docs.Document())
        self.listbox.selection_clear(0, tk.END)
        self.title_entry.focus_set()
        self._say(_t("Новый документ — пишите, всё сохранится само"), GREEN)

    def _remove(self) -> None:
        if not (self.doc and self.doc.path):
            return
        from tkinter import messagebox
        if not messagebox.askyesno(_t("ДОКУМЕНТЫ"), _t("Убрать документ в корзину (папка .trash)?"), parent=self):
            return
        self._cancel_save()
        docs.remove_to_trash(self.doc.path)
        self._show_doc(None)
        self.refresh()

    def _open_folder(self) -> None:
        shots.open_file(docs.docs_dir())

    # -- редактор ------------------------------------------------------------------
    def _show_doc(self, doc) -> None:
        if self.tts is not None:
            self.read_stop()
        self._loading = True
        self.doc = doc
        self._photos.clear()
        self._widths.clear()
        self.text.delete("1.0", tk.END)
        self.title_var.set(doc.title if doc else "")
        if doc:
            for seg in doc.segments:
                if "t" in seg:
                    self.text.insert(tk.END, seg["t"])
                elif seg.get("img") in doc.images:
                    self._put_image(seg["img"], int(seg.get("w") or 0), tk.END)
        self.text.edit_reset()
        self.text.edit_modified(False)
        self._loading = False
        self.highlight()
        self._update_status()

    def _ensure_doc(self) -> docs.Document:
        if self.doc is None:
            self.doc = docs.Document()
        return self.doc

    def _photo(self, name: str, width: int):
        try:
            from PIL import Image, ImageTk
        except Exception:  # noqa: BLE001
            return None
        img = Image.open(io.BytesIO(self.doc.images[name]))
        if width and width < img.width:
            img = img.resize((width, max(1, round(img.height * width / img.width))), Image.LANCZOS)
        return ImageTk.PhotoImage(img, master=self)

    def _put_image(self, name: str, width: int, index) -> None:
        photo = self._photo(name, width)
        if photo is None:
            self.text.insert(index, f"[{name}]")
            return
        self._photos[name] = photo
        self._widths[name] = width
        self.text.image_create(index, image=photo, name=name, padx=2, pady=4)

    def insert_image(self, img) -> None:
        """PIL-картинка в позицию курсора (снимок, буфер, файл)."""
        doc = self._ensure_doc()
        name = doc.add_image(docs.image_bytes(img))
        self._put_image(name, min(img.width, px(IMG_WIDTH)), tk.INSERT)
        self.text.insert(tk.INSERT, "\n")
        self._changed()

    def paste_shot(self) -> None:
        img = compose.clipboard_image()
        if img is None:
            self._say(_t("В буфере нет картинки: сделайте снимок (Win+Shift+S) и нажмите ещё раз"), AMBER)
            return
        self.insert_image(img)

    def screen_shot(self) -> None:
        """СКРИН: окно программы прячется, снимается экран, снимок встаёт в документ."""
        top = self.winfo_toplevel()
        top.iconify()

        def grab():
            try:
                img = shots.grab_screen()
            finally:
                top.deiconify()
                top.lift()
                self.text.focus_set()
            if img is None:
                self._say(_t(compose.NO_PILLOW), AMBER)
            else:
                self.insert_image(img)
        self.after(450, grab)

    def image_menu(self) -> None:
        m = tk.Menu(self, tearoff=0, bg=PANEL, fg=TEXT, activebackground=CYAN)
        m.add_command(label=_t("Снимок из буфера (Ctrl+V)"), command=self.paste_shot)
        m.add_command(label=_t("Скрин экрана"), command=self.screen_shot)
        m.add_command(label=_t("Файл…"), command=self.pick_images)
        b = self.img_btn
        m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

    def pick_images(self) -> None:
        names = compose.pick_image_files(self, _t("Картинки в документ"))
        try:
            from PIL import Image
        except Exception:  # noqa: BLE001
            self._say(_t(compose.NO_PILLOW), AMBER)
            return
        for p in compose.image_paths(names):
            try:
                with Image.open(p) as im:
                    self.insert_image(im.convert("RGB") if im.mode not in ("RGB", "RGBA") else im.copy())
            except Exception as exc:  # noqa: BLE001
                self._say(_t("Не открылся: {0}").format(exc), AMBER)

    def _on_paste(self, _e=None):
        img = compose.clipboard_image()
        if img is not None:
            self.insert_image(img)
            return "break"
        return None            # обычный текст — стандартная вставка Tk

    def insert_dictation(self, text: str) -> None:
        before = self.text.get("insert-1c", "insert")
        if before and not before.isspace():
            text = " " + text
        self.text.insert(tk.INSERT, text)
        self.text.see(tk.INSERT)
        self._changed()

    # картинка под мышью: меню размеров, двойной клик — открыть
    def _image_at(self, e) -> str | None:
        idx = self.text.index(f"@{e.x},{e.y}")
        for key, value, _i in self.text.dump(idx, image=True):
            if key == "image":
                return re.sub(r"#\d+$", "", value)
        return None

    def _image_menu(self, e) -> None:
        name = self._image_at(e)
        if not name or not self.doc:
            return None
        m = tk.Menu(self, tearoff=0, bg=PANEL, fg=TEXT, activebackground=CYAN)
        for pct in SIZES:
            m.add_command(label=_t("Размер {0}%").format(pct), command=lambda p=pct, n=name: self._resize(n, p))
        m.add_separator()
        m.add_command(label=_t("Открыть"), command=lambda n=name: self._open_image(n))
        m.tk_popup(e.x_root, e.y_root)
        return "break"

    def _resize(self, name: str, pct: int) -> None:
        try:
            from PIL import Image
            full = Image.open(io.BytesIO(self.doc.images[name])).width
        except Exception:  # noqa: BLE001
            return
        width = max(px(40), round(full * pct / 100))
        photo = self._photo(name, width)
        for key, value, idx in self.text.dump("1.0", tk.END, image=True):
            if key == "image" and re.sub(r"#\d+$", "", value) == name:
                self.text.image_configure(idx, image=photo)
        self._photos[name] = photo
        self._widths[name] = width
        self._changed()

    def _open_image_at(self, e):
        name = self._image_at(e)
        if name:
            self._open_image(name)
            return "break"
        return None

    def _open_image(self, name: str) -> None:
        tmp = docs.docs_dir() / ".view"
        tmp.mkdir(exist_ok=True)
        p = tmp / Path(name).name
        p.write_bytes(self.doc.images[name])
        compose.open_image(self, str(p))

    # -- сохранение -------------------------------------------------------------------
    def segments(self) -> list[dict]:
        out: list[dict] = []
        for key, value, _idx in self.text.dump("1.0", "end-1c", text=True, image=True):
            if key == "text":
                if out and "t" in out[-1]:
                    out[-1]["t"] += value
                else:
                    out.append({"t": value})
            elif key == "image":
                name = re.sub(r"#\d+$", "", value)
                out.append({"img": name, "w": self._widths.get(name, 0)})
        return out

    def _on_modified(self, _e=None) -> None:
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self.schedule_highlight()
            self._changed()

    def _changed(self) -> None:
        if self._loading:
            return
        self._cancel_save()
        self._save_job = self.after(AUTOSAVE_MS, self.save_now)
        self._say(_t("правка…"), MUTED)

    def _cancel_save(self) -> None:
        if self._save_job is not None:
            self.after_cancel(self._save_job)
            self._save_job = None

    def save_now(self) -> None:
        self._cancel_save()
        segs = self.segments()
        title = self.title_var.get()
        if self.doc is None and not title.strip() and not "".join(s.get("t", "") for s in segs).strip():
            return
        doc = self._ensure_doc()
        if doc.path is None and not title.strip() and not any(s.get("t", "").strip() or "img" in s for s in segs):
            return             # пустой новый документ не плодим
        doc.title, doc.segments = title, segs
        try:
            docs.save(doc)
        except OSError as exc:
            self._say(_t("Не сохранилось: {0}").format(exc), AMBER)
            return
        self.refresh()
        self._update_status(saved=True)

    def _update_status(self, saved: bool = False) -> None:
        if self.doc is None:
            self._say(_t("Выберите документ или создайте новый"), MUTED)
            return
        words = len(self.text.get("1.0", "end-1c").split())
        line = _t("{0} слов").format(words)
        if saved:
            line += " · " + _t("сохранено {0}").format(time.strftime("%H:%M:%S"))
        self._say(line, GREEN if saved else MUTED)

    # -- просмотр: готовый документ страницей, только чтение ------------------------
    def preview(self) -> None:
        self.save_now()
        if not self.doc:
            self._say(_t("Выберите документ или создайте новый"), MUTED)
            return
        DocPreview(self, self.doc, self._widths)

    def save_pdf(self) -> None:
        self.save_now()
        if not self.doc:
            return
        if not docs.pdf_available():
            self._say(_t("PDF: нужна библиотека fpdf2 (pip install fpdf2)"), AMBER)
            return
        from tkinter import filedialog
        name = docs._safe_name(self.doc.display_title())
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".pdf", initialfile=f"{name}.pdf",
                                            filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            docs.export_pdf(self.doc, Path(path))
        except Exception as exc:  # noqa: BLE001
            self._say(_t("Не сохранилось: {0}").format(exc), AMBER)
            return
        self._say(_t("Экспорт: {0}").format(path), GREEN)
        shots.open_file(Path(path))

    # -- экспорт -------------------------------------------------------------------------
    def _export_menu(self) -> None:
        m = tk.Menu(self, tearoff=0, bg=PANEL, fg=TEXT, activebackground=CYAN)
        m.add_command(label="Word (.docx)", command=lambda: self._export("docx"))
        m.add_command(label="Markdown (.md)", command=lambda: self._export("md"))
        m.add_command(label="HTML", command=lambda: self._export("html"))
        m.add_command(label=_t("TXT (без разметки)"), command=lambda: self._export("txt"))
        m.add_separator()
        m.add_command(label=_t("Открыть .md…"), command=self.import_md)
        x = self.export_btn.winfo_rootx()
        y = self.export_btn.winfo_rooty() + self.export_btn.winfo_height()
        m.tk_popup(x, y)

    def _export(self, kind: str) -> None:
        self.save_now()
        if not self.doc:
            return
        from tkinter import filedialog
        name = docs._safe_name(self.doc.display_title())
        path = filedialog.asksaveasfilename(parent=self, defaultextension=f".{kind}",
                                            initialfile=f"{name}.{kind}",
                                            filetypes=[(kind.upper(), f"*.{kind}")])
        if not path:
            return
        fn = {"html": docs.export_html, "txt": docs.export_txt, "md": docs.export_md,
              "docx": docs.export_docx}[kind]
        try:
            fn(self.doc, Path(path))
        except Exception as exc:  # noqa: BLE001
            self._say(_t("Не сохранилось: {0}").format(exc), AMBER)
            return
        self._say(_t("Экспорт: {0}").format(path), GREEN)

    def import_md(self) -> None:
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self, filetypes=[("Markdown", "*.md *.markdown *.txt")])
        if not path:
            return
        self.save_now()
        try:
            doc = docs.import_md(Path(path))
        except Exception as exc:  # noqa: BLE001
            self._say(_t("Не открылся: {0}").format(exc), AMBER)
            return
        docs.save(doc)
        self._show_doc(doc)
        self.refresh()
        self._say(_t("Импорт: {0}").format(Path(path).name), GREEN)

    # -- письмо ------------------------------------------------------------------------
    def send_mail(self) -> None:
        """Письмо с документом (.docx) во вложении — окно почтовой программы, отправляет пилот."""
        self.save_now()
        if not self.doc:
            self._say(_t("Выберите документ или создайте новый"), MUTED)
            return
        out = docs.docs_dir() / ".send"
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{docs._safe_name(self.doc.display_title())}.docx"
        try:
            docs.export_docx(self.doc, path)
        except Exception as exc:  # noqa: BLE001
            self._say(_t("Не сохранилось: {0}").format(exc), AMBER)
            return
        how = mailer.send_file(path, self.doc.display_title(), _t("Документ во вложении."))
        if how == "mailto":
            self._say(_t("Почтовая программа без вложений: файл в открытой папке — перетащите его в письмо"), AMBER)
        elif how == "cancel":
            self._say(_t("Письмо не отправлено"), MUTED)
        else:
            self._say(_t("Письмо готово — проверьте и отправьте"), GREEN)

    # -- справка в левой панели ------------------------------------------------------
    def toggle_help(self, show: bool | None = None) -> None:
        show = not getattr(self, "_help_on", False) if show is None else show
        refocus = getattr(self, "_focus", None) is not None
        if refocus:
            self.toggle_focus(False)
        self._help_on = show
        if show:
            self.list_view.pack_forget()
            self.help_view.pack(fill=tk.BOTH, expand=True)
            self.left_panel.title = _t("СПРАВКА · ОФОРМЛЕНИЕ")
        else:
            self.help_view.pack_forget()
            self.list_view.pack(fill=tk.BOTH, expand=True)
            self.left_panel.title = _t("МОИ ДОКУМЕНТЫ")
        try:
            self.left_panel._draw()
        except Exception:  # noqa: BLE001
            pass
        self.fmt_buttons["help"].set_active(show)
        if refocus:
            self.toggle_focus(True)     # справка открыта/закрыта — фокус пересобираем
        self.text.focus_set()

    def update_empty_hint(self) -> None:
        if self.text.get("1.0", "end-1c").strip() or self.text.dump("1.0", "end", image=True):
            self.text_hint.place_forget()
        else:
            self.text_hint.place(x=px(32), y=px(18))

    # -- голос --------------------------------------------------------------------------
    def _tick_mic(self) -> None:
        try:
            self.mic.poll()
            self.poll_tools()
        finally:
            self.after(160, self._tick_mic)

    def _mic_status(self, text: str, color=None) -> None:
        self.mic_hint.config(text=text, fg=color or MUTED)

    def _say(self, text: str, color=None) -> None:
        self.status.config(text=text, fg=color or MUTED)


class DocPreview(tk.Toplevel):
    """Полноэкранный просмотр: белый «лист» по центру, только чтение. Esc — закрыть."""

    PAGE_BG, INK = "#fbfaf6", "#1d1d1f"

    def __init__(self, master, doc, widths: dict) -> None:
        super().__init__(master, bg="#2a2c31")
        self.title(doc.display_title() or _t("ПРОСМОТР"))
        try:
            self.attributes("-fullscreen", True)
        except tk.TclError:
            self.state("zoomed")
        self._photos: list = []
        bar = tk.Frame(self, bg="#2a2c31")
        bar.pack(fill=tk.X, padx=px(14), pady=px(6))
        tk.Label(bar, text=_t("ПРОСМОТР · Esc — закрыть"), bg="#2a2c31", fg="#b8bcc6",
                 font=theme.font(9)).pack(side=tk.LEFT)
        HudButton(bar, "✕", self.destroy, height=28, width=36, font_size=10).pack(side=tk.RIGHT)
        page = tk.Frame(self, bg=self.PAGE_BG, highlightthickness=1, highlightbackground="#55585f")
        page.pack(fill=tk.Y, expand=True, pady=(0, px(14)))
        sb = make_vscroll(page)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        txt = tk.Text(page, wrap=tk.WORD, width=78, bg=self.PAGE_BG, fg=self.INK, relief=tk.FLAT, bd=0,
                      font=("Georgia", 12), padx=px(48), pady=px(36), spacing1=2, spacing3=4,
                      highlightthickness=0, cursor="arrow", yscrollcommand=sb.set)
        txt.pack(side=tk.LEFT, fill=tk.Y)
        sb.config(command=txt.yview)
        txt.tag_configure("title", font=("Georgia", 20, "bold"), spacing3=px(14))
        txt.tag_configure("h1", font=("Georgia", 17, "bold"), spacing1=px(10), spacing3=px(6))
        txt.tag_configure("h2", font=("Georgia", 14, "bold"), spacing1=px(8), spacing3=px(4))
        txt.tag_configure("b", font=("Georgia", 12, "bold"))
        txt.tag_configure("i", font=("Georgia", 12, "italic"))
        txt.tag_configure("bi", font=("Georgia", 12, "bold italic"))
        txt.tag_configure("u", underline=True)
        txt.tag_configure("code", font=("Consolas", 11), background="#ecebe6")
        txt.tag_configure("link", foreground="#1f5fbf", underline=True)
        txt.tag_configure("quote", foreground="#55585f", lmargin1=px(22), lmargin2=px(22),
                          font=("Georgia", 12, "italic"))
        txt.tag_configure("li", lmargin1=px(10), lmargin2=px(24))
        for tg in ("b", "i", "bi", "code"):
            txt.tag_raise(tg)
        if doc.title.strip():
            txt.insert(tk.END, doc.title.strip() + "\n", "title")
        try:
            from PIL import Image, ImageTk
        except Exception:  # noqa: BLE001
            Image = None
        for seg in doc.segments:
            if "t" in seg:
                from stamina import mdlite
                paras = mdlite.paragraphs(seg["t"])
                for n, (kind, rs) in enumerate(paras):
                    for t, st, _url in rs:
                        tags = [kind] + [x for x in st]
                        if "b" in st and "i" in st:
                            tags.append("bi")
                        txt.insert(tk.END, t, tuple(tags))
                    if n < len(paras) - 1:
                        txt.insert(tk.END, "\n", (kind,))
            elif Image is not None and seg.get("img") in doc.images:
                im = Image.open(io.BytesIO(doc.images[seg["img"]]))
                w = int(widths.get(seg["img"]) or seg.get("w") or im.width)
                if w < im.width:
                    im = im.resize((w, max(1, round(im.height * w / im.width))), Image.LANCZOS)
                ph = ImageTk.PhotoImage(im, master=self)
                self._photos.append(ph)
                txt.image_create(tk.END, image=ph, pady=4)
        txt.config(state=tk.DISABLED)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<MouseWheel>", lambda e: txt.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.focus_set()
