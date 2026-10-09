"""Первый запуск: «ДОБРО ПОЖАЛОВАТЬ НА БОРТ» → создание пилота → мостик.

Показывается, когда пилотов нет и прежних данных тоже нет (чистая установка).
Три коротких шага о разделах, проверка зависимостей с подсказками по установке и большая кнопка
«СОЗДАТЬ ПИЛОТА» (Enter) — открывает обычное «Зачисление в экипаж» (позывной, эмблема, код по желанию).
"""
from __future__ import annotations

import time
import tkinter as tk

from stamina import avatars, deps, theme
from stamina.hud import HudButton, HudPanel
from stamina.theme import AMBER, BG, CYAN, GREEN, LINE, MUTED, PANEL, RED, TEXT, px

STEPS = (
    ("1", "СОЗДАЙТЕ ПИЛОТА", AMBER,
     "Позывной, эмблема и (по желанию) код доступа. У каждого пилота свой прогресс — "
     "за одним компьютером может учиться вся семья."),
    ("2", "МОСТИК И МИССИИ", CYAN,
     "Печатайте текст в иллюминаторе, не глядя на клавиатуру: подсказка покажет клавишу и палец. "
     "Миссии учат клавиатуру ряд за рядом, за точность — звёзды и звания."),
    ("3", "СВОЙ ТЕКСТ · АНГЛИЙСКИЙ · СКОРОЧТЕНИЕ", GREEN,
     "Загрузите книгу и печатайте её с переводом UPLINK, учите слова и читайте быстрее. "
     "F1 — подробная инструкция в любой момент."),
)


def L(master, text="", *, fg=TEXT, size=10, bold=False, bg=PANEL, **kw) -> tk.Label:
    return tk.Label(master, text=text, fg=fg, bg=bg, font=theme.font(size, bold), justify="left", **kw)


