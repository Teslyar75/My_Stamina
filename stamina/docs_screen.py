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

from stamina import compose, docs, shots, theme
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


class DocsScreen(tk.Frame):
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

        body = tk.Frame(self, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=px(14), pady=(0, px(10)))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # -- список
        left = HudPanel(body, title=_t("МОИ ДОКУМЕНТЫ"))
        left.grid(row=0, column=0, sticky="nsew", padx=(0, px(10)))
        lb = left.body
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
        rb = right.body
        self.title_var = tk.StringVar()
        self.title_entry = tk.Entry(rb, textvariable=self.title_var, bg=theme.BG2, fg=TEXT,
                                    insertbackground=CYAN, relief=tk.FLAT, font=theme.font(13, True),
                                    highlightthickness=1, highlightbackground=LINE, highlightcolor=CYAN)
        self.title_entry.pack(fill=tk.X, pady=(0, px(6)), ipady=px(3))
        self.title_var.trace_add("write", lambda *_a: self._changed())

        bar = tk.Frame(rb, bg=PANEL)
        bar.pack(fill=tk.X, pady=(0, px(6)))
        # Две группы: «вставить» слева и «выдать» справа. На узком окне (1024)
        # правая группа уходит второй строкой, чтобы ни одна кнопка не обрезалась.
        ins = tk.Frame(bar, bg=PANEL)
        out = tk.Frame(bar, bg=PANEL)
        ins.grid(row=0, column=0, sticky="w")
        bar.grid_columnconfigure(1, weight=1)
        HudButton(ins, _t("СНИМОК"), self.paste_shot, height=30, font_size=9,
                  color=CYAN).pack(side=tk.LEFT)
        HudButton(ins, _t("СКРИН"), self.screen_shot, height=30, font_size=9,
                  color=CYAN).pack(side=tk.LEFT, padx=(px(6), 0))
        HudButton(ins, _t("КАРТИНКА…"), self.pick_images, height=30, font_size=9,
                  color=CYAN).pack(side=tk.LEFT, padx=(px(6), 0))
        store = getattr(self.app, "store", None)
        self.mic = MicControl(ins, on_text=self.insert_dictation, on_status=self._mic_status,
                              label=_t("ДИКТОВКА F9"), height=30, font_size=9,
                              settings=getattr(store, "settings", None),
                              save=getattr(store, "save_settings", None))
        self.mic.button.pack(side=tk.LEFT, padx=(px(6), 0))
        self.export_btn = HudButton(out, _t("ЭКСПОРТ"), self._export_menu, height=30, font_size=9,
                                    color=AMBER)
        self.export_btn.pack(side=tk.RIGHT)
        HudButton(out, "PDF", self.save_pdf, height=30, font_size=9,
                  color=AMBER).pack(side=tk.RIGHT, padx=(0, px(6)))
        HudButton(out, _t("ПРОСМОТР"), self.preview, height=30, font_size=9,
                  color=GREEN).pack(side=tk.RIGHT, padx=(0, px(6)))
        self._bar_wrapped = None

        def _reflow(_e=None):
            need = ins.winfo_reqwidth() + out.winfo_reqwidth() + px(12)
            wrap_now = bar.winfo_width() < need
            if wrap_now == self._bar_wrapped:
                return
            self._bar_wrapped = wrap_now
            if wrap_now:
                out.grid(row=1, column=0, columnspan=2, sticky="e", pady=(px(6), 0))
            else:
                out.grid(row=0, column=1, sticky="e", pady=0)
        out.grid(row=0, column=1, sticky="e")
        bar.bind("<Configure>", _reflow, add="+")

        self.mic_hint = _label(rb, "", fg=MUTED, size=8, bg=PANEL, anchor="w")
        self.mic_hint.pack(side=tk.BOTTOM, fill=tk.X)
        wrap = tk.Frame(rb, bg=PANEL)
        wrap.pack(fill=tk.BOTH, expand=True)
        tsb = make_vscroll(wrap)
        tsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text = tk.Text(wrap, wrap=tk.WORD, bg=theme.BG2, fg=TEXT, insertbackground=CYAN,
                            relief=tk.FLAT, font=theme.font(12), undo=True, padx=px(10), pady=px(8),
                            highlightthickness=0, yscrollcommand=tsb.set, spacing1=2, spacing3=2)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tsb.config(command=self.text.yview)
        self.text.bind("<<Modified>>", self._on_modified)
        self.text.bind("<<Paste>>", self._on_paste)
        self.text.bind("<Button-3>", self._image_menu)
        self.text.bind("<Double-Button-1>", self._open_image_at)

        self.after(160, self._tick_mic)
        self.refresh()
        self._show_doc(None)

    # -- для кокпита ------------------------------------------------------------
    def focus_input(self) -> None:
        self.refresh()
        self.text.focus_set()

    def on_key(self, _e) -> None:
        return None          # набор принадлежит редактору

    def on_leave(self) -> None:
        self.save_now()

    def dictate(self) -> None:
        """F9 в этом отсеке: начать/закончить диктовку."""
        self.text.focus_set()
        self.mic.toggle()

    # -- список ------------------------------------------------------------------
    def refresh(self) -> None:
        self._items = docs.list_docs()
        self.listbox.delete(0, tk.END)
        cur = self.doc.path if self.doc else None
        for i, it in enumerate(self._items):
            when = time.strftime("%d.%m %H:%M", time.localtime(it["modified"])) if it["modified"] else ""
            title = it["title"] or _t("Без названия")
            self.listbox.insert(tk.END, f"{title}  ·  {when}")
            if cur and Path(it["path"]) == Path(cur):
                self.listbox.selection_set(i)
        if self._items:
            self.empty_hint.place_forget()
        else:
            self.empty_hint.place(relx=0.04, rely=0.08)

    def _on_pick(self, _e=None) -> None:
        sel = self.listbox.curselection()
        if not sel:
            return
        it = self._items[sel[0]]
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
        m.add_command(label="HTML", command=lambda: self._export("html"))
        m.add_command(label="TXT", command=lambda: self._export("txt"))
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
        (docs.export_html if kind == "html" else docs.export_txt)(self.doc, Path(path))
        self._say(_t("Экспорт: {0}").format(path), GREEN)

    # -- голос --------------------------------------------------------------------------
    def _tick_mic(self) -> None:
        try:
            self.mic.poll()
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
        txt.tag_configure("h1", font=("Georgia", 20, "bold"), spacing3=px(14))
        if doc.title.strip():
            txt.insert(tk.END, doc.title.strip() + "\n", "h1")
        try:
            from PIL import Image, ImageTk
        except Exception:  # noqa: BLE001
            Image = None
        for seg in doc.segments:
            if "t" in seg:
                txt.insert(tk.END, seg["t"])
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
