"""Единый блок проверки произношения — тот же, что в СКАНЕРЕ (pages_main.ScannerPage).

Раскладка как в сканере: слева «СОВПАДЕНИЕ: N%» (ui.MatchReadout) + строка заметки,
справа на постоянном месте кнопка ПЕРЕДАЧА (mic.MicPanel). Клавиши и пороги — speech_std:
M — микрофон, T (держать) — подсказка, ≥80% — через ADVANCE_MS дальше, ниже — остаёмся.
Все экраны с проверкой речи строят именно этот блок (см. tests/test_english_unified_check.py).
"""
from __future__ import annotations

import tkinter as tk

from stamina.i18n import t as _t
from stamina.theme import AMBER, MUTED, px

from .mic import MicPanel
from .speech_std import advance_later, passed
from .textutil import score_sentence
from .ui import L, MatchReadout, target_missed


class HoldGrab:
    """Удержание кнопки «💡 ПОДСКАЗКА»: нажал — показать, отпустил — скрыть.

    grab держит отпускание даже вне кнопки (смена RU→EN двигает вёрстку и курсор «уезжает»).
    Один помощник для книги, склада и всех экранов с подсказкой-удержанием.
    """

    def __init__(self) -> None:
        self.btn = None

    def bind(self, btn, on_down, on_up) -> None:
        btn.command = None  # не клик, а удержание
        btn.bind("<ButtonPress-1>", lambda _e: on_down(btn), add="+")
        btn.bind("<ButtonRelease-1>", lambda _e: on_up(), add="+")

    def take(self, btn) -> None:
        if btn is None:
            return
        self.btn = btn
        try:
            btn.grab_set()
        except tk.TclError:
            self.btn = None

    def release(self) -> None:
        btn, self.btn = self.btn, None
        if btn is None:
            return
        try:
            btn.grab_release()
        except tk.TclError:
            pass


class SpeechCheck(tk.Frame):
    """API: .mic, .match, .note; toggle(), reset(), clear(), evaluate(), judge(), hint_down/up()."""

    def __init__(self, master, ctx, on_result, bg=None) -> None:
        bg = bg or master.cget("bg")
        super().__init__(master, bg=bg)
        self.ctx = ctx
        self.grid_columnconfigure(0, weight=1)
        left = tk.Frame(self, bg=bg)
        left.grid(row=0, column=0, sticky="nsew")
        self.keys = L(left, _t("M — микрофон · T (держать) — подсказка · ≥80% — дальше"),
                      fg=MUTED, size=8, bg=bg)
        self.keys.pack(anchor="w")
        self.hint = L(left, "", fg=AMBER, size=10, bg=bg, wraplength=px(560), justify="left")
        self.hint.pack(anchor="w")
        self.match = MatchReadout(left)
        self.match.pack(fill=tk.X, pady=(px(4), 0))
        self.note = L(left, "", fg=MUTED, size=9, bg=bg, wraplength=px(560), justify="left")
        self.note.pack(anchor="w")
        self.mic: MicPanel | None = None
        if hasattr(ctx, "asr"):
            self.mic = MicPanel(self, ctx, on_result, bg=bg)
            self.mic.grid(row=0, column=1, sticky="n", padx=px(10))
        else:
            L(self, _t("Микрофон доступен в приложении"), fg=MUTED, size=8,
              bg=bg).grid(row=0, column=1, sticky="n", padx=px(10))

    # -- микрофон -------------------------------------------------------------
    def toggle(self) -> None:
        if self.mic is not None:
            self.mic.toggle()

    def reset(self) -> None:
        if self.mic is not None:
            try:
                self.mic.reset()
            except Exception:  # noqa: BLE001
                pass

    def clear(self) -> None:
        self.match.clear()
        self.hint.configure(text="")

    # -- подсказка T ----------------------------------------------------------
    def hint_down(self, text: str) -> None:
        self.hint.configure(text=text or _t("подсказки нет"))

    def hint_up(self) -> None:
        self.hint.configure(text="")

    HoldGrab = HoldGrab  # SpeechCheck.HoldGrab — общий помощник удержания подсказки

    # -- оценка ---------------------------------------------------------------
    def evaluate(self, target: str, alts, self_score, keyword: str = ""):
        """Оценить попытку как сканер и показать «СОВПАДЕНИЕ». None — нечего оценивать."""
        if self_score is not None:
            score, marks, heard = int(self_score), None, ""
        else:
            if not alts or not target:
                return None
            level = self.ctx.progress.settings.get("speech_strictness", "normal")
            res = [(score_sentence(target, a, keyword, strictness=level), a) for a in alts]
            (score, marks), heard = max(res, key=lambda r: r[0][0])
        self.match.set(score, marks, heard, bool(marks) and bool(keyword) and target_missed(marks, keyword),
                       self_rated=self_score is not None)
        return score, marks, heard

    def judge(self, score: int, step, still_same) -> bool:
        """Звук и единый переход: ≥80% — дальше через паузу, иначе остаёмся на месте."""
        ok = passed(score)
        try:
            self.ctx.sfx("click" if ok else "error")
        except Exception:  # noqa: BLE001
            pass
        if ok:
            advance_later(self, step, still_same)
        return ok
