"""Главное окно — «пульт космического корабля»: верхняя панель, разделы, статус."""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox

from pathlib import Path

from stamina import APP_NAME, __version__, avatars, english_hook, missions, pilots, speedread_hook, theme
from stamina.bridge import Bridge
from stamina.hud import HudButton
from stamina.screens import CargoScreen, HelpScreen, LogScreen, MissionsScreen, SettingsScreen
from stamina.session_storage import clear_session, load_session
from stamina.sounds import SoundBoard
from stamina.storage import Store
from stamina.text_processing import process_text
from stamina.theme import AMBER, BG, CYAN, CYAN_DIM, GREEN, LINE, MUTED, PANEL, TEXT, blend, px


class Cockpit(tk.Tk):
    SCREENS = [("bridge", "МОСТИК"), ("missions", "МИССИИ"), ("cargo", "СВОЙ ТЕКСТ"),
               ("log", "БОРТЖУРНАЛ"), ("settings", "НАСТРОЙКИ")]

    def __init__(self) -> None:
        super().__init__()
        theme.init(self)
        self.store = Store()
        st = self.store.settings
        self.sound = SoundBoard(bool(st["sound"]), int(st.get("volume", 3)))
        self.translator = None
        self.current: str | None = None
        self._prev_screen: str | None = None
        self._last_action = None      # для F5: функция перезапуска
        self.pilot = pilots.active()  # None — режим без экипажа (миграция не удалась)
        self._update_title()
        self._set_icon()
        self.configure(bg=BG)
        self._apply_geometry()
        self._english_cls = english_hook.load_class()  # вкладка «АНГЛИЙСКИЙ» (stamina/english)
        if self._english_cls is not None:
            self.SCREENS = [s for s in self.SCREENS if s[0] != "settings"] + \
                [(english_hook.KEY, english_hook.TITLE), ("settings", "НАСТРОЙКИ")]
        self._speed_cls = speedread_hook.load_class()  # вкладка «СКОРОЧТЕНИЕ» (stamina/speedread)
        if self._speed_cls is not None:
            self.SCREENS = [s for s in self.SCREENS if s[0] != "settings"] + \
                [(speedread_hook.KEY, speedread_hook.TITLE), ("settings", "НАСТРОЙКИ")]
        self._build()
        self.bind("<Key>", self._on_key)
        for i, (name, _t) in enumerate(self.SCREENS, 1):
            self.bind(f"<Control-Key-{i}>", lambda _e, n=name: self.show(n))
        self.bind("<Control-Shift-P>", lambda _e: self.switch_pilot())
        self.bind("<F5>", lambda _e: self.restart_current())
        self.bind("<F9>", lambda _e: self.toggle_sound())
        self.bind("<F1>", lambda _e: self.open_help())
        self.bind("<FocusOut>", self._on_focus_out)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._clock_tick()
        from stamina.living_space import LivingSpace, DEFAULT_MODE
        self.living = LivingSpace(self, self.content, self.store.settings.get("living_space", DEFAULT_MODE))
        self.after(60, self._bootstrap)
        self.after(100, self._tick)

    # ------------------------------------------------------------------
    def _apply_geometry(self) -> None:
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.minsize(min(px(1000), sw - 40), min(px(660), sh - 80))
        geo = self.store.settings.get("geometry") or ""
        if self.pilot is not None:
            geo = pilots.load_app().get("geometry") or geo  # окно — общее для экипажа
        if geo == "zoomed":
            self.after(10, lambda: self.state("zoomed"))
            geo = ""
        if geo:
            try:
                size, x, y = geo.replace("+", " +").split(" ")[0], *geo.split("+")[1:3]
                w, h = (int(v) for v in size.split("x"))
                if 0 <= int(x) < sw - 100 and 0 <= int(y) < sh - 100 and w <= sw and h <= sh:
                    self.geometry(geo)
                    return
            except (ValueError, TypeError):
                pass
        w = min(px(1260), int(sw * 0.94))
        h = min(px(800), int(sh * 0.90))
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 2 - 20)}")

    def _build(self) -> None:
        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(10), pady=(px(8), 0))
        self._compact = len(self.SCREENS) > 6  # много разделов — шапка поуже
        logo = tk.Canvas(top, bg=BG, highlightthickness=0, width=px(200 if self._compact else 250),
                         height=px(44))
        logo.pack(side=tk.LEFT)
        self._draw_logo(logo)
        nav = tk.Frame(top, bg=BG)
        nav.pack(side=tk.LEFT, padx=px(4 if self._compact else 10))
        self.nav_buttons: dict[str, HudButton] = {}
        for i, (name, title) in enumerate(self.SCREENS, 1):
            fs = 10 if len(self.SCREENS) <= 5 else 9 if len(self.SCREENS) <= 6 else 8
            bw = None
            if self._compact:  # узкие поля у кнопок, чтобы всё влезло в 1260 px
                import tkinter.font as tkfont
                bw = int(tkfont.Font(font=theme.font(fs, True)).measure(title) / theme.S) + 18
            b = HudButton(nav, f"{title}", lambda n=name: self.show(n), height=36, font_size=fs, width=bw)
            b.pack(side=tk.LEFT, padx=px(3) if len(self.SCREENS) <= 6 else px(1))
            self.nav_buttons[name] = b
        right = tk.Frame(top, bg=BG)
        right.pack(side=tk.RIGHT)
        self.clock = tk.Label(right, text="", bg=BG, fg=CYAN, font=theme.font(14, True, mono=True))
        self.clock.pack(side=tk.RIGHT, padx=(px(10), 0))
        self.btn_sound = HudButton(right, "♪ ЗВУК ВЫКЛ", self.toggle_sound, height=36, font_size=9,
                                   width=116 if len(self.SCREENS) <= 6 else 38)
        self.btn_sound.pack(side=tk.RIGHT, padx=px(4))
        self.btn_help = HudButton(right, "?" if self._compact else "? F1", self.open_help, height=36,
                                  font_size=9, width=36 if self._compact else 60, color=AMBER)
        self.btn_help.pack(side=tk.RIGHT, padx=px(4))
        self.rank_label = tk.Canvas(right, bg=BG, highlightthickness=0, height=px(44),
                                    width=px(170 if self._compact else 230), cursor="hand2")
        self.rank_label.pack(side=tk.RIGHT, padx=px(6))
        self.rank_label.bind("<Button-1>", lambda _e: self.pilot_menu())
        line = tk.Canvas(self, bg=BG, highlightthickness=0, height=px(6))
        line.pack(fill=tk.X, padx=px(10), pady=(px(4), 0))
        line.bind("<Configure>", lambda e: self._draw_line(line))

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(fill=tk.BOTH, expand=True)
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        status = tk.Frame(self, bg=blend(BG, CYAN, 0.04))
        status.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_dot = tk.Label(status, text="●", bg=status["bg"], fg=GREEN, font=theme.font(9))
        self.status_dot.pack(side=tk.LEFT, padx=(px(10), px(4)))
        self.status = tk.Label(status, text="ВСЕ СИСТЕМЫ В НОРМЕ", bg=status["bg"], fg=MUTED,
                               font=theme.font(8, True))
        self.status.pack(side=tk.LEFT)
        tk.Label(status, text=f"F1 справка · F5 заново · Esc пауза · F9 звук · Ctrl+1…{len(self.SCREENS)} разделы",
                 bg=status["bg"], fg=MUTED, font=theme.font(8)).pack(side=tk.RIGHT, padx=px(10))

        self.screens = {
            "bridge": Bridge(self.content, self),
            "missions": MissionsScreen(self.content, self),
            "cargo": CargoScreen(self.content, self),
            "log": LogScreen(self.content, self),
            "settings": SettingsScreen(self.content, self),
            "help": HelpScreen(self.content, self),
            "honor": self._make_honor(),
        }
        if self._english_cls is not None:
            eng = english_hook.create(self._english_cls, self.content, self)
            if eng is not None:
                self.screens[english_hook.KEY] = eng
            else:
                self.SCREENS = [s for s in self.SCREENS if s[0] != english_hook.KEY]
                self.nav_buttons.pop(english_hook.KEY).destroy()
        if self._speed_cls is not None:
            spd = speedread_hook.create(self._speed_cls, self.content, self)
            if spd is not None:
                self.screens[speedread_hook.KEY] = spd
            else:
                self.SCREENS = [s for s in self.SCREENS if s[0] != speedread_hook.KEY]
                self.nav_buttons.pop(speedread_hook.KEY).destroy()
        for scr in self.screens.values():
            scr.grid(row=0, column=0, sticky="nsew")
        self.update_rank()
        self._update_sound_button()

    def _set_icon(self) -> None:
        """Иконка окна и панели задач: звезда в шестиграннике (stamina/assets)."""
        assets = Path(__file__).resolve().parent / "assets"
        try:
            self._icon_img = tk.PhotoImage(file=str(assets / "star_typing_64.png"))
            self.iconphoto(True, self._icon_img)
        except tk.TclError:
            pass
        ico = assets / "star_typing.ico"
        if ico.exists() and self.tk.call("tk", "windowingsystem") == "win32":
            try:
                self.iconbitmap(default=str(ico))
            except tk.TclError:
                pass

    def _draw_logo(self, c: tk.Canvas) -> None:
        cx, cy, r = px(22), px(22), px(17)
        import math
        pts = []
        for i in range(6):
            a = math.radians(60 * i + 30)
            pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
        c.create_polygon(pts, fill=blend(BG, CYAN, 0.15), outline=CYAN, width=2)
        star = []
        for i in range(10):
            a = math.radians(-90 + 36 * i)
            rr = r * (0.62 if i % 2 == 0 else 0.26)
            star += [cx + rr * math.cos(a), cy + px(1) + rr * math.sin(a)]
        c.create_polygon(star, fill=AMBER, outline="")
        compact = getattr(self, "_compact", False)
        c.create_text(px(48), px(15), text="STAR TYPING", anchor="w", fill=TEXT,
                      font=theme.font(14 if compact else 17, True))
        c.create_text(px(49), px(35), text="ПУЛЬТ ПИЛОТА" if compact else "ПУЛЬТ ПИЛОТА · ТРЕНАЖЁР ПЕЧАТИ",
                      anchor="w", fill=CYAN_DIM, font=theme.font(7, True))

    def _draw_line(self, c: tk.Canvas) -> None:
        c.delete("all")
        w = c.winfo_width()
        c.create_line(0, px(3), w, px(3), fill=LINE)
        c.create_line(0, px(3), px(260), px(3), fill=CYAN, width=2)
        c.create_line(w - px(160), px(3), w, px(3), fill=AMBER, width=2)
        for i in range(12):
            x = px(280) + i * px(10)
            c.create_line(x, px(1), x + px(5), px(1), fill=CYAN_DIM, width=2)

    # ------------------------------------------------------------------
    def open_help(self) -> None:
        """F1: справка; с вкладки «Английский» — сразу глава про неё."""
        chapter = {english_hook.KEY: "АНГЛИЙСКИЙ",
                   speedread_hook.KEY: "СКОРОЧТЕНИЕ", "honor": "ЭКИПАЖ"}.get(self.current or "")
        self.show("help")
        scr = self.screens.get("help")
        if scr is not None and hasattr(scr, "goto"):
            scr.goto(chapter)

    def show(self, name: str) -> None:
        if name == self.current:
            return
        bridge: Bridge = self.screens["bridge"]
        if self.current == "bridge" and bridge.state in ("run", "ready") and name != "bridge":
            bridge.pause("Пауза — вы перешли в другой раздел")
        if self.current == speedread_hook.KEY and name != self.current:
            try:
                self.screens[speedread_hook.KEY].on_leave()
            except Exception:  # noqa: BLE001
                pass
        if name == "honor" and self.current != "honor":
            self._prev_screen = self.current
            try:
                from stamina.pilot_stats import summary
                self.store.save_stats()
                if self.pilot is not None:
                    pilots.update_pilot(self.pilot["id"], summary=summary(self.pilot["id"]))
            except Exception:  # noqa: BLE001
                pass
        self.current = name
        scr = self.screens[name]
        if hasattr(scr, "refresh"):
            scr.refresh()
        scr.tkraise()
        if hasattr(self, "living"):
            self.after(30, lambda s_=scr: self.current_screen_is(s_) and self.living.attach(s_))
        for n, b in self.nav_buttons.items():
            b.set_active(n == name)
        self.btn_help.set_active(name == "help")
        if name == "cargo":
            scr.text.focus_set()
        else:
            self.focus_set()

    def _make_honor(self):
        from stamina.pilot_screens import HonorBoard
        return HonorBoard(self.content, on_back=lambda: self.show(self._prev_screen or "bridge"),
                          active=self.pilot["id"] if self.pilot else None)

    def set_status(self, text: str, color: str = MUTED) -> None:
        self.status.configure(text=text, fg=color)

    def update_rank(self) -> None:
        xp = self.store.stats["xp"]
        rank, lo, hi = missions.rank_for(xp)
        tail = f"{xp} / {hi} XP" if hi else f"{xp} XP"
        c = self.rank_label
        c.delete("all")
        w = int(c.cget("width"))
        x = w - px(2)
        if self.pilot is not None:
            avatars.draw(c, w - px(18), px(22), px(34), self.pilot, bg=BG)
            x = w - px(42)
            name = self.pilot["callsign"]
            if len(name) > 13:
                name = name[:12] + "…"
            c.create_text(x, px(9), text=f"{name.upper()} ▾", anchor="e", fill=TEXT, font=theme.font(8, True))
            c.create_text(x, px(24), text=f"★ {rank.upper()}", anchor="e", fill=AMBER, font=theme.font(7, True))
            c.create_text(x, px(37), text=tail, anchor="e", fill=MUTED, font=theme.font(7, True))
        else:
            c.create_text(x, px(13), text=f"★ {rank.upper()}", anchor="e", fill=AMBER, font=theme.font(10, True))
            c.create_text(x, px(32), text=tail, anchor="e", fill=AMBER, font=theme.font(9, True))

    # ------------------------------------------------------------------
    # Экипаж
    # ------------------------------------------------------------------
    def _update_title(self) -> None:
        who = f"пилот {self.pilot['callsign']}" if self.pilot else "пульт пилота"
        self.title(f"{APP_NAME} — {who}  v{__version__}")

    def pilot_menu(self) -> None:
        m = tk.Menu(self, tearoff=0, bg=PANEL, fg=TEXT, activebackground=blend(PANEL, AMBER, 0.2),
                    activeforeground=TEXT, font=theme.font(10, True))
        if self.pilot is not None:
            m.add_command(label="⇄  СМЕНИТЬ ПИЛОТА   Ctrl+Shift+P", command=self.switch_pilot)
            m.add_command(label="✎  ЛИЧНОЕ ДЕЛО", command=self.edit_pilot)
            m.add_command(label="⇪  ЭКСПОРТ ПИЛОТА", command=self.export_pilot)
            m.add_separator()
        m.add_command(label="★  ДОСКА ПОЧЁТА", command=lambda: self.show("honor"))
        c = self.rank_label
        m.tk_popup(c.winfo_rootx(), c.winfo_rooty() + c.winfo_height())

    def edit_pilot(self) -> None:
        from stamina.pilot_screens import ProfileDialog
        if self.pilot is None:
            return
        ProfileDialog(self, self.pilot["id"]).run()
        self.pilot = pilots.get(self.pilot["id"]) or self.pilot
        self._update_title()
        self.update_rank()

    def export_pilot(self) -> None:
        from stamina.pilot_screens import export_pilot
        if self.pilot is not None:
            export_pilot(self, pilots.get(self.pilot["id"]) or self.pilot, __version__)

    def switch_pilot(self) -> None:
        """Сохранить всё и перезапустить программу с экраном «ВХОД В КАБИНУ» (SPEC §6.3)."""
        if self.pilot is None:
            return
        import subprocess
        import sys
        self._save_all()
        main = Path(__file__).resolve().parent.parent / "main.py"
        try:
            subprocess.Popen([sys.executable, str(main), "--select"], cwd=str(main.parent))
        except OSError as exc:
            messagebox.showerror("Смена пилота", f"Не удалось перезапустить программу:\n{exc}", parent=self)
            return
        self.destroy()

    # ------------------------------------------------------------------
    # Запуск упражнений
    # ------------------------------------------------------------------
    def start_mission(self, m: dict) -> None:
        if not self.store.is_unlocked(m):
            self.set_status("МИССИЯ ЗАКРЫТА — сначала пройдите предыдущую", AMBER)
            return
        text = missions.generate_mission_text(m)
        keys = " ".join(m["new"].upper()) if m["new"] and not m["new"].isdigit() else (
            "цифры 0–9" if m["new"] else "все буквы")
        self.screens["bridge"].start(
            text, mode="mission", mission=m,
            title=f"МИССИЯ {m['lang'].upper()}-{m['num']:02d} · {m['title'].upper()}",
            subtitle=f"Сектор: {m['sector'].lower()} · новые клавиши: {keys} · цель: "
                     f"{m['goal']} зн/мин при точности ≥ {missions.PASS_ACCURACY:.0f}%")
        self._last_action = lambda: self.start_mission(m)
        self.show("bridge")

    def start_repair(self, lang: str | None = None) -> None:
        lang = lang or self.store.settings.get("lang", "en")
        weak = self.store.weakest_keys(lang)
        if not weak:
            other = "ru" if lang == "en" else "en"
            if self.store.weakest_keys(other):
                lang, weak = other, self.store.weakest_keys(other)
        if not weak:
            messagebox.showinfo("Ремонт систем", "Пока недостаточно данных об ошибках.\n"
                                "Пройдите пару миссий — и бортовой компьютер найдёт слабые клавиши.",
                                parent=self)
            return
        chars = [ch for ch, _r in weak]
        text = missions.generate_repair_text(chars, lang)
        self.screens["bridge"].start(
            text, mode="repair", title="РЕМОНТ СИСТЕМ · СЛАБЫЕ КЛАВИШИ",
            subtitle="Тренируем: " + "  ".join(f"«{c}»" for c in chars) +
                     " — упражнение собрано из слов с этими буквами")
        self._last_action = lambda: self.start_repair(lang)
        self.show("bridge")

    def cargo_process(self):
        """Функция подготовки своего текста по текущим опциям."""
        opts = dict(self.store.settings.get("cargo_opts") or {})
        lower, punct, spaces = (bool(opts.get(k, True)) for k in ("lower", "punct", "spaces"))
        return lambda t: process_text(t, lower=lower, punct=punct, spaces=spaces)

    def start_cargo(self, adapted: str, original: str, switch: bool = True) -> None:
        self.store.save_cargo(adapted, original)
        spd = self.screens.get(speedread_hook.KEY)
        if spd is not None:  # общая библиотека: текст сразу доступен и для чтения
            try:
                spd.lib.upsert_from_cargo(adapted, original, self.store.settings.get("cargo_opts"))
            except Exception:  # noqa: BLE001
                speedread_hook._log(__import__("traceback").format_exc())
        clear_session()
        self._start_cargo_engine(adapted, original, None, switch=switch)

    def resume_cargo(self) -> None:
        saved = load_session()
        if saved is None:
            self.show("cargo")
            return
        adapted, original = self.store.load_cargo()
        if not original or self.cargo_process()(original) != saved.text:
            original = ""
        self._start_cargo_engine(saved.text, original, saved)

    def _start_cargo_engine(self, text: str, original: str, resume, switch: bool = True) -> None:
        preview = text[:40] + ("…" if len(text) > 40 else "")
        lower = bool((self.store.settings.get("cargo_opts") or {}).get("lower", True))
        case_sensitive = resume.case_sensitive if resume is not None else not lower
        self.screens["bridge"].start(
            text, mode="cargo", resume=resume, original=original,
            case_sensitive=case_sensitive, process=self.cargo_process(),
            title="СВОЙ ТЕКСТ · ДОСТАВКА ГРУЗА",
            subtitle=f"«{preview}» · прогресс сохраняется автоматически, можно закрыть программу"
                     + (" · с заглавными буквами" if case_sensitive else ""))

        def again():
            if messagebox.askyesno("Заново", "Начать этот текст с самого начала?", parent=self):
                clear_session()
                self._start_cargo_engine(text, original, None)
        self._last_action = again
        if switch:
            self.show("bridge")

    def restart_current(self) -> None:
        if self._last_action:
            self._last_action()
        else:
            self.show("missions")

    # ------------------------------------------------------------------
    def get_translator(self):
        if self.translator is None:
            from stamina.translator import Translator
            self.translator = Translator()
        return self.translator

    def toggle_sound(self) -> None:
        st = self.store.settings
        st["sound"] = not st["sound"]
        self.apply_settings()
        self.screens["settings"].refresh()

    def _update_sound_button(self) -> None:
        on = self.store.settings["sound"]
        if len(self.SCREENS) > 6:  # много разделов — компактная кнопка
            self.btn_sound.set_text("♪" if on else "♪̸")
        else:
            self.btn_sound.set_text("♪ ЗВУК ВКЛ" if on else "♪ ЗВУК ВЫКЛ")
        self.btn_sound.set_active(on)
        self.btn_sound.set_color(CYAN if on else MUTED)

    def current_screen_is(self, scr) -> bool:
        return self.screens.get(self.current) is scr

    def apply_settings(self) -> None:
        st = self.store.settings
        self.sound.enabled = bool(st["sound"])
        self.sound.volume = int(st.get("volume", 3))
        self._update_sound_button()
        self.screens["bridge"].apply_settings()
        mode = st.get("living_space", "light")
        if hasattr(self, "living"):
            self.living.set_mode(mode)
        try:   # окно входа не знает настроек пилота — режим фона дублируется в app.json
            app = pilots.load_app()
            if app.get("living_space") != mode:
                app["living_space"] = mode
                pilots.save_app(app)
        except Exception:  # noqa: BLE001
            pass
        self.store.save_settings()

    # ------------------------------------------------------------------
    def _bootstrap(self) -> None:
        saved = load_session()
        adapted, original = self.store.load_cargo()
        if not adapted and saved:
            adapted = saved.text
        self.screens["cargo"].load_initial(adapted, original)
        if saved is not None:
            self.resume_cargo()
        else:
            self.show("missions")

    def _on_key(self, e: tk.Event) -> None:
        # Ctrl+Shift+P в любой раскладке (Windows: код клавиши P = 80)
        if (e.state & 0x4) and (e.state & 0x1) and (e.keycode == 80 or e.keysym in ("P", "p")):
            self.switch_pilot()
            return
        if self.current == "bridge":
            self.screens["bridge"].on_key(e)
        elif self.current == english_hook.KEY:
            self.screens[english_hook.KEY].on_key(e)
        elif self.current == speedread_hook.KEY:
            self.screens[speedread_hook.KEY].on_key(e)
        elif self.current == "honor":
            self.screens["honor"].on_key(e)

    def _on_focus_out(self, _e) -> None:
        def check():
            try:
                if self.focus_displayof() is None and self.current == "bridge":
                    self.screens["bridge"].pause("Окно потеряло фокус — полёт на паузе")
            except (tk.TclError, KeyError):
                pass
        self.after(150, check)

    def _clock_tick(self) -> None:
        self.clock.configure(text=time.strftime("%H:%M"))
        self.status_dot.configure(fg=GREEN if int(time.time()) % 2 else blend(GREEN, BG, 0.6))
        self.after(1000, self._clock_tick)

    def _tick(self) -> None:
        smooth = False
        try:
            visible = self.current == "bridge" and self.state() != "iconic"
            smooth = self.screens["bridge"].tick(visible)
        except tk.TclError:
            return
        self.after(33 if smooth else 200, self._tick)

    def _on_close(self) -> None:
        self._save_all()
        self.destroy()

    def _save_all(self) -> None:
        try:
            self.screens["bridge"].leave_current()
        except Exception:
            pass
        for key in (english_hook.KEY, speedread_hook.KEY):
            if key in self.screens:
                try:
                    self.screens[key].close()
                except Exception:
                    pass
        st = self.store.settings
        st["geometry"] = "zoomed" if self.state() == "zoomed" else self.geometry()
        self.store.save_settings()
        self.store.save_stats()
        if self.translator is not None:
            self.translator.save()
        if self.pilot is not None:
            try:
                app = pilots.load_app()
                app["geometry"] = st["geometry"]
                pilots.save_app(app)
                from stamina.pilot_stats import summary
                pilots.update_pilot(self.pilot["id"], last_seen=pilots.now_iso(), summary=summary(self.pilot["id"]))
            except Exception:  # noqa: BLE001
                pass
