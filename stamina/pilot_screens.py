"""Экраны экипажа: «ВХОД В КАБИНУ», «ЗАЧИСЛЕНИЕ / ЛИЧНОЕ ДЕЛО», код доступа, списание, ДОСКА ПОЧЁТА.

Работают и в лёгком окне до запуска кабины, и внутри кабины (Toplevel / экран).
Данные пилотов читаются через stamina.pilots / pilot_stats (не через stamina.storage).
"""
from __future__ import annotations

import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from stamina import avatars, pilot_pin, pilots, theme
from stamina.hud import HudButton, HudPanel
from stamina.pilot_stats import pilot_stats
from stamina.theme import (AMBER, BG, BG2, CYAN, FAINT, LINE, LINE_HI, MUTED, PANEL,
                           RED, TEXT, blend, chamfer, px)

SILVER, BRONZE = "#C9D6E3", "#D08A4E"
MEDALS = (AMBER, SILVER, BRONZE)


def L(master, text="", *, fg=TEXT, size=10, bold=False, mono=False, bg=None, **kw) -> tk.Label:
    if bg is None:
        try:
            bg = master.cget("bg")
        except tk.TclError:
            bg = PANEL
    return tk.Label(master, text=text, fg=fg, bg=bg, font=theme.font(size, bold, mono), **kw)


def entry(master, width=24, size=12, show=None, mono=False) -> tk.Entry:
    return tk.Entry(master, width=width, bg=BG2, fg=TEXT, insertbackground=CYAN, relief="flat", show=show or "",
                    font=theme.font(size, True, mono), highlightthickness=1, highlightbackground=LINE_HI,
                    highlightcolor=AMBER)


def fmt_num(v, unit="") -> str:
    if v is None or v == 0:
        return "—"
    s = f"{v:,.0f}".replace(",", " ") if isinstance(v, (int, float)) else str(v)
    return f"{s}{unit}"


def when(day: str | None) -> str:
    if not day:
        return "ещё не летал"
    today = time.strftime("%Y-%m-%d")
    y = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
    return "сегодня" if day == today else "вчера" if day == y else ".".join(reversed(day.split("-")[1:]))


class Modal(tk.Toplevel):
    """Модальное окно в стиле пульта."""

    def __init__(self, master, title: str, accent=AMBER) -> None:
        super().__init__(master, bg=BG)
        self.title(title)
        self.transient(master.winfo_toplevel())
        self.resizable(False, False)
        self.result = None
        self.panel = HudPanel(self, title.upper(), accent=accent, pad=16)
        self.panel.pack(fill=tk.BOTH, expand=True, padx=px(10), pady=px(10))
        self.body = self.panel.body
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", lambda _e: self.cancel())

    def run(self):
        self.update_idletasks()
        m = self.master.winfo_toplevel()
        try:
            x = m.winfo_rootx() + (m.winfo_width() - self.winfo_reqwidth()) // 2
            y = m.winfo_rooty() + (m.winfo_height() - self.winfo_reqheight()) // 3
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_force()
        self.wait_window()
        return self.result

    def cancel(self) -> None:
        self.result = None
        self.destroy()


