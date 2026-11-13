"""Отсек «ТЕРРАФОРМЕР»: загрузка роботов-терраформеров двух линеек.

Каталог — из :mod:`stamina.terraformer_models` (12 роботов: 8 CEFR + 4 частотных).
Робота рисует только :class:`stamina.terraformer_render.TerraformerViewer` на
холсте отсека; фон ангара — простые примитивы Canvas позади модели.

Открытие уровней CEFR — правило «Английского» (:mod:`stamina.english.access`),
частотные наборы — по тому же порогу: следующий набор открывается, когда
предыдущий освоен на unlock_pct %. Капитан (разработчик с доступом к GitHub)
видит всё. Выбор пилота хранится в
``Progress.settings`` (``terraformer_cefr`` / ``terraformer_freq``).

Импорт модуля не создаёт окон Tk.
"""
from __future__ import annotations

import tkinter as tk

from stamina import theme
from stamina.english import access, cefr
from stamina.english.progress import Progress
from stamina.hud import HudButton, HudPanel
from stamina.i18n import t
from stamina.terraformer_models import ROBOTS, robot
from stamina.terraformer_render import TerraformerViewer

KEY = "terraformer"
SETTING_KEYS = {"cefr": "terraformer_cefr", "freq": "terraformer_freq"}

LINES = {
    "cefr": tuple(r.id for r in ROBOTS if r.line == "cefr"),
    "freq": tuple(r.id for r in ROBOTS if r.line == "freq"),
}


def _progress_for(app=None) -> Progress:
    """Прогресс пилота: english.json активного пилота (или корня данных)."""
    try:
        from stamina.pilots import active_dir
        return Progress(active_dir() / "english.json", app=app)
    except Exception:  # noqa: BLE001
        return Progress(app=app)


def _done(progress, slug: str) -> bool:
    return bool(access._word_done(progress, slug))


# робот частотной линейки → набор слов «Английского» (по порядку лестницы)
FREQ_SETS = {"s1000": "top-1000", "s3000": "top-3000", "s10k": "top-10000", "s20k": "top-20000"}
_VOCAB = None


def _freq_slugs(set_id: str) -> list[str]:
    """Слова частотного набора; словарь грузится один раз (ленивый индекс)."""
    global _VOCAB
    if _VOCAB is None:
        from stamina.english.vocab import Vocab
        v = Vocab()
        try:
            v.load()
        except Exception:  # noqa: BLE001
            return []
        _VOCAB = v
    try:
        return [w["slug"] for w in _VOCAB.in_set(set_id)]
    except Exception:  # noqa: BLE001
        return []


def _freq_need(progress, robot_id: str):
    """(предыдущий набор, нужно %, сейчас %) для частотного робота; None — открыт."""
    ids = LINES["freq"]
    if access.is_captain(progress) or robot_id not in ids:
        return None
    i = ids.index(robot_id)
    if i == 0:
        return None
    prev = ids[i - 1]
    slugs = _freq_slugs(FREQ_SETS[prev])
    pct = access.unlock_pct(progress)
    now = access.level_pct(slugs, lambda s: _done(progress, s)) if slugs else 0
    return None if (slugs and now >= pct) else (robot(prev).name, pct, now)


def robot_open(progress, robot_id: str) -> bool:
    """Открыт ли робот: только после прохождения предыдущего уровня; капитану — всё."""
    r = robot(robot_id)
    if r.line != "cefr":
        return _freq_need(progress, robot_id) is None
    levels = cefr.available()
    if not levels:
        return access.is_captain(progress)
    return access.level_open(progress, r.name, levels, cefr.slugs,
                             lambda s: _done(progress, s))


def robot_need(progress, robot_id: str):
    """(предыдущий уровень, нужно %, сейчас %) для закрытого робота, иначе None."""
    r = robot(robot_id)
    if r.line != "cefr":
        return _freq_need(progress, robot_id)
    if robot_open(progress, robot_id):
        return None
    levels = cefr.available()
    if r.name not in levels:
        return None
    return access.level_need(progress, r.name, levels, cefr.slugs,
                             lambda s: _done(progress, s))


def need_hint(progress, robot_id: str) -> str:
    """Подсказка у замка: предыдущий уровень и порог прохождения."""
    need = robot_need(progress, robot_id)
    if need is None:
        return ""
    prev, pct, now = need
    return t("🔒 Откроется после {0}: нужно {1}% (сейчас {2}%)").format(prev, pct, now)


