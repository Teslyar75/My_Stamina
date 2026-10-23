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
        self.btn = HudButton(row, "↻", self.refresh_now, height=22, font_size=9, width=26, color=CYAN)
        self.btn.pack(side=tk.LEFT, padx=px(8))
        self.status = tk.Label(row, text="", bg=PANEL, fg=MUTED, font=theme.font(8))
        self.status.pack(side=tk.LEFT, padx=px(4))
        tabs = tk.Frame(self.body, bg=PANEL)
        tabs.pack(fill=tk.X, pady=(px(4), 0))
        self._tab_btns = {}
        for k, lab in (("all", t("общая")), ("st", "Star Typing"), ("mt", "Monkeytype")):
            b = tk.Label(tabs, text=lab, bg=PANEL, fg=MUTED, cursor="hand2", font=theme.font(9, True))
            b.pack(side=tk.LEFT, padx=(0, px(12)))
            b.bind("<Button-1>", lambda _e, k=k: self._set_src(k))
            self._tab_btns[k] = b
        self._tabs()
        self.cv = tk.Canvas(self.body, bg=PANEL, highlightthickness=0, height=px(200))
        self.cv.pack(fill=tk.X, pady=(px(4), 0))
        self.cv.bind("<Configure>", lambda _e: self._redraw())
        self._data = None
        self._msg = ""
        self._busy = False
        self.show_cached()
        for e in (self.user, self.key):     # ник/ключ: сохранить и сразу подтянуть
            e.bind("<Return>", lambda _e: self.refresh_now())
            e.bind("<FocusOut>", lambda _e: self._save_creds())
        self.bind("<Map>", lambda _e: self.auto())
        self.after(800, self.auto)          # старт приложения

    def show_cached(self) -> None:
        data = monkeytype.load_cache()
        if data and data.get("summary"):
            self._render(data)
        else:
            self._msg = t("Укажите имя пользователя Monkeytype — данные подтянутся сами.")
            self._redraw()

    def _render(self, data: dict) -> None:
        self._data = data
        when = time.strftime("%d.%m %H:%M", time.localtime(data.get("fetched_at", 0)))
        warn = data.get("warning") or ""
        self.status.configure(text=(warn + " · " if warn else "") + t("обновлено {0}").format(when),
                              fg=AMBER if warn else MUTED)
        self._redraw()

    def _tabs(self) -> None:
        src = self.app.store.settings.get("zen_acct_src", "all")
        for k, b in self._tab_btns.items():
            b.configure(fg=AMBER if k == src else MUTED)

    def _set_src(self, k: str) -> None:
        self.app.store.settings["zen_acct_src"] = k
        try:
            self.app.store.save_settings()
        except Exception:
            pass
        self._tabs()
        self._redraw()

    def _redraw(self) -> None:
        """Общая таблица прогресса (Star Typing + Monkeytype), вкладки — фильтры."""
        from stamina import account_view
        cv = self.cv
        w = max(cv.winfo_width(), px(600))
        src = self.app.store.settings.get("zen_acct_src", "all")
        zen = getattr(self.app, "zen", None)
        s = zen.account_summary(src) if zen else None
        pal = {"bg": PANEL, "sub": MUTED, "subalt": BG, "text": TEXT, "main": AMBER}
        h = account_view.draw(cv, s, pal, theme.font(10, mono=True)[0], w, scale=px(100) / 100,
                              empty=self._msg or t("Пока нет данных."))
        cv.configure(height=int(h + px(4)))
        cv.tag_bind("acct_name", "<Button-1>", lambda _e: self._open_profile())
        cv.tag_bind("acct_name", "<Enter>", lambda _e: cv.configure(cursor="hand2"))
        cv.tag_bind("acct_name", "<Leave>", lambda _e: cv.configure(cursor=""))

    def _open_profile(self) -> None:
        """Щелчок по имени — профиль на monkeytype.com (только просмотр)."""
        name = (self.user.get() or "").strip()
        if not name:
            self.user.focus_set()
            return
        import urllib.parse
        import webbrowser
        webbrowser.open("https://monkeytype.com/profile/" + urllib.parse.quote(name))

    def _save_creds(self) -> tuple[str, str]:
        user, key = self.user.get().strip(), self.key.get().strip()
        st = self.app.store.settings
        if (st.get("mt_username", ""), st.get("mt_apekey", "")) != (user, key):
            st["mt_username"], st["mt_apekey"] = user, key
            try:
                self.app.store.save_settings()
            except Exception:  # noqa: BLE001
                pass
        return user, key

    def auto(self) -> None:
        """Тихая синхронизация (тот же путь, что у портала: интервал, кэш, пауза после 429)."""
        self._redraw()
        self._sync(force=False)

    def refresh_now(self) -> None:
        """Ручное ↻: обходит 5-минутный интервал, но не паузу после 429."""
        self._sync(force=True)

    def _sync(self, force: bool) -> None:
        user, key = self._save_creds()
        if not user:
            if force:
                self.user.focus_set()
            return
        left = monkeytype.backoff_left()
        if left:
            if force:
                self.status.configure(text=t("лимит Monkeytype — повтор через {0} мин").format(
                    max(1, round(left / 60))), fg=AMBER)
            return
        box: dict = {}
        started = monkeytype.auto_sync(user, key, force=force,
                                       on_done=lambda d: box.setdefault("data", d),
                                       on_error=lambda e: box.setdefault("err", e))
        if not started:
            if force and monkeytype._sync["busy"]:
                self.status.configure(text=t("загрузка…"), fg=MUTED)
            return
        self.status.configure(text=t("загрузка…"), fg=MUTED)

        def poll() -> None:
            if not box:
                if self.winfo_exists():
                    self.after(150, poll)
                return
            if "data" in box:
                self._render(box["data"])
                zen = getattr(self.app, "zen", None)
                if zen is not None and getattr(zen, "overlay", None) is not None and zen.on:
                    zen.overlay._draw_chrome()
            else:
                self.status.configure(text=t(box["err"]), fg=RED)
                if not self._data:
                    self._msg = t(box["err"])
                    self._redraw()

        self.after(150, poll)
