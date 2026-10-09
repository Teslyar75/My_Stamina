"""Экран «Мостик» — тренировка: иллюминатор, приборы, клавиатура, UPLINK."""

from __future__ import annotations

import time
import tkinter as tk
from typing import TYPE_CHECKING

from stamina import layouts, missions, theme
from stamina.engine import DONE, ERROR, TypingEngine
from stamina.hud import (
    HudButton, HudKeyboard, HudPanel, Readouts, RingGauge, SegmentBar, SpeedGauge,
    TranslatorPanel, Viewport,
)
from stamina.session_storage import SessionState, clear_session, save_session
from stamina.theme import (
    AMBER, BG, CYAN, GREEN, LINE, LINE_HI, MUTED, PANEL, RED, TEXT, blend,
    chamfer, px,
)

if TYPE_CHECKING:
    from stamina.cockpit import Cockpit

FONT_SIZES = {"S": 20, "M": 26, "L": 32}


def fmt_time(sec: float) -> str:
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", " ")


class MissionStrip(tk.Canvas):
    """Заголовок миссии + цель + полоса прогресса."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, bg=BG, highlightthickness=0, bd=0, height=px(52))
        self.title = "ОЖИДАНИЕ ЗАДАНИЯ"
        self.subtitle = "Выберите миссию или загрузите свой текст"
        self.progress = 0.0
        self.progress_text = ""
        self.bind("<Configure>", lambda _e: self.redraw())

    def set(self, *, title=None, subtitle=None, progress=None, progress_text=None) -> None:
        changed = False
        for name, val in (("title", title), ("subtitle", subtitle), ("progress", progress),
                          ("progress_text", progress_text)):
            if val is not None and getattr(self, name) != val:
                setattr(self, name, val)
                changed = True
        if changed:
            self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50:
            return
        self.create_polygon(px(2), px(8), px(10), px(8), px(10), h - px(8), px(2), h - px(8),
                            fill=AMBER, outline="")
        self.create_text(px(20), px(16), text=self.title, anchor="w", fill=TEXT,
                         font=theme.font(14, True))
        self.create_text(px(20), px(38), text=self.subtitle, anchor="w", fill=MUTED,
                         font=theme.font(9))
        bw = min(px(380), w * 0.34)
        x2 = w - px(4)
        x1 = x2 - bw
        y1, y2 = px(26), px(40)
        self.create_polygon(chamfer(x1, y1, x2, y2, px(5)), fill=PANEL, outline=LINE_HI)
        fill_w = (bw - px(4)) * max(0.0, min(1.0, self.progress))
        if fill_w > 1:
            self.create_rectangle(x1 + px(2), y1 + px(3), x1 + px(2) + fill_w, y2 - px(3),
                                  fill=CYAN, outline="")
        for i in range(1, 10):
            x = x1 + bw * i / 10
            self.create_line(x, y1 + px(2), x, y2 - px(2), fill=blend(BG, LINE, 0.5))
        self.create_text(x1, px(14), text="ПРОГРЕСС МАРШРУТА", anchor="w", fill=MUTED,
                         font=theme.font(8, True))
        self.create_text(x2, px(14), text=self.progress_text, anchor="e", fill=CYAN,
                         font=theme.font(9, True, mono=True))


class Bridge(tk.Frame):
    def __init__(self, master: tk.Misc, app: "Cockpit") -> None:
        super().__init__(master, bg=BG)
        self.app = app
        self.engine: TypingEngine | None = None
        self.meta: dict = {}
        self.state = "idle"        # idle | ready | run | pause | done
        self._session_dirty = False
        self._last_persist = 0.0
        self._segments = None
        self._seg_i: int | None = None
        self._seg_key: str | None = None
        self._tr_dir = ("en", "ru")
        self._last_retry = 0.0
        self._last_stats = 0.0
        self._segments = None
        self._seg_i = None
        self._seg_key = None
        self._word_key = None
        self._word_src = None
        self.debrief: HudPanel | None = None
        self._build()

    # ------------------------------------------------------------------
    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=0, minsize=px(220))
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0, minsize=px(220))
        self.grid_rowconfigure(3, weight=1)

        self.strip = MissionStrip(self)
        self.strip.grid(row=0, column=0, columnspan=3, sticky="ew", padx=px(10), pady=(px(6), 0))

        st = self.app.store.settings
        self.viewport = Viewport(self, FONT_SIZES.get(st["font"], 26))
        self.viewport.grid(row=1, column=0, columnspan=3, sticky="ew", padx=px(10), pady=px(6))

        self.uplink = TranslatorPanel(self)
        self.uplink.grid(row=2, column=0, columnspan=3, sticky="ew", padx=px(10), pady=(0, px(6)))
        self.uplink.grid_remove()

        left = HudPanel(self, "ДВИГАТЕЛЬ")
        left.grid(row=3, column=0, sticky="nsew", padx=(px(10), px(5)), pady=(0, px(8)))
        self.speed = SpeedGauge(left.body)
        self.speed.pack(fill=tk.BOTH, expand=True)
        self.rhythm = SegmentBar(left.body, "РИТМ ПЕЧАТИ", color="auto")
        self.rhythm.pack(fill=tk.X, pady=(px(4), 0))

        center = HudPanel(self, "НАВИГАЦИЯ ПАЛЬЦЕВ", accent=AMBER)
        center.grid(row=3, column=1, sticky="nsew", padx=px(5), pady=(0, px(8)))
        self.center = center
        self.keyboard = HudKeyboard(center.body)
        self.keyboard.pack(fill=tk.BOTH, expand=True)
        self.keyboard.set_zones(st["zones"])
        bar = tk.Frame(center.body, bg=PANEL)
        bar.pack(fill=tk.X, pady=(px(4), 0))
        self.btn_pause = HudButton(bar, "❚❚ ПАУЗА  Esc", self.toggle_pause, height=28, font_size=9,
                                   width=180)
        self.btn_pause.pack(side=tk.LEFT)
        HudButton(bar, "↻ ЗАНОВО  F5", self.app.restart_current, height=28,
                  font_size=9).pack(side=tk.LEFT, padx=px(6))
        self.btn_heat = HudButton(bar, "ТЕПЛОВАЯ КАРТА", self.toggle_heat, height=28,
                                  font_size=9, color=AMBER)
        self.btn_heat.pack(side=tk.RIGHT)
        self.legend = tk.Label(bar, text="", bg=PANEL, fg=MUTED, font=theme.font(8))
        self.legend.pack(side=tk.RIGHT, padx=px(8))
        if not st["keyboard"]:
            self.keyboard.pack_forget()

        self.living = None
        right = HudPanel(self, "ТЕЛЕМЕТРИЯ")
        right.grid(row=3, column=2, sticky="nsew", padx=(px(5), px(10)), pady=(0, px(8)))
        self.ring = RingGauge(right.body)
        self.ring.pack(fill=tk.BOTH, expand=True)
        self.readouts = Readouts(right.body, rows=4)
        self.readouts.pack(fill=tk.X)
        self.panels = [left, center, right]

        self._setup_living()
        self.show_idle()
        self.refresh_stats()

    # ------------------------------------------------------------------
    # «Живой космос» (прототип)
    # ------------------------------------------------------------------
    def _setup_living(self) -> None:
        from stamina import living_space
        mode = self.app.store.settings.get("living_space", "full")
        old = getattr(self, "living", None)
        if old is not None:
            old.disable()
            self.living = None
        on = living_space.available() and mode in ("light", "full")
        glass = [self.panels[0], self.panels[1], self.panels[2], self.uplink, self.strip,
                 self.speed, self.rhythm, self.keyboard, self.ring, self.readouts]
        for c in glass:
            c.glass = on
        self.viewport.living = on
        if on:
            self.living = living_space.LivingSpace(self, mode)
            self.living.add_sharp(self.viewport)
            for c in glass:
                self.living.add_glass(c)
            self.living.enable()
        for c in self.panels + [self.uplink]:
            c.event_generate("<Configure>")
        self.viewport._rebuild()

    # ------------------------------------------------------------------
    # Старт / состояние
    # ------------------------------------------------------------------
    def show_idle(self, message: str = "ПУЛЬТ ГОТОВ К ПОЛЁТУ",
                  sub: str = "Ctrl+2 — миссии   ·   Ctrl+3 — свой текст   ·   Ctrl+4 — бортжурнал") -> None:
        self.state = "idle" if self.engine is None else self.state
        self.viewport.set_state(mode="idle", message=message, sub_message=sub,
                                status="ОЖИДАНИЕ", status_color=MUTED, finger="")
        self.keyboard.highlight(None)

    def start(self, text: str, *, mode: str, title: str, subtitle: str,
              mission: dict | None = None, resume: SessionState | None = None,
              original: str = "", case_sensitive: bool = False, process=None) -> None:
        self.leave_current()
        self.hide_debrief()
        if resume is not None:
            self.engine = TypingEngine(text, index=resume.index, typed=resume.typed,
                                       errors=resume.errors, elapsed=resume.elapsed,
                                       case_sensitive=case_sensitive)
        else:
            self.engine = TypingEngine(text, case_sensitive=case_sensitive)
        lang = missions.detect_lang(text)
        self.meta = {"mode": mode, "title": title, "subtitle": subtitle,
                     "mission": mission, "lang": lang, "original": original,
                     "process": process}
        self.state = "ready"
        self.keyboard.set_lang(lang)
        self.keyboard.set_heat(None)
        self.btn_heat.set_active(False)
        self._tr_dir = ("en", "ru") if lang == "en" else ("ru", "en")
        self._setup_uplink()
        sub = ""
        if resume is not None:
            sub = (f"Продолжение: {fmt_int(resume.index)} из {fmt_int(len(text))} "
                   f"({resume.index / max(1, len(text)) * 100:.0f}%)")
        self.viewport.set_state(text=text, index=self.engine.index, mode="ready",
                                sub_message=sub, status="К ЗАПУСКУ ГОТОВ", status_color=AMBER)
        self.strip.set(title=title, subtitle=subtitle)
        self._update_cursor()
        self.refresh_stats()
        self.app.sound.start()
        self.app.focus_set()

    def leave_current(self) -> None:
        """Сохранить текущий заход перед переключением (журнал + сессия груза)."""
        if self.engine is None or self.state == "done":
            return
        now = time.perf_counter()
        if self.meta.get("mode") == "cargo":
            self.persist(force=True)
        seg = self.engine.segment(now)
        if seg["chars"] >= 30:
            self._record_run(seg, stars=0, partial=True)
            self.engine.mark_segment_saved(now)

    def _record_run(self, seg: dict, stars: int, partial: bool = False) -> int:
        xp = missions.xp_for(seg["chars"], seg["acc"], stars)
        m = self.meta.get("mission")
        run = dict(seg, mode=self.meta.get("mode"), title=self.meta.get("title"),
                   mission=m["id"] if m else None, stars=stars, xp=xp, partial=partial)
        self.app.store.add_run(run)
        self.app.update_rank()
        return xp

    # ------------------------------------------------------------------
    # Клавиатура
    # ------------------------------------------------------------------
    def on_key(self, e: tk.Event) -> None:
        if self.debrief is not None:
            self._debrief_key(e)
            return
        ks = e.keysym
        eng = self.engine
        if ks == "Escape":
            self.toggle_pause()
            return
        if eng is None or eng.finished:
            return
        if self.state == "pause":
            if ks in ("space", "Return"):
                self.resume()
            return
        if e.state & 0x4:      # Ctrl+что-то — не печать
            return
        ch = e.char
        if not ch or len(ch) != 1 or not ch.isprintable():
            return
        now = time.perf_counter()
        expected = eng.current
        res = eng.press(ch, now)
        if res is None:
            return
        ok = res != ERROR
        self.app.store.record_key(expected, ok)
        if ok:
            self.app.sound.click()
        else:
            self.app.sound.error()
            hint = ""
            if expected.isalpha() and ch.isalpha() and \
                    layouts.is_cyrillic(ch) != layouts.is_cyrillic(expected):
                hint = "ПЕРЕКЛЮЧИТЕ РАСКЛАДКУ (Alt+Shift)"
            self.viewport.flash_error(ch, expected, hint)
            self.keyboard.flash(layouts.key_for_char(expected, self.meta.get("lang", "en")))
        if self.state == "ready":
            self.state = "run"
        if self.meta.get("mode") == "cargo":
            self._session_dirty = True
        if res == DONE:
            self.finish()
            return
        if ok:
            self._update_cursor()
        self.refresh_stats()

    def _update_cursor(self) -> None:
        eng = self.engine
        if eng is None:
            return
        cur = eng.current
        lang = self.meta.get("lang", "en")
        finger = layouts.finger_for_char(cur, lang)
        finger_info = ""
        if finger is not None and layouts.FINGER_NAMES.get(finger):
            name = layouts.FINGER_NAMES[finger]
            if layouts.needs_shift(cur, lang):
                name += " + Shift другой рукой"
            finger_info = (name, layouts.FINGER_COLORS[finger])
        mode = "pause" if self.state == "pause" else ("ready" if self.state == "ready" else "run")
        status = {"ready": ("К ЗАПУСКУ ГОТОВ", AMBER), "run": ("● В ПОЛЁТЕ", GREEN),
                  "pause": ("❚❚ ПАУЗА", AMBER)}[mode]
        self.viewport.set_state(index=eng.index, mode=mode, finger=finger_info,
                                status=status[0], status_color=status[1])
        self.keyboard.highlight(layouts.key_for_char(cur, lang))
        self._update_uplink()

    # ------------------------------------------------------------------
    # Пауза
    # ------------------------------------------------------------------
    def toggle_pause(self) -> None:
        if self.state == "pause":
            self.resume()
        elif self.state in ("run", "ready"):
            self.pause()

    def pause(self, sub: str = "") -> None:
        if self.engine is None or self.state not in ("run", "ready"):
            return
        self.engine.pause(time.perf_counter())
        self._prev_state = self.state
        self.state = "pause"
        self.viewport.set_state(sub_message=sub)
        self._update_cursor()
        self.btn_pause.set_text("▶ ПРОДОЛЖИТЬ  Esc")
        self.persist(force=True)
        self.refresh_stats()

    def resume(self) -> None:
        if self.engine is None or self.state != "pause":
            return
        self.engine.resume()
        self.state = getattr(self, "_prev_state", "run")
        self.viewport.set_state(sub_message="")
        self.btn_pause.set_text("❚❚ ПАУЗА  Esc")
        self._update_cursor()
        self.app.focus_set()

    # ------------------------------------------------------------------
    # Завершение и отчёт
    # ------------------------------------------------------------------
    def finish(self) -> None:
        eng = self.engine
        now = time.perf_counter()
        seg = eng.segment(now)
        m = self.meta.get("mission")
        stars = 0
        if m:
            stars = missions.stars_for(seg["acc"], seg["cpm"], m["goal"])
            self.app.store.update_mission(m["id"], stars, seg["cpm"], seg["acc"])
        old_rank = missions.rank_for(self.app.store.stats["xp"])[0]
        xp = self._record_run(seg, stars)
        new_rank = missions.rank_for(self.app.store.stats["xp"])[0]
        if self.meta.get("mode") == "cargo":
            clear_session()
            self._session_dirty = False
        self.state = "done"
        passed = stars > 0 or not m
        if passed:
            self.app.sound.bell()
        else:
            self.app.sound.error()
        self.viewport.set_state(mode="done",
                                message="МИССИЯ ВЫПОЛНЕНА" if passed else "МИССИЯ НЕ ЗАСЧИТАНА",
                                sub_message="", status="ФИНИШ", status_color=GREEN if passed else RED,
                                finger="")
        self.keyboard.highlight(None)
        self.strip.set(progress=1.0)
        weak = sorted(((ch, s[1]) for ch, s in eng.key_stats.items() if s[1] > 0 and ch != " "),
                      key=lambda x: x[1], reverse=True)[:5]
        self.show_debrief(seg, stars, xp, passed, weak,
                          new_rank if new_rank != old_rank else None)
        self.refresh_stats()
        self.app.screens["missions"].refresh()

    def show_debrief(self, seg, stars, xp, passed, weak, new_rank) -> None:
        self.hide_debrief()
        m = self.meta.get("mission")
        accent = GREEN if passed else RED
        panel = HudPanel(self, "ОТЧЁТ О ПОЛЁТЕ", accent=accent, pad=16)
        self.debrief = panel
        panel.place(relx=0.5, rely=0.56, anchor="center", relwidth=0.7, relheight=0.76)
        b = panel.body
        if m:
            title = "МИССИЯ ВЫПОЛНЕНА" if passed else "МИССИЯ НЕ ЗАСЧИТАНА"
        else:
            title = "ГРУЗ ДОСТАВЛЕН — ТЕКСТ ПРОЙДЕН"
        tk.Label(b, text=title, bg=PANEL, fg=accent, font=theme.font(20, True)).pack(pady=(0, px(2)))
        if m:
            tk.Label(b, text="★" * stars + "☆" * (3 - stars), bg=PANEL, fg=AMBER,
                     font=theme.font(26)).pack()
            if not passed:
                tk.Label(b, text=f"Нужна точность не ниже {missions.PASS_ACCURACY:.0f}% — попробуйте "
                                 "ещё раз, не спешите.", bg=PANEL, fg=MUTED,
                         font=theme.font(10)).pack()
            else:
                tk.Label(b, text=f"Цель: {m['goal']} зн/мин. ★★ — точность ≥95% и цель по скорости, "
                                 "★★★ — точность ≥98% и скорость на 25% выше цели.",
                         bg=PANEL, fg=MUTED, font=theme.font(9), wraplength=px(700)).pack()
        grid = tk.Frame(b, bg=PANEL)
        grid.pack(pady=px(10))
        cells = [
            ("СКОРОСТЬ", f"{seg['cpm']:.0f}", "зн/мин", CYAN),
            ("ТОЧНОСТЬ", f"{seg['acc']:.1f}%", "", GREEN if seg["acc"] >= 96 else AMBER),
            ("ОШИБКИ", str(seg["errors"]), "", RED if seg["errors"] else GREEN),
            ("ВРЕМЯ", fmt_time(seg["elapsed"]), "", TEXT),
            ("РИТМ", f"{seg['rhythm']:.0f}%", "", CYAN),
            ("ЛУЧШАЯ СЕРИЯ", str(seg["best_streak"]), "без ошибок", AMBER),
        ]
        for i, (cap, val, unit, col) in enumerate(cells):
            f = tk.Frame(grid, bg=PANEL)
            f.grid(row=i // 3, column=i % 3, padx=px(22), pady=px(6))
            tk.Label(f, text=cap, bg=PANEL, fg=MUTED, font=theme.font(8, True)).pack()
            tk.Label(f, text=val, bg=PANEL, fg=col, font=theme.font(20, True, mono=True)).pack()
            if unit:
                tk.Label(f, text=unit, bg=PANEL, fg=MUTED, font=theme.font(8)).pack()
        info = f"+{xp} XP"
        if new_rank:
            info += f"   ·   НОВОЕ ЗВАНИЕ: {new_rank.upper()}!"
        tk.Label(b, text=info, bg=PANEL, fg=AMBER, font=theme.font(12, True)).pack()
        if weak:
            keys = ", ".join(f"«{ch}» ×{n}" for ch, n in weak)
            tk.Label(b, text=f"Ошибки чаще всего на: {keys}", bg=PANEL, fg=TEXT,
                     font=theme.font(10), wraplength=px(700)).pack(pady=(px(4), 0))
        row = tk.Frame(b, bg=PANEL)
        row.pack(side=tk.BOTTOM, pady=(px(8), 0))
        HudButton(row, "↻ ПОВТОР  Enter", self.app.restart_current, color=CYAN,
                  height=36, font_size=9).pack(side=tk.LEFT, padx=px(4))
        nxt = missions.next_mission(m["id"]) if (m and passed) else None
        if nxt:
            HudButton(row, f"▶ ДАЛЕЕ: {nxt['title'].upper()}  →",
                      lambda: self.app.start_mission(nxt), color=GREEN,
                      height=36, font_size=9).pack(side=tk.LEFT, padx=px(4))
        if weak or self.app.store.weakest_keys():
            HudButton(row, "⚙ РЕМОНТ  R", lambda: self.app.start_repair(self.meta.get("lang")),
                      color=AMBER, height=36, font_size=9).pack(side=tk.LEFT, padx=px(4))
        HudButton(row, "✕ ЗАКРЫТЬ  Esc", self._close_debrief, color=MUTED,
                  height=36, font_size=9).pack(side=tk.LEFT, padx=px(4))
        self._debrief_next = nxt

    def _debrief_key(self, e: tk.Event) -> None:
        ks = e.keysym
        if ks == "Return":
            self.app.restart_current()
        elif ks == "Escape":
            self._close_debrief()
        elif ks == "Right" and getattr(self, "_debrief_next", None):
            self.app.start_mission(self._debrief_next)
        elif ks.lower() in ("r", "cyrillic_ka"):
            self.app.start_repair(self.meta.get("lang"))

    def _close_debrief(self) -> None:
        self.hide_debrief()
        self.show_idle("ПОЛЁТ ЗАВЕРШЁН",
                       "F5 — повторить   ·   Ctrl+2 — миссии   ·   Ctrl+3 — свой текст")

    def hide_debrief(self) -> None:
        if self.debrief is not None:
            self.debrief.destroy()
            self.debrief = None

    # ------------------------------------------------------------------
    # Сохранение сессии своего текста
    # ------------------------------------------------------------------
    def persist(self, force: bool = False) -> None:
        eng = self.engine
        if eng is None or self.meta.get("mode") != "cargo" or eng.finished:
            return
        now = time.perf_counter()
        if not force and (not self._session_dirty or now - self._last_persist < 3.0):
            return
        save_session(SessionState(text=eng.text, index=eng.index, typed=eng.typed,
                                  errors=eng.errors, elapsed=eng.elapsed(now),
                                  case_sensitive=eng.case_sensitive))
        self._session_dirty = False
        self._last_persist = now

    # ------------------------------------------------------------------
    # Тепловая карта
    # ------------------------------------------------------------------
    def toggle_heat(self) -> None:
        if self.keyboard.heat is None:
            self.keyboard.set_heat(self.app.store.key_error_rates(min_total=5))
            self.btn_heat.set_active(True)
            self.legend.configure(text="процент ошибок по клавишам (за всё время)")
        else:
            self.keyboard.set_heat(None)
            self.btn_heat.set_active(False)
            self.legend.configure(text="")

    def apply_settings(self) -> None:
        st = self.app.store.settings
        self.viewport.set_font_size(FONT_SIZES.get(st["font"], 26))
        self.viewport.set_stars_visible(st["stars"])
        self.keyboard.set_zones(st["zones"])
        if st["keyboard"]:
            if not self.keyboard.winfo_ismapped():
                self.keyboard.pack(fill=tk.BOTH, expand=True, before=self.keyboard.master.winfo_children()[1])
        else:
            self.keyboard.pack_forget()
        self._setup_uplink()
        if st.get("living_space", "full") != getattr(self.living, "mode", "off"):
            self._setup_living()

    # ------------------------------------------------------------------
    # UPLINK — переводчик
    # ------------------------------------------------------------------
    @staticmethod
    def _word_at(text: str, index: int) -> str:
        """Слово под прицелом: токен вокруг index; на пробеле — следующее слово."""
        if not text or index < 0:
            return ""
        if index >= len(text):
            index = len(text) - 1
        if text[index] != " ":
            i = index
            while i > 0 and text[i - 1] != " ":
                i -= 1
            j = index
            while j < len(text) and text[j] != " ":
                j += 1
            return text[i:j]
        j = index + 1
        while j < len(text) and text[j] == " ":
            j += 1
        k = j
        while k < len(text) and text[k] != " ":
            k += 1
        return text[j:k]

    @staticmethod
    def _word_cursor(text: str, index: int) -> int:
        """Индекс текущей буквы внутри слова (−1, если сейчас пробел)."""
        if not text or index < 0 or index >= len(text) or text[index] == " ":
            return -1
        start = index
        while start > 0 and text[start - 1] != " ":
            start -= 1
        return index - start

    def _setup_uplink(self) -> None:
        self._segments = None
        self._seg_i = None
        self._seg_key = None
        self._word_key = None
        self._word_src = None
        on = (self.app.store.settings.get("translator") and self.engine is not None
              and self.meta.get("mode") == "cargo")
        if not on:
            self.uplink.grid_remove()
            return
        from stamina.translator import Segments
        self._segments = Segments(self.engine.text, self.meta.get("original") or None,
                                  self.meta.get("process"))
        sl, tl = self._tr_dir
        self.uplink.set(direction=f"{sl.upper()} → {tl.upper()}", source="", translation="",
                        word="", word_tr="", status="")
        self.uplink.grid()
        self._update_uplink(force=True)

    def _update_uplink(self, *, force: bool = False) -> None:
        if self._segments is None or self.engine is None or not len(self._segments):
            return
        eng = self.engine
        si = self._segments.index_at(min(eng.index, len(eng.text) - 1))
        tr = self.app.get_translator()
        sl, tl = self._tr_dir

        # --- предложение (только при смене сегмента) ---
        if force or si != self._seg_i:
            self._seg_i = si
            source = self._segments.sources[si]
            self._seg_key = tr.key(source, sl, tl)
            cached = tr.cached(source, sl, tl)
            if cached:
                self.uplink.set(source=source, translation=cached, status="✓ ПРИНЯТО",
                                status_color=GREEN)
            else:
                tr.request(source, sl, tl)
                self.uplink.set(source=source, translation="Запрос перевода…",
                                status="◌ ПРИЁМ…", status_color=AMBER)
            if si + 1 < len(self._segments):
                tr.request(self._segments.sources[si + 1], sl, tl)

        # --- слово под прицелом (при каждом сдвиге индекса) ---
        word = self._word_at(eng.text, eng.index)
        cursor = self._word_cursor(eng.text, eng.index)
        if not word:
            self._word_src = ""
            self._word_key = None
            self.uplink.set(word="—", word_tr="—", word_cursor=-1)
            return
        if word == self._word_src and not force:
            # то же слово — только сдвигаем красную букву
            self.uplink.set(word_cursor=cursor)
            return
        self._word_src = word
        self._word_key = tr.key(word, sl, tl)
        w_cached = tr.cached(word, sl, tl)
        if w_cached:
            self.uplink.set(word=word, word_tr=w_cached, word_cursor=cursor)
        else:
            tr.request(word, sl, tl)
            self.uplink.set(word=word, word_tr="…", word_cursor=cursor)

    def _poll_uplink(self) -> None:
        tr = self.app.translator
        if tr is None:
            return
        results = tr.poll()
        if self._segments is None:
            return
        for key, result in results:
            if key == self._word_key:
                if result:
                    self.uplink.set(word_tr=result)
                else:
                    self.uplink.set(word_tr="?")
            if key != self._seg_key:
                continue
            if result:
                self.uplink.set(translation=result, status="✓ ПРИНЯТО", status_color=GREEN)
            else:
                self.uplink.set(translation="Нет связи с интернетом — перевод появится, когда сеть "
                                            "вернётся. Уже переведённые фразы хранятся в кэше.",
                                status="✕ НЕТ СВЯЗИ", status_color=RED)
                self._last_retry = time.monotonic()
        # повторная попытка раз в 20 секунд, если связи не было
        if tr.online is False and time.monotonic() - self._last_retry > 20 and self._seg_i is not None:
            self._last_retry = time.monotonic()
            sl, tl = self._tr_dir
            tr.request(self._segments.sources[self._seg_i], sl, tl)
            if self._word_src:
                tr.request(self._word_src, sl, tl)

    # ------------------------------------------------------------------
    # Приборы и анимация
    # ------------------------------------------------------------------
    def refresh_stats(self) -> None:
        eng = self.engine
        now = time.perf_counter()
        self._last_stats = time.monotonic()
        if eng is None:
            self.speed.set(0)
            self.ring.set(None, "ОШИБОК 0")
            self.rhythm.set(None, "—")
            self.readouts.set([("ВРЕМЯ", "00:00", CYAN), ("ОШИБКИ", "0", GREEN),
                               ("СЕРИЯ / ЛУЧШАЯ", "0 / 0", AMBER), ("ОСТАЛОСЬ", "—", TEXT)])
            return
        avg = eng.cpm(now)
        running = self.state == "run" and eng.elapsed(now) - eng._elapsed < 3.0
        live = eng.instant_cpm() if running else avg
        m = self.meta.get("mission")
        self.speed.set(live, goal=m["goal"] if m else None,
                       sub=f"СРЕДН. {avg:.0f} · ≈{avg / 5:.0f} WPM")
        acc = eng.accuracy
        self.ring.set(acc, f"ОШИБОК {eng.errors}")
        r = eng.rhythm
        self.rhythm.set(None if r is None else r / 100, "—" if r is None else f"{r:.0f}%")
        left = len(eng.text) - eng.index
        eta = f"≈{fmt_time(left / avg * 60)}" if avg > 10 and left else fmt_int(left)
        self.readouts.set([
            ("ВРЕМЯ", fmt_time(eng.elapsed(now)), CYAN),
            ("ОШИБКИ", str(eng.errors), RED if eng.errors else GREEN),
            ("СЕРИЯ / ЛУЧШАЯ", f"{eng.streak} / {eng.best_streak}", AMBER),
            ("ОСТАЛОСЬ", eta, TEXT),
        ])
        self.strip.set(progress=eng.progress,
                       progress_text=f"{fmt_int(eng.index)} / {fmt_int(len(eng.text))} · "
                                     f"{eng.progress * 100:.0f}%")

    def tick(self, visible: bool) -> bool:
        """Вызывается таймером окна. Возвращает True, если нужна плавная анимация."""
        self._poll_uplink()
        if not visible:
            return False
        stars_on = bool(self.app.store.settings.get("stars"))
        eng = self.engine
        if self.state == "run" and eng is not None:
            warp = 1.0 + eng.instant_cpm() / 70.0
        elif self.state == "pause":
            warp = 0.15
        else:
            warp = 0.6
        live = False
        if self.living is not None:
            live = self.living.tick(typing=self.state == "run", warp=warp)
            stars_on = False
        self.viewport.tick(warp, stars_on)
        self.keyboard.tick()
        moving = self.speed.animate()
        if time.monotonic() - self._last_stats > 0.25 and self.state in ("run", "ready"):
            self.refresh_stats()
        self.persist()
        return stars_on or moving or live
