"""Точка сборки приложения Star Typing (пакет по-прежнему называется stamina)."""

from __future__ import annotations

from stamina.i18n import t

import os
import sys
import time


def _enable_dpi_awareness() -> None:
    """Чёткий текст на экранах с масштабом 125–150 % (Windows)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _set_app_id() -> None:
    """Своя иконка на панели задач Windows вместо иконки Python."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Teslyar75.StarTyping")
    except Exception:
        pass


def _arg(argv: list[str], name: str) -> str | None:
    for i, a in enumerate(argv):
        if a == name and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith(name + "="):
            return a.split("=", 1)[1]
    return None


def _journal(msg: str) -> None:
    """Журнал запуска: пишем в %APPDATA%\\Stamina\\start.log.

    Нужен, чтобы увидеть путь запуска и ошибки даже под pythonw, где нет консоли.
    """
    try:
        from stamina import pilots
        pilots.log_error(msg, "start.log")
    except Exception:  # noqa: BLE001 — журнал не должен мешать полётам
        pass


def _safe_streams() -> None:
    """Под pythonw.exe sys.stdout/sys.stderr = None.

    Любая печать (в том числе трейсбек из обработчика Tk) в таком процессе падает,
    и окно остаётся «живым», но не отвечает. Поэтому направляем вывод в файл.
    """
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        from stamina import pilots
        pilots.ROOT_DIR.mkdir(parents=True, exist_ok=True)
        f = open(pilots.ROOT_DIR / "startup_out.log", "a", encoding="utf-8", buffering=1)
    except Exception:  # noqa: BLE001
        return
    if sys.stdout is None:
        sys.stdout = f
    if sys.stderr is None:
        sys.stderr = f


def _center(root, w: int, h: int) -> None:
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    w, h = min(w, int(sw * 0.94)), min(h, int(sh * 0.9))
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 2 - 20)}")