class WelcomeScreen(tk.Frame):
    def __init__(self, master, *, on_create, on_import, on_exit, app_version: str = "") -> None:
        super().__init__(master, bg=BG)
        self.on_create, self.on_import, self.on_exit = on_create, on_import, on_exit
        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(16), pady=(px(10), 0))
        logo = tk.Canvas(top, bg=BG, highlightthickness=0, width=px(300), height=px(44))
        logo.pack(side=tk.LEFT)
        avatars.draw(logo, px(22), px(22), px(36), {"id": "-", "accent": "cyan",
                                                     "avatar": {"kind": "builtin", "glyph": "star"}})
        logo.create_text(px(48), px(15), text="STAR TYPING", anchor="w", fill=TEXT, font=theme.font(17, True))
        logo.create_text(px(49), px(35), text="ПЕРВЫЙ ЗАПУСК", anchor="w", fill=AMBER, font=theme.font(8, True))
        self.clock = L(top, "", fg=CYAN, size=14, bold=True, bg=BG)
        self.clock.pack(side=tk.RIGHT)
        if app_version:
            L(top, f"версия {app_version}", fg=MUTED, size=9, bg=BG).pack(side=tk.RIGHT, padx=px(12))
        tk.Frame(self, bg=LINE, height=1).pack(fill=tk.X, padx=px(16), pady=px(6))

        hero = tk.Canvas(self, bg=BG, highlightthickness=0, height=px(150))
        hero.living_sharp = True
        hero.pack(fill=tk.X, padx=px(16))
        hero.bind("<Configure>", lambda _e: self._hero(hero, hero.winfo_width()))

        row = tk.Frame(self, bg=BG)
        row.pack(fill=tk.X, padx=px(16), pady=px(12))
        for i, (num, title, col, text) in enumerate(STEPS):
            row.grid_columnconfigure(i, weight=1, uniform="s")
            p = HudPanel(row, f"ШАГ {num}", accent=col, pad=12)
            p.grid(row=0, column=i, sticky="nsew", padx=px(6))
            L(p.body, title, fg=col, size=11, bold=True).pack(anchor="w")
            L(p.body, text, fg=TEXT, size=10, wraplength=px(340)).pack(anchor="w", pady=(px(6), 0))

        sysp = HudPanel(self, "ПРОВЕРКА БОРТОВЫХ СИСТЕМ", accent=CYAN, pad=10)
        sysp.pack(fill=tk.X, padx=px(22), pady=px(8))
        head = tk.Frame(sysp.body, bg=PANEL)
        head.pack(fill=tk.X, pady=(0, px(4)))
        self.system = deps.detect_system()
        L(head, "ВАША СИСТЕМА:", fg=MUTED, size=9, bold=True).pack(side=tk.LEFT)
        L(head, f"определена автоматически — {deps.system_details()}", fg=TEXT, size=9).pack(side=tk.LEFT, padx=px(8))
        self.sys_btns = {}
        for key in deps.SYSTEMS:
            b = HudButton(head, deps.SYSTEM_TITLES[key], lambda k=key: self.set_system(k), height=28, font_size=9,
                          width=110, active=key == self.system)
            b.pack(side=tk.LEFT, padx=px(3))
            self.sys_btns[key] = b
        self.sys_note = L(head, "", fg=AMBER, size=8)
        self.sys_note.pack(side=tk.LEFT, padx=px(8))
        self.list = tk.Frame(sysp.body, bg=PANEL)
        self.list.pack(fill=tk.X)
        act = tk.Frame(sysp.body, bg=PANEL)
        act.pack(fill=tk.X, pady=(px(6), 0))
        self.btn_install = HudButton(act, "⇩ УСТАНОВИТЬ ВСЁ", self.install_all, color=GREEN, height=34, font_size=10,
                                     width=220)
        self.btn_install.pack(side=tk.LEFT)
        self.log = L(act, "", fg=MUTED, size=8, anchor="w", wraplength=px(900))
        self.log.pack(side=tk.LEFT, padx=px(10), fill=tk.X, expand=True)
        L(sysp.body, "Без необязательных пунктов всё работает: печать, миссии, свой текст, английский (без микрофона), "
                     "скорочтение. Установить их можно и позже — README, раздел «Быстрый старт».",
          fg=MUTED, size=8).pack(anchor="w", pady=(px(4), 0))
        self._busy = False
        self._last = ""
        self.refresh_items()

        bottom = tk.Frame(self, bg=BG)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=px(22), pady=(0, px(14)))
        self.btn_create = HudButton(bottom, "► СОЗДАТЬ ПИЛОТА И НАЧАТЬ  ENTER", self.on_create, color=AMBER,
                                    height=48, font_size=12, width=420)
        self.btn_create.nav_primary = True
        self.btn_create.pack(side=tk.LEFT)
        HudButton(bottom, "⇩ У МЕНЯ ЕСТЬ ФАЙЛ ПИЛОТА (.stpilot)", self.on_import, height=48,
                  font_size=9).pack(side=tk.LEFT, padx=px(10))
        HudButton(bottom, "ВЫХОД  ESC", self.on_exit, height=48, font_size=9).pack(side=tk.RIGHT)
        self._tick()

    # -- компоненты
    def set_system(self, key: str) -> None:
        self.system = key
        for k, b in self.sys_btns.items():
            b.set_active(k == key)
        real = deps.detect_system()
        self.sys_note.configure(text="" if key == real else
                                f"программа запущена в {deps.SYSTEM_TITLES[real]} — команды показаны для "
                                f"{deps.SYSTEM_TITLES[key]}")
        self.refresh_items()

    def refresh_items(self) -> None:
        for w in self.list.winfo_children():
            w.destroy()
        self.items = deps.check(self.system)
        for it in self.items:
            line = tk.Frame(self.list, bg=PANEL)
            line.pack(fill=tk.X, pady=px(1))
            ok = it["ok"]
            mark, col = ("✓", GREEN) if ok else (("✕", RED) if it["need"] == "нужно" else ("○", AMBER))
            L(line, mark, fg=col, size=11, bold=True, width=2).pack(side=tk.LEFT)
            L(line, it["name"], fg=TEXT, size=10, bold=True, width=20, anchor="w").pack(side=tk.LEFT)
            L(line, f"{it['need']} · {it['what']}", fg=MUTED, size=9, width=50, anchor="w").pack(side=tk.LEFT)
            L(line, "готово" if ok else "нет · " + it["how"], fg=GREEN if ok else AMBER,
              size=9, anchor="w").pack(side=tk.LEFT, fill=tk.X)
        miss = deps.missing(self.items)
        can = bool(miss) and self.system == deps.detect_system()
        self.btn_install.set_enabled(can and not self._busy)
        if not miss and not self._busy:
            self.log.configure(text="Все компоненты на месте.", fg=GREEN)

    def install_all(self) -> None:
        if self._busy or self.system != deps.detect_system():
            return
        miss = deps.missing(self.items)
        if not miss:
            return
        import queue
        import threading
        self._busy = True
        q: queue.Queue = queue.Queue()
        self.log.configure(text="Устанавливаю: " + ", ".join(it["name"] for it in miss) + "…", fg=AMBER)

        def work():
            res = deps.install_all(self.items, log=q.put, system=self.system)
            q.put(("__done__", res))

        def poll():
            try:
                while True:
                    m = q.get_nowait()
                    if isinstance(m, tuple):
                        self._busy = False
                        self.refresh_items()
                        self.log.configure(text=("Готово: компоненты установлены." if m[1] else
                                                 "Установлено не всё: " + self._last), fg=GREEN if m[1] else AMBER)
                        return
                    self._last = m.strip()
                    self.log.configure(text=self._last[-150:])
            except Exception:  # noqa: BLE001 — очередь пуста
                pass
            if self.winfo_exists():
                self.after(150, poll)
        threading.Thread(target=work, daemon=True).start()
        poll()

    def _hero(self, c: tk.Canvas, w: int) -> None:
        c.delete("t")
        c.create_text(w // 2, px(58), text="ДОБРО ПОЖАЛОВАТЬ НА БОРТ", fill=AMBER, font=theme.font(32, True), tags="t")
        c.create_text(w // 2, px(110), text="Star Typing — тренажёр слепой печати, английского и скорочтения "
                      "в кабине космолёта. Три шага — и вы на мостике.", fill=TEXT, font=theme.font(11), tags="t")

    def _tick(self) -> None:
        if self.winfo_exists():
            self.clock.configure(text=time.strftime("%H:%M"))
            self._job = self.after(15000, self._tick)

    def destroy(self) -> None:
        job = getattr(self, "_job", None)
        if job is not None:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        super().destroy()

    def on_key(self, e) -> None:
        if e.keysym in ("Return", "KP_Enter"):
            self.on_create()
        elif e.keysym == "Escape":
            self.on_exit()


def run_welcome(root: tk.Tk, *, app_version: str = "") -> str | None:
    """Экран приветствия в окне root → id созданного (или импортированного) пилота, None — выход."""
    from stamina import pilot_screens
    root.title("Star Typing — добро пожаловать на борт")
    box = {"pid": None}
    holder = tk.Frame(root, bg=BG)
    holder.pack(fill=tk.BOTH, expand=True)
    busy = {"on": False}

    def done(pid):
        box["pid"] = pid
        root.quit()

    def create():
        if busy["on"]:
            return
        busy["on"] = True
        try:
            pid = pilot_screens.ProfileDialog(root).run()
        finally:
            busy["on"] = False
        if pid:
            done(pid)

    def import_():
        pid = pilot_screens.import_pilot(root)
        if pid:
            done(pid)

    page = WelcomeScreen(holder, on_create=create, on_import=import_, on_exit=lambda: done(None),
                         app_version=app_version)
    page.pack(fill=tk.BOTH, expand=True)
    live = None
    try:
        from stamina.living_space import DEFAULT_MODE, LivingSpace
        live = LivingSpace(root, holder, DEFAULT_MODE)
        root.after(120, lambda: page.winfo_exists() and live.attach(page))
    except Exception:  # noqa: BLE001
        live = None
    from stamina import keynav
    keynav.install(root)
    root.bind("<Key>", lambda e: e.widget.winfo_toplevel() is root and page.on_key(e))
    root.protocol("WM_DELETE_WINDOW", lambda: done(None))
    root.after(200, root.focus_force)
    root.mainloop()
    root.unbind("<Key>")
    if live is not None:
        live.detach()
    holder.destroy()
    return box["pid"]
