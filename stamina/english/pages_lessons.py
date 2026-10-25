"""УРОКИ: карта уровней, последовательные уроки и справочник правил.

Урок ссылается на правила (grammar) и слова (CEFR A1). Правило открывается
рядом, не уводя из урока; в справочнике те же карточки правил.
"""
from __future__ import annotations

import tkinter as tk

from stamina.hud import HudButton, HudPanel
from stamina.i18n import t as _t
from stamina.theme import AMBER, BG, BG2, CYAN, FAINT, GREEN, LINE, MUTED, PANEL, RED, TEXT, px

from . import cefr, grammar, lessons
from .ui import L, ScrollFrame, Strip

LEVEL_TITLE = {"A1": "A1 · ВЫЖИВАНИЕ", "A2": "A2 · БЫТ"}


class LessonsPage(tk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.level = (lessons.levels() or ["A1"])[0]
        self.tab = "lessons"        # lessons | ref
        self.view = "lesson"        # lesson | rule
        self.lid: str | None = None
        self.rid: str | None = None
        self.back_lid: str | None = None

        self.strip = Strip(self)
        self.strip.pack(fill=tk.X, padx=px(12), pady=(px(4), 0))

        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(12), pady=px(2))
        self.tab_btns: dict[str, HudButton] = {}
        for key, title in (("lessons", _t("УРОКИ")), ("ref", _t("СПРАВОЧНИК"))):
            b = HudButton(top, title, lambda k=key: self.set_tab(k), height=28, font_size=9, width=130)
            b.pack(side=tk.LEFT, padx=px(2))
            self.tab_btns[key] = b
        self.levels_lbl = L(top, "", fg=TEXT, size=9, bold=True, bg=BG)
        self.levels_lbl.pack(side=tk.LEFT, padx=px(14))
        self.hint = L(top, "", fg=MUTED, size=8, bg=BG)
        self.hint.pack(side=tk.RIGHT)

        body = tk.Frame(self, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=px(10), pady=px(4))
        body.grid_columnconfigure(0, weight=0, minsize=px(320))
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self.left = ScrollFrame(body, bg=BG)
        self.left.grid(row=0, column=0, sticky="nsew", padx=(0, px(6)))
        self.right_box = HudPanel(body, _t("УРОК И ПРАВИЛА"))
        self.right_box.grid(row=0, column=1, sticky="nsew")
        self.right = ScrollFrame(self.right_box.body, bg=PANEL)
        self.right.pack(fill=tk.BOTH, expand=True)

        self.refresh()

    # -- вкладки и выбор -------------------------------------------------------
    def set_tab(self, key: str) -> None:
        self.tab = key if key in ("lessons", "ref") else "lessons"
        if self.tab == "ref":
            self.view = "rule"
            if not self.rid:
                rules = grammar.rules(self.level)
                self.rid = rules[0]["id"] if rules else None
        else:
            self.view = "lesson"
        self.refresh()

    def select_lesson(self, lid: str) -> None:
        self.lid = lid
        self.view = "lesson"
        self.tab = "lessons"
        self.back_lid = None
        self.refresh()

    def show_rule(self, rid: str, back: bool = False) -> None:
        self.rid = rid
        self.view = "rule"
        if back or self.tab == "lessons":
            self.back_lid = self.lid
        else:
            self.back_lid = None
        self.refresh()

    # -- данные ---------------------------------------------------------------
    def refresh(self) -> None:
        p = self.ctx.progress
        if self.level not in cefr.available():
            self._message(f"{self.level} — НАБОР ГОТОВИТСЯ", "Сначала пройди доступный уровень.")
            return
        try:
            cefr.merge_into(self.ctx.vocab, self.level)
        except Exception:  # noqa: BLE001
            pass
        sm = lessons.summary(p, self.level)
        if self.lid is None:
            nxt = sm["next"] or (lessons.plan(self.level) or [{}])[0]
            self.lid = nxt.get("id")
        if self.tab == "ref" and self.rid is None:
            rules = grammar.rules(self.level)
            self.rid = rules[0]["id"] if rules else None
        self.strip.set(
            _t("УРОКИ · {0}").format(self.level),
            _t("Последовательно: правило → слова → миссия → склад. Урок открывается после предыдущего."),
            sm["done"] / max(1, sm["total"]),
            _t("{0} / {1} уроков").format(sm["done"], sm["total"]),
        )
        self.levels_lbl.configure(text=f"{LEVEL_TITLE.get(self.level, self.level)}")
        self.hint.configure(text=_t("правил: {0} · уроков: {1}").format(
            grammar.count(self.level), sm["total"]))
        for k, b in self.tab_btns.items():
            b.set_active(k == self.tab)
        self._build_left()
        self._build_right()

    def _build_left(self) -> None:
        self._clear(self.left.inner)
        p = self.ctx.progress
        if self.tab == "lessons":
            for lesson in lessons.plan(self.level):
                self._lesson_row(lesson)
        else:
            rules = grammar.rules(self.level)
            if not rules:
                L(self.left.inner, _t("Правил пока нет"), fg=MUTED, size=10, bg=BG).pack(anchor="w", padx=px(6))
            for r in rules:
                self._rule_row(r)

    def _lesson_row(self, lesson: dict) -> None:
        p = self.ctx.progress
        lid = lesson["id"]
        ok = lessons.done(p, lid)
        un = lessons.unlocked(p, lesson)
        sel = lid == self.lid and self.tab == "lessons"
        bg = PANEL if sel else BG2
        row = tk.Frame(self.left.inner, bg=bg, highlightthickness=1,
                       highlightbackground=CYAN if sel else LINE, cursor="hand2")
        row.pack(fill=tk.X, pady=px(2), padx=px(1))
        col = GREEN if ok else (AMBER if un else FAINT)
        L(row, f"{lesson['n']:02d}", fg=col, size=15, bold=True, mono=True, bg=bg).pack(
            side=tk.LEFT, padx=(px(8), px(6)), pady=px(4))
        mid = tk.Frame(row, bg=bg)
        mid.pack(side=tk.LEFT, fill=tk.X, expand=True)
        L(mid, lesson["title"], fg=TEXT if un else MUTED, size=11, bold=True, bg=bg).pack(anchor="w")
        L(mid, _t("правил {0} · слов {1}").format(len(lesson["rules"]), len(lesson["words"])),
          fg=MUTED, size=8, bg=bg).pack(anchor="w")
        L(row, "✓" if ok else ("▶" if un else "🔒"), fg=col, size=13, bold=True, bg=bg).pack(
            side=tk.RIGHT, padx=px(8))
        for wdg in (row, mid):
            wdg.bind("<Button-1>", lambda _e, i=lid: self.select_lesson(i))
        for wdg in mid.winfo_children():
            wdg.bind("<Button-1>", lambda _e, i=lid: self.select_lesson(i))

    def _rule_row(self, rule: dict) -> None:
        sel = rule["id"] == self.rid and self.tab == "ref"
        bg = PANEL if sel else BG2
        row = tk.Frame(self.left.inner, bg=bg, highlightthickness=1,
                       highlightbackground=CYAN if sel else LINE, cursor="hand2")
        row.pack(fill=tk.X, pady=px(2), padx=px(1))
        L(row, rule["id"].split("-")[-1].upper(), fg=CYAN, size=8, bold=True, mono=True, bg=bg).pack(
            anchor="w", padx=px(8), pady=(px(4), 0))
        t = L(row, rule["title"], fg=TEXT, size=11, bold=True, bg=bg, wraplength=px(280), justify="left")
        t.pack(anchor="w", padx=px(8))
        L(row, rule.get("short", ""), fg=MUTED, size=8, bg=bg, wraplength=px(280),
          justify="left").pack(anchor="w", padx=px(8), pady=(0, px(4)))
        for wdg in (row, t):
            wdg.bind("<Button-1>", lambda _e, i=rule["id"]: self.show_rule(i))

    # -- правая часть ----------------------------------------------------------
    def _build_right(self) -> None:
        self._clear(self.right.inner)
        if self.view == "rule" and self.rid:
            self._render_rule(self.rid)
        else:
            lesson = lessons.get(self.lid) if self.lid else None
            if lesson:
                self._render_lesson(lesson)
            else:
                L(self.right.inner, _t("Выбери урок слева"), fg=MUTED, size=12, bg=PANEL).pack(
                    anchor="w", padx=px(10), pady=px(10))

    def _render_lesson(self, lesson: dict) -> None:
        p = self.ctx.progress
        lid = lesson["id"]
        ok = lessons.done(p, lid)
        un = lessons.unlocked(p, lesson)
        box = tk.Frame(self.right.inner, bg=PANEL)
        box.pack(fill=tk.BOTH, expand=True, padx=px(10), pady=px(6))
        L(box, _t("УРОК {0:02d}").format(lesson["n"]), fg=CYAN, size=9, bold=True, mono=True, bg=PANEL).pack(anchor="w")
        L(box, lesson["title"], fg=TEXT, size=20, bold=True, bg=PANEL).pack(anchor="w")
        L(box, lesson["goal"], fg=MUTED, size=10, bg=PANEL, wraplength=px(620), justify="left").pack(
            anchor="w", pady=(px(2), px(6)))
        status, col = ((_t("ПРОЙДЕН"), GREEN) if ok else
                       ((_t("ОТКРЫТ"), AMBER) if un else (_t("ЗАКРЫТ · сначала предыдущий урок"), RED)))
        L(box, status, fg=col, size=9, bold=True, bg=PANEL).pack(anchor="w")

        L(box, _t("ПРАВИЛА УРОКА"), fg=MUTED, size=8, bold=True, bg=PANEL).pack(anchor="w", pady=(px(10), px(2)))
        rrow = tk.Frame(box, bg=PANEL)
        rrow.pack(fill=tk.X)
        for rid in lesson["rules"]:
            found = grammar.find(rid)
            if not found:
                continue
            _lv, rule = found
            HudButton(rrow, rule["title"], lambda r=rid: self.show_rule(r), height=30, font_size=9,
                      color=CYAN).pack(side=tk.LEFT, padx=px(2), pady=px(1))
        L(box, _t("Правило откроется справа — из урока не выходишь."), fg=FAINT, size=8, bg=PANEL).pack(anchor="w")

        L(box, _t("СЛОВА УРОКА"), fg=MUTED, size=8, bold=True, bg=PANEL).pack(anchor="w", pady=(px(10), px(2)))
        words = [self.ctx.vocab.get(s) for s in lesson["words"]]
        words = [w for w in words if w]
        L(box, " · ".join(w["word"] for w in words) or _t("слова ещё не загружены"),
          fg=TEXT, size=11, bold=True, bg=PANEL, wraplength=px(640), justify="left").pack(anchor="w")
        L(box, " · ".join(w.get("ru") or "" for w in words), fg=MUTED, size=9, bg=PANEL,
          wraplength=px(640), justify="left").pack(anchor="w")

        L(box, _t("ШАГИ"), fg=MUTED, size=8, bold=True, bg=PANEL).pack(anchor="w", pady=(px(10), px(2)))
        for i, step in enumerate(lesson["steps"], 1):
            L(box, f"{i}. {step}", fg=TEXT, size=9, bg=PANEL, wraplength=px(640), justify="left").pack(anchor="w")

        acts = tk.Frame(box, bg=PANEL)
        acts.pack(anchor="w", pady=px(10))
        HudButton(acts, _t("▶ НАЧАТЬ УРОК"), lambda: self.start(lid), color=GREEN, height=38,
                  font_size=10, width=180).pack(side=tk.LEFT, padx=px(3))
        if lesson["rules"]:
            HudButton(acts, _t("С ПРАВИЛА"), lambda r=lesson["rules"][0]: self.show_rule(r),
                      height=38, font_size=9, width=120).pack(side=tk.LEFT, padx=px(3))
        if not ok:
            HudButton(acts, _t("УРОК ПРОЙДЕН"), lambda: self.mark_done(lid), color=AMBER,
                      height=38, font_size=9, width=150).pack(side=tk.LEFT, padx=px(3))
        else:
            HudButton(acts, _t("ПОВТОРИТЬ"), lambda: self.start(lid), height=38, font_size=9,
                      width=120).pack(side=tk.LEFT, padx=px(3))
        if not un:
            prev = self._prev_lesson(lesson)
            if prev:
                HudButton(acts, _t("← К УРОКУ {0:02d}").format(prev["n"]),
                          lambda i=prev["id"]: self.select_lesson(i), height=38, font_size=9,
                          width=150).pack(side=tk.LEFT, padx=px(3))

    def _render_rule(self, rid: str) -> None:
        found = grammar.find(rid)
        if not found:
            L(self.right.inner, _t("Правило не найдено"), fg=RED, size=12, bg=PANEL).pack(
                anchor="w", padx=px(10), pady=px(10))
            return
        lv, rule = found
        box = tk.Frame(self.right.inner, bg=PANEL)
        box.pack(fill=tk.BOTH, expand=True, padx=px(10), pady=px(6))
        head = tk.Frame(box, bg=PANEL)
        head.pack(fill=tk.X)
        if self.back_lid:
            HudButton(head, _t("← К УРОКУ"), lambda: self.select_lesson(self.back_lid), height=28,
                      font_size=9, width=110).pack(side=tk.LEFT, padx=(0, px(8)))
        L(head, _t("СПРАВОЧНИК · {0}").format(lv), fg=CYAN, size=9, bold=True, mono=True, bg=PANEL).pack(
            side=tk.LEFT)
        L(box, rule["title"], fg=TEXT, size=20, bold=True, bg=PANEL).pack(anchor="w", pady=(px(4), 0))
        L(box, rule.get("short", ""), fg=AMBER, size=10, bg=PANEL, wraplength=px(640), justify="left").pack(
            anchor="w", pady=(px(2), px(8)))
        for sec in rule.get("sections") or []:
            L(box, sec.get("h", ""), fg=CYAN, size=12, bold=True, bg=PANEL).pack(anchor="w", pady=(px(8), px(2)))
            L(box, sec.get("text", ""), fg=TEXT, size=10, bg=PANEL, wraplength=px(650), justify="left").pack(
                anchor="w")
            for ex in sec.get("examples") or []:
                erow = tk.Frame(box, bg=PANEL)
                erow.pack(fill=tk.X, pady=px(1))
                self.ctx.audio_button(erow, "🔊", lambda t=ex.get("en", ""): t, height=24,
                                      font_size=8, width=34).pack(side=tk.LEFT, padx=(0, px(4)))
                txt = tk.Frame(erow, bg=PANEL)
                txt.pack(side=tk.LEFT, fill=tk.X, expand=True)
                L(txt, ex.get("en", ""), fg=GREEN, size=10, mono=True, bg=PANEL, wraplength=px(590),
                  justify="left").pack(anchor="w")
                L(txt, ex.get("ru", ""), fg=MUTED, size=9, bg=PANEL, wraplength=px(590),
                  justify="left").pack(anchor="w")

    # -- действия --------------------------------------------------------------
    def start(self, lid: str) -> None:
        lesson = lessons.get(lid)
        if not lesson:
            return
        if not lessons.unlocked(self.ctx.progress, lesson):
            self.ctx.status(_t("Сначала пройди предыдущий урок"), AMBER)
            return
        ids = [s for s in lesson["words"] if self.ctx.vocab.get(s)]
        if not ids:
            self.ctx.status(_t("Слова урока ещё не загружены"), AMBER)
            return
        lessons.set_current(self.ctx.progress, lid)
        self.ctx.start_session("random", source="filtered", ids=ids)

    def mark_done(self, lid: str) -> None:
        lesson = lessons.get(lid)
        if lesson and not lessons.unlocked(self.ctx.progress, lesson):
            self.ctx.status(_t("Урок ещё закрыт"), AMBER)
            return
        lessons.complete(self.ctx.progress, lid)
        self.ctx.status(_t("Урок пройден. Открыт следующий."), GREEN)
        self.ctx.changed()
        nxt = lessons.next_lesson(self.ctx.progress, self.level)
        if nxt:
            self.lid = nxt["id"]
        self.refresh()

    def _prev_lesson(self, lesson: dict) -> dict | None:
        for other in lessons.plan(self.level):
            if int(other["n"]) == int(lesson["n"]) - 1:
                return other
        return None

    # -- утилиты ---------------------------------------------------------------
    def _message(self, title: str, text: str) -> None:
        self._clear(self.left.inner)
        self._clear(self.right.inner)
        L(self.left.inner, title, fg=AMBER, size=12, bold=True, bg=BG).pack(anchor="w", padx=px(4))
        L(self.right.inner, text, fg=MUTED, size=10, bg=PANEL).pack(anchor="w", padx=px(10), pady=px(10))

    @staticmethod
    def _clear(frame) -> None:
        for c in frame.winfo_children():
            c.destroy()