# ===================================================================== код доступа
class PinPad(tk.Frame):
    """Ячейки-точки + цифровая клавиатура."""

    def __init__(self, master, on_enter, max_len=8) -> None:
        super().__init__(master, bg=PANEL)
        self.code = ""
        self.max_len = max_len
        self.on_enter = on_enter
        self.cells = tk.Canvas(self, bg=PANEL, highlightthickness=0, height=px(46), width=px(8 * 40))
        self.cells.pack(pady=(px(4), px(10)))
        grid = tk.Frame(self, bg=PANEL)
        grid.pack()
        keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "⌫", "0", "✓"]
        for i, k in enumerate(keys):
            col = AMBER if k == "✓" else (MUTED if k == "⌫" else CYAN)
            HudButton(grid, k, lambda k=k: self.press(k), width=64, height=44, font_size=14, color=col).grid(
                row=i // 3, column=i % 3, padx=px(3), pady=px(3))
        self.flash = None
        self.draw()

    def press(self, k: str) -> None:
        if k == "⌫":
            self.code = self.code[:-1]
        elif k == "✓":
            self.on_enter()
            return
        elif k.isdigit() and len(self.code) < self.max_len:
            self.code += k
        self.flash = None
        self.draw()

    def key(self, e) -> None:
        if e.char and e.char.isdigit():
            self.press(e.char)
        elif e.keysym == "BackSpace":
            self.press("⌫")
        elif e.keysym in ("Return", "KP_Enter"):
            self.press("✓")

    def clear(self, flash=None) -> None:
        self.code = ""
        self.flash = flash
        self.draw()

    def draw(self) -> None:
        c = self.cells
        c.delete("all")
        n = max(4, len(self.code))
        w = int(c.cget("width"))
        cw = px(34)
        x0 = (w - n * (cw + px(6))) / 2
        for i in range(n):
            x = x0 + i * (cw + px(6))
            filled = i < len(self.code)
            col = self.flash or (AMBER if filled else LINE_HI)
            c.create_polygon(chamfer(x, px(4), x + cw, px(42), px(6)), fill=blend(col, BG, 0.85), outline=col)
            if filled:
                c.create_oval(x + cw / 2 - px(6), px(17), x + cw / 2 + px(6), px(29), fill=col, outline=col)


class PinDialog(Modal):
    """Ввод кода доступа. result = True при верном коде; "reset" — код сброшен через «Забыли код?»."""

    def __init__(self, master, pilot: dict, purpose: str = "ВХОД В КАБИНУ") -> None:
        super().__init__(master, "Код доступа", AMBER)
        self.pilot = pilot
        top = tk.Frame(self.body, bg=PANEL)
        top.pack(fill=tk.X)
        av = tk.Canvas(top, bg=PANEL, highlightthickness=0, width=px(64), height=px(64))
        av.pack(side=tk.LEFT)
        avatars.draw(av, px(32), px(32), px(58), pilot)
        box = tk.Frame(top, bg=PANEL)
        box.pack(side=tk.LEFT, padx=px(10))
        L(box, pilot["callsign"], size=16, bold=True).pack(anchor="w")
        L(box, f"{purpose} · ВВЕДИТЕ КОД ДОСТУПА", fg=AMBER, size=9, bold=True).pack(anchor="w")
        self.pad = PinPad(self.body, self.submit)
        self.pad.pack(pady=px(8))
        self.msg = L(self.body, "", fg=RED, size=9, bold=True)
        self.msg.pack()
        row = tk.Frame(self.body, bg=PANEL)
        row.pack(fill=tk.X, pady=(px(8), 0))
        self.btn_ok = HudButton(row, "✓ ВОЙТИ  ENTER", self.submit, color=AMBER, height=38)
        self.btn_ok.pack(side=tk.LEFT)
        HudButton(row, "ОТМЕНА  ESC", self.cancel, height=38).pack(side=tk.LEFT, padx=px(6))
        lnk = L(self.body, "ЗАБЫЛИ КОД?", fg=CYAN, size=9, bold=True, cursor="hand2")
        lnk.pack(anchor="e", pady=(px(8), 0))
        lnk.bind("<Button-1>", lambda _e: self.forgot())
        self.bind("<Key>", self._key)
        self._tick()

    def _key(self, e) -> None:
        if e.keysym != "Escape":
            self.pad.key(e)

    def _tick(self) -> None:
        if not self.winfo_exists():
            return
        left = pilot_pin.lock_left(self.pilot["id"])
        if left:
            self.msg.configure(text=f"ВВОД ЗАБЛОКИРОВАН · ПОДОЖДИТЕ {left} С", fg=RED)
            self.btn_ok.set_enabled(False)
        elif not self.btn_ok._enabled:
            self.btn_ok.set_enabled(True)
            self.msg.configure(text="")
        self.after(500, self._tick)

    def submit(self) -> None:
        if pilot_pin.lock_left(self.pilot["id"]):
            return
        ok, msg = pilot_pin.verify(self.pilot["id"], self.pad.code)
        if ok:
            self.result = True
            self.destroy()
            return
        self.pad.clear(flash=RED)
        self.msg.configure(text=msg, fg=RED)
        self.after(600, lambda: self.winfo_exists() and self.pad.clear())

    def forgot(self) -> None:
        if ResetPinDialog(self, self.pilot).run():
            self.result = "reset"
            self.destroy()


class SetPinDialog(Modal):
    """Задать новый код. result: "set" | "later" | "none" | None."""

    def __init__(self, master, pilot: dict, first_time: bool = False) -> None:
        super().__init__(master, "Задайте код доступа", AMBER)
        self.pilot = pilot
        L(self.body, pilot["callsign"], size=16, bold=True).pack(anchor="w")
        L(self.body, ("Вы решили защитить пилота кодом доступа. Задайте его сейчас: 4–8 цифр.\n"
                      "Код хранится только в виде солёного хэша; это защита от случайного входа,\n"
                      "а не шифрование данных.") if first_time else "Новый код: 4–8 цифр.",
          fg=MUTED, size=9, justify="left").pack(anchor="w", pady=(px(4), px(10)))
        g = tk.Frame(self.body, bg=PANEL)
        g.pack(anchor="w")
        L(g, "НОВЫЙ КОД", fg=MUTED, size=9, bold=True).grid(row=0, column=0, sticky="w", pady=px(4))
        self.e1 = entry(g, width=12, size=16, show="●", mono=True)
        self.e1.grid(row=0, column=1, padx=px(10))
        L(g, "ПОВТОРИТЕ КОД", fg=MUTED, size=9, bold=True).grid(row=1, column=0, sticky="w", pady=px(4))
        self.e2 = entry(g, width=12, size=16, show="●", mono=True)
        self.e2.grid(row=1, column=1, padx=px(10))
        self.msg = L(self.body, "", fg=RED, size=9, bold=True)
        self.msg.pack(anchor="w", pady=px(6))
        row = tk.Frame(self.body, bg=PANEL)
        row.pack(fill=tk.X)
        HudButton(row, "✓ СОХРАНИТЬ КОД", self.save, color=AMBER, height=38).pack(side=tk.LEFT)
        HudButton(row, "ПОЗЖЕ" if first_time else "ОТМЕНА", self.later, height=38).pack(side=tk.LEFT, padx=px(6))
        if first_time:
            HudButton(row, "БЕЗ КОДА", self.no_pin, color=MUTED, height=38).pack(side=tk.LEFT)
        self.e1.focus_set()
        self.e1.bind("<Return>", lambda _e: self.e2.focus_set())
        self.e2.bind("<Return>", lambda _e: self.save())

    def save(self) -> None:
        a, b = self.e1.get().strip(), self.e2.get().strip()
        if not pilot_pin.valid_code(a):
            self.msg.configure(text="Код — от 4 до 8 цифр")
            return
        if a != b:
            self.msg.configure(text="Коды не совпадают")
            return
        pilot_pin.set_pin(self.pilot["id"], a)
        self.e1.delete(0, tk.END)
        self.e2.delete(0, tk.END)
        self.result = "set"
        self.destroy()

    def later(self) -> None:
        self.result = "later"
        self.destroy()

    def no_pin(self) -> None:
        pilot_pin.no_pin_wanted(self.pilot["id"])
        self.result = "none"
        self.destroy()


class ResetPinDialog(Modal):
    WAIT = 10

    def __init__(self, master, pilot: dict) -> None:
        super().__init__(master, f"Сброс кода доступа · {pilot['callsign']}", RED)
        self.pilot = pilot
        self.t0 = time.time()
        L(self.body, "Код будет удалён, прогресс сохранится.", fg=RED, size=11, bold=True).pack(anchor="w")
        L(self.body, "Введите позывной полностью для подтверждения:", fg=MUTED, size=9).pack(anchor="w", pady=(px(8), 0))
        self.e = entry(self.body, width=24)
        self.e.pack(anchor="w", pady=px(4))
        self.var = tk.BooleanVar(value=False)
        tk.Checkbutton(self.body, text="Я владелец этого пилота или имею разрешение", variable=self.var,
                       bg=PANEL, fg=TEXT, selectcolor=BG2, activebackground=PANEL, activeforeground=TEXT,
                       font=theme.font(9)).pack(anchor="w")
        row = tk.Frame(self.body, bg=PANEL)
        row.pack(fill=tk.X, pady=(px(10), 0))
        self.btn = HudButton(row, "СБРОСИТЬ КОД", self.do, color=RED, height=36)
        self.btn.pack(side=tk.LEFT)
        HudButton(row, "ОТМЕНА", self.cancel, height=36).pack(side=tk.LEFT, padx=px(6))
        self._tick()

    def _ready(self) -> bool:
        return (time.time() - self.t0 >= self.WAIT and self.var.get()
                and self.e.get().strip().casefold() == self.pilot["callsign"].casefold())

    def _tick(self) -> None:
        if not self.winfo_exists():
            return
        left = int(self.WAIT - (time.time() - self.t0)) + 1
        self.btn.set_text(f"СБРОСИТЬ КОД · {left}" if left > 0 else "СБРОСИТЬ КОД")
        self.btn.set_enabled(self._ready())
        self.after(300, self._tick)

    def do(self) -> None:
        if not self._ready():
            return
        pilot_pin.clear_pin(self.pilot["id"], reason="Код доступа сброшен через «Забыли код?»")
        self.result = True
        self.destroy()


def ask_pin(master, pilot: dict, purpose: str = "ВХОД В КАБИНУ") -> bool:
    """True — можно продолжать (кода нет, или он верен, или сброшен)."""
    if not pilot_pin.has_pin(pilot["id"]):
        return True
    r = PinDialog(master, pilot, purpose).run()
    if r == "reset":
        if SetPinDialog(master, pilots.get(pilot["id"]) or pilot).run() is None:
            pass
        return True
    return bool(r)


# ===================================================================== списание
class DeleteDialog(Modal):
    def __init__(self, master, pilot: dict, s: dict) -> None:
        super().__init__(master, f"Списать пилота «{pilot['callsign']}»?", RED)
        self.pilot = pilot
        L(self.body, f"СПИСАТЬ ПИЛОТА «{pilot['callsign'].upper()}»?", fg=RED, size=16, bold=True).pack(anchor="w")
        info = (f"Звание: {s['rank']} · {s['xp']} XP\nЗаходов печати: {s['runs']}\n"
                f"Свой текст: {fmt_num(s['book_pct'], ' %')}\nАнглийский: {s['en_known']} слов\n\n"
                "Папка пилота не стирается: она переносится в backups\\deleted\\.")
        L(self.body, info, fg=TEXT, size=10, justify="left").pack(anchor="w", pady=px(8))
        L(self.body, "Введите позывной для подтверждения:", fg=MUTED, size=9).pack(anchor="w")
        self.e = entry(self.body)
        self.e.pack(anchor="w", pady=px(4))
        row = tk.Frame(self.body, bg=PANEL)
        row.pack(fill=tk.X, pady=(px(8), 0))
        self.btn = HudButton(row, "✕ СПИСАТЬ", self.do, color=RED, height=36)
        self.btn.pack(side=tk.LEFT)
        self.btn.set_enabled(False)
        HudButton(row, "ОТМЕНА", self.cancel, height=36).pack(side=tk.LEFT, padx=px(6))
        self.e.bind("<KeyRelease>", lambda _e: self.btn.set_enabled(self._ok()))
        self.e.focus_set()

    def _ok(self) -> bool:
        return self.e.get().strip().casefold() == self.pilot["callsign"].casefold()

    def do(self) -> None:
        if self._ok():
            self.result = True
            self.destroy()


# ===================================================================== личное дело
class ProfileDialog(Modal):
    """Зачисление нового пилота (pid=None) или редактирование личного дела."""

    def __init__(self, master, pid: str | None = None) -> None:
        self.pid = pid
        self.p = dict(pilots.get(pid) or {}) if pid else {"callsign": "", "name": "", "accent": "cyan",
                                                           "avatar": {"kind": "builtin", "glyph": "star"},
                                                           "id": "preview"}
        super().__init__(master, "Личное дело · редактирование" if pid else "Зачисление в экипаж", AMBER)
        self.img_src: str | None = None
        cols = tk.Frame(self.body, bg=PANEL)
        cols.pack(fill=tk.BOTH, expand=True)
        left = tk.Frame(cols, bg=PANEL)
        left.pack(side=tk.LEFT, fill=tk.Y, anchor="n")
        mid = tk.Frame(cols, bg=PANEL)
        mid.pack(side=tk.LEFT, fill=tk.Y, padx=px(18), anchor="n")
        right = tk.Frame(cols, bg=PANEL)
        right.pack(side=tk.LEFT, fill=tk.Y, anchor="n")
        # -- личное дело
        L(left, "ЛИЧНОЕ ДЕЛО", fg=AMBER, size=10, bold=True).pack(anchor="w")
        L(left, "ПОЗЫВНОЙ *", fg=MUTED, size=8, bold=True).pack(anchor="w", pady=(px(8), 0))
        self.e_cs = entry(left, width=20, size=16)
        self.e_cs.insert(0, self.p.get("callsign", ""))
        self.e_cs.pack(anchor="w")
        self.err = L(left, "", fg=RED, size=8, bold=True)
        self.err.pack(anchor="w")
        L(left, "ИМЯ (ВТОРАЯ СТРОКА)", fg=MUTED, size=8, bold=True).pack(anchor="w", pady=(px(6), 0))
        self.e_name = entry(left, width=20, size=12)
        self.e_name.insert(0, self.p.get("name", ""))
        self.e_name.pack(anchor="w")
        L(left, "АКЦЕНТНЫЙ ЦВЕТ", fg=MUTED, size=8, bold=True).pack(anchor="w", pady=(px(10), px(2)))
        self.acc = tk.Canvas(left, bg=PANEL, highlightthickness=0, height=px(34), width=px(5 * 40))
        self.acc.pack(anchor="w")
        self.acc.bind("<Button-1>", self._pick_accent)
        # код доступа
        L(left, "КОД ДОСТУПА (НЕОБЯЗАТЕЛЬНО)", fg=MUTED, size=8, bold=True).pack(anchor="w", pady=(px(10), px(2)))
        pinbox = tk.Frame(left, bg=PANEL)
        pinbox.pack(anchor="w")
        if pid is None:
            self.e_pin1 = entry(pinbox, width=10, size=12, show="●", mono=True)
            self.e_pin1.grid(row=0, column=0)
            self.e_pin2 = entry(pinbox, width=10, size=12, show="●", mono=True)
            self.e_pin2.grid(row=0, column=1, padx=px(6))
            L(pinbox, "код · повторите (4–8 цифр)", fg=FAINT, size=8).grid(row=1, column=0, columnspan=2, sticky="w")
        else:
            has = pilot_pin.has_pin(pid)
            L(pinbox, "🔒 КОД ЗАДАН" if has else "КОДА НЕТ", fg=AMBER if has else MUTED, size=9,
              bold=True).pack(side=tk.LEFT, padx=(0, px(8)))
            HudButton(pinbox, "СМЕНИТЬ" if has else "ЗАДАТЬ", self._change_pin, height=28, font_size=8).pack(side=tk.LEFT)
            if has:
                HudButton(pinbox, "СНЯТЬ", self._remove_pin, height=28, font_size=8, color=RED).pack(
                    side=tk.LEFT, padx=px(4))
        if pid is None:
            L(left, "СТАРТОВЫЕ НАСТРОЙКИ", fg=MUTED, size=8, bold=True).pack(anchor="w", pady=(px(10), px(2)))
            self.copy_from = tk.StringVar(value="по умолчанию")
            names = ["по умолчанию"] + [f"от {x['callsign']}" for x in pilots.pilots()]
            om = tk.OptionMenu(left, self.copy_from, *names)
            om.configure(bg=BG2, fg=TEXT, activebackground=PANEL, activeforeground=TEXT, relief="flat",
                         highlightthickness=1, highlightbackground=LINE_HI, font=theme.font(9))
            om["menu"].configure(bg=BG2, fg=TEXT, font=theme.font(9))
            om.pack(anchor="w")
            L(left, "копируются только настройки, не прогресс", fg=FAINT, size=8).pack(anchor="w")
        # -- эмблема
        L(mid, "ЭМБЛЕМА ПИЛОТА", fg=AMBER, size=10, bold=True).pack(anchor="w")
        self.grid = tk.Canvas(mid, bg=PANEL, highlightthickness=0, width=px(8 * 56), height=px(2 * 56))
        self.grid.pack(anchor="w", pady=px(6))
        self.grid.bind("<Button-1>", self._pick_glyph)
        L(mid, "СВОЁ ИЗОБРАЖЕНИЕ", fg=MUTED, size=8, bold=True).pack(anchor="w", pady=(px(6), px(2)))
        r = tk.Frame(mid, bg=PANEL)
        r.pack(anchor="w")
        HudButton(r, "⇪ ЗАГРУЗИТЬ ФАЙЛ…", self._load_image, height=30, font_size=8).pack(side=tk.LEFT)
        HudButton(r, "⟲ СБРОСИТЬ", self._reset_image, height=30, font_size=8).pack(side=tk.LEFT, padx=px(4))
        L(mid, "PNG / GIF (JPG — если установлен Pillow), до 15 МБ.\nКартинка обрезается по центру до квадрата 256×256.",
          fg=FAINT, size=8, justify="left").pack(anchor="w")
        # -- предпросмотр
        L(right, "ПРЕДПРОСМОТР", fg=AMBER, size=10, bold=True).pack(anchor="w")
        self.prev = tk.Canvas(right, bg=PANEL, highlightthickness=0, width=px(230), height=px(230))
        self.prev.pack(pady=px(6))
        # -- кнопки
        row = tk.Frame(self.body, bg=PANEL)
        row.pack(fill=tk.X, pady=(px(12), 0))
        HudButton(row, "✓ СОХРАНИТЬ  ENTER" if pid else "✓ СОЗДАТЬ ПИЛОТА  ENTER", self.save, color=AMBER,
                  height=40).pack(side=tk.LEFT)
        HudButton(row, "ОТМЕНА  ESC", self.cancel, height=40).pack(side=tk.LEFT, padx=px(6))
        self.bind("<Return>", lambda _e: self.save())
        self.e_cs.bind("<KeyRelease>", lambda _e: self.redraw())
        self.e_name.bind("<KeyRelease>", lambda _e: self.redraw())
        self.e_cs.focus_set()
        self.redraw()

    # -- рисование
    def redraw(self) -> None:
        self.p["callsign"] = self.e_cs.get()
        self.p["name"] = self.e_name.get()
        c = self.acc
        c.delete("all")
        for i, a in enumerate(pilots.ACCENTS):
            col = avatars.accent_color(a)
            x = i * px(40) + px(2)
            on = self.p.get("accent") == a
            c.create_polygon(chamfer(x, px(3), x + px(32), px(31), px(5)), fill=col if on else blend(col, BG, 0.55),
                             outline=TEXT if on else "")
        g = self.grid
        g.delete("all")
        cur = self.p.get("avatar") or {}
        for i, (key, _gl, col) in enumerate(avatars.GLYPHS):
            x, y = (i % 8) * px(56) + px(28), (i // 8) * px(56) + px(28)
            on = cur.get("kind") == "builtin" and cur.get("glyph") == key
            if on:
                g.create_rectangle(x - px(26), y - px(26), x + px(26), y + px(26), outline=AMBER, width=2)
            avatars.draw(g, x, y, px(44), {"id": "x", "accent": col, "avatar": {"kind": "builtin", "glyph": key}})
        pv = self.prev
        pv.delete("all")
        w = px(230)
        pv.create_polygon(chamfer(2, 2, w - 2, w - 2, px(12)), fill=BG2, outline=avatars.accent_color(self.p.get("accent")))
        show = dict(self.p)
        if self.img_src and show.get("avatar", {}).get("kind") == "file":
            show["avatar"] = {"kind": "builtin", "glyph": "star"}
            pv.create_text(w / 2, px(150), text="(своя картинка — после сохранения)", fill=MUTED,
                           font=theme.font(7))
        avatars.draw(pv, w / 2, px(80), px(110), show, bg=BG2)
        pv.create_text(w / 2, px(165), text=self.p["callsign"] or "ПОЗЫВНОЙ", fill=TEXT, font=theme.font(15, True))
        pv.create_text(w / 2, px(190), text=self.p["name"], fill=MUTED, font=theme.font(9))
        pv.create_text(w / 2, px(212), text="★ КАДЕТ · 0 XP" if not self.pid else "", fill=AMBER, font=theme.font(8, True))

    def _pick_accent(self, e) -> None:
        i = int(e.x // px(40))
        if 0 <= i < len(pilots.ACCENTS):
            self.p["accent"] = pilots.ACCENTS[i]
            self.redraw()

    def _pick_glyph(self, e) -> None:
        i = int(e.y // px(56)) * 8 + int(e.x // px(56))
        if 0 <= i < len(avatars.GLYPHS):
            key, _g, col = avatars.GLYPHS[i]
            self.p["avatar"] = {"kind": "builtin", "glyph": key}
            self.p["accent"] = col
            self.img_src = None
            self.redraw()

    def _load_image(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="Эмблема пилота",
                                          filetypes=[("Картинки", "*.png *.gif *.jpg *.jpeg *.webp"), ("Все", "*.*")])
        if not path:
            return
        if Path(path).stat().st_size > avatars.MAX_FILE:
            messagebox.showwarning("Эмблема", "Файл больше 15 МБ", parent=self)
            return
        self.img_src = path
        self.p["avatar"] = {"kind": "file"}
        if self.pid:
            try:
                avatars.save_image(path, self.pid)
                self.img_src = None
            except ValueError as exc:
                messagebox.showwarning("Эмблема", str(exc), parent=self)
                self.p["avatar"] = {"kind": "builtin", "glyph": "star"}
        self.redraw()

    def _reset_image(self) -> None:
        self.img_src = None
        self.p["avatar"] = {"kind": "builtin", "glyph": "star"}
        self.redraw()

    def _change_pin(self) -> None:
        if not ask_pin(self, pilots.get(self.pid), "СМЕНА КОДА"):
            return
        SetPinDialog(self, pilots.get(self.pid)).run()
        self.destroy()
        self.result = "pin"

    def _remove_pin(self) -> None:
        if not ask_pin(self, pilots.get(self.pid), "СНЯТИЕ КОДА"):
            return
        pilot_pin.clear_pin(self.pid)
        pilots.update_pilot(self.pid, pin_setup_pending=False)
        self.result = "pin"
        self.destroy()

    def save(self) -> None:
        cs = self.e_cs.get().strip()
        err = pilots.validate_callsign(cs, exclude=self.pid)
        if err:
            self.err.configure(text=err)
            return
        if self.pid is None:
            a, b = self.e_pin1.get().strip(), self.e_pin2.get().strip()
            if a or b:
                if not pilot_pin.valid_code(a):
                    self.err.configure(text="Код доступа — от 4 до 8 цифр")
                    return
                if a != b:
                    self.err.configure(text="Коды доступа не совпадают")
                    return
            src = None
            sel = self.copy_from.get()
            for x in pilots.pilots():
                if sel == f"от {x['callsign']}":
                    src = x["id"]
            av = self.p.get("avatar") if not self.img_src else {"kind": "builtin", "glyph": "star"}
            entry_ = pilots.create(cs, name=self.e_name.get(), accent=self.p.get("accent", "cyan"), avatar=av,
                                   copy_settings_from=src)
            if self.img_src:
                try:
                    avatars.save_image(self.img_src, entry_["id"])
                    pilots.update_pilot(entry_["id"], avatar={"kind": "file"})
                except ValueError as exc:
                    messagebox.showwarning("Эмблема", str(exc), parent=self)
            if a:
                pilot_pin.set_pin(entry_["id"], a)
            self.e_pin1.delete(0, tk.END)
            self.e_pin2.delete(0, tk.END)
            self.result = entry_["id"]
        else:
            pilots.update_pilot(self.pid, callsign=cs, name=self.e_name.get().strip(),
                                accent=self.p.get("accent", "cyan"), avatar=self.p.get("avatar"))
            self.result = self.pid
        self.destroy()


# ===================================================================== карточка пилота
class PilotCard(tk.Canvas):
    W, H = 270, 360

    def __init__(self, master, pilot: dict, s: dict, selected: bool, on_click, on_double) -> None:
        super().__init__(master, bg=master.cget("bg"), highlightthickness=0, width=px(self.W), height=px(self.H),
                         cursor="hand2")
        self.pilot, self.s, self.selected = pilot, s, selected
        self.bind("<Button-1>", lambda _e: on_click(pilot["id"]))
        self.bind("<Double-Button-1>", lambda _e: on_double(pilot["id"]))
        self.draw()

    def draw(self) -> None:
        p, s = self.pilot, self.s
        w, h = px(self.W), px(self.H)
        acc = avatars.accent_color(p.get("accent"))
        frame = AMBER if self.selected else blend(acc, BG, 0.35)
        fill = blend(PANEL, AMBER, 0.06) if self.selected else PANEL
        self.create_polygon(chamfer(2, 2, w - 2, h - 2, px(14)), fill=fill, outline=frame, width=2 if self.selected else 1)
        if self.selected:
            self.create_text(px(14), px(16), text="▶ ВЫБРАН", anchor="w", fill=AMBER, font=theme.font(8, True))
        if p.get("locked"):
            self.create_text(w - px(14), px(16), text="🔒 КОД", anchor="e", fill=AMBER, font=theme.font(8, True))
        avatars.draw(self, w / 2, px(84), px(104), p, bg=fill)
        y = px(150)
        self.create_text(w / 2, y, text=p["callsign"], fill=TEXT, font=theme.font(17, True), width=w - px(20),
                         justify="center")
        if p.get("name"):
            self.create_text(w / 2, y + px(24), text=p["name"], fill=MUTED, font=theme.font(9, True))
        y += px(48)
        self.create_text(w / 2, y, text=f"★ {s['rank'].upper()}", fill=AMBER, font=theme.font(10, True))
        lo, hi = s.get("rank_lo", 0), s.get("rank_hi")
        frac = 1.0 if not hi else (s["xp"] - lo) / max(1, hi - lo)
        bx0, bx1, by = px(30), w - px(30), y + px(16)
        self.create_rectangle(bx0, by, bx1, by + px(5), fill=BG2, outline="")
        self.create_rectangle(bx0, by, bx0 + (bx1 - bx0) * max(0, min(1, frac)), by + px(5), fill=AMBER, outline="")
        self.create_text(w / 2, by + px(16), text=f"{s['xp']} / {hi} XP" if hi else f"{s['xp']} XP", fill=MUTED,
                         font=theme.font(8, True))
        rows = [("ПЕЧАТЬ", fmt_num(s["best_cpm"], " зн/мин")),
                (s.get("book_title", "свой текст")[:14].upper() or "СВОЙ ТЕКСТ", fmt_num(s["book_pct"], " %")),
                ("ENGLISH", fmt_num(s["en_known"], " слов")),
                ("ЧТЕНИЕ", fmt_num(s.get("sr_eff") or s.get("sr_best"), " сл/мин"))]
        y = by + px(36)
        for k, v in rows:
            self.create_text(px(22), y, text=k, anchor="w", fill=MUTED, font=theme.font(8, True))
            self.create_text(w - px(22), y, text=v, anchor="e", fill=CYAN, font=theme.font(10, True, mono=True))
            y += px(19)
        self.create_text(w / 2, h - px(16), text=f"последний полёт · {when(s.get('last_day'))}", fill=FAINT,
                         font=theme.font(8))


class AddCard(tk.Canvas):
    def __init__(self, master, on_add, on_import) -> None:
        super().__init__(master, bg=master.cget("bg"), highlightthickness=0, width=px(PilotCard.W),
                         height=px(PilotCard.H), cursor="hand2")
        w, h = px(PilotCard.W), px(PilotCard.H)
        self.create_polygon(chamfer(2, 2, w - 2, h - px(60), px(14)), fill=BG, outline=LINE_HI, dash=(5, 4))
        self.create_text(w / 2, px(120), text="+", fill=CYAN, font=theme.font(40, True))
        self.create_text(w / 2, px(190), text="ЗАЧИСЛИТЬ\nВ ЭКИПАЖ", fill=TEXT, font=theme.font(12, True),
                         justify="center")
        self.create_text(w / 2, px(236), text="Insert", fill=MUTED, font=theme.font(8, True))
        self.create_text(w / 2, h - px(30), text="⇩ ИМПОРТ ПИЛОТА", fill=CYAN, font=theme.font(10, True), tags="imp")
        self.bind("<Button-1>", lambda e: on_import() if e.y > h - px(60) else on_add())


# ===================================================================== вход в кабину
class LoginScreen(tk.Frame):
    """«ВХОД В КАБИНУ». on_enter(pid) вызывается после проверки кода."""

    def __init__(self, master, *, on_enter, on_exit, on_board, active: str | None = None, app_version="") -> None:
        super().__init__(master, bg=BG)
        self.on_enter, self.on_exit, self.on_board = on_enter, on_exit, on_board
        self.active = active
        self.app_version = app_version
        reg = pilots.load_registry() or {}
        self.sel = reg.get("last_pilot")
        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(16), pady=(px(10), 0))
        logo = tk.Canvas(top, bg=BG, highlightthickness=0, width=px(260), height=px(44))
        logo.pack(side=tk.LEFT)
        avatars.draw(logo, px(22), px(22), px(36), {"id": "-", "accent": "cyan",
                                                     "avatar": {"kind": "builtin", "glyph": "star"}})
        logo.create_text(px(48), px(15), text="STAR TYPING", anchor="w", fill=TEXT, font=theme.font(17, True))
        logo.create_text(px(49), px(35), text="ВХОД В КАБИНУ", anchor="w", fill=AMBER, font=theme.font(8, True))
        self.clock = L(top, "", fg=CYAN, size=14, bold=True, mono=True, bg=BG)
        self.clock.pack(side=tk.RIGHT)
        HudButton(top, "★ ДОСКА ПОЧЁТА", self.on_board, color=AMBER, height=36).pack(side=tk.RIGHT, padx=px(10))
        self.crew = L(top, "", fg=MUTED, size=10, bold=True, bg=BG)
        self.crew.pack(side=tk.RIGHT, padx=px(10))
        tk.Frame(self, bg=LINE, height=1).pack(fill=tk.X, padx=px(16), pady=px(6))
        L(self, "ВЫБЕРИТЕ ПИЛОТА", fg=AMBER, size=12, bold=True, bg=BG).pack(anchor="w", padx=px(20))
        L(self, "← → — выбор · Enter или двойной щелчок — вход · Insert — новый пилот · F2 — личное дело · Del — списать",
          fg=MUTED, size=8, bg=BG).pack(anchor="w", padx=px(20))
        wrap = tk.Frame(self, bg=BG)
        wrap.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(8))
        self.canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        self.bar = tk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Canvas(self.canvas, bg=BG, highlightthickness=0, bd=0)   # холст: «Живой космос» между карточками
        self.inner.living_sharp = True
        self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.bar.pack(side=tk.RIGHT, fill=tk.Y)
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda _e: self._layout())
        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill=tk.X, padx=px(16), pady=(0, px(12)))
        self.enter_box = tk.Frame(bottom, bg=BG)
        self.enter_box.pack(side=tk.LEFT)
        self.btn_enter = None
        for t, f, c in (("✎ ЛИЧНОЕ ДЕЛО  F2", self.edit, CYAN), ("⇪ ЭКСПОРТ", self.export, CYAN),
                        ("✕ СПИСАТЬ  DEL", self.delete, RED)):
            HudButton(bottom, t, f, color=c, height=40, font_size=9).pack(side=tk.LEFT, padx=px(3))
        self.ask = tk.BooleanVar(value=bool(reg.get("ask_on_start", True)))
        tk.Checkbutton(bottom, text="СПРАШИВАТЬ ПРИ ЗАПУСКЕ", variable=self.ask, command=self._ask_changed,
                       bg=BG, fg=MUTED, selectcolor=BG2, activebackground=BG, activeforeground=TEXT,
                       font=theme.font(9, True)).pack(side=tk.RIGHT)
        HudButton(bottom, "ВЫХОД  ESC", self.on_exit, height=40, font_size=9).pack(side=tk.RIGHT, padx=px(8))
        self.cards: list = []
        self.refresh()
        self._tick()

    def _tick(self) -> None:
        if self.winfo_exists():
            self.clock.configure(text=time.strftime("%H:%M"))
            self.after(5000, self._tick)

    def _ask_changed(self) -> None:
        reg = pilots.load_registry()
        if reg:
            reg["ask_on_start"] = bool(self.ask.get())
            pilots.save_registry(reg)

    def refresh(self) -> None:
        self.plist = pilots.pilots()
        ids = [p["id"] for p in self.plist]
        if self.sel not in ids:
            self.sel = ids[0] if ids else None
        self.stats = {p["id"]: pilot_stats(p["id"]) for p in self.plist}
        n = len(self.plist)
        self.crew.configure(text=f"ЭКИПАЖ: {n} {'ПИЛОТ' if n == 1 else 'ПИЛОТА' if 2 <= n <= 4 else 'ПИЛОТОВ'}")
        self._layout()

    def _layout(self) -> None:
        for w in self.inner.winfo_children():
            w.destroy()
        width = max(self.canvas.winfo_width(), px(600))
        per = max(1, min(4, int(width // px(PilotCard.W + 16))))
        items = [PilotCard(self.inner, p, self.stats[p["id"]], p["id"] == self.sel, self.select, self.enter_id)
                 for p in self.plist]
        items.append(AddCard(self.inner, self.add, self.import_))
        for i, it in enumerate(items):
            it.grid(row=i // per, column=i % per, padx=px(8), pady=px(8))
        cur = next((p for p in self.plist if p["id"] == self.sel), None)
        if self.btn_enter is not None:
            self.btn_enter.destroy()
        text = f"► ВОЙТИ В КАБИНУ · {cur['callsign'].upper()}  ENTER" if cur else "► ВОЙТИ В КАБИНУ"
        self.btn_enter = HudButton(self.enter_box, text, self.enter, color=AMBER, height=44, font_size=11, active=True)
        self.btn_enter.pack()

    def select(self, pid: str) -> None:
        self.sel = pid
        self._layout()

    def move(self, d: int) -> None:
        ids = [p["id"] for p in self.plist]
        if ids:
            i = (ids.index(self.sel) + d) % len(ids) if self.sel in ids else 0
            self.select(ids[i])

    def enter_id(self, pid: str) -> None:
        self.sel = pid
        self.enter()

    def enter(self) -> None:
        p = pilots.get(self.sel) if self.sel else None
        if p is None:
            return
        if not ask_pin(self, p, "ВХОД В КАБИНУ"):
            return
        self.on_enter(p["id"])

    def add(self) -> None:
        pid = ProfileDialog(self).run()
        if pid:
            self.sel = pid
            self.refresh()

    def edit(self) -> None:
        p = pilots.get(self.sel) if self.sel else None
        if p and ask_pin(self, p, "ЛИЧНОЕ ДЕЛО"):
            ProfileDialog(self, p["id"]).run()
            self.refresh()

    def export(self) -> None:
        p = pilots.get(self.sel) if self.sel else None
        if p:
            export_pilot(self, p, self.app_version)

    def import_(self) -> None:
        pid = import_pilot(self)
        if pid:
            self.sel = pid
            self.refresh()

    def delete(self) -> None:
        p = pilots.get(self.sel) if self.sel else None
        if p is None:
            return
        if p["id"] == self.active:
            messagebox.showinfo("Списание", "Этот пилот сейчас в кабине. Сначала войдите другим пилотом.", parent=self)
            return
        if len(self.plist) <= 1:
            messagebox.showinfo("Списание", "Нельзя списать последнего пилота.", parent=self)
            return
        if not ask_pin(self, p, "СПИСАНИЕ"):
            return
        if DeleteDialog(self, p, self.stats[p["id"]]).run():
            try:
                pilots.delete(p["id"], active=self.active)
            except ValueError as exc:
                messagebox.showwarning("Списание", str(exc), parent=self)
            self.sel = None
            self.refresh()

    def on_key(self, e) -> None:
        k = e.keysym
        if k in ("Left", "Up"):
            self.move(-1)
        elif k in ("Right", "Down", "Tab"):
            self.move(1)
        elif k in ("Return", "KP_Enter"):
            self.enter()
        elif k == "Insert":
            self.add()
        elif k == "F2":
            self.edit()
        elif k == "Delete":
            self.delete()
        elif k == "Escape":
            self.on_exit()


def export_pilot(master, p: dict, app_version: str = "") -> None:
    if not ask_pin(master, p, "ЭКСПОРТ"):
        return
    docs = Path.home() / "Documents"
    path = filedialog.asksaveasfilename(parent=master, title="Экспорт пилота", defaultextension=".stpilot",
                                        initialdir=str(docs if docs.exists() else Path.home()),
                                        initialfile=f"{p['callsign']}_{time.strftime('%Y-%m-%d')}.stpilot",
                                        filetypes=[("Пилот Star Typing", "*.stpilot")])
    if path:
        pilots.export(p["id"], Path(path), app_version)
        messagebox.showinfo("Экспорт", f"Пилот сохранён:\n{path}", parent=master)


def import_pilot(master) -> str | None:
    path = filedialog.askopenfilename(parent=master, title="Импорт пилота",
                                      filetypes=[("Пилот Star Typing", "*.stpilot"), ("Все", "*.*")])
    if not path:
        return None
    try:
        man = pilots.read_package(Path(path))
        cs = man["pilot"].get("callsign", "Пилот")
        new_cs = pilots.free_callsign(cs)
        if new_cs != cs and not messagebox.askyesno(
                "Импорт", f"Позывной «{cs}» уже занят. Импортировать как «{new_cs}»?", parent=master):
            return None
        return pilots.import_package(Path(path), new_cs)["id"]
    except Exception as exc:  # noqa: BLE001
        messagebox.showerror("Импорт", f"Не удалось импортировать:\n{exc}", parent=master)
        return None


# ===================================================================== доска почёта
COLUMNS = [
    # key, title, width, sort key
    ("place", "№", 50, None),
    ("pilot", "ПИЛОТ", 230, lambda s, p: p["callsign"].casefold()),
    ("rank", "ЗВАНИЕ", 205, lambda s, p: (s["rank_idx"], s["xp"])),
    ("xp", "XP", 90, lambda s, p: s["xp"]),
    ("typing", "ПЕЧАТЬ", 140, lambda s, p: (s["best_cpm"], s["best_acc"])),
    ("book", "СВОЙ ТЕКСТ", 120, lambda s, p: s["book_pct"] or 0),
    ("english", "ENGLISH", 140, lambda s, p: (s["en_known"], s["en_pron"] or 0)),
    ("reading", "ЧТЕНИЕ", 120, lambda s, p: s["sr_eff"] or 0),
    ("schulte", "ШУЛЬТЕ", 110, lambda s, p: -(s["schulte"][1]) if s["schulte"] else -1e9),
    ("streak", "СЕРИЯ", 80, lambda s, p: s["streak"]),
    ("ach", "ДОСТИЖЕНИЯ", 120, lambda s, p: s["ach_done"]),
]


class HonorBoard(tk.Frame):
    """«ДОСКА ПОЧЁТА»: все пилоты экипажа, только чтение (код не нужен)."""

    ROW = 66

    def __init__(self, master, *, on_back=None, active: str | None = None) -> None:
        super().__init__(master, bg=BG)
        self.on_back = on_back
        self.active = active
        self.period = "all"
        self.sort_key = "rank"
        self.desc = True
        self.detail_id: str | None = None
        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(16), pady=(px(8), px(4)))
        tk.Frame(top, bg=AMBER, width=px(5)).pack(side=tk.LEFT, fill=tk.Y, padx=(0, px(10)))
        box = tk.Frame(top, bg=BG)
        box.pack(side=tk.LEFT)
        L(box, "ДОСКА ПОЧЁТА", fg=TEXT, size=16, bold=True, bg=BG).pack(anchor="w")
        L(box, "все пилоты экипажа · щелчок по заголовку — сортировка · щелчок по пилоту — достижения",
          fg=MUTED, size=8, bg=BG).pack(anchor="w")
        if on_back:
            HudButton(top, "← НАЗАД  ESC", on_back, height=34).pack(side=tk.RIGHT)
        self.btn_week = HudButton(top, "НЕДЕЛЯ", lambda: self.set_period("week"), height=34)
        self.btn_week.pack(side=tk.RIGHT, padx=px(4))
        self.btn_all = HudButton(top, "ВСЁ ВРЕМЯ", lambda: self.set_period("all"), height=34)
        self.btn_all.pack(side=tk.RIGHT, padx=px(4))
        L(top, "ПЕРИОД:", fg=MUTED, size=8, bold=True, bg=BG).pack(side=tk.RIGHT, padx=px(4))
        body = tk.Frame(self, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=(px(4), px(12)))
        self.table = tk.Canvas(body, bg=BG, highlightthickness=0)
        self.table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.table.bind("<Configure>", lambda _e: self.draw())
        self.table.bind("<Button-1>", self.click)
        self.side = HudPanel(body, "ДОСТИЖЕНИЯ", accent=AMBER)
        self.side.configure(width=px(300))
        self.side.pack_propagate(False)
        self.refresh()

    def set_period(self, period: str) -> None:
        self.period = period
        if period == "week" and self.sort_key == "rank":
            self.sort_key = "xp"
        self.refresh()

    def refresh(self) -> None:
        self.plist = pilots.pilots()
        self.stats = {p["id"]: pilot_stats(p["id"], self.period) for p in self.plist}
        self.btn_all.set_active(self.period == "all")
        self.btn_week.set_active(self.period == "week")
        self.draw()
        self._detail()

    def _sorted(self) -> list[dict]:
        col = next(c for c in COLUMNS if c[0] == self.sort_key)
        fn = col[3]
        if self.sort_key == "xp" and self.period == "week":
            fn = lambda s, p: s["xp_week"]  # noqa: E731
        return sorted(self.plist, key=lambda p: fn(self.stats[p["id"]], p), reverse=self.desc)

    def _cols(self, w: int):
        total = sum(c[2] for c in COLUMNS)
        k = max(0.6, (w - px(10)) / px(total))
        x = px(5)
        out = []
        for c in COLUMNS:
            cw = px(c[2]) * k
            out.append((c, x, cw))
            x += cw
        return out

    def draw(self) -> None:
        t = self.table
        t.delete("all")
        w = t.winfo_width()
        if w < 100:
            return
        cols = self._cols(w)
        hh = px(34)
        t.create_rectangle(0, 0, w, hh, fill=PANEL, outline=LINE)
        for (key, title, _cw0, fn), x, cw in cols:
            on = key == self.sort_key
            label = title + ((" ▼" if self.desc else " ▲") if on else "")
            if key == "xp" and self.period == "week":
                label = "XP ЗА НЕДЕЛЮ" + ((" ▼" if self.desc else " ▲") if on else "")
            t.create_text(x + px(6), hh / 2, text=label, anchor="w", fill=AMBER if on else MUTED,
                          font=theme.font(8, True))
        self._row_ids = []
        for i, p in enumerate(self._sorted()):
            s = self.stats[p["id"]]
            y0 = hh + px(4) + i * px(self.ROW)
            y1 = y0 + px(self.ROW) - px(4)
            yc = (y0 + y1) / 2
            acc = avatars.accent_color(p.get("accent"))
            hl = p["id"] == self.detail_id
            fill = blend(PANEL, AMBER, 0.08) if hl else (blend(PANEL, CYAN, 0.04) if p["id"] == self.active else PANEL)
            t.create_polygon(chamfer(2, y0, w - 2, y1, px(8)), fill=fill,
                             outline=MEDALS[i] if i < 3 else LINE, width=2 if i < 3 else 1)
            self._row_ids.append((y0, y1, p["id"]))
            for (key, _t, _c, _f), x, cw in cols:
                cx = x + px(6)
                if key == "place":
                    if i < 3:
                        r = px(15)
                        t.create_oval(x + cw / 2 - r, yc - r, x + cw / 2 + r, yc + r, fill=blend(MEDALS[i], BG, 0.35),
                                      outline=MEDALS[i], width=2)
                        t.create_text(x + cw / 2, yc, text=str(i + 1), fill=TEXT, font=theme.font(12, True))
                    else:
                        t.create_text(x + cw / 2, yc, text=str(i + 1), fill=MUTED, font=theme.font(12, True))
                elif key == "pilot":
                    avatars.draw(t, cx + px(22), yc, px(46), p, bg=fill)
                    t.create_text(cx + px(52), yc - px(9), text=p["callsign"], anchor="w", fill=TEXT,
                                  font=theme.font(12, True))
                    sub = (p.get("name") or "") + ("  · В КАБИНЕ" if p["id"] == self.active else "")
                    t.create_text(cx + px(52), yc + px(11), text=sub, anchor="w",
                                  fill=CYAN if p["id"] == self.active else MUTED, font=theme.font(8, True))
                    if p.get("locked"):
                        t.create_text(x + cw - px(4), y0 + px(10), text="🔒", anchor="e", fill=AMBER,
                                      font=theme.font(8))
                elif key == "rank":
                    self._badge(t, cx, yc, s["rank_idx"], acc)
                    t.create_text(cx + px(30), yc, text=s["rank"], anchor="w", fill=AMBER, font=theme.font(9, True),
                                  width=cw - px(36))
                else:
                    a, b = self._cell(key, s)
                    t.create_text(cx, yc - (px(8) if b else 0), text=a, anchor="w", fill=CYAN if a != "—" else FAINT,
                                  font=theme.font(12, True, mono=True))
                    if b:
                        t.create_text(cx, yc + px(12), text=b, anchor="w", fill=MUTED, font=theme.font(8))
        if not self.plist:
            t.create_text(w / 2, hh + px(60), text="Экипаж пуст", fill=MUTED, font=theme.font(12))
        t.configure(scrollregion=(0, 0, w, hh + px(10) + len(self.plist) * px(self.ROW)))

    def _badge(self, t, x, y, idx, acc) -> None:
        """Шеврон звания: число полосок = индекс звания (0–7)."""
        r = px(13)
        t.create_polygon(x, y - r, x + 2 * r, y - r, x + 2 * r, y + r * 0.4, x + r, y + r, x, y + r * 0.4,
                         fill=blend(AMBER, BG, 0.7), outline=AMBER)
        n = min(idx, 4)
        for k in range(n):
            yy = y - r * 0.55 + k * r * 0.33
            t.create_line(x + r * 0.45, yy, x + r, yy + r * 0.22, x + r * 1.55, yy, fill=AMBER, width=2)
        if idx > 4:
            t.create_text(x + r, y + r * 0.2, text="★" * (idx - 4), fill=TEXT, font=theme.font(6, True))

    def _cell(self, key: str, s: dict) -> tuple[str, str]:
        if key == "xp":
            return (fmt_num(s["xp_week"]) if self.period == "week" else fmt_num(s["xp"])), ""
        if key == "typing":
            return fmt_num(s["best_cpm"]), (f"зн/мин · {s['best_acc']:.1f} %" if s["best_cpm"] else "")
        if key == "book":
            return fmt_num(s["book_pct"], " %") if s["book_pct"] else "—", (s["book_title"][:16] if s["book_pct"] else "")
        if key == "english":
            return fmt_num(s["en_known"]), (f"слов · речь {s['en_pron']} %" if s["en_pron"] is not None
                                             else ("слов" if s["en_known"] else ""))
        if key == "reading":
            return fmt_num(s["sr_eff"]), ("эфф. сл/мин" if s["sr_eff"] else "")
        if key == "schulte":
            return (f"{s['schulte'][1]:.1f} с", s["schulte"][0]) if s["schulte"] else ("—", "")
        if key == "streak":
            return (f"{s['streak']}", "дн.") if s["streak"] else ("—", "")
        if key == "ach":
            return f"{s['ach_done']}", f"из {s['ach_total']}"
        return "", ""

    def click(self, e) -> None:
        if e.y < px(34):
            for (key, _t, _c, fn), x, cw in self._cols(self.table.winfo_width()):
                if x <= e.x < x + cw and fn is not None:
                    if self.sort_key == key:
                        self.desc = not self.desc
                    else:
                        self.sort_key, self.desc = key, key != "pilot"
                    self.draw()
            return
        for y0, y1, pid in getattr(self, "_row_ids", []):
            if y0 <= e.y <= y1:
                self.detail_id = None if self.detail_id == pid else pid
                self.draw()
                self._detail()

    def _detail(self) -> None:
        if not self.detail_id or self.detail_id not in self.stats:
            self.side.pack_forget()
            return
        if not self.side.winfo_ismapped():
            self.side.pack(side=tk.RIGHT, fill=tk.Y, padx=(px(10), 0))
        b = self.side.body
        for w in b.winfo_children():
            w.destroy()
        p = pilots.get(self.detail_id) or {}
        s = self.stats[self.detail_id]
        L(b, p.get("callsign", ""), size=13, bold=True).pack(anchor="w")
        L(b, f"{s['ach_done']} из {s['ach_total']}", fg=AMBER, size=9, bold=True).pack(anchor="w", pady=(0, px(6)))
        for name, ok in sorted(s["achievements"], key=lambda x: not x[1]):
            L(b, ("★ " if ok else "☆ ") + name, fg=TEXT if ok else FAINT, size=9, anchor="w", justify="left",
              wraplength=px(260)).pack(anchor="w")

    def on_key(self, e) -> None:
        if e.keysym == "Escape" and self.on_back:
            self.on_back()


# ===================================================================== окно до запуска кабины
def run_login(root: tk.Tk, *, app_version: str = "", initial_board: bool = False) -> str | None:
    """Показать «ВХОД В КАБИНУ» в root; вернуть выбранный id (код проверен) или None (выход)."""
    box: dict = {"pid": None}
    root.title("Star Typing — вход в кабину")
    root.configure(bg=BG)
    holder = tk.Frame(root, bg=BG)
    holder.pack(fill=tk.BOTH, expand=True)
    holder.grid_rowconfigure(0, weight=1)
    holder.grid_columnconfigure(0, weight=1)
    cur = {"page": None}
    live = None
    try:
        from stamina.living_space import LivingSpace, DEFAULT_MODE
        live = LivingSpace(root, holder, pilots.load_app().get("living_space", DEFAULT_MODE))
    except Exception:  # noqa: BLE001
        live = None

    def done(pid):
        box["pid"] = pid
        root.quit()

    def show_board():
        board = HonorBoard(holder, on_back=show_login)
        board.grid(row=0, column=0, sticky="nsew")
        _swap(board)

    def show_login():
        login = LoginScreen(holder, on_enter=done, on_exit=lambda: done(None), on_board=show_board,
                            app_version=app_version)
        login.grid(row=0, column=0, sticky="nsew")
        _swap(login)

    def _swap(page):
        if cur["page"] is not None:
            cur["page"].destroy()
        cur["page"] = page
        page.tkraise()
        if live is not None:
            root.after(80, lambda: page.winfo_exists() and live.attach(page))

    root.bind("<Key>", lambda e: cur["page"] is not None and e.widget.winfo_toplevel() is root
              and not isinstance(e.widget, tk.Entry) and cur["page"].on_key(e))
    root.protocol("WM_DELETE_WINDOW", lambda: done(None))
    from stamina import keynav
    keynav.install(root)
    show_board() if initial_board else show_login()
    root.after(200, root.focus_force)
    root.mainloop()
    root.unbind("<Key>")
    if live is not None:
        live.detach()
    holder.destroy()
    return box["pid"]
