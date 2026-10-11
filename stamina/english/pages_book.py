"""Раздел «ИЗ КНИГИ»: карточки предложений из прочитанного (RU → EN)."""
from __future__ import annotations

from stamina.i18n import t as _t

import tkinter as tk

from stamina import theme
from stamina.hud import HudButton, HudPanel
from stamina.theme import AMBER, BG, BG2, CYAN, GREEN, LINE, MUTED, PANEL, PANEL_HI, RED, TEXT, px

from . import book_sentences as bs
from . import sm2
from .mic import MicPanel
from .textutil import score_sentence, verdict
from .ui import L, MatchReadout, ScrollFrame, Strip

VCOL = {"green": GREEN, "amber": AMBER, "red": RED}


def _clear(frame) -> None:
    for c in frame.winfo_children():
        c.destroy()


class BookCardsPage(tk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.tid: str | None = None
        self.queue: list[dict] = []
        self.i = 0
        self.shown = False
        self.mode = "hub"  # hub | drill
        self._holding = False
        self._hint_grab: HudButton | None = None
        self._poll_after = None

        self.strip = Strip(self)
        self.strip.pack(fill=tk.X, padx=px(12), pady=(px(4), 0))
        self.panel = HudPanel(self, _t("ИЗ КНИГИ"))
        self.panel.pack(fill=tk.BOTH, expand=True, padx=px(40), pady=px(8))
        # HudPanel.body — Canvas: pack прямо в него глотает часть виджетов (карточка «исчезает»).
        self.body = tk.Frame(self.panel.body, bg=PANEL)
        self.body.pack(fill=tk.BOTH, expand=True)
        self.btns = tk.Frame(self, bg=BG)
        self.btns.pack(pady=(0, px(12)))

        self.mic: MicPanel | None = None
        self.match: MatchReadout | None = None
        self.fb: tk.Label | None = None
        self._face_lab: tk.Label | None = None
        self._face_ru = ""
        self._face_en = ""
        self._last_score: int | None = None

    # -- library / translator -------------------------------------------------
    def _lib(self):
        from stamina import library as libmod
        return libmod.Library()

    def _tr(self):
        try:
            return self.ctx.app.get_translator()
        except Exception:
            return None

    def _tl(self) -> str:
        return bs.uplink_tl(self.ctx.app)

    def _sync(self, *, request: bool = True) -> tuple[int, int]:
        lib = self._lib()
        books_n, sent_n = bs.sync_all(self.ctx.progress, lib)
        tr = self._tr()
        tl = self._tl()
        filled = bs.fill_ru_from_cache(self.ctx.progress, tr, tl)
        req = 0
        if request and tr is not None:
            req = bs.request_missing_ru(self.ctx.progress, tr, tl)
            if req:
                self._schedule_poll()
        if filled:
            self.ctx.status(_t("Подставлено переводов из кэша: {0}").format(filled), CYAN)
        return books_n, sent_n

    def _schedule_poll(self) -> None:
        if self._poll_after is not None:
            try:
                self.after_cancel(self._poll_after)
            except Exception:
                pass
        self._poll_after = self.after(400, self._poll_tr)

    def _poll_tr(self) -> None:
        self._poll_after = None
        tr = self._tr()
        if tr is None:
            return
        try:
            tr.poll()
        except Exception:
            pass
        n = bs.fill_ru_from_cache(self.ctx.progress, tr, self._tl())
        if n and self.mode == "hub":
            self.render()
            self.ctx.changed()
        if tr.inflight("book_cards") > 0:
            self._schedule_poll()
        elif n:
            self.ctx.status(_t("Переводы предложений обновлены"), GREEN)

    # -- navigation -----------------------------------------------------------
    def refresh(self) -> None:
        if self.mode == "hub":
            self._sync(request=True)
            self.render()
        elif self.mode == "drill" and not self.queue:
            self.mode = "hub"
            self.render()
        self.ctx.changed()

    def focus_book(self, tid: str | None = None) -> None:
        """Вход из читалки / обзора: синхронизация → хаб (или сразу практика книги)."""
        self.mode = "hub"
        self.queue = []
        self.i = 0
        self.shown = False
        self.tid = tid
        _books_n, sent_n = self._sync(request=True)
        if tid:
            # точечная синхронизация текущей книги (на случай если sync_all пропустил lang)
            try:
                book = bs.sync_book(self.ctx.progress, self._lib(), tid)
                if book:
                    sent_n = max(sent_n, len(book.get("sentences") or []))
                tr = self._tr()
                tl = self._tl()
                bs.fill_ru_from_cache(self.ctx.progress, tr, tl)
                bs.request_missing_ru(self.ctx.progress, tr, tl)
            except Exception:
                pass
        self.ctx.show("book")
        ready = (len(bs.ready_sentences(self.ctx.progress, tid)) if tid
                 else bs.count_ready(self.ctx.progress))
        if ready:
            self.ctx.status(
                _t("Из прочитанного: {0} предложений с переводом — можно практиковать").format(ready),
                GREEN)
        elif sent_n:
            self.ctx.status(
                _t("Собрано {0} предложений из прочитанного. Ждём перевод UPLINK…").format(sent_n),
                AMBER)
        else:
            self.ctx.status(
                _t("Пока нет прочитанного: откройте книгу и перелистните несколько страниц"),
                AMBER)
        self.render()
        self.ctx.changed()

    def open_book(self, tid: str) -> None:
        self.tid = tid
        self.start_drill(tid)

    def start_drill(self, tid: str | None = None, *, due_only: bool = True) -> None:
        self._sync(request=True)
        self.tid = tid
        self.queue = bs.build_queue(self.ctx.progress, tid, due_only=due_only, limit=50)
        if not self.queue and due_only:
            self.queue = bs.build_queue(self.ctx.progress, tid, due_only=False, limit=50)
        self.i = 0
        self.shown = False
        self._last_score = None
        self.mode = "drill" if self.queue else "hub"
        if not self.queue:
            self.ctx.status(_t("Нет предложений с переводом — почитайте книгу или подождите UPLINK"), AMBER)
        self.render()

    def back_hub(self) -> None:
        self.mode = "hub"
        self.queue = []
        self.i = 0
        self.shown = False
        self._last_score = None
        self.render()

    # -- render ---------------------------------------------------------------
    def render(self) -> None:
        self._release_hint_grab()
        self._holding = False
        _clear(self.body)
        _clear(self.btns)
        self.mic = self.match = self.fb = self._face_lab = None
        try:
            if self.mode == "drill":
                self._render_drill()
            else:
                self._render_hub()
        except Exception as e:
            L(self.body, _t("Ошибка показа карточки: {0}").format(e), fg=AMBER, size=12,
              wraplength=px(700), justify="left").pack(anchor="w", pady=px(20), padx=px(12))
            HudButton(self.btns, _t("← К СПИСКУ"), self.back_hub, color=CYAN, height=36).pack(
                side=tk.LEFT, padx=px(4))
            try:
                self.ctx.status(_t("Ошибка показа карточки: {0}").format(e), AMBER)
            except Exception:
                pass

    def _render_hub(self) -> None:
        books = bs.list_books(self.ctx.progress)
        ready = bs.count_ready(self.ctx.progress)
        due = bs.count_due(self.ctx.progress)
        self.strip.set(
            _t("ИЗ КНИГИ · {0}").format(ready),
            _t("Предложения только из прочитанного. Карточка: русский → скажи по-английски."),
            (due / max(1, ready)) if ready else 0.0,
            _t("к повтору {0} · книг {1}").format(due, len(books)),
        )
        top = tk.Frame(self.body, bg=PANEL)
        top.pack(fill=tk.X, pady=(px(4), px(6)))
        HudButton(top, _t("СФОРМИРОВАТЬ ИЗ ПРОЧИТАННОГО"), self._on_sync_click, color=CYAN, height=34,
                  font_size=9, width=260).pack(side=tk.LEFT, padx=(0, px(6)))
        HudButton(top, _t("▶ ПРАКТИКА"), lambda: self.start_drill(None), color=AMBER, height=34,
                  font_size=9, width=140).pack(side=tk.LEFT, padx=(0, px(6)))
        if due:
            HudButton(top, _t("К ПОВТОРУ ({0})").format(due),
                      lambda: self.start_drill(None, due_only=True), color=GREEN, height=34,
                      font_size=9, width=150).pack(side=tk.LEFT)

        L(self.body,
          _t("Карточки = предложения до вашей позиции в книге (СКОРОЧТЕНИЕ → КАРТОЧКИ). "
             "Практика: русский → скажи по-английски."),
          fg=MUTED, size=9, wraplength=px(820), justify="left").pack(anchor="w", pady=(0, px(6)))

        if not books:
            L(self.body, _t("ПОКА НЕТ КАРТОЧЕК ИЗ КНИГ"), fg=AMBER, size=20, bold=True).pack(
                pady=(px(40), px(8)))
            L(self.body,
              _t("1) СКОРОЧТЕНИЕ → откройте английскую книгу и полистайте страницы\n"
                 "2) Нажмите «КАРТОЧКИ» в панели книги — или кнопку выше\n"
                 "3) Дождитесь перевода (UPLINK) и нажмите «ПРАКТИКА»"),
              fg=MUTED, size=11, justify="left").pack()
            return

        sf = ScrollFrame(self.body, bg=PANEL)
        sf.pack(fill=tk.BOTH, expand=True)
        for b in books:
            row = tk.Frame(sf.inner, bg=PANEL, cursor="hand2",
                           highlightthickness=1, highlightbackground=LINE)
            row.pack(fill=tk.X, pady=px(3), padx=px(2))
            left = tk.Frame(row, bg=PANEL)
            left.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=px(10), pady=px(8))
            title = b["title"]
            if b["author"]:
                title = f"{title} — {b['author']}"
            L(left, title, fg=TEXT, size=13, bold=True, bg=PANEL, wraplength=px(520)).pack(anchor="w")
            L(left,
              _t("предложений {0} · с переводом {1} · к повтору {2} · позиция слова {3}").format(
                  b["total"], b["ready"], b["due"], b["word_pos"]),
              fg=MUTED, size=8, mono=True, bg=PANEL).pack(anchor="w", pady=(px(2), 0))
            actions = tk.Frame(row, bg=PANEL)
            actions.pack(side=tk.RIGHT, padx=px(8))
            HudButton(actions, _t("ПРАКТИКА"), lambda tid=b["id"]: self.open_book(tid),
                      color=CYAN if b["ready"] else MUTED, height=30, font_size=8, width=120).pack()
            for wdg in (left, *left.winfo_children()):
                wdg.bind("<Button-1>", lambda _e, tid=b["id"]: self.open_book(tid))
                wdg.bind("<Enter>", lambda _e, r=row: self._hover(r, True))
                wdg.bind("<Leave>", lambda _e, r=row: self._hover(r, False))

    def _hover(self, row: tk.Frame, on: bool) -> None:
        try:
            bg = PANEL_HI if on else PANEL
            row.configure(bg=bg, highlightbackground=CYAN if on else LINE)
            for c in row.winfo_children():
                if isinstance(c, tk.Frame):
                    c.configure(bg=bg)
                    for x in c.winfo_children():
                        if isinstance(x, tk.Label):
                            x.configure(bg=bg)
        except tk.TclError:
            pass

    def _on_sync_click(self) -> None:
        books_n, sent_n = self._sync(request=True)
        self.ctx.sfx("click")
        self.ctx.status(
            _t("Синхронизация: {0} книг, {1} предложений из прочитанного").format(books_n, sent_n),
            GREEN if sent_n else AMBER)
        self.render()
        self.ctx.changed()

    def _render_drill(self) -> None:
        if not self.queue or self.i >= len(self.queue):
            L(self.body, _t("СЕССИЯ ЗАВЕРШЕНА ✓"), fg=GREEN, size=22, bold=True).pack(pady=(px(50), px(8)))
            L(self.body, _t("Все доступные предложения пройдены."), fg=MUTED, size=11).pack()
            HudButton(self.btns, _t("← К СПИСКУ"), self.back_hub, color=CYAN, height=36).pack(
                side=tk.LEFT, padx=px(4))
            HudButton(self.btns, _t("ЕЩЁ РАЗ"), lambda: self.start_drill(self.tid, due_only=False),
                      color=AMBER, height=36).pack(side=tk.LEFT, padx=px(4))
            return

        sent = self.queue[self.i]
        card = bs.get_card(self.ctx.progress, bs.card_key(sent))
        total = len(self.queue)
        self.strip.set(
            _t("ИЗ КНИГИ · {0}/{1}").format(self.i + 1, total),
            _t("Русский на карточке → скажи по-английски (≥ {0}%). "
               "💡 ПОДСКАЗКА — удерживай, чтобы увидеть EN.").format(bs.FLIP_OK),
            self.i / max(1, total),
            (sent.get("title") or "")[:40],
        )

        top = tk.Frame(self.body, bg=PANEL)
        top.pack(fill=tk.X, pady=(px(4), px(2)))
        HudButton(top, _t("← К СПИСКУ"), self.back_hub, height=30, font_size=9, width=120).pack(side=tk.LEFT)
        tag = _t("НОВОЕ") if card.get("reps", 0) == 0 else _t("повтор · интервал {0} дн").format(card["interval"])
        L(top, f"#{sent.get('i', 0) + 1} · {tag}", fg=MUTED, size=8, bold=True, mono=True, bg=PANEL).pack(
            side=tk.LEFT, padx=px(12))

        self._face_ru = (sent.get("ru") or "").strip() or _t("(нет перевода)")
        self._face_en = (sent.get("en") or "").strip()

        # прокручиваемая область — как на складе; контент не в Canvas напрямую
        sf = ScrollFrame(self.body, bg=PANEL)
        sf.pack(fill=tk.BOTH, expand=True, pady=(px(6), 0))
        host = sf.inner

        card_row = tk.Frame(host, bg=BG2, highlightthickness=1, highlightbackground=CYAN)
        card_row.pack(fill=tk.X, pady=(px(4), px(4)), padx=px(2))
        mid = tk.Frame(card_row, bg=BG2)
        mid.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=px(14), pady=px(12))
        L(mid, _t("ПРЕДЛОЖЕНИЕ · скажи по-английски"), fg=MUTED, size=8, bold=True, bg=BG2).pack(anchor="w")
        self._face_lab = L(mid, self._face_ru, fg=TEXT, size=16, bold=True, bg=BG2, wraplength=px(620),
                           justify="left", anchor="w")
        self._face_lab.pack(anchor="w", pady=(px(6), 0))
        if self.shown or (self._last_score is not None and self._last_score >= bs.FLIP_OK):
            L(mid, self._face_en, fg=GREEN if (self._last_score or 0) >= bs.FLIP_OK else CYAN,
              size=12, bold=True, mono=True, bg=BG2, wraplength=px(620), justify="left",
              anchor="w").pack(anchor="w", pady=(px(6), 0))

        right = tk.Frame(card_row, bg=BG2)
        right.pack(side=tk.RIGHT, padx=px(10), pady=px(8))
        hb = HudButton(right, _t("💡 ПОДСКАЗКА"), None, color=AMBER, height=32, font_size=9, width=130)
        hb.pack(pady=(px(2), 0))
        self._bind_hint(hb)
        self.ctx.audio_button(right, _t("🔊 EN"), lambda: self._face_en,
                              height=30, font_size=8, width=90).pack(pady=(px(4), 0))
        self.ctx.audio_button(right, _t("🐢 МЕДЛЕННО"), lambda: self._face_en, slow=True,
                              height=28, font_size=8, width=90).pack(pady=(px(2), 0))
        if self._last_score is not None:
            col = GREEN if self._last_score >= bs.FLIP_OK else (AMBER if self._last_score >= 40 else RED)
            L(right, f"{self._last_score}%", fg=col, size=14, bold=True, mono=True, bg=BG2).pack(
                pady=(px(8), 0))
        else:
            L(right, _t("проверка ↓"), fg=MUTED, size=8, bg=BG2).pack(pady=(px(8), 0))

        box = tk.Frame(host, bg=PANEL)
        box.pack(fill=tk.X, pady=(px(8), 0))
        L(box, _t("АКТИВНО · скажи по-английски:"), fg=MUTED, size=8, bg=PANEL).pack(anchor="w")
        tools = tk.Frame(box, bg=PANEL)
        tools.pack(anchor="w", pady=(px(4), 0))
        hb2 = HudButton(tools, _t("💡 ПОДСКАЗКА"), None, color=AMBER, height=30, font_size=9, width=120)
        hb2.pack(side=tk.LEFT, padx=(0, px(4)))
        self._bind_hint(hb2)
        self.ctx.audio_button(tools, _t("🔊 ОЗВУЧИТЬ EN"), lambda: self._face_en,
                              height=30, font_size=9, width=140).pack(side=tk.LEFT)
        L(tools, _t("→ затем проверка микрофоном"), fg=MUTED, size=8, bg=PANEL).pack(
            side=tk.LEFT, padx=px(10))

        mic_row = tk.Frame(box, bg=PANEL)
        mic_row.pack(anchor="w", pady=px(6))
        self.mic = MicPanel(mic_row, self.ctx, self.on_speech, bg=PANEL)
        self.mic.pack(side=tk.LEFT)
        self.match = MatchReadout(box)
        self.match.pack(fill=tk.X, pady=(px(4), 0))
        self.fb = L(box, "", fg=MUTED, size=10, bg=PANEL)
        self.fb.pack(anchor="w")

        L(host,
          _t("Удерживай «ПОДСКАЗКА», чтобы мельком увидеть английский — как на складе карточек."),
          fg=MUTED, size=9, bg=PANEL).pack(anchor="w", pady=(px(8), px(12)))

        if not self.shown:
            HudButton(self.btns, _t("РАСШИФРОВАТЬ  Space"), self.show_answer, color=CYAN, height=36,
                      font_size=10).pack(side=tk.LEFT, padx=px(4))
        else:
            for q, text, col, key in ((1, _t("СНОВА"), RED, "1"), (3, _t("ТРУДНО"), AMBER, "2"),
                                      (4, _t("ХОРОШО"), CYAN, "3"), (5, _t("ЛЕГКО"), GREEN, "4")):
                f = tk.Frame(self.btns, bg=BG)
                f.pack(side=tk.LEFT, padx=px(6))
                HudButton(f, f"{text}  {key}", lambda qq=q: self.grade(qq), color=col, height=40,
                          width=140, font_size=11).pack()
                L(f, sm2.preview(card, q), fg=MUTED, size=8, bg=BG, mono=True).pack()
        HudButton(self.btns, _t("ПРОПУСТИТЬ"), self.skip, height=36, font_size=9).pack(
            side=tk.LEFT, padx=px(8))

    def _bind_hint(self, btn: HudButton) -> None:
        btn.command = None  # не клик, а удержание

        def down(_e) -> None:
            self._hint_down(btn)

        def up(_e) -> None:
            self._hint_up()

        btn.bind("<ButtonPress-1>", down, add="+")
        btn.bind("<ButtonRelease-1>", up, add="+")
        # Leave не трогаем: RU→EN меняет высоту карточки, курсор «уезжает» с кнопки
        # и подсказка слетала бы сразу. grab держит release даже вне кнопки.

    def _release_hint_grab(self) -> None:
        btn = self._hint_grab
        self._hint_grab = None
        if btn is None:
            return
        try:
            btn.grab_release()
        except tk.TclError:
            pass

    def show_answer(self) -> None:
        self.shown = True
        self.render()

    def skip(self) -> None:
        if not self.queue or self.i >= len(self.queue):
            return
        self.i += 1
        self.shown = False
        self._last_score = None
        self.render()

    def grade(self, q: int) -> None:
        if not self.queue or self.i >= len(self.queue):
            return
        sent = self.queue[self.i]
        bs.grade(self.ctx.progress, sent, q)
        try:
            self.ctx.progress.add_xp(2 if q >= 3 else 1)
        except Exception:
            pass
        self.ctx.sfx("click" if q >= 3 else "error")
        if q < 3:
            self.queue.insert(min(self.i + 4, len(self.queue)), sent)
        self.i += 1
        self.shown = False
        self._last_score = None
        self.ctx.changed()
        self.render()

    def on_speech(self, alts, self_score) -> None:
        if not self.queue or self.i >= len(self.queue):
            return
        if self._holding:
            self._hint_up()
        sent = self.queue[self.i]
        en = sent.get("en") or ""
        heard = ""
        marks = None
        if self_score is not None:
            score = self_score
        else:
            if not alts:
                return
            res = [(score_sentence(en, a, None), a) for a in alts]
            (score, marks), heard = max(res, key=lambda r: r[0][0])
        self._last_score = score
        if self.match is not None:
            self.match.set(score, marks, heard if self_score is None else "",
                           False, self_rated=self_score is not None)
        ok, _q = bs.record_speech(self.ctx.progress, sent, score)
        text, vk = verdict(score)
        if ok:
            self.ctx.sfx("click")
            msg = _t("Совпадение {0}% · {1}").format(score, text)
            if self.fb is not None:
                self.fb.configure(text=msg + _t("  Оригинал: {0}").format(en), fg=VCOL[vk])
            self.ctx.status(msg, GREEN)
            # коротко показать EN, затем следующая карточка
            self.shown = True
            self.render()
            self.after(900, self._advance_after_ok)
        else:
            self.ctx.sfx("error")
            self.ctx.status(_t("Ещё раз: {0}%").format(score), VCOL[vk])
            # обновить % на карточке, сохранить текст ошибки
            err = _t("Совпадение {0}% · нужно ≥ {1}% · {2}").format(score, bs.FLIP_OK, text)
            self.render()
            if self.fb is not None:
                self.fb.configure(text=err, fg=VCOL[vk])

    def _advance_after_ok(self) -> None:
        if self.mode != "drill" or not self.queue:
            return
        self.i += 1
        self.shown = False
        self._last_score = None
        self.ctx.changed()
        self.render()

    def _hint_down(self, btn: HudButton | None = None) -> None:
        if self._holding or self._face_lab is None:
            return
        if not self._face_en:
            self.ctx.status(_t("Нет английского образца"), AMBER)
            return
        self._holding = True
        if btn is not None:
            self._hint_grab = btn
            try:
                btn.grab_set()
            except tk.TclError:
                self._hint_grab = None
        try:
            # размер шрифта тот же — меньше скачок вёрстки при удержании
            self._face_lab.configure(text=self._face_en, fg=CYAN, font=theme.font(16, True))
        except tk.TclError:
            pass
        self.ctx.status(_t("Подсказка (держи) · английский"), AMBER)

    def _hint_up(self) -> None:
        if not self._holding:
            self._release_hint_grab()
            return
        self._holding = False
        self._release_hint_grab()
        if self._face_lab is None:
            return
        try:
            self._face_lab.configure(text=self._face_ru, fg=TEXT, font=theme.font(16, True))
        except tk.TclError:
            pass

    def on_key(self, e) -> None:
        k = e.keysym.lower()
        if self.mode != "drill":
            if k == "r":
                self._on_sync_click()
            return
        if k in ("escape", "backspace"):
            self.back_hub()
        elif k == "space" and not self.shown:
            self.show_answer()
        elif self.shown and k in ("1", "2", "3", "4"):
            self.grade({"1": 1, "2": 3, "3": 4, "4": 5}[k])
        elif k == "h":
            if self._holding:
                self._hint_up()
            else:
                self._hint_down()
        elif k == "m" and self.mic is not None:
            self.mic.toggle()
        elif k == "s":
            self.skip()
