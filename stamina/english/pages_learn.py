"""Проверка систем (флеш-карточки SM-2) и миссии (практика R1–R3, Q1–Q4, S1–S3, случайный микс)."""
from __future__ import annotations

from stamina.i18n import t as _t

import random
import time
import tkinter as tk

from stamina import theme
from stamina.hud import HudButton, HudPanel, Readouts, RingGauge
from stamina.theme import AMBER, BG, BG2, CYAN, FAINT, GREEN, LINE, LINE_HI, MUTED, PANEL, RED, TEXT, blend, px

from . import sm2
from .mic import MicPanel
from .tasks import MODES, POS_RU, TYPE_TITLE, TaskFactory
from .textutil import score_sentence, score_word, verdict, word_forms
from .ui import Choice, L, MatchReadout, ScrollFrame, Strip, entry, target_missed
from .vocab import POS_SHORT, SETS

VCOL = {"green": GREEN, "amber": AMBER, "red": RED}


def _clear(frame) -> None:
    for c in frame.winfo_children():
        c.destroy()


# =============================================================================
# ПРОВЕРКА СИСТЕМ — флеш-карточки
# =============================================================================

class ReviewPage(tk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.queue: list[str] = []
        self.done = 0
        self.shown = False
        self.custom = False
        self.strip = Strip(self)
        self.strip.pack(fill=tk.X, padx=px(12), pady=(px(4), 0))
        self.panel = HudPanel(self, _t("КАРТОЧКА"))
        self.panel.pack(fill=tk.BOTH, expand=True, padx=px(60), pady=px(8))
        self.body = self.panel.body
        self.btns = tk.Frame(self, bg=BG)
        self.btns.pack(pady=(0, px(12)))
        self.started = False

    def refresh(self) -> None:
        if not self.started or not self.queue:
            self.start(None)

    def build_queue(self) -> list[str]:
        p, v = self.ctx.progress, self.ctx.vocab
        due = p.due_cards(p.settings["reviews_per_day"])
        unseen = [s for s, c in p.data["cards"].items() if c.get("reps", 0) == 0 and not p.is_known(s)]
        left = max(0, p.settings["new_per_day"] - p.new_today_count())
        fresh = []
        if left:
            for w in v.in_set(p.settings["current_set"]):
                if not p.is_known(w["slug"]) and not p.has_card(w["slug"]):
                    fresh.append(w["slug"])
                    if len(fresh) >= left:
                        break
        return due + unseen[: p.settings["new_per_day"]] + fresh

    def start(self, slugs: list[str] | None) -> None:
        self.custom = slugs is not None
        self.queue = list(dict.fromkeys(slugs)) if slugs is not None else self.build_queue()
        self.queue = [s for s in self.queue if self.ctx.vocab.get(s)]
        self.done = 0
        self.started = True
        self.shown = False
        self.render()

    def render(self) -> None:
        _clear(self.body)
        _clear(self.btns)
        p = self.ctx.progress
        self.strip.set(_t("ПРОВЕРКА СИСТЕМ · ОСТАЛОСЬ {0}").format(len(self.queue)),
                       _t("Space — расшифровать, 1–4 — оценка. Интервалы по алгоритму SM-2."),
                       self.done / max(1, self.done + len(self.queue)), f"{self.done} / {self.done + len(self.queue)}")
        if not self.queue:
            L(self.body, _t("ВСЕ СИСТЕМЫ В НОРМЕ ✓"), fg=GREEN, size=22, bold=True).pack(pady=(px(60), px(8)))
            nxt = min((c["due"] for c in p.data["cards"].values()), default=None)
            L(self.body, _t("Ближайшая проверка: {0}").format(nxt) if nxt else _t("Колода пока пустая."), fg=MUTED, size=11).pack()
            HudButton(self.btns, _t("ДОБАВИТЬ 10 НОВЫХ"), self.add_new, color=AMBER, height=36).pack()
            if self.done:
                p.mark_review_done()
            return
        slug = self.queue[0]
        w = self.ctx.vocab.get(slug)
        p.add_card(slug)
        card = p.card(slug)
        rev = bool(p.settings.get("reverse"))
        tag = _t("НОВОЕ") if card.get("reps", 0) == 0 else _t("повтор · интервал {0} дн").format(card['interval'])
        L(self.body, f"#{w['rank']} · {POS_SHORT.get(w['pos'], w['pos'].upper())} · {tag}", fg=MUTED, size=8,
          bold=True, mono=True).pack(pady=(px(20), px(6)))
        front = (p.tr(slug) or w.get("definition", "")) if rev else w["word"]
        L(self.body, front, fg=TEXT, size=34 if not rev else 16, bold=True, mono=not rev,
          wraplength=px(800)).pack(pady=px(6))
        if not rev and p.settings.get("autoplay") and not self.shown:
            self.after(200, lambda: self.ctx.say(w["word"]))
        if not self.shown:
            HudButton(self.btns, _t("РАСШИФРОВАТЬ  Space"), self.show_answer, color=AMBER, height=40,
                      font_size=11).pack()
            return
        if rev:
            L(self.body, w["word"], fg=CYAN, size=30, bold=True, mono=True).pack()
        if w.get("respelling"):
            L(self.body, f"[ {w['respelling']} ]  {w.get('ipa') or ''}", fg=CYAN, size=14, mono=True).pack(pady=px(2))
        if p.tr(slug) and not rev:
            L(self.body, p.tr(slug), fg=AMBER, size=14, bold=True).pack()
        if not rev:
            L(self.body, w.get("definition", ""), fg=TEXT, size=12, wraplength=px(800)).pack(pady=px(4))
        s = self.ctx.vocab.sentences(w)
        if s:
            L(self.body, s[0]["en"], fg=MUTED, size=11, wraplength=px(800)).pack(pady=(px(6), 0))
            if s[0].get("ru"):
                L(self.body, s[0]["ru"], fg=FAINT if False else MUTED, size=10, wraplength=px(800)).pack()
        self.ctx.audio_button(self.body, _t("🔊 ГОЛОС"), lambda: w["word"], height=30, font_size=9).pack(pady=px(6))
        for q, text, col, key in ((1, _t("СНОВА"), RED, "1"), (3, _t("ТРУДНО"), AMBER, "2"), (4, _t("ХОРОШО"), CYAN, "3"),
                                  (5, _t("ЛЕГКО"), GREEN, "4")):
            f = tk.Frame(self.btns, bg=BG)
            f.pack(side=tk.LEFT, padx=px(6))
            HudButton(f, f"{text}  {key}", lambda qq=q: self.grade(qq), color=col, height=40, width=150,
                      font_size=11).pack()
            L(f, sm2.preview(card, q), fg=MUTED, size=8, bg=BG, mono=True).pack()

    def show_answer(self) -> None:
        self.shown = True
        self.render()

    def grade(self, q: int) -> None:
        if not self.queue or not self.shown:
            return
        slug = self.queue.pop(0)
        p = self.ctx.progress
        p.grade(slug, q)
        p.record_attempt(slug, "review", "review", q >= 3, q)
        p.add_xp(2)
        if q < 3:  # повтор в этой же сессии через ~5 карточек
            self.queue.insert(min(5, len(self.queue)), slug)
        else:
            self.done += 1
        self.ctx.sfx("click" if q >= 3 else "error")
        self.shown = False
        self.ctx.changed()
        self.render()

    def add_new(self) -> None:
        p, v = self.ctx.progress, self.ctx.vocab
        fresh = [w["slug"] for w in v.in_set(p.settings["current_set"])
                 if not p.is_known(w["slug"]) and not p.has_card(w["slug"])][:10]
        if not fresh:
            self.ctx.status(_t("В текущем наборе нет новых слов — выбери набор побольше в настройках"), AMBER)
        self.start(fresh)

    def on_key(self, e) -> None:
        k = e.keysym
        if k == "space" and not self.shown and self.queue:
            self.show_answer()
        elif self.shown and k in ("1", "2", "3", "4"):
            self.grade({"1": 1, "2": 3, "3": 4, "4": 5}[k])


# =============================================================================
# МИССИИ — практика
# =============================================================================

class MissionCardC(tk.Canvas):
    def __init__(self, master, ctx, mode: str, on_click) -> None:
        super().__init__(master, bg=BG, highlightthickness=0, bd=0, height=px(150), width=px(220), cursor="hand2")
        self.ctx, self.mode = ctx, mode
        self.hover = False
        self.bind("<Configure>", lambda _e: self.redraw())
        self.bind("<Enter>", lambda _e: self._h(True))
        self.bind("<Leave>", lambda _e: self._h(False))
        self.bind("<Button-1>", lambda _e: on_click(mode))

    def _h(self, v) -> None:
        self.hover = v
        self.redraw()

    def redraw(self) -> None:
        from stamina.theme import PANEL_HI, chamfer
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 40:
            return
        title, code, desc = MODES[self.mode]
        rec = self.ctx.progress.data.get("missions", {}).get(self.mode, {})
        stars = rec.get("stars", 0)
        col = GREEN if stars else (CYAN if self.hover else LINE_HI)
        self.create_polygon(chamfer(1, 1, w - 2, h - 2, px(12)), fill=PANEL_HI if self.hover else PANEL,
                            outline=col, width=2 if stars else 1)
        self.create_text(px(12), px(14), text=code, anchor="w", fill=GREEN if stars else CYAN,
                         font=theme.font(9, True, mono=True))
        self.create_text(px(12), px(42), text=title, anchor="w", fill=TEXT, font=theme.font(14, True))
        self.create_text(px(12), px(70), text=desc, anchor="nw", width=w - px(24), fill=MUTED, font=theme.font(8))
        best = rec.get("best_acc")
        self.create_text(w - px(12), h - px(18), text="★" * stars + "☆" * (3 - stars), anchor="e", fill=AMBER,
                         font=theme.font(14, True))
        if best is not None:
            self.create_text(px(12), h - px(18), text=_t("рекорд {0}%").format(best), anchor="w", fill=MUTED, font=theme.font(8))


class PracticePage(tk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.src = "set"
        self.src_list = "favorites"
        self.length = ctx.progress.settings.get("session_len", 10)
        self.hub = tk.Frame(self, bg=BG)
        self.sess = tk.Frame(self, bg=BG)
        self._build_hub()
        self._build_session()
        self.hub.pack(fill=tk.BOTH, expand=True)
        self.active = False

    # -- хаб --------------------------------------------------------------------------
    def _build_hub(self) -> None:
        h = self.hub
        L(h, _t("МИССИИ · ПРАКТИКА"), fg=TEXT, size=16, bold=True, bg=BG).pack(anchor="w", padx=px(14), pady=(px(10), 0))
        L(h, _t("Чтение, вопросы и говорение. Аудирования, диктанта и письменной проверки нет (решение пользователя)."),
          fg=MUTED, size=9, bg=BG).pack(anchor="w", padx=px(16))
        opt = HudPanel(h, _t("ПОЛЁТНЫЙ ПЛАН"))
        opt.pack(fill=tk.X, padx=px(12), pady=px(8))
        r = tk.Frame(opt.body, bg=PANEL)
        r.pack(fill=tk.X)
        L(r, _t("ИСТОЧНИК"), fg=MUTED, size=8, bold=True).pack(side=tk.LEFT, padx=(0, px(6)))
        self.src_btns = {}
        for key, text in (("set", _t("ТЕКУЩИЙ НАБОР · НЕЗНАКОМЫЕ")), ("list", _t("ОТСЕК ▾")), ("due", _t("НА ПОВТОРЕНИИ")),
                          ("mistakes", _t("ОШИБКИ 7 ДН"))):
            b = HudButton(r, text, lambda k=key: self.set_src(k), height=28, font_size=8)
            b.pack(side=tk.LEFT, padx=px(2))
            self.src_btns[key] = b
        L(r, _t("   ДЛИНА"), fg=MUTED, size=8, bold=True).pack(side=tk.LEFT, padx=(px(6), px(6)))
        self.len_btns = {}
        for n in (5, 10, 20):
            b = HudButton(r, str(n), lambda k=n: self.set_len(k), width=44, height=28, font_size=9)
            b.pack(side=tk.LEFT, padx=px(2))
            self.len_btns[n] = b
        self.src_info = L(opt.body, "", fg=CYAN, size=9)
        self.src_info.pack(anchor="w", pady=(px(6), 0))
        grid = tk.Frame(h, bg=BG)
        grid.pack(fill=tk.BOTH, expand=True, padx=px(10), pady=px(4))
        self.mcards = []
        for i, m in enumerate(("random", "speaking", "reading", "questions")):
            c = MissionCardC(grid, self.ctx, m, lambda mode: self.start(mode, source=self.src))
            c.grid(row=0, column=i, sticky="nsew", padx=px(4), pady=px(4))
            grid.grid_columnconfigure(i, weight=1, uniform="m")
            self.mcards.append(c)
        grid.grid_rowconfigure(0, weight=0)

    def set_src(self, key: str) -> None:
        if key == "list":
            m = tk.Menu(self, tearoff=0, bg=PANEL, fg=TEXT, activebackground=LINE_HI, activeforeground=CYAN,
                        font=theme.font(10))
            for l in self.ctx.progress.lists:
                m.add_command(label=f"{l['name']}  ({len(l['slugs'])})",
                              command=lambda lid=l["id"]: self._pick_list(lid))
            b = self.src_btns["list"]
            try:
                m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())
            finally:
                m.grab_release()
            return
        self.src = key
        self.refresh()

    def _pick_list(self, lid: str) -> None:
        self.src, self.src_list = "list", lid
        self.refresh()

    def set_len(self, n: int) -> None:
        self.length = n
        self.ctx.progress.settings["session_len"] = n
        self.ctx.progress.save()
        self.refresh()

    def pool(self, source: str, ids=None) -> list[dict]:
        p, v = self.ctx.progress, self.ctx.vocab
        if source == "filtered" and ids:
            return [v.get(s) for s in ids if v.get(s)]
        if source == "list":
            l = p.list_by_id(self.src_list)
            return [v.get(s) for s in (l["slugs"] if l else []) if v.get(s)]
        if source == "due":
            return [v.get(s) for s in p.due_cards() if v.get(s)]
        if source == "mistakes":
            return [v.get(s) for s in p.mistakes(7) if v.get(s)]
        cur = v.in_set(p.settings["current_set"])
        return [w for w in cur if not p.is_known(w["slug"])] or cur

    def refresh(self) -> None:
        if self.active:
            return
        for k, b in self.src_btns.items():
            b.set_active(k == self.src)
        for n, b in self.len_btns.items():
            b.set_active(n == self.length)
        name = {"set": _t("набор {0}").format(self.ctx.progress.settings['current_set']), "due": _t("слова на повторении"),
                "mistakes": _t("ошибки за 7 дней")}.get(self.src)
        if self.src == "list":
            l = self.ctx.progress.list_by_id(self.src_list)
            name = _t("отсек «{0}»").format(l['name'] if l else '?')
        self.src_info.configure(text=_t("Слова для миссии: {0} · доступно {1}").format(name, len(self.pool(self.src))))
        for c in self.mcards:
            c.redraw()

    # -- сессия -----------------------------------------------------------------------
    def _build_session(self) -> None:
        s = self.sess
        self.strip = Strip(s)
        self.strip.pack(fill=tk.X, padx=px(12), pady=(px(4), 0))
        main = tk.Frame(s, bg=BG)
        main.pack(fill=tk.BOTH, expand=True, padx=px(12), pady=px(4))
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, minsize=px(240))
        main.grid_rowconfigure(0, weight=1)
        self.chan = HudPanel(main, _t("НАВИГАЦИОННЫЙ КАНАЛ"))
        self.chan.grid(row=0, column=0, sticky="nsew", padx=(0, px(6)))
        self.tb = self.chan.body
        tel = HudPanel(main, _t("ТЕЛЕМЕТРИЯ"))
        tel.grid(row=0, column=1, sticky="nsew")
        self.ring = RingGauge(tel.body, title=_t("ТОЧНОСТЬ"))
        self.ring.pack(fill=tk.X)
        self.ro = Readouts(tel.body, rows=4)
        self.ro.pack(fill=tk.BOTH, expand=True)
        bot = tk.Frame(s, bg=BG)
        bot.pack(fill=tk.X, padx=px(12), pady=(0, px(8)))
        HudButton(bot, _t("✕ ВЫЙТИ  Esc"), self.quit_session, color=RED, height=32, font_size=9).pack(side=tk.LEFT)
        HudButton(bot, _t("ПРОПУСТИТЬ"), self.skip, height=32, font_size=9).pack(side=tk.LEFT, padx=px(6))
        self.next_btn = HudButton(bot, _t("ДАЛЕЕ  Enter"), self.next_task, color=GREEN, height=32, font_size=10)
        self.next_btn.pack(side=tk.RIGHT)

    def start(self, mode: str, source: str = "set", single: str | None = None, ids=None) -> None:
        v, p = self.ctx.vocab, self.ctx.progress
        self.mode = mode
        speech_ok = (p.settings.get("asr", True) and self.ctx.asr.available()) or p.settings.get("self_assess", True)
        fac = TaskFactory(v, p)
        sw = v.get(single) if single else None
        n = 5 if sw else self.length
        pool = self.pool(source, ids) if not sw else [sw]
        if not pool:
            self.ctx.status(_t("Для этой миссии нет слов — выбери другой источник"), AMBER)
            self.active = False
            self.ctx.show("practice")
            return
        words = fac.pick_words(pool, n, single=sw)
        if mode == "speaking" and not speech_ok:
            self.ctx.status(_t("Говорение недоступно: нет распознавания и выключена самооценка"), AMBER)
            return
        self.tasks = fac.build(mode, words, speech_ok)
        self.repeat_added: set[int] = set()
        self.i = 0
        self.ok = 0
        self.bad = 0
        self.answered = 0
        self.xp = 0
        self.results: list[tuple[str, bool]] = []
        self.t0 = time.time()
        self.combo = 0
        self.best_combo = 0
        self.active = True
        self.hub.pack_forget()
        self.sess.pack(fill=tk.BOTH, expand=True)
        self.ctx.sfx("start")
        self.render_task()
        self._tick()

    def _tick(self) -> None:
        if not self.active:
            return
        self._telemetry()
        self.after(1000, self._tick)

    def _telemetry(self) -> None:
        acc = 100 * self.ok / self.answered if self.answered else None
        self.ring.set(acc, _t("ошибок {0}").format(self.bad))
        el = int(time.time() - self.t0)
        self.ro.set([(_t("ВРЕМЯ"), f"{el // 60:02d}:{el % 60:02d}", CYAN), (_t("ОШИБКИ"), str(self.bad), RED),
                     (_t("СЕРИЯ / ЛУЧШАЯ"), f"{self.combo} / {self.best_combo}", AMBER), ("XP", f"+{self.xp}", GREEN)])

    def render_task(self) -> None:
        _clear(self.tb)
        self.answered_cur = False
        self.attempt = 1
        self.next_btn.set_enabled(False)
        if self.i >= len(self.tasks):
            self.finish()
            return
        t = self.tasks[self.i]
        w = t["word"]
        title = MODES[self.mode][0]
        self.strip.set(_t("МИССИЯ · {0} · {1}").format(title, TYPE_TITLE[t['type']]),
                       _t("Слово #{0} · 1–4 выбрать, Enter — далее, M — микрофон, Space — голос").format(w['rank']),
                       self.i / len(self.tasks), f"{self.i + 1} / {len(self.tasks)}")
        L(self.tb, TYPE_TITLE[t["type"]], fg=AMBER, size=10, bold=True).pack(anchor="w")
        self.fb = None
        getattr(self, f"_t_{t['type']}")(t, w)
        self.fb = L(self.tb, "", fg=MUTED, size=11, bold=True, wraplength=px(700), justify="left")
        self.fb.pack(anchor="w", pady=(px(8), 0))

    # ---- задания с выбором ----------------------------------------------------------
    def _choices(self, t, wrap=640) -> None:
        self.choice_w = []
        box = tk.Frame(self.tb, bg=PANEL)
        box.pack(fill=tk.X, pady=px(6))
        for i, text in enumerate(t["options"]):
            c = Choice(box, i + 1, text, lambda k=i: self.choose(k), wrap=wrap)
            c.pack(fill=tk.X, pady=px(3))
            self.choice_w.append(c)

    def _big(self, text, size=26, mono=True, fg=TEXT) -> None:
        L(self.tb, text, fg=fg, size=size, bold=True, mono=mono, wraplength=px(760), justify="left").pack(
            anchor="w", pady=px(8))

    def _t_R1(self, t, w) -> None:
        self._big(t["cloze"], size=16, mono=False)
        self._choices(t)

    def _t_R2(self, t, w) -> None:
        self._big(t["sentence"]["en"], size=16, mono=False)
        L(self.tb, _t("Какой перевод верный?"), fg=MUTED, size=9).pack(anchor="w")
        self._choices(t)

    def _t_R3(self, t, w) -> None:
        self._sent_with_word(t["sentence"]["en"], w["word"])
        L(self.tb, _t("Что значит «{0}» в этом предложении?").format(w['word']), fg=MUTED, size=9).pack(anchor="w")
        self._choices(t)

    def _t_Q1(self, t, w) -> None:
        self._big(w.get("definition", ""), size=15, mono=False)
        self._choices(t)

    def _t_Q2(self, t, w) -> None:
        r = tk.Frame(self.tb, bg=PANEL)
        r.pack(anchor="w")
        L(r, w["word"], fg=TEXT, size=28, bold=True, mono=True).pack(side=tk.LEFT)
        self.ctx.audio_button(r, _t("🔊 ГОЛОС"), lambda: w["word"], height=32, font_size=9).pack(side=tk.LEFT, padx=px(10))
        self._choices(t)

    def _t_Q3(self, t, w) -> None:
        self._big(w["word"], size=28)
        self._choices(t)

    def _t_Q4(self, t, w) -> None:
        self._big(w.get("definition", ""), size=15, mono=False)
        self.q4_hint = L(self.tb, "", fg=CYAN, size=18, bold=True, mono=True)
        self.q4_hint.pack(anchor="w")
        self._q4_hint_update(t)
        r = tk.Frame(self.tb, bg=PANEL)
        r.pack(anchor="w", pady=px(6))
        self.q4 = entry(r, width=24, size=16, mono=True)
        self.q4.pack(side=tk.LEFT, ipady=px(4))
        self.q4.bind("<Return>", lambda _e: self.check_q4() if not self.answered_cur else self.next_task())
        HudButton(r, _t("ПРОВЕРИТЬ"), self.check_q4, color=GREEN, height=34).pack(side=tk.LEFT, padx=px(6))
        HudButton(r, _t("💡 ЕЩЁ БУКВА"), lambda: self._q4_more(t), color=AMBER, height=34).pack(side=tk.LEFT)
        self.after(50, self.q4.focus_set)

    def _q4_hint_update(self, t) -> None:
        word = t["word"]["word"]
        n = t["revealed"]
        self.q4_hint.configure(text=" ".join(ch if i < n or not ch.isalpha() else "_" for i, ch in enumerate(word)))

    def _q4_more(self, t) -> None:
        if self.answered_cur:
            return
        t["revealed"] = min(len(t["word"]["word"]), t["revealed"] + 1)
        t["hinted"] = True
        self._q4_hint_update(t)

    def check_q4(self) -> None:
        if self.answered_cur:
            return
        t = self.tasks[self.i]
        guess = self.q4.get().strip().lower()
        word = t["word"]["word"].lower()
        ok = guess == word or guess in word_forms(word) and guess.startswith(word[:-1])
        if not ok and self.attempt == 1 and guess:
            self.attempt = 2
            self.fb.configure(text=_t("Не совсем. Попробуй ещё раз (или возьми подсказку)."), fg=AMBER)
            return
        q = 2 if not ok else (3 if self.attempt > 1 or t.get("hinted") else 4)
        self.answer(ok, q, _t("Правильно: {0}").format(t['word']['word']))

    def choose(self, k: int) -> None:
        if self.answered_cur:
            return
        t = self.tasks[self.i]
        good = t.get("answers") or [t["answer"]]
        ok = k in good
        for i, c in enumerate(self.choice_w):
            if i in good:
                c.mark("ok")
            elif i == k:
                c.mark("bad")
            else:
                c.mark("dim")
        right = t["options"][t["answer"]]
        self.answer(ok, 4 if ok else 2, "" if ok else _t("Правильный ответ: {0}").format(right))

    # ---- говорение ------------------------------------------------------------------
    def _sent_with_word(self, text, word, size=16) -> None:
        tw = tk.Text(self.tb, height=2, bg=PANEL, fg=TEXT, relief="flat", wrap="word", bd=0,
                     font=theme.font(size), highlightthickness=0, cursor="arrow")
        tw.tag_configure("t", foreground=CYAN, font=theme.font(size, True))
        tw.insert("1.0", text)
        import re
        forms = word_forms(word)
        for m in re.finditer(r"[A-Za-z']+", text):
            if m.group(0).lower() in forms:
                tw.tag_add("t", f"1.0+{m.start()}c", f"1.0+{m.end()}c")
        tw.configure(state="disabled", height=max(1, min(4, 1 + len(text) // 55)))
        tw.pack(fill=tk.X, pady=px(8))
        self.sent_tw = tw
        return tw

    def _speak_box(self, t, sample: str) -> None:
        r = tk.Frame(self.tb, bg=PANEL)
        r.pack(fill=tk.X)
        left = tk.Frame(r, bg=PANEL)
        left.pack(side=tk.LEFT, anchor="n")
        self.ctx.audio_button(left, _t("🔊 ОБРАЗЕЦ"), lambda: sample, height=30, font_size=9).pack(anchor="w", pady=px(2))
        self.ctx.audio_button(left, _t("🐢 МЕДЛЕННО"), lambda: sample, slow=True, height=30, font_size=9).pack(anchor="w")
        self.mic = MicPanel(r, self.ctx, self.on_speech)
        self.mic.pack(side=tk.LEFT, padx=px(30))
        self.match = MatchReadout(self.tb)  # «СОВПАДЕНИЕ: N%» после каждой попытки
        self.match.pack(fill=tk.X, pady=(px(8), 0))

    def _t_S1(self, t, w) -> None:
        self._big(w["word"], size=34)
        if w.get("respelling"):
            L(self.tb, f"[ {w['respelling']} ]   {w.get('ipa') or ''}", fg=CYAN, size=16, mono=True).pack(anchor="w")
        self._speak_box(t, w["word"])

    def _t_S2(self, t, w) -> None:
        self._sent_with_word(t["sentence"]["en"], w["word"], size=18)
        self._speak_box(t, t["sentence"]["en"])

    def _t_S3(self, t, w) -> None:
        L(self.tb, _t("Скажи по-английски:"), fg=MUTED, size=9).pack(anchor="w", pady=(px(6), 0))
        self._big(t["sentence"]["ru"], size=16, mono=False)
        L(self.tb, _t("подсказка: в предложении есть слово «{0}»").format(w['word']), fg=MUTED, size=8).pack(anchor="w")
        self._speak_box(t, "")

    def on_speech(self, alts, self_score) -> None:
        if self.answered_cur:
            return
        t = self.tasks[self.i]
        w = t["word"]
        marks = None
        heard = (alts or [""])[0]
        if self_score is not None:
            score = self_score
        elif t["type"] == "S1":
            score = score_word(w["word"], alts or [], w.get("sounds_like"))
        else:
            res = [(score_sentence(t["sentence"]["en"], a, w["word"]), a) for a in (alts or [])] or [((0, []), "")]
            (score, marks), heard = max(res, key=lambda r: r[0][0])
        self.match.set(score, marks, heard if self_score is None else "",
                       bool(marks) and target_missed(marks, w["word"]), self_rated=self_score is not None)
        passed = score >= (60 if t["type"] == "S3" else 60)
        if not passed and self.attempt < 3 and self_score is None:
            self.attempt += 1
            text, vk = verdict(score)
            self.fb.configure(text=_t("Совпадение {0}% · {1} — попытка {2} из 3").format(score, text, self.attempt), fg=VCOL[vk])
            self._marks(marks)
            return
        q = 5 if score >= 85 else 4 if score >= 60 else 3 if score >= 40 else 2
        text, vk = verdict(score)
        extra = _t("Оригинал: {0}").format(t['sentence']['en']) if t["type"] == "S3" else ""
        self._marks(marks)
        lab = _t("Самооценка") if self_score is not None else _t("Совпадение")
        self.answer(passed, q, f"{lab} {score}% · {text}. {extra}", score=score, color=VCOL[vk])

    def _marks(self, marks) -> None:
        if not marks or not hasattr(self, "sent_tw") or not self.sent_tw.winfo_exists():
            return
        tw = self.sent_tw
        tw.configure(state="normal")
        tw.delete("1.0", tk.END)
        tw.tag_configure("ok", foreground=GREEN)
        tw.tag_configure("bad", foreground=RED, underline=True)
        for i, (tok, ok) in enumerate(marks):
            tw.insert(tk.END, ("" if i == 0 else " ") + tok, "ok" if ok else "bad")
        tw.configure(state="disabled")

    # ---- общее ------------------------------------------------------------------------
    def answer(self, ok: bool, q: int, msg: str, score=None, color=None) -> None:
        self.answered_cur = True
        t = self.tasks[self.i]
        p = self.ctx.progress
        self.answered += 1
        if ok:
            self.ok += 1
            self.combo += 1
            self.best_combo = max(self.best_combo, self.combo)
            gain = 10 if q >= 4 else 5
            self.xp += gain
            p.add_xp(gain)
            self.ctx.sfx("click")
        else:
            self.bad += 1
            self.combo = 0
            self.ctx.sfx("error")
            if self.i not in self.repeat_added and t["type"] not in ("S1", "S2", "S3"):
                self.repeat_added.add(len(self.tasks))
                self.tasks.append(dict(t))
        self.results.append((t["slug"], ok))
        mode = {"S": "speaking", "R": "reading", "Q": "questions"}[t["type"][0]]
        p.record_attempt(t["slug"], mode, t["type"], ok, q, score)
        p.grade(t["slug"], q)
        txt = (_t("✓ ВЕРНО") if ok else _t("✗ ОШИБКА")) + (f"  +{10 if q >= 4 else 5} XP" if ok else "")
        self.fb.configure(text=f"{txt}   {msg}".strip(), fg=color or (GREEN if ok else RED))
        self.next_btn.set_enabled(True)
        self._telemetry()

    def next_task(self) -> None:
        if not self.active:
            return
        if not self.answered_cur:
            return
        if hasattr(self, "mic"):
            try:
                self.mic.reset()
            except tk.TclError:
                pass
        self.i += 1
        self.render_task()

    def skip(self) -> None:
        if not self.active or self.i >= len(self.tasks):
            return
        if not self.answered_cur:
            t = self.tasks[self.i]
            self.answered += 1
            self.bad += 1
            self.combo = 0
            self.results.append((t["slug"], False))
            self.ctx.progress.record_attempt(t["slug"], {"S": "speaking", "R": "reading", "Q": "questions"}[t["type"][0]],
                                             t["type"], False, 2)
        self.answered_cur = True
        self.next_task()

    def quit_session(self) -> None:
        if not self.active:
            return
        self.finish(aborted=True)

    def finish(self, aborted: bool = False) -> None:
        self.active = False
        self.ctx.asr.stop()
        _clear(self.tb)
        p = self.ctx.progress
        acc = round(100 * self.ok / self.answered, 1) if self.answered else 0.0
        stars = 3 if acc >= 95 else 2 if acc >= 80 else 1 if acc >= 60 else 0
        if aborted:
            stars = 0
        perfect = not aborted and self.answered >= 10 and self.bad == 0
        if perfect:
            p.data["perfect_session"] = True
            p.add_xp(20)
            self.xp += 20
        rec = p.data.setdefault("missions", {}).setdefault(self.mode, {"stars": 0, "best_acc": 0})
        if not aborted and self.answered:
            rec["stars"] = max(rec.get("stars", 0), stars)
            rec["best_acc"] = max(rec.get("best_acc", 0), acc)
        p.check_achievements()
        p.save()
        self.strip.set(_t("ОТЧЁТ О ПОЛЁТЕ · {0}").format(MODES[self.mode][0]), _t("Enter — ещё раз, R — повторить ошибки, Esc — к миссиям"),
                       1.0, _t("{0} заданий").format(self.answered))
        L(self.tb, _t("МИССИЯ ПРЕРВАНА") if aborted else _t("МИССИЯ ВЫПОЛНЕНА"), fg=AMBER if aborted else GREEN, size=20,
          bold=True).pack(pady=(px(10), px(2)))
        L(self.tb, "★" * stars + "☆" * (3 - stars), fg=AMBER, size=26, bold=True).pack()
        L(self.tb, _t("★ — точность ≥ 60%, ★★ — ≥ 80%, ★★★ — ≥ 95%"), fg=MUTED, size=8).pack()
        grid = tk.Frame(self.tb, bg=PANEL)
        grid.pack(pady=px(8))
        el = int(time.time() - self.t0)
        for i, (t, v, c) in enumerate(((_t("ТОЧНОСТЬ"), f"{acc}%", GREEN), (_t("ОШИБКИ"), str(self.bad), RED),
                                       (_t("ВРЕМЯ"), f"{el // 60:02d}:{el % 60:02d}", TEXT),
                                       (_t("ЛУЧШАЯ СЕРИЯ"), str(self.best_combo), AMBER))):
            f = tk.Frame(grid, bg=PANEL)
            f.grid(row=0, column=i, padx=px(20))
            L(f, t, fg=MUTED, size=8, bold=True).pack()
            L(f, v, fg=c, size=20, bold=True, mono=True).pack()
        L(self.tb, f"+{self.xp} XP", fg=AMBER, size=12, bold=True).pack(pady=px(4))
        words = tk.Frame(self.tb, bg=PANEL)
        words.pack(pady=px(4))
        seen = {}
        for slug, ok in self.results:
            seen[slug] = seen.get(slug, True) and ok
        for i, (slug, ok) in enumerate(list(seen.items())[:20]):
            w = self.ctx.vocab.get(slug)
            lb = L(words, f"{'✓' if ok else '✗'} {w['word']}", fg=GREEN if ok else RED, size=10, bold=True,
                   cursor="hand2")
            lb.grid(row=i // 5, column=i % 5, padx=px(10), pady=px(1), sticky="w")
            lb.bind("<Button-1>", lambda _e, s=slug: self.ctx.open_word(s))
        btns = tk.Frame(self.tb, bg=PANEL)
        btns.pack(pady=px(10))
        self._last_bad = [s for s, ok in seen.items() if not ok]
        HudButton(btns, _t("⟲ ЕЩЁ РАЗ  Enter"), lambda: self.start(self.mode, source=self.src), color=CYAN, height=34).pack(
            side=tk.LEFT, padx=px(4))
        HudButton(btns, _t("⚙ ПОВТОРИТЬ ОШИБКИ  R"), self.retry_bad, color=AMBER, height=34).pack(side=tk.LEFT, padx=px(4))
        HudButton(btns, _t("✕ К МИССИЯМ  Esc"), self.to_hub, height=34).pack(side=tk.LEFT, padx=px(4))
        self.next_btn.set_enabled(False)
        self.finished = True
        self.ctx.sfx("bell")
        self.ctx.changed()

    def retry_bad(self) -> None:
        if self._last_bad:
            self.start(self.mode, source="filtered", ids=self._last_bad)
        else:
            self.ctx.status(_t("Ошибок не было — отличная работа!"), GREEN)

    def to_hub(self) -> None:
        self.active = False
        self.finished = False
        self.sess.pack_forget()
        self.hub.pack(fill=tk.BOTH, expand=True)
        self.refresh()

    def on_key(self, e) -> None:
        k = e.keysym
        if getattr(self, "finished", False) and not self.active:
            if k == "Return":
                self.start(self.mode, source=self.src)
            elif k.lower() == "r":
                self.retry_bad()
            elif k == "Escape":
                self.to_hub()
            return
        if not self.active:
            return
        t = self.tasks[self.i] if self.i < len(self.tasks) else None
        if k == "Escape":
            self.quit_session()
        elif k == "Return":
            self.next_task()
        elif k in ("1", "2", "3", "4") and t and "options" in t:
            idx = int(k) - 1
            if idx < len(t["options"]):
                self.choose(idx)
        elif k.lower() == "m" and t and t["type"].startswith("S") and hasattr(self, "mic"):
            self.mic.toggle()
        elif k == "space" and t:
            self.ctx.say(t["word"]["word"] if t["type"] in ("S1", "Q2", "Q3") else
                         (t.get("sentence") or {}).get("en", "") if t["type"] in ("S2",) else "")
