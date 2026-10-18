"""Экран «ЭФИР» — общая лента сообщений экипажа.

Пилот выбирает вкладку ЭФИР в шапке, читает, что написали другие, и отвечает.
Данные — `stamina/comm.py` (общий файл экипажа). Пока это прототип на одном
компьютере; экран специально не знает, откуда берутся сообщения, поэтому при
появлении онлайна его не придётся переписывать.
"""
from __future__ import annotations

from stamina.i18n import t as _t

import time
import tkinter as tk

from stamina import comm, pilots, theme
from stamina.adapt import make_vscroll
from stamina.hud import HudButton, HudPanel
from stamina.theme import AMBER, BG, BG2, CYAN, LINE, MUTED, PANEL, TEXT, px

# позывной красим цветом «акцента» пилота из реестра экипажа (сами цвета берём у скина)
ACCENTS = ("cyan", "amber", "green", "red", "purple")


def _label(master, text="", *, fg=TEXT, size=10, bold=False, bg=PANEL, **kw):
    return tk.Label(master, text=text, fg=fg, bg=bg, font=theme.font(size, bold), **kw)


class CommScreen(tk.Frame):
    """Лента эфира: сообщения экипажа, поле ввода и отправка."""

    def __init__(self, master, app) -> None:
        super().__init__(master, bg=BG)
        self.app = app
        self._accents: dict[str, str] = {}

        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(14), pady=(px(10), px(4)))
        _label(top, _t("ЭФИР — СВЯЗЬ ЭКИПАЖА"), size=16, bold=True, bg=BG).pack(side=tk.LEFT)
        self.info = _label(top, "", fg=MUTED, size=9, bg=BG)
        self.info.pack(side=tk.LEFT, padx=(px(10), px(6)))
        HudButton(top, "?", lambda: self.app.open_help(), height=32, font_size=10,
                  width=32, color=AMBER).pack(side=tk.RIGHT)
        HudButton(top, _t("ОБНОВИТЬ"), self.refresh, height=32, font_size=10,
                  color=CYAN).pack(side=tk.RIGHT, padx=(0, px(8)))

        panel = HudPanel(self, title=_t("ОБЩИЙ КАНАЛ"))
        panel.pack(fill=tk.BOTH, expand=True, padx=px(14), pady=px(4))
        sb = make_vscroll(panel.body)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text = tk.Text(panel.body, wrap=tk.WORD, bg=PANEL, fg=TEXT, relief=tk.FLAT,
                            font=theme.font(10), padx=px(8), pady=px(6), cursor="arrow",
                            state=tk.DISABLED, highlightthickness=0, bd=0,
                            yscrollcommand=sb.set)
        self.text.pack(fill=tk.BOTH, expand=True)
        sb.configure(command=self.text.yview)
        self._apply_tags()
        # колесо мыши: Windows/macOS — <MouseWheel>, Linux (X11) — кнопки 4/5
        for w in (self.text, panel.body):
            w.bind("<MouseWheel>", self._wheel)
            w.bind("<Button-4>", lambda _e: self.text.yview_scroll(-3, "units"))
            w.bind("<Button-5>", lambda _e: self.text.yview_scroll(3, "units"))

        row = tk.Frame(self, bg=BG)
        row.pack(fill=tk.X, padx=px(14), pady=(px(6), px(10)))
        self.entry = tk.Entry(row, bg=BG2, fg=TEXT, insertbackground=CYAN, relief=tk.FLAT,
                              font=theme.font(11), highlightthickness=1, highlightbackground=LINE,
                              highlightcolor=CYAN, selectbackground=CYAN, selectforeground=BG)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=px(6), padx=(0, px(8)))
        self.entry.bind("<Return>", self._on_return)
        self.entry.bind("<KP_Enter>", self._on_return)
        self.send_btn = HudButton(row, _t("ОТПРАВИТЬ"), self._send, height=36, font_size=11)
        self.send_btn.pack(side=tk.LEFT)

    # -- данные -------------------------------------------------------------
    def _pid(self) -> str:
        return (self.app.pilot or {}).get("id", "")

    def _callsign(self) -> str:
        return (self.app.pilot or {}).get("callsign", "")

    def _wheel(self, e) -> str:
        self.text.yview_scroll(int(-e.delta / 120) * 3, "units")
        return "break"

    # -- отрисовка ----------------------------------------------------------
    def _apply_tags(self) -> None:
        """Цвета берём у текущего скина в момент отрисовки (токены, без хардкода)."""
        self.text.tag_configure("time", foreground=theme.MUTED, font=theme.font(8))
        self.text.tag_configure("body", foreground=theme.TEXT, font=theme.font(10))
        self.text.tag_configure("hint", foreground=theme.MUTED, font=theme.font(10))
        for name in ACCENTS:
            color = getattr(theme, name.upper(), theme.CYAN)
            self.text.tag_configure(f"acc_{name}", foreground=color, font=theme.font(10, True))

    def refresh(self) -> None:
        """Перечитать эфир, показать ленту и отметить прочитанным."""
        self._accents = {p["id"]: p.get("accent", "cyan") for p in pilots.pilots()}
        self._apply_tags()
        pid = self._pid()
        fresh = comm.unread(pid)
        self._render()
        if pid:
            comm.mark_read(pid)
        total = len(comm.messages())
        tail = f" · {_t('Новых: {0}').format(fresh)}" if fresh else ""
        self.info.configure(text=_t("Сообщений: {0}").format(total) + tail)
        has_pilot = bool(pid)
        self.entry.configure(state=tk.NORMAL if has_pilot else tk.DISABLED)
        self.send_btn.set_active(has_pilot)

    def _render(self) -> None:
        msgs = comm.messages()
        pid = self._pid()
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        if not pid:
            self.text.insert(tk.END, _t("Войдите в кабину пилота — тогда можно писать в эфир.") + "\n", "hint")
        if not msgs:
            self.text.insert(tk.END, _t("Пока в эфире пусто. Передайте первое сообщение экипажу.") + "\n", "hint")
        for m in msgs:
            accent = self._accents.get(m.get("author", ""))
            if accent not in ACCENTS:
                accent = "cyan"
            self.text.insert(tk.END, str(m.get("callsign") or "—"), f"acc_{accent}")
            if m.get("author") == pid:
                self.text.insert(tk.END, " ▸", "time")     # своё сообщение
            when = time.strftime("%d.%m %H:%M", time.localtime(float(m.get("ts", 0.0))))
            self.text.insert(tk.END, f"  {when}\n", "time")
            self.text.insert(tk.END, f"{m.get('text', '')}\n\n", "body")
        self.text.configure(state=tk.DISABLED)
        self.text.see(tk.END)

    # -- ввод ---------------------------------------------------------------
    def focus_input(self) -> None:
        """Фокус в поле ввода (при входе в раздел)."""
        if str(self.entry.cget("state")) != tk.DISABLED:
            self.entry.focus_set()

    def _on_return(self, _e) -> str:
        self._send()
        return "break"

    def _send(self) -> None:
        pid = self._pid()
        if not pid:
            return
        if comm.send(pid, self._callsign(), self.entry.get()) is not None:
            self.entry.delete(0, tk.END)
            self.refresh()
            self.app.after(30, self._refresh_chrome)

    def _refresh_chrome(self) -> None:
        """Обновить счётчик непрочитанного на кнопке раздела."""
        try:
            self.app.update_comm_badge()
        except Exception:  # noqa: BLE001
            pass

    def page_help_key(self) -> str:
        return "comm"

    def on_key(self, _e) -> None:
        """Клавиши раздела: поле ввода само обрабатывает набор и Enter."""