def choose_pilot(argv: list[str]) -> str | None:
    """Миграция → реестр → (при необходимости) «ВХОД В КАБИНУ», код доступа, задание кода.

    → id пилота, "" (работать по-старому, без пилотов) или None (выход)."""
    from stamina import pilot_migrate, pilots
    rep = pilot_migrate.migrate()
    reg = pilots.load_registry()
    if reg is None and rep.get("reason") == "error":
        return ""          # миграция не удалась — по-старому, данные не тронуты
    if reg is not None:
        pilot_migrate.late_sync()
    want = _arg(argv, "--pilot") or os.environ.get("STAMINA_PILOT")
    plist = pilots.pilots()
    p = pilots.find(want) if want else None
    first_run = "--welcome" in argv or (not plist and p is None and "--select" not in argv and "--board" not in argv)
    need_login = "--select" in argv or "--board" in argv or (
        p is None and (not plist or (len(plist) >= 2 and (reg or {}).get("ask_on_start", True))))
    _journal(f"choose_pilot argv={argv} want={want} pilots={[x.get('id') for x in plist]} "
             f"found={getattr(p, 'get', lambda *_: None)('id')} first_run={first_run} need_login={need_login}")
    if p is None and not need_login:
        p = pilots.get((reg or {}).get("last_pilot") or "") or plist[0]
    import tkinter as tk
    from stamina import __version__, pilot_pin, pilot_screens, theme
    root = tk.Tk()
    theme.init(root)
    try:
        from stamina import pilots as _pilots
        skin = (_pilots.load_app() or {}).get("skin") or "spaceship"
        theme.load_theme(skin, apply_ui=False, root=root)
    except Exception:  # noqa: BLE001
        theme.load_theme("spaceship", apply_ui=False, root=root)
    root.configure(bg=theme.BG)
    try:
        from pathlib import Path
        img = tk.PhotoImage(file=str(Path(__file__).resolve().parent / "assets" / "star_typing_64.png"))
        root.iconphoto(True, img)
    except tk.TclError:
        pass
    pid = None
    try:
        if first_run:     # чистая установка: приветствие → создание пилота → мостик
            from stamina import welcome
            _center(root, theme.px(1260), theme.px(800))
            pid = welcome.run_welcome(root, app_version=__version__)
            if pid is None:
                return None
            p = pilots.get(pid)
        elif need_login:
            _center(root, theme.px(1260), theme.px(800))
            pid = pilot_screens.run_login(root, app_version=__version__, initial_board="--board" in argv)
            if pid is None:
                return None
            p = pilots.get(pid)
        else:
            if pilot_pin.has_pin(p["id"]):
                root.title(t("Star Typing — код доступа"))
                _center(root, theme.px(520), theme.px(560))
                root.update_idletasks()
                ok_pin = pilot_screens.ask_pin(root, p, t("ВХОД В КАБИНУ"))
                try:
                    grab = root.grab_current()
                except tk.TclError:
                    grab = "?"
                _journal(f"ask_pin -> {ok_pin}, grab после диалога: {grab}, "
                         f"root viewable: {root.winfo_viewable()}")
                if not ok_pin:
                    return None
            pid = p["id"]
        p = pilots.get(pid) or p
        if p.get("pin_setup_pending") and not pilot_pin.has_pin(pid):
            if not root.winfo_viewable():
                _center(root, theme.px(620), theme.px(420))
            root.title(t("Star Typing — код доступа"))
            root.update_idletasks()
            pilot_screens.SetPinDialog(root, p, first_time=True).run()
        return pid
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def run_app(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else list(argv)
    _safe_streams()
    _journal(f"=== ЗАПУСК argv={argv} exe={sys.executable} cwd={os.getcwd()}")
    # Ошибку в обратном вызове Tk пишем в журнал: под pythonw её больше некуда девать
    try:
        import tkinter as _tk

        def _cb_exc(_self, exc, val, tb):
            import traceback
            _journal("Ошибка в обратном вызове Tk:\n" + "".join(traceback.format_exception(exc, val, tb)))

        _tk.Tk.report_callback_exception = _cb_exc
    except Exception:  # noqa: BLE001
        pass
    _enable_dpi_awareness()
    _set_app_id()
    try:
        pid = choose_pilot(argv)
    except Exception:  # noqa: BLE001 — экипаж не должен мешать полётам
        import traceback
        from stamina import pilots
        text = t("Ошибка выбора пилота:\n") + traceback.format_exc()
        pilots.log_error(text)
        _journal(text)
        # с реестром нельзя молча работать «по-старому» (корень уже пуст) — выходим, ошибка в логе
        pid = None if pilots.load_registry() is not None else ""
    _journal(f"choose_pilot -> {pid}")
    if pid is None:
        return
    if pid:
        from stamina import pilots
        pilots.activate(pid)
    try:
        from stamina.cockpit import Cockpit
        cockpit = Cockpit()
        _journal("Cockpit создан")

        # Снимки состояния окна первые 12 секунд: видно, если окно «живое», но не отвечает
        def _snap(tag: str) -> None:
            try:
                grab = cockpit.grab_current()
            except Exception as e:  # noqa: BLE001
                grab = f"err {e}"
            try:
                focus = cockpit.focus_get()
            except Exception as e:  # noqa: BLE001
                focus = f"err {e}"
            try:
                view = (cockpit.winfo_viewable(), cockpit.winfo_ismapped(),
                        cockpit.winfo_width(), cockpit.winfo_height())
            except Exception as e:  # noqa: BLE001
                view = f"err {e}"
            # Какое окно реально впереди на уровне Windows
            fg = "?"
            try:
                import ctypes
                h = ctypes.windll.user32.GetForegroundWindow()
                buf = ctypes.create_unicode_buffer(256)
                ctypes.windll.user32.GetWindowTextW(h, buf, 256)
                fg = f"{buf.value!r} (hwnd={h})"
            except Exception as e:  # noqa: BLE001
                fg = f"err {e}"
            # Какие ещё окна Tk открыты
            tops = []
            try:
                def walk(w):
                    for ch in w.winfo_children():
                        if isinstance(ch, __import__("tkinter").Toplevel):
                            tops.append((ch.title(), bool(ch.winfo_viewable())))
                        walk(ch)
                walk(cockpit)
            except Exception as e:  # noqa: BLE001
                tops = [f"err {e}"]
            _journal(f"снимок {tag}: grab={grab} focus={focus} окно={view} "
                     f"экран={getattr(cockpit, 'current', '?')} "
                     f"переднее окно Windows={fg} прочие окна={tops}")
            # Ширины: если требуемая ширина больше окна, шапка и клавиатура не влезают,
            # и раскладка может зациклиться (окно встаёт при живом главном потоке).
            try:
                parts = [f"окно={cockpit.winfo_width()}", f"нужно={cockpit.winfo_reqwidth()}"]
                for name in ("nav_strip", "subnav", "_mini_row", "content"):
                    w = getattr(cockpit, name, None)
                    if w is not None:
                        parts.append(f"{name}={w.winfo_reqwidth()}/{w.winfo_width()}")
                _journal("ширины: " + " ".join(parts))
            except Exception as e:  # noqa: BLE001
                _journal(f"ширины: err {e}")
            # Кто именно просит лишнюю ширину: строки окна и каждый экран
            try:
                rows = []
                for ch in cockpit.winfo_children():
                    rows.append(f"{ch.winfo_class()}#{str(ch).split('.')[-1]}="
                                f"{ch.winfo_reqwidth()}/{ch.winfo_width()}")
                _journal("строки: " + " ".join(rows))
                scr = []
                for name, s in (getattr(cockpit, "screens", {}) or {}).items():
                    try:
                        scr.append(f"{name}={s.winfo_reqwidth()}")
                    except Exception:  # noqa: BLE001
                        pass
                _journal("экраны: " + " ".join(scr))
            except Exception as e:  # noqa: BLE001
                _journal(f"строки: err {e}")

        for _t in (1000, 2000, 3500, 6000, 12000):
            cockpit.after(_t, lambda tag=_t: _snap(f"{tag} мс"))

        # Пульс главного потока: если окно «замерло», видно, когда и на сколько
        _beat = {"last": time.time()}

        def _pulse() -> None:
            now = time.time()
            gap = now - _beat["last"]
            _beat["last"] = now
            if gap > 0.3:
                pending = "?"
                try:  # сколько таймеров висит: если растёт — кто-то плодит after()
                    pending = len(cockpit.tk.splitlist(cockpit.tk.call("after", "info")))
                except Exception:  # noqa: BLE001
                    pass
                _journal(f"ГЛАВНЫЙ ПОТОК ЗАМИРАЛ на {gap:.2f} с "
                         f"(экран={getattr(cockpit, 'current', '?')}, таймеров={pending})")
            # пульс живёт всё время работы: без него сторож замираний считает
            # «замиранием» сам факт остановки пульса и врёт в журнал
            cockpit.after(250, _pulse)

        cockpit.after(250, _pulse)

        # Диагностика: пишем в журнал обратные вызовы, которые держат главный поток долго.
        # Нужно, чтобы найти виновника вечной перерисовки — по имени функции, а не догадками.
        def _install_slow_log(limit: float = 0.20) -> None:
            import tkinter
            orig = tkinter.Misc.after

            def after(self, ms, func=None, *args):
                if func is None:
                    return orig(self, ms, func, *args)
                name = getattr(func, "__qualname__", None) or repr(func)

                def wrapper(*a, **k):
                    t0 = time.perf_counter()
                    try:
                        return func(*a, **k)
                    finally:
                        dt = time.perf_counter() - t0
                        if dt > limit:
                            _journal(f"ДОЛГИЙ ВЫЗОВ {name}: {dt:.2f} с")
                return orig(self, ms, wrapper, *args)

            tkinter.Misc.after = after

        try:
            _install_slow_log()
            _journal("журнал долгих вызовов включён")
        except Exception:  # noqa: BLE001
            pass

        # Сторож петель раскладки: шапка умеет уходить в петлю «Configure → рисовать →
        # Configure» — тысячи перерисовок в секунду, окно встаёт. Считаем события по
        # виджетам и, если виджет зашкалил, снимаем с него обработчик и пишем в журнал.
        def _install_layout_guard(root) -> None:
            import tkinter
            per_widget: dict[str, int] = {}
            hooked: set[str] = set()

            def on_cfg(_e, key: str, widget) -> None:
                n = per_widget.get(key, 0) + 1
                per_widget[key] = n
                if n == 300:
                    _journal(f"ПЕТЛЯ РАСКЛАДКИ: {widget.winfo_class()} {key} — "
                             f"{n} событий, снимаю обработчик")
                    try:
                        widget.unbind("<Configure>")
                    except Exception:  # noqa: BLE001
                        pass

            def hook(widget) -> None:
                key = str(widget)
                if key in hooked:
                    return
                try:
                    hooked.add(key)
                    widget.bind("<Configure>", lambda e, k=key, w=widget: on_cfg(e, k, w), add="+")
                except Exception:  # noqa: BLE001
                    pass

            def walk(widget) -> None:
                hook(widget)
                try:
                    children = widget.winfo_children()
                except Exception:  # noqa: BLE001
                    return
                for ch in children:
                    walk(ch)

            def sweep() -> None:
                per_widget.clear()
                try:
                    walk(root)
                    root.after(1000, sweep)
                except Exception:  # noqa: BLE001
                    pass

            root.after(1000, sweep)

        try:
            _install_layout_guard(cockpit)
            _journal("сторож петель раскладки включён")
        except Exception:  # noqa: BLE001
            pass
        # Автоматическая проверка и восстановление связи с OpenCode
        def _ensure_connection(cp):
            """Проверить привязку; если потеряна — восстановить автоматически."""
            import json
            from pathlib import Path
            from stamina import orion
            rec = orion.active()
            status = orion.binding_status(rec["id"])
            if status["access_ok"]:
                return  # связь есть — ничего делаем
            # Токен OpenCode из service.json
            oc_token = ""
            try:
                svc = Path.home() / ".config" / "opencode" / "service.json"
                if svc.exists():
                    oc_token = (json.loads(svc.read_text(encoding="utf-8")).get("password") or "")
            except Exception:
                pass
            # Токен GitHub через gh auth token
            gh_token = ""
            try:
                import subprocess
                # Без CREATE_NO_WINDOW консоль gh мелькает и забирает фокус у кабины
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True,
                                   timeout=10, creationflags=flags)
                gh_token = r.stdout.strip() if r.returncode == 0 else ""
            except Exception:
                pass
            if oc_token or gh_token:
                orion.save_binding(rec["id"], opencode_token=oc_token, github_token=gh_token)
                cp.set_status("Связь с OpenCode восстановлена автоматически", "green")
            else:
                cp.set_status("Нет связи с OpenCode — войди в opencode auth login", "red")
        cockpit.after(100, lambda: _ensure_connection(cockpit))
        _journal("mainloop старт")
        cockpit.mainloop()
        _journal("mainloop завершён")
    except Exception:  # noqa: BLE001 — иначе окно «мелькает» без следа
        import traceback
        from stamina import pilots
        text = t("Ошибка пульта:\n") + traceback.format_exc()
        pilots.log_error(text, "cockpit_error.log")
        _journal(text)
        raise


def relaunch(extra_env: dict | None = None) -> bool:
    """Запустить программу заново тем же Python и с теми же аргументами (смена языка, скина)."""
    import subprocess
    try:
        from stamina import pilots
        env = dict(os.environ)
        cur = pilots.active()
        if cur:
            env["STAMINA_PILOT"] = cur["id"]          # вернуться в кабину того же пилота
        env.update(extra_env or {})
        subprocess.Popen([sys.executable] + sys.argv, cwd=os.getcwd(), close_fds=True, env=env)
    except OSError:
        return False
    return True