def saved_choice(progress, line: str) -> str | None:
    try:
        rid = (progress.settings or {}).get(SETTING_KEYS[line])
    except (AttributeError, KeyError):
        return None
    return rid if rid in LINES[line] else None


def save_choice(progress, line: str, robot_id: str) -> bool:
    """Запомнить выбор открытого робота. Закрытого выбрать нельзя."""
    if robot_id not in LINES[line] or not robot_open(progress, robot_id):
        return False
    progress.settings[SETTING_KEYS[line]] = robot_id
    try:
        progress.save()
    except Exception:  # noqa: BLE001
        pass
    return True


class TerraformerBayScreen(tk.Frame):
    """Экран отсека: две линейки, стрелки, выбор и замок закрытых CEFR-уровней."""

    TITLE = t("ЗАГРУЗКА ТЕРРАФОРМЕРА")

    def __init__(self, master, app) -> None:
        super().__init__(master, bg=theme.BG)
        self.app = app
        self.progress = _progress_for(app)
        for key in SETTING_KEYS.values():
            self.progress.settings.setdefault(key, "")
        self.line = "cefr"
        self.index = 0
        self._viewer: TerraformerViewer | None = None
        self._raise_job = None
        self._lock_job = None
        self._build()
        self._restore()
        self._make_viewer()
        self._sync()

    # -- сборка ---------------------------------------------------------------
    def _build(self) -> None:
        top = tk.Frame(self, bg=theme.BG)
        top.pack(fill=tk.X, padx=theme.px(10), pady=(theme.px(8), theme.px(4)))
        tk.Label(top, text=self.TITLE, bg=theme.BG, fg=theme.TEXT,
                 font=theme.font(12, True)).pack(side=tk.LEFT)
        self.count_lbl = tk.Label(top, text="", bg=theme.BG, fg=theme.MUTED, font=theme.font(9))
        self.count_lbl.pack(side=tk.LEFT, padx=theme.px(10))
        self.btn_freq = HudButton(top, t("ЧАСТОТНЫЙ КУРС"), lambda: self.set_line("freq"),
                                  height=30, font_size=9)
        self.btn_freq.pack(side=tk.RIGHT)
        self.btn_cefr = HudButton(top, "CEFR", lambda: self.set_line("cefr"), height=30, font_size=9)
        self.btn_cefr.pack(side=tk.RIGHT, padx=(0, theme.px(6)))

        self.panel = HudPanel(self, title=self.TITLE)
        self.panel.pack(fill=tk.BOTH, expand=True, padx=theme.px(10),
                        pady=(0, theme.px(10)))
        stage = tk.Frame(self.panel.body, bg=theme.PANEL)
        stage.pack(fill=tk.BOTH, expand=True, padx=theme.px(4), pady=theme.px(4))

        self.canvas = tk.Canvas(stage, bg=theme.blend(theme.BG, theme.PANEL, 0.6),
                                highlightthickness=0, bd=0, takefocus=1)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        row = tk.Frame(stage, bg=theme.PANEL)
        row.pack(fill=tk.X, pady=(theme.px(4), 0))
        self.btn_prev = HudButton(row, "◀", lambda: self.step(-1), width=44, height=34, font_size=10)
        self.btn_prev.pack(side=tk.LEFT)
        self.btn_next = HudButton(row, "▶", lambda: self.step(1), width=44, height=34, font_size=10)
        self.btn_next.pack(side=tk.LEFT, padx=(theme.px(4), theme.px(10)))
        self.name_lbl = tk.Label(row, text="", bg=theme.PANEL, fg=theme.TEXT,
                                 font=theme.font(10, True), anchor="w")
        self.name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.choose_btn = HudButton(row, t("ВЫБРАТЬ"), self.choose, height=34, font_size=9,
                                    color=theme.GREEN)
        self.choose_btn.pack(side=tk.RIGHT)
        self.hint_lbl = tk.Label(stage, text="", bg=theme.PANEL, fg=theme.MUTED,
                                 font=theme.font(9), anchor="w")
        self.hint_lbl.pack(fill=tk.X, pady=(theme.px(3), 0))

        self.canvas.bind("<Configure>", self._on_configure, add="+")
        self.canvas.bind("<Left>", self._on_left)
        self.canvas.bind("<Right>", self._on_right)
        self.bind("<Left>", self._on_left)
        self.bind("<Right>", self._on_right)
        self.bind("<Unmap>", self._on_unmap, add="+")
        self.bind("<Map>", self._on_map, add="+")
        self.bind("<Destroy>", self._on_destroy, add="+")

    def _restore(self) -> None:
        rid = saved_choice(self.progress, self.line)
        if rid in LINES[self.line]:
            self.index = LINES[self.line].index(rid)

    def _make_viewer(self) -> None:
        self._viewer = TerraformerViewer(self.canvas, self._line_ids()[self.index])

    # -- каталог --------------------------------------------------------------
    def _line_ids(self) -> tuple[str, ...]:
        return LINES[self.line]

    def current_robot(self):
        return robot(self._line_ids()[self.index % len(self._line_ids())])

    def set_line(self, line: str) -> None:
        if line not in LINES:
            return
        self.line = line
        self.index = 0
        rid = saved_choice(self.progress, line)
        if rid in LINES[line]:
            self.index = LINES[line].index(rid)
        self._sync()

    def step(self, delta: int) -> None:
        n = len(self._line_ids())
        self.index = (self.index + delta) % n
        self._sync()

    def choose(self) -> bool:
        r = self.current_robot()
        ok = save_choice(self.progress, self.line, r.id)
        if ok:
            self.hint_lbl.configure(text=t("Выбран: {0}").format(r.name), fg=theme.GREEN)
        self._sync(keep_hint=ok)
        return ok

    # -- клавиши --------------------------------------------------------------
    def _on_left(self, _e=None):
        if getattr(self.app, "current", None) != KEY:
            return None
        self.step(-1)
        return "break"

    def _on_right(self, _e=None):
        if getattr(self.app, "current", None) != KEY:
            return None
        self.step(1)
        return "break"

    # -- синхронизация --------------------------------------------------------
    def _sync(self, keep_hint: bool = False) -> None:
        r = self.current_robot()
        ids = self._line_ids()
        open_ = robot_open(self.progress, r.id)
        self.btn_cefr.set_active(self.line == "cefr")
        self.btn_freq.set_active(self.line == "freq")
        self.count_lbl.configure(text=t("{0} из {1}").format(self.index + 1, len(ids)))
        self.name_lbl.configure(text=f"{r.name} · {r.caption}")
        chosen = saved_choice(self.progress, self.line) == r.id
        self.choose_btn.set_enabled(open_)
        self.choose_btn.set_text(t("ВЫБРАН") if chosen else t("ВЫБРАТЬ"))
        if not keep_hint:
            if not open_:
                self.hint_lbl.configure(text=need_hint(self.progress, r.id), fg=theme.AMBER)
            elif access.is_captain(self.progress):
                self.hint_lbl.configure(text=t("Капитан — открыты все уровни"), fg=theme.CYAN)
            else:
                self.hint_lbl.configure(text=t("Уровень открыт"), fg=theme.MUTED)
        if self._viewer is not None and self._viewer.robot_id != r.id:
            self._viewer.set_robot(r.id)
        self._draw_lock(open_, r)

    def refresh(self) -> None:
        """Экран показан: перечитать прогресс и запустить показ робота."""
        self.progress = _progress_for(self.app)
        for key in SETTING_KEYS.values():
            self.progress.settings.setdefault(key, "")
        self._restore()
        self._sync()
        self.start()

    # -- фон ангара -----------------------------------------------------------
    def _on_configure(self, _e=None) -> None:
        self._draw_hangar()
        if self._raise_job is not None:
            try:
                self.after_cancel(self._raise_job)
            except tk.TclError:
                pass
        self._raise_job = self.after_idle(self._raise_lock)

    def _draw_hangar(self) -> None:
        cv = self.canvas
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 20 or h < 20:
            return
        cv.delete("tf_bg")
        horizon = int(h * 0.44)
        # стены ангара: мягкие полосы от тёмного верха к полу
        bands = 10
        for i in range(bands):
            y0 = int(horizon * i / bands)
            y1 = int(horizon * (i + 1) / bands)
            col = theme.blend(theme.BG, theme.PANEL, 0.10 + 0.30 * i / bands)
            cv.create_rectangle(0, y0, w, y1, fill=col, outline="", tags="tf_bg")
        # пол с перспективной сеткой
        floor = theme.blend(theme.BG, theme.CYAN_DIM, 0.16)
        cv.create_rectangle(0, horizon, w, h, fill=floor, outline="", tags="tf_bg")
        cx = w / 2
        for i in range(-9, 10):
            x = cx + i * w * 0.075
            cv.create_line(cx, horizon, x, h, fill=theme.blend(floor, theme.CYAN, 0.18),
                           tags="tf_bg")
        y = horizon
        step = max(8, int((h - horizon) / 7))
        while y < h:
            cv.create_line(0, y, w, y, fill=theme.blend(floor, theme.CYAN, 0.12), tags="tf_bg")
            y += step
            step = int(step * 1.35) or (h - horizon)
        # стартовая площадка под роботом
        pw, ph = w * 0.34, max(16, h * 0.10)
        cv.create_oval(cx - pw, h * 0.80 - ph, cx + pw, h * 0.80 + ph,
                       outline=theme.blend(theme.CYAN, floor, 0.35), width=2, tags="tf_bg")
        cv.create_oval(cx - pw * 0.72, h * 0.80 - ph * 0.55, cx + pw * 0.72, h * 0.80 + ph * 0.55,
                       outline=theme.blend(theme.AMBER, floor, 0.30), tags="tf_bg")
        for dx in (-0.72, 0.72):
            x = cx + dx * pw
            cv.create_line(x, h * 0.80 - ph * 0.5, x, h * 0.80 + ph * 0.5,
                           fill=theme.blend(theme.AMBER, floor, 0.45), width=3, tags="tf_bg")
        # приглушённый свет: два конуса от потолка
        for dx in (-0.28, 0.28):
            x = cx + dx * w
            cv.create_polygon(x - w * 0.05, 0, x + w * 0.05, 0,
                              x + w * 0.13, h * 0.78, x - w * 0.13, h * 0.78,
                              fill=theme.blend(theme.BG, theme.CYAN, 0.05),
                              outline="", tags="tf_bg")
        cv.create_line(0, horizon, w, horizon, fill=theme.blend(theme.CYAN_DIM, theme.BG, 0.25),
                       width=2, tags="tf_bg")
        cv.tag_lower("tf_bg")

    def _raise_lock(self) -> None:
        self._raise_job = None
        try:
            self.canvas.tag_raise("tf_lock")
        except tk.TclError:
            pass

    def _draw_lock(self, open_: bool, r) -> None:
        cv = self.canvas
        cv.delete("tf_lock")
        if open_:
            return
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 20 or h < 20:
            return
        cv.create_rectangle(0, 0, w, h, fill=theme.BG, stipple="gray50", outline="",
                            tags="tf_lock")
        cv.create_text(w / 2, h * 0.12, text=t("🔒 ЗАКРЫТ"), fill=theme.AMBER,
                       font=theme.font(14, True), tags="tf_lock")
        cv.create_text(w / 2, h * 0.90, text=need_hint(self.progress, r.id), fill=theme.TEXT,
                       font=theme.font(9), tags="tf_lock")
        cv.tag_raise("tf_lock")

    # -- жизненный цикл -------------------------------------------------------
    def start(self) -> None:
        if self._viewer is not None:
            self._viewer.start()
        self._draw_lock(robot_open(self.progress, self.current_robot().id), self.current_robot())
        if self._raise_job is not None:
            try:
                self.after_cancel(self._raise_job)
            except tk.TclError:
                pass
        self._raise_job = self.after_idle(self._raise_lock)

    def stop(self) -> None:
        if self._viewer is not None:
            self._viewer.stop()
        for attr in ("_raise_job", "_lock_job"):
            job = getattr(self, attr, None)
            if job is not None:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
                setattr(self, attr, None)

    def _on_unmap(self, e=None) -> None:
        if e is not None and e.widget is not self:
            return
        self.stop()

    def _on_map(self, e=None) -> None:
        if e is not None and e.widget is not self:
            return
        if getattr(self.app, "current", None) == KEY and self._viewer is not None:
            self.start()

    def _on_destroy(self, e=None) -> None:
        if e is not None and e.widget is not self:
            return
        self.stop()
