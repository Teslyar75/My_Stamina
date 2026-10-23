"""Панель «MONKEYTYPE» в Бортжурнале: импорт своего прогресса (только чтение).

Имя пользователя → публичный профиль (рекорды, тестов, серия). ApeKey —
необязательно, для последних результатов. Сеть — в фоне, по кнопке; данные
кэшируются (stamina/monkeytype.py), отправки на Monkeytype нет.
"""
from __future__ import annotations

import threading
import time
import tkinter as tk

from stamina import monkeytype, theme
from stamina.hud import HudButton, HudPanel
from stamina.i18n import t
from stamina.theme import AMBER, BG, CYAN, MUTED, PANEL, RED, TEXT, px


class MonkeytypePanel(HudPanel):
    def __init__(self, master, app) -> None:
        super().__init__(master, "MONKEYTYPE", accent=CYAN, pad=6)
        self.app = app
        st = app.store.settings
        row = tk.Frame(self.body, bg=PANEL)
        row.pack(fill=tk.X)
        tk.Label(row, text=t("Пилот:"), bg=PANEL, fg=MUTED, font=theme.font(9)).pack(side=tk.LEFT)
        self.user = tk.Entry(row, width=16, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat",
                             font=theme.font(10, mono=True))
        self.user.insert(0, st.get("mt_username", ""))
        self.user.pack(side=tk.LEFT, padx=(px(4), px(10)))
        tk.Label(row, text=t("ApeKey (необязательно):"), bg=PANEL, fg=MUTED,
                 font=theme.font(9)).pack(side=tk.LEFT)
        self.key = tk.Entry(row, width=18, show="•", bg=BG, fg=TEXT, insertbackground=TEXT,
                            relief="flat", font=theme.font(10, mono=True))
        self.key.insert(0, st.get("mt_apekey", ""))
        self.key.pack(side=tk.LEFT, padx=px(4))
        self.btn = HudButton(row, t("↻ ОБНОВИТЬ"), self.refresh_now, height=26, font_size=9, color=CYAN)
        self.btn.pack(side=tk.LEFT, padx=px(8))
        self.status = tk.Label(row, text="", bg=PANEL, fg=MUTED, font=theme.font(8))
        self.status.pack(side=tk.LEFT, padx=px(4))
        self.cv = tk.Canvas(self.body, bg=PANEL, highlightthickness=0, height=px(200))
        self.cv.pack(fill=tk.X, pady=(px(4), 0))
        self.cv.bind("<Configure>", lambda _e: self._redraw())
        self._data = None
        self._msg = ""
        self._busy = False
        self.show_cached()

    def show_cached(self) -> None:
        data = monkeytype.load_cache()
        if data and data.get("summary"):
            self._render(data)
        else:
            self._msg = t("Укажите имя пользователя Monkeytype и нажмите «Обновить».")
            self._redraw()

    def _render(self, data: dict) -> None:
        self._data = data
        when = time.strftime("%d.%m %H:%M", time.localtime(data.get("fetched_at", 0)))
        warn = data.get("warning") or ""
        self.status.configure(text=(warn + " · " if warn else "") + t("обновлено {0}").format(when),
                              fg=AMBER if warn else MUTED)
        self._redraw()

    def _redraw(self) -> None:
        """Как страница аккаунта Monkeytype: счётчики, карточки рекордов, тепловая карта."""
        cv = self.cv
        cv.delete("all")
        w = max(cv.winfo_width(), px(600))
        if not self._data:
            cv.create_text(px(6), px(14), text=self._msg, anchor="w", fill=MUTED, font=theme.font(10))
            return
        s = self._data["summary"]
        f_cap, f_val, f_sm = theme.font(8), theme.font(16, True, mono=True), theme.font(8, mono=True)
        hh, mm = divmod(int(s["hours"] * 60), 60)
        cells = [(t("тестов начато"), f"{s['started']:,}".replace(",", " ")),
                 (t("тестов пройдено"), f"{s['tests']:,}".replace(",", " ")),
                 (t("время набора"), f"{hh}:{mm:02d}"),
                 (t("серия дней"), f"{s['streak']} / {s.get('max_streak', 0)}")]
        lbs = s.get("lbs") or []
        if lbs:
            b = min(lbs, key=lambda r: r["rank"])
            cells.append((t("рейтинг {0} {1}").format(b["mode"], b["mode2"]),
                          f"#{b['rank']:,}".replace(",", " ")))
        cw = w / len(cells)
        for i, (cap, val) in enumerate(cells):
            x = px(6) + i * cw
            cv.create_text(x, px(10), text=cap, anchor="w", fill=MUTED, font=f_cap)
            cv.create_text(x, px(30), text=val, anchor="w", fill=TEXT, font=f_val)
        # карточки рекордов: time 15/30/60/120 и words 10/25/50/100
        y0, ch = px(52), px(46)
        pbs = s["pbs"]
        n = max(1, len(pbs))
        gap = px(6)
        cw = (w - gap * (n + 1)) / n
        for i, pb in enumerate(pbs):
            x = gap + i * (cw + gap)
            cv.create_rectangle(x, y0, x + cw, y0 + ch, outline=theme.LINE, fill=BG)
            cv.create_text(x + cw / 2, y0 + px(9), text=f"{pb['mode']} {pb['mode2']}", fill=MUTED, font=f_sm)
            wpm = "-" if pb["wpm"] is None else f"{pb['wpm']:.0f}"
            cv.create_text(x + cw / 2, y0 + px(25), text=wpm, fill=CYAN, font=theme.font(14, True, mono=True))
            acc = "" if pb["acc"] is None else f"{pb['acc']:.0f}%"
            cv.create_text(x + cw / 2, y0 + px(39), text=acc, fill=MUTED, font=f_sm)
        y = y0 + ch + px(12)
        if s.get("recent"):
            cv.create_text(px(6), y, anchor="w", fill=MUTED, font=f_sm,
                           text=t("последние WPM: {0}").format(" ".join(f"{v:.0f}" for v in s["recent"])))
            y += px(14)
        # тепловая карта активности за 12 месяцев (недели × дни)
        act = s.get("activity") or []
        if act:
            import datetime as dt
            first = dt.date.fromisoformat(act[0][0])
            pad = first.weekday()
            weeks = (len(act) + pad + 6) // 7
            cell = min(px(11), (w - px(12)) / max(1, weeks) - 1)
            mx = max(v for _d, v in act) or 1
            hot = theme.c("accent")
            for i, (_d, v) in enumerate(act):
                k = i + pad
                cx, cy = px(6) + (k // 7) * (cell + 1), y + (k % 7) * (cell + 1)
                col = theme.blend(BG, hot, 0.2 + 0.8 * min(1, v / (mx * 0.6))) if v else theme.blend(BG, MUTED, 0.15)
                cv.create_rectangle(cx, cy, cx + cell, cy + cell, outline="", fill=col)
            y += 7 * (cell + 1) + px(4)
            tot = sum(v for _d, v in act)
            cv.create_text(px(6), y + px(6), anchor="w", fill=MUTED, font=f_sm,
                           text=t("{0} тестов за последние 12 месяцев").format(tot))
            y += px(14)
        cv.configure(height=int(y + px(4)))

    def refresh_now(self) -> None:
        if self._busy:
            return
        user, key = self.user.get().strip(), self.key.get().strip()
        st = self.app.store.settings
        st["mt_username"], st["mt_apekey"] = user, key
        self.app.store.save_settings()
        self._busy = True
        self.status.configure(text=t("загрузка…"), fg=MUTED)
        box: dict = {}

        def work() -> None:
            try:
                box["data"] = monkeytype.refresh(user, key)
            except monkeytype.MonkeytypeError as e:
                box["err"] = str(e)
            except Exception as e:  # noqa: BLE001
                box["err"] = f"Monkeytype: {e}"

        th = threading.Thread(target=work, daemon=True, name="monkeytype")
        th.start()

        def poll() -> None:
            if th.is_alive():
                self.after(150, poll)
                return
            self._busy = False
            if "data" in box:
                self._render(box["data"])
            else:
                self.status.configure(text=t(box.get("err", "ошибка")), fg=RED)
                if not self._data:
                    self._msg = t(box.get("err", "ошибка"))
                    self._redraw()

        self.after(150, poll)
