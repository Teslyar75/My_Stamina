"""Кнопка микрофона «ПЕРЕДАЧА» с живым текстом и самооценкой при недоступном распознавании."""
from __future__ import annotations

from stamina.i18n import t as _t

import tkinter as tk

from stamina.hud import HudButton
from stamina.theme import AMBER, BG2, GREEN, LINE, MUTED, RED, TEXT, blend, px

from .ui import L


class LevelMeter(tk.Canvas):
    """Живой индикатор громкости микрофона: 20 сегментов (зелёный → янтарный → красный)."""

    SEG = 20

    def __init__(self, master, width: int = 210, height: int = 12) -> None:
        super().__init__(master, bg=master.cget("bg"), highlightthickness=0, bd=0,
                         width=px(width), height=px(height))
        self.level = 0.0
        self.bind("<Configure>", lambda _e: self._draw())

    def set(self, rms: float) -> None:
        # RMS 0.003 (тишина) … 0.3 (громко) → 0…1 по логарифмической шкале
        import math
        v = 0.0 if rms <= 0.002 else min(1.0, max(0.0, (math.log10(rms) + 2.7) / 2.2))
        self.level = max(v, self.level * 0.6)  # плавный спад
        self._draw()

    def clear(self) -> None:
        self.level = 0.0
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20:
            return
        gap = px(2)
        sw = (w - gap * (self.SEG - 1)) / self.SEG
        filled = round(self.level * self.SEG)
        for i in range(self.SEG):
            x = i * (sw + gap)
            t = i / (self.SEG - 1)
            col = GREEN if t < 0.6 else (AMBER if t < 0.85 else RED)
            on = i < filled
            self.create_rectangle(x, 1, x + sw, h - 1, fill=col if on else BG2,
                                  outline=col if on else blend(LINE, BG2, 0.3))


class MicPanel(tk.Frame):
    def __init__(self, master, ctx, on_result, bg=None) -> None:
        bg = bg or master.cget("bg")
        super().__init__(master, bg=bg)
        self.ctx, self.on_result = ctx, on_result
        self.btn = HudButton(self, _t("🎤 ПЕРЕДАЧА  M"), self.toggle, color=RED, height=44, font_size=12, width=210)
        self.btn.pack(pady=(0, px(4)))
        self.meter = LevelMeter(self)
        self.meter.pack(pady=(0, px(4)))
        self.live = L(self, "", fg=MUTED, size=9, bg=bg, wraplength=px(260), justify="center")
        self.live.pack()
        self._silent = ""
        self.selfbox = tk.Frame(self, bg=bg)
        L(self.selfbox, _t("Оцени себя после прослушивания образца:"), fg=MUTED, size=8, bg=bg).pack()
        row = tk.Frame(self.selfbox, bg=bg)
        row.pack(pady=px(2))
        for text, score, col in ((_t("СКАЗАЛ ХОРОШО"), 90, GREEN), (_t("ТАК СЕБЕ"), 60, AMBER), (_t("НЕ ПОЛУЧИЛОСЬ"), 20, RED)):
            HudButton(row, text, lambda s=score: self._self(s), color=col, height=28, font_size=8).pack(
                side=tk.LEFT, padx=px(2))
        self._polling = False
        self.refresh_mode()

    def speech_on(self) -> bool:
        return bool(self.ctx.progress.settings.get("asr", True)) and self.ctx.asr.available()

    def refresh_mode(self) -> None:
        if self.speech_on():
            self.btn.pack(pady=(0, px(4)))
            self.selfbox.pack_forget()
            self.live.configure(text=_t("Нажми и прочитай вслух. Запись остановится сама после паузы."))
        else:
            self.btn.pack_forget()
            if self.ctx.progress.settings.get("self_assess", True):
                self.selfbox.pack()
            why = self.ctx.asr.why_unavailable() if self.ctx.progress.settings.get("asr", True) else _t("выключено в настройках")
            self.live.configure(text=_t("Распознавание недоступно: {0}").format(why))

    def _btn_idle(self) -> None:
        self.btn.set_text(_t("🎤 ПЕРЕДАЧА  M"))
        self.btn.set_color(RED)
        self.btn.set_active(False)
        self.meter.clear()

    def reset(self) -> None:
        self.ctx.asr.stop()
        self._btn_idle()
        self.refresh_mode()

    def toggle(self) -> None:
        asr = self.ctx.asr
        if asr.listening:
            asr.stop()
            return
        if not self.speech_on():
            self.refresh_mode()
            return
        self.ctx.tts.stop()
        asr.poll()  # очистить старые события
        self._silent = ""
        if asr.listen():
            self.btn.set_text(_t("● СЛУШАЮ…"))
            self.btn.set_color(RED)
            self.btn.set_active(True)
            self.meter.clear()
            self.live.configure(text=_t("Включаю микрофон… (при первом запуске загружается модель)"), fg=AMBER)
            if not self._polling:
                self._polling = True
                self.after(80, self._poll)

    def _poll(self) -> None:
        if not self.winfo_exists():
            self._polling = False
            self.ctx.asr.stop()
            return
        done = False
        for kind, val in self.ctx.asr.poll():
            if kind == "started":
                self.live.configure(text=_t("● Говори — полоска выше показывает, что звук доходит"), fg=RED)
            elif kind == "level":
                self.meter.set(val)
            elif kind == "processing":
                self.btn.set_text(_t("◌ РАСПОЗНАЮ…"))
                self.btn.set_color(AMBER)
                self.meter.clear()
                self.live.configure(text=_t("Распознаю речь…"), fg=AMBER)
            elif kind == "silent":
                self._silent = val
            elif kind == "partial":
                self.live.configure(text=f"«{val}»", fg=TEXT)
            elif kind == "final":
                done = True
                self.live.configure(text=_t("Распознано: «{0}»").format(val[0]) if val else
                                    (self._silent or _t("Звук был, но слова не распознаны — попробуй ещё раз чётче")),
                                    fg=TEXT if val else (RED if self._silent else AMBER))
                if not val and self._silent:
                    self.ctx.status(self._silent, RED)
                self.on_result(val, None)
            elif kind == "error":
                done = True
                self.live.configure(text=_t("Ошибка микрофона: {0}").format(val), fg=RED)
                self.ctx.status(_t("Ошибка микрофона: {0}").format(val), RED)
        if done or (not self.ctx.asr.listening and self.ctx.asr.events.empty()):
            self._polling = False
            self._btn_idle()
            return
        self.after(80, self._poll)

    def _self(self, score: int) -> None:
        self.on_result(None, score)
