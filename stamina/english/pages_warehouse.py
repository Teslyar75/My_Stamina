"""Вкладка «СКЛАД КАРТОЧЕК»: перебор собранных карточек (RU → микрофон ≥ 80% → EN + TTS)."""
from __future__ import annotations

from stamina.i18n import t as _t

import random
import tkinter as tk

from stamina.hud import HudButton, HudPanel
from stamina.theme import AMBER, BG, CYAN, GREEN, MUTED, PANEL, RED, TEXT, px

from .mic import MicPanel
from .textutil import score_word, verdict
from .ui import L, MatchReadout, Strip
from . import warehouse as wh
from .vocab import POS_SHORT

VCOL = {"green": GREEN, "amber": AMBER, "red": RED}


def _clear(frame) -> None:
    for c in frame.winfo_children():
        c.destroy()


class WarehousePage(tk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.cards: list[dict] = []
        self.i = 0
        self.diff_filter: int | None = None
        self.flipped = False
        self._last_score: int | None = None

        self.strip = Strip(self)
        self.strip.pack(fill=tk.X, padx=px(12), pady=(px(4), 0))

        filt = tk.Frame(self, bg=BG)
        filt.pack(fill=tk.X, padx=px(12), pady=(px(4), 0))
        L(filt, _t("СЛОЖНОСТЬ"), fg=MUTED, size=8, bold=True, bg=BG).pack(side=tk.LEFT, padx=(0, px(6)))
        self._filt_btns: dict[int | None, HudButton] = {}
        for key, label in ((None, _t("ВСЕ")), (1, "★"), (2, "★★"), (3, "★★★")):
            b = HudButton(filt, label, lambda k=key: self.set_filter(k), height=28, font_size=9, width=70)
            b.pack(side=tk.LEFT, padx=px(2))
            self._filt_btns[key] = b

        self.panel = HudPanel(self, _t("СКЛАД КАРТОЧЕК"))
        self.panel.pack(fill=tk.BOTH, expand=True, padx=px(60), pady=px(8))
        self.body = self.panel.body

        self.btns = tk.Frame(self, bg=BG)
        self.btns.pack(pady=(0, px(12)))

        self.mic: MicPanel | None = None
        self.match: MatchReadout | None = None

    # -- данные ------------------------------------------------------------------
    def refresh(self) -> None:
        self.cards = wh.collect_cards(self.ctx.progress, self.ctx.vocab, difficulty=self.diff_filter)
        if self.i >= len(self.cards):
            self.i = max(0, len(self.cards) - 1)
        self.flipped = False
        self._last_score = None
        for k, b in self._filt_btns.items():
            b.set_active(k == self.diff_filter)
        self.render()

    def set_filter(self, d: int | None) -> None:
        self.diff_filter = d
        self.i = 0
        self.refresh()

    def shuffle(self) -> None:
        if len(self.cards) > 1:
            random.shuffle(self.cards)
            self.i = 0
            self.flipped = False
            self._last_score = None
            self.render()

    def step(self, d: int) -> None:
        if not self.cards:
            return
        self.i = (self.i + d) % len(self.cards)
        self.flipped = False
        self._last_score = None
        self.render()

    # -- отрисовка ---------------------------------------------------------------
    def render(self) -> None:
        _clear(self.body)
        _clear(self.btns)
        self.mic = None
        self.match = None
        stats = wh.ensure_stats(self.ctx.progress)
        n = len(self.cards)
        self.strip.set(
            _t("СКЛАД КАРТОЧЕК · {0}").format(n),
            _t("Сначала русский → скажи слово в микрофон (≥ {0}%) → английский и голос.").format(wh.FLIP_OK),
            (stats["ok"] / max(1, stats["flips"])) if stats["flips"] else 0.0,
            _t("{0} ок / {1} попыток").format(stats["ok"], stats["flips"]),
        )
        if not self.cards:
            L(self.body, _t("СКЛАД ПОКА ПУСТ"), fg=AMBER, size=22, bold=True).pack(pady=(px(50), px(8)))
            L(self.body,
              _t("Сюда попадают слова, которые ты уже знаешь или выучил,\n"
                 "и у которых в СКАНЕРЕ пройдены все примеры (≥ {0}%).").format(wh.SENT_PASS),
              fg=MUTED, size=11, justify="center").pack()
            HudButton(self.btns, _t("ОТКРЫТЬ СКАНЕР"), lambda: self.ctx.show("scanner"),
                      color=CYAN, height=36).pack(side=tk.LEFT, padx=px(4))
            HudButton(self.btns, _t("ПРОВЕРКА СИСТЕМ"), lambda: self.ctx.show("review"),
                      color=AMBER, height=36).pack(side=tk.LEFT, padx=px(4))
            return

        card = self.cards[self.i]
        L(self.body,
          _t("#{0} · {1} · {2} · {3} / {4}").format(
              card["rank"], POS_SHORT.get(card["pos"], (card["pos"] or "").upper()),
              wh.difficulty_text(card["difficulty"]), self.i + 1, n),
          fg=MUTED, size=8, bold=True, mono=True).pack(pady=(px(16), px(4)))

        if not self.flipped:
            L(self.body, _t("СКАЖИ ПО-АНГЛИЙСКИ"), fg=MUTED, size=9).pack()
            L(self.body, card["ru"] or _t("(перевод не найден)"),
              fg=TEXT, size=22, bold=True, wraplength=px(720), justify="center").pack(pady=px(10))
            box = tk.Frame(self.body, bg=PANEL)
            box.pack(pady=px(8))
            self.mic = MicPanel(box, self.ctx, self.on_speech)
            self.mic.pack()
            self.match = MatchReadout(self.body)
            self.match.pack(fill=tk.X, padx=px(20), pady=(px(8), 0))
            if self._last_score is not None:
                text, vk = verdict(self._last_score)
                L(self.body, _t("Совпадение {0}% · {1} — нужно ≥ {2}%").format(
                    self._last_score, text, wh.FLIP_OK),
                  fg=VCOL[vk], size=11).pack(pady=px(4))
        else:
            L(self.body, card["word"], fg=CYAN, size=34, bold=True, mono=True).pack(pady=(px(20), px(4)))
            if card["respelling"] or card["ipa"]:
                L(self.body, f"[ {card['respelling']} ]  {card['ipa']}",
                  fg=MUTED, size=14, mono=True).pack()
            L(self.body, card["ru"], fg=AMBER, size=14, bold=True, wraplength=px(720)).pack(pady=px(8))
            if self._last_score is not None:
                text, vk = verdict(self._last_score)
                L(self.body, _t("Совпадение {0}% · {1}").format(self._last_score, text),
                  fg=VCOL[vk], size=12, bold=True).pack(pady=px(4))
            self.ctx.audio_button(self.body, _t("🔊 ГОЛОС"), lambda: card["word"],
                                  height=32, font_size=10).pack(pady=px(6))

        HudButton(self.btns, _t("← НАЗАД"), lambda: self.step(-1), height=36, width=120).pack(side=tk.LEFT, padx=px(4))
        HudButton(self.btns, _t("ПЕРЕМЕШАТЬ"), self.shuffle, color=AMBER, height=36, width=140).pack(
            side=tk.LEFT, padx=px(4))
        if self.flipped:
            HudButton(self.btns, _t("СЛЕДУЮЩАЯ →"), lambda: self.step(1), color=GREEN,
                      height=36, width=150).pack(side=tk.LEFT, padx=px(4))
        else:
            HudButton(self.btns, _t("ПРОПУСТИТЬ →"), lambda: self.step(1), height=36, width=140).pack(
                side=tk.LEFT, padx=px(4))

    # -- речь --------------------------------------------------------------------
    def on_speech(self, alts, self_score) -> None:
        if self.flipped or not self.cards:
            return
        card = self.cards[self.i]
        w = self.ctx.vocab.get(card["slug"]) or {}
        if self_score is not None:
            score = self_score
            heard = ""
        else:
            if not alts:
                return
            score = score_word(card["word"], alts, w.get("sounds_like"))
            heard = alts[0]
        self._last_score = score
        if self.match is not None:
            self.match.set(score, None, heard, False, self_rated=self_score is not None)
        ok = score >= wh.FLIP_OK
        xp = wh.record_flip(self.ctx.progress, card["slug"], score, ok=ok)
        if ok:
            self.flipped = True
            self.ctx.sfx("click")
            self.ctx.say(card["word"])
            if xp:
                self.ctx.status(_t("Склад: «{0}» · +{1} XP").format(card["word"], xp), GREEN)
            else:
                self.ctx.status(_t("Склад: «{0}» · совпадение {1}%").format(card["word"], score), GREEN)
            self.render()
        else:
            self.ctx.sfx("error")
            text, vk = verdict(score)
            self.ctx.status(_t("Ещё раз: {0}% · нужно ≥ {1}%").format(score, wh.FLIP_OK), VCOL[vk])
            # обновить подпись под match без полной перерисовки mic
            self.render()

    def on_key(self, e) -> None:
        k = e.keysym.lower()
        if k in ("left", "a"):
            self.step(-1)
        elif k in ("right", "d") or (k == "space" and self.flipped):
            self.step(1)
        elif k == "m" and self.mic is not None and not self.flipped:
            self.mic.toggle()
        elif k == "r":
            self.shuffle()
