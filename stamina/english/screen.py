"""Вкладка «АНГЛИЙСКИЙ» внутри Star Typing: подразделы, общий контекст, горячие клавиши."""
from __future__ import annotations

from stamina.i18n import t

import tkinter as tk
from tkinter import simpledialog

from stamina import theme
from stamina.hud import HudButton
import time
from tkinter import font as tkfont

from stamina.theme import AMBER, BG, BG2, CYAN, GREEN, LINE_HI, MUTED, PANEL, RED, TEXT, px

from . import paths
from .asr import ASR
from .progress import Progress
from .tts import TTS
from .ui import L, entry
from .vocab import Vocab

SUBPAGES = [("overview", t("ОБЗОР")), ("sets", t("ЗВЁЗДНЫЕ КАРТЫ")), ("scanner", t("СКАНЕР")),
            ("practice", t("МИССИИ")), ("review", t("ПРОВЕРКА СИСТЕМ")), ("lists", t("ОТСЕКИ")),
            ("log", t("ЖУРНАЛ")), ("settings", t("НАСТРОЙКИ"))]


class EnglishScreen(tk.Frame):
    TITLE = t("АНГЛИЙСКИЙ")

    def __init__(self, master, app) -> None:
        super().__init__(master, bg=BG)
        self.app = app
        self.vocab = Vocab()
        self.progress = Progress(app=app)
        self.progress.dict_tr = lambda slug: (self.vocab.get(slug) or {}).get("ru") or ""
        self.progress.on_change.append(self._on_progress_event)
        self.tts = TTS()
        self.asr = ASR()
        self.current = None
        self._built = False
        self._search_pop = None
        self._loading = L(self, t("ЗАГРУЗКА СЛОВАРЯ…"), fg=CYAN, size=14, bold=True, bg=BG)
        self._loading.place(relx=0.5, rely=0.4, anchor="center")
        self.vocab.load_async()
        self.after(150, self._wait_vocab)

    def _wait_vocab(self) -> None:  # опрос из главного потока (Tk не любит вызовы из других потоков)
        if self.vocab.ready:
            self._on_loaded()
        else:
            self.after(150, self._wait_vocab)

    # -- сборка после загрузки словаря --------------------------------------------
    def _on_loaded(self) -> None:
        self._loading.destroy()
        if self.vocab.error or not self.vocab.words:
            L(self, t("Словарь не загрузился: {0}\nОжидается файл {1}").format(self.vocab.error or 'пустой файл', paths.VOCAB_PATH), fg=AMBER, size=11, bg=BG,
              justify="left").place(relx=0.5, rely=0.4, anchor="center")
            return
        self._build()

    def _build(self) -> None:
        from .pages_learn import PracticePage, ReviewPage
        from .pages_main import OverviewPage, ScannerPage, SetsPage
        from .pages_misc import ListsPage, LogPage, SettingsPage
        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(12), pady=(px(8), px(2)))
        self.nav: dict[str, HudButton] = {}
        for name, title in SUBPAGES:
            b = HudButton(top, title, lambda n=name: self.show(n), height=30, font_size=9)
            b.pack(side=tk.LEFT, padx=px(2))
            self.nav[name] = b
        sbox = tk.Frame(top, bg=BG)
        sbox.pack(side=tk.RIGHT)
        L(sbox, "⌕", fg=CYAN, size=13, bold=True, bg=BG).pack(side=tk.LEFT, padx=(0, px(4)))
        self.search = entry(sbox, width=22, size=10)
        self.search.pack(side=tk.LEFT, ipady=px(4))
        self._ph = t("СКАНИРОВАТЬ СЛОВО…")
        self._placeholder(True)
        self.search.bind("<FocusIn>", lambda _e: self._placeholder(False))
        self.search.bind("<FocusOut>", lambda _e: (self._placeholder(True), self.after(200, self._close_pop)))
        self.search.bind("<KeyRelease>", self._on_search)
        self.search.bind("<Return>", self._search_enter)
        self.search.bind("<Escape>", lambda _e: (self._close_pop(), self.focus_set()))
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill=tk.BOTH, expand=True)
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(0, weight=1)
        self.pages = {
            "overview": OverviewPage(self.body, self), "sets": SetsPage(self.body, self),
            "scanner": ScannerPage(self.body, self), "practice": PracticePage(self.body, self),
            "review": ReviewPage(self.body, self), "lists": ListsPage(self.body, self),
            "log": LogPage(self.body, self), "settings": SettingsPage(self.body, self),
        }
        for p in self.pages.values():
            p.grid(row=0, column=0, sticky="nsew")
        self._built = True
        self.tts.warm_up()
        if self.progress.settings.get("asr", True):
            self.asr.load_async()
        self.show("overview")

    # -- навигация ------------------------------------------------------------------
    def show(self, name: str) -> None:
        if not self._built:
            return
        self.current = name
        page = self.pages[name]
        if hasattr(page, "refresh"):
            page.refresh()
        page.tkraise()
        for n, b in self.nav.items():
            b.set_active(n == name)
        self._update_nav()

    def refresh(self) -> None:  # вызывается Star Typing при открытии вкладки
        if self._built and self.current:
            self.show(self.current)

    def _update_nav(self) -> None:
        due = len(self.progress.due_cards())
        self.nav["review"].set_text(t("ПРОВЕРКА СИСТЕМ ({0})").format(due) if due else t("ПРОВЕРКА СИСТЕМ"))

    def changed(self) -> None:
        self._update_nav()

    def open_word(self, slug: str) -> None:
        if self.vocab.get(slug):
            self.pages["scanner"].set_word(slug, back=self.current if self.current != "scanner" else None)
            self.show("scanner")

    def start_session(self, mode: str, source: str = "set", single: str | None = None, ids=None) -> None:
        self.pages["practice"].start(mode, source=source, single=single, ids=ids)
        self.show("practice")

    def start_review(self, slugs: list[str] | None = None) -> None:
        self.pages["review"].start(slugs)
        self.show("review")

    # -- озвучка с индикацией на кнопке ------------------------------------------------
    SPEAK_LABEL, ERR_LABEL = t("▶ ЧИТАЕТ…"), t("ОШИБКА ЗВУКА")

    def audio_button(self, parent, label: str, text_fn, slow: bool = False, **kw) -> HudButton:
        """Кнопка озвучки: при нажатии светится и пишет «▶ ЧИТАЕТ…», пока голос не договорит."""
        b = HudButton(parent, label, None, **kw)
        b.command = lambda: self.say(text_fn(), slow=slow, btn=b)
        return b

    def say(self, text: str, slow: bool = False, btn: HudButton | None = None) -> None:
        if not text:
            return
        rate = int(self.progress.settings.get("rate", 0))
        if not hasattr(self, "_tts_btns"):
            self._tts_btns: dict[int, tuple] = {}
            self._tts_polling = False
        sid = self.tts.speak(text, rate - 4 if slow else rate)
        self._tts_until = time.time() + 12  # ловим ошибки и без кнопки (озвучка с клавиатуры)
        if btn is not None and sid:
            for k, (b, *_r) in list(self._tts_btns.items()):
                if b is btn:  # повторное нажатие той же кнопки — старая фраза будет отменена
                    self._tts_btns.pop(k)
                    self._btn_restore(b)
            self._btn_light(btn)
            self._tts_btns[sid] = (btn, time.time(), False)
        elif btn is not None:
            self._tts_btns[0] = (btn, time.time(), False)
        if not self._tts_polling:
            self._tts_polling = True
            self.after(60, self._tts_poll)

    def _btn_light(self, b: HudButton) -> None:
        if not hasattr(b, "_orig"):
            b._orig = (b._text, b.color)  # type: ignore[attr-defined]
        need = tkfont.Font(font=b._font).measure(self.SPEAK_LABEL) + px(30)
        if b.winfo_reqwidth() < need:
            b.configure(width=need)
        b.set_text(self.SPEAK_LABEL)
        b.set_color(AMBER)
        b.set_active(True)

    def _btn_restore(self, b: HudButton) -> None:
        try:
            if not b.winfo_exists():
                return
            text, color = getattr(b, "_orig", (b._text, b.color))
            b.set_text(text)
            b.set_color(color)
            b.set_active(False)
        except tk.TclError:
            pass

    def _btn_error(self, b: HudButton | None, msg: str) -> None:
        self.status(t("ОШИБКА ЗВУКА: {0}").format(msg), RED)
        self.sfx("error")
        if b is None:
            return
        try:
            if not hasattr(b, "_orig"):
                b._orig = (b._text, b.color)  # type: ignore[attr-defined]
            b.set_text(self.ERR_LABEL)
            b.set_color(RED)
            b.set_active(True)
            self.after(2200, lambda: self._btn_restore(b))
        except tk.TclError:
            pass

    def _tts_poll(self) -> None:
        for kind, sid, msg in self.tts.poll():
            if kind == "start":
                ent = self._tts_btns.get(sid)
                if ent:
                    self._tts_btns[sid] = (ent[0], ent[1], True)
            elif kind in ("done", "cancel"):
                ent = self._tts_btns.pop(sid, None)
                if ent:
                    self._btn_restore(ent[0])
            elif kind in ("error", "dead"):
                targets = [sid] if sid in self._tts_btns else list(self._tts_btns) if kind == "dead" or sid == 0 else []
                if not targets:
                    self._btn_error(None, msg)
                for k in targets:
                    self._btn_error(self._tts_btns.pop(k)[0], msg)
        now = time.time()
        for k, (b, t0, started) in list(self._tts_btns.items()):
            if not started and now - t0 > 10:  # голос так и не начал говорить
                self._tts_btns.pop(k)
                self._btn_error(b, self.tts.last_error or t("голос Windows не ответил за 10 с"))
            elif started and now - t0 > 120:
                self._tts_btns.pop(k)
                self._btn_restore(b)
        if self._tts_btns or time.time() < getattr(self, "_tts_until", 0):
            self.after(80, self._tts_poll)
        else:
            self._tts_polling = False

    def status(self, text: str, color=MUTED) -> None:
        try:
            self.app.set_status(text, color)
        except Exception:
            pass

    def sfx(self, name: str) -> None:
        try:
            getattr(self.app.sound, name)()
        except Exception:
            pass

    def _on_progress_event(self, kind, name, bonus) -> None:
        if kind == "achievement":
            self.status(t("★ НОВЫЙ ЗНАК ОТЛИЧИЯ: «{0}»  +{1} XP").format(name, bonus), AMBER)
            self.sfx("bell")

    # -- меню «В отсек» ---------------------------------------------------------------
    def list_menu(self, widget, slug: str, event=None, after=None) -> None:
        m = tk.Menu(self, tearoff=0, bg=PANEL, fg=TEXT, activebackground=LINE_HI, activeforeground=CYAN,
                    font=theme.font(10))
        cur = set(self.progress.lists_of(slug))
        for l in self.progress.lists:
            mark = "✓ " if l["id"] in cur else "   "
            m.add_command(label=f"{mark}{l['name']}  ({len(l['slugs'])})",
                          command=lambda lid=l["id"]: self._toggle_list(lid, slug, after))
        m.add_separator()
        m.add_command(label=t("+ Новый отсек…"), command=lambda: self._new_list(slug, after))
        x = event.x_root if event else widget.winfo_rootx() + 10
        y = event.y_root if event else widget.winfo_rooty() + widget.winfo_height()
        try:
            m.tk_popup(x, y)
        finally:
            m.grab_release()

    def _toggle_list(self, lid, slug, after) -> None:
        added = self.progress.toggle_in_list(lid, slug)
        name = self.progress.list_by_id(lid)["name"]
        self.status(t("«{0}» {1} отсек «{2}»").format(slug, 'добавлено в' if added else 'убрано из', name), CYAN)
        if after:
            after()

    def _new_list(self, slug, after) -> None:
        name = simpledialog.askstring(t("Новый отсек"), t("Название отсека:"), parent=self)
        if name:
            l = self.progress.create_list(name)
            self._toggle_list(l["id"], slug, after)

    # -- поиск -------------------------------------------------------------------------
    def _placeholder(self, on: bool) -> None:
        cur = self.search.get()
        if on and not cur:
            self.search.insert(0, self._ph)
            self.search.configure(fg=MUTED)
        elif not on and cur == self._ph:
            self.search.delete(0, tk.END)
            self.search.configure(fg=TEXT)

    def _on_search(self, e) -> None:
        if e.keysym in ("Return", "Escape", "Down", "Up"):
            return
        q = self.search.get()
        if q == self._ph:
            return
        self._close_pop()
        res = self.vocab.search(q, extra=self.progress.tr)
        if not res:
            return
        pop = tk.Frame(self, bg=LINE_HI, padx=1, pady=1)
        inner = tk.Frame(pop, bg=PANEL)
        inner.pack(fill=tk.BOTH)
        for w in res:
            row = tk.Frame(inner, bg=PANEL, cursor="hand2")
            row.pack(fill=tk.X)
            a = L(row, w["word"], fg=TEXT, size=11, bold=True, bg=PANEL)
            a.pack(side=tk.LEFT, padx=px(8), pady=px(3))
            b = L(row, f"{w['pos']}  #{w['rank']}", fg=MUTED, size=8, bg=PANEL)
            b.pack(side=tk.RIGHT, padx=px(8))
            for x in (row, a, b):
                x.bind("<Button-1>", lambda _e, s=w["slug"]: self._pick(s))
                x.bind("<Enter>", lambda _e, r=row: [c.configure(bg=BG2) for c in [r, *r.winfo_children()]])
                x.bind("<Leave>", lambda _e, r=row: [c.configure(bg=PANEL) for c in [r, *r.winfo_children()]])
        self.update_idletasks()
        x = self.search.winfo_rootx() - self.winfo_rootx() - px(20)
        y = self.search.winfo_rooty() - self.winfo_rooty() + self.search.winfo_height() + px(2)
        pop.place(x=x, y=y, width=px(300))
        pop.lift()
        self._search_pop = pop
        self._search_res = res

    def _search_enter(self, _e) -> None:
        res = getattr(self, "_search_res", None) or self.vocab.search(self.search.get())
        if res:
            self._pick(res[0]["slug"])

    def _pick(self, slug: str) -> None:
        self._close_pop()
        self.search.delete(0, tk.END)
        self.focus_set()
        self.open_word(slug)

    def _close_pop(self) -> None:
        if self._search_pop is not None:
            self._search_pop.destroy()
            self._search_pop = None

    # -- клавиши (Star Typing передаёт сюда события, когда открыта вкладка) ---------------
    def on_key(self, e) -> None:
        if not self._built:
            return
        if isinstance(e.widget, tk.Entry):
            return
        page = self.pages.get(self.current)
        if page is not None and hasattr(page, "on_key"):
            page.on_key(e)

    def close(self) -> None:
        self.progress.save()
        self.tts.close()
        self.asr.stop()
