"""Портал спряжения: весь экран — 12 времён, таблица ВОПРОС · УТВЕРЖДЕНИЕ · ОТРИЦАНИЕ.

Открывается клавишей O (Ctrl+O, O, o, Щ, щ) на вкладке ГЛАГОЛЫ и закрывается той же
клавишей или Esc. Как бумажный справочник: по пять лиц и три формы на каждое время.
В каждой из 12 плиток — озвучка фразы и проверка качества чтения: тот же SpeechCheck
и те же клавиши (M — микрофон, T — подержать подсказку), что в обычном режиме.
Оценки лежат под теми же ключами `verb_scores["<глагол>:<время>"]`, поэтому портал и
вкладка видят один прогресс.

Вёрстка резиновая: число колонок берётся по ширине окна, а плотность плитки (шрифты,
отступы, высота кнопок) — по высоте. Сначала пробуем самую крупную плотность, при
которой все 12 плиток влезают целиком; только если не влезает даже самая плотная —
появляется прокрутка. Замер настоящий (плитка-образец и winfo_reqwidth), а не «на глаз».

Чистые функции (`is_portal_key`, `portal_cells`, `fit_cols`, `plan`) — без Tk:
их проверяют тесты (tests/test_english_verbs_portal.py).
"""
from __future__ import annotations

import math
import tkinter as tk

from stamina.hud import HudButton
from stamina.i18n import t as _t
from stamina.theme import AMBER, BG, CYAN, GREEN, LINE, MUTED, PANEL, PANEL_HI, RED, TEXT, px

from . import conjugation as cj
from . import quality, verbs
from .check import SpeechCheck
from .speech_std import is_hint_key, is_mic_key, passed
from .ui import L, ScrollFrame

#: Колонки таблицы — как в бумажном справочнике: вопрос, утверждение, отрицание.
MODES = (("question", _t("ВОПРОС")), ("affirmative", _t("УТВЕРЖДЕНИЕ")), ("negative", _t("ОТРИЦАНИЕ")))
MODE_KEYS = [m[0] for m in MODES]
MODE_LABEL = dict(MODES)

#: Физическая клавиша O (латиница и Щ на той же кнопке) — код 79 на Windows.
KEYCODE_O = 79

#: Больше четырёх плиток в ряд не ставим: строка становится нечитаемой.
MAX_COLS = 4

#: Плотности плитки от «комфортной» к «самой плотной». Порядок важен: берём первую,
#: при которой все 12 плиток влезают в окно без прокрутки.
#: cells — шрифт фраз, name — заголовок времени, labels — подписи форм (0 — без них),
#: sub — строка перевода и подсказки (0 — без неё), btn/bfont — кнопки плитки.
DENSITIES = (
    {"cells": 9, "name": 10, "labels": 7, "sub": 8, "pady": 1, "btn": 24, "bfont": 8},
    {"cells": 8, "name": 9, "labels": 7, "sub": 7, "pady": 1, "btn": 22, "bfont": 7},
    {"cells": 8, "name": 9, "labels": 7, "sub": 7, "pady": 0, "btn": 20, "bfont": 7},
    {"cells": 8, "name": 9, "labels": 6, "sub": 7, "pady": 0, "btn": 18, "bfont": 7},
    {"cells": 7, "name": 8, "labels": 6, "sub": 6, "pady": 0, "btn": 18, "bfont": 6},
    {"cells": 7, "name": 8, "labels": 0, "sub": 0, "pady": 0, "btn": 16, "bfont": 6},
    {"cells": 6, "name": 7, "labels": 0, "sub": 0, "pady": 0, "btn": 14, "bfont": 6},
)


def is_portal_key(e) -> bool:
    """O / o / Щ / щ / Ctrl+O в любой раскладке — вход и выход из портала."""
    if getattr(e, "keycode", 0) == KEYCODE_O:
        return True
    ks = str(getattr(e, "keysym", "") or "").lower()
    ch = str(getattr(e, "char", "") or "").lower()
    return ks in ("o", _t("щ"), "cyrillic_shcha") or ch in ("o", _t("щ"))


def _cap(text: str) -> str:
    """Ячейка таблицы — самостоятельная строка, поэтому с большой буквы («They do not go»)."""
    return text[:1].upper() + text[1:]


def fit_cols(width: int, need: int, tiles: int = 12, max_cols: int = MAX_COLS) -> int:
    """Сколько плиток встанет в ряд без сжатия: чем шире окно, тем больше колонок."""
    if need <= 0:
        return min(max_cols, tiles)
    for cols in range(min(max_cols, tiles), 0, -1):
        if cols * need <= width:
            return cols
    return 1


def plan(width: int, height: int, sizes, tiles: int = 12, gap: int = 8,
         max_cols: int = MAX_COLS) -> tuple[int, int, int]:
    """Выбрать плотность, число колонок и строк так, чтобы все плитки были видны.

    `sizes` — замеренные (ширина, высота) плитки для каждой плотности, от крупной к
    плотной; `gap` — внешний отступ плитки (учитывается и по ширине, и по высоте).
    Возвращаем (плотность, колонки, строки); если не влезает даже самая плотная —
    её и прокрутку.
    """
    sizes = list(sizes)
    for level, (need_w, need_h) in enumerate(sizes):
        cols = fit_cols(width, need_w + gap, tiles, max_cols)
        rows = math.ceil(tiles / cols)
        if rows * (need_h + gap) <= height:
            return level, cols, rows
    level = len(sizes) - 1
    cols = fit_cols(width, sizes[level][0] + gap, tiles, max_cols)
    return level, cols, math.ceil(tiles / cols)


def portal_cells(verb: dict) -> list[dict]:
    """12 плиток портала: время, подписи, ячейки 5 лиц × 3 формы и настоящий пример Tatoeba."""
    pack = verb.get("pack") or verbs.pack_verb(verb["slug"]) or {}
    base = verb["slug"]
    v2, v3 = pack.get("v2"), pack.get("v3")
    out = []
    for i, (key, en_name, ru_name, hint) in enumerate(verbs.TENSES):
        cells = {mode: {person: _cap(cj.conjugate(base, key, person, mode=mode, v2=v2, v3=v3))
                        for person in cj.PERSON_KEYS}
                 for mode in MODE_KEYS}
        ex = verbs.example_for(pack, key) if pack.get("examples") else None
        out.append({"index": i, "key": key, "en": en_name, "ru": ru_name, "hint": hint,
                    "cells": cells, "example": ex})
    return out


class VerbsPortal(tk.Frame):
    """Портал на весь экран: 12 плиток, в каждой — таблица, озвучка и проверка речи."""

    def __init__(self, master, ctx, on_close=None) -> None:
        super().__init__(master, bg=BG, highlightthickness=0, bd=0, takefocus=1)
        self.ctx = ctx
        self._on_close = on_close
        self.slug = verbs.entries()[0]["slug"]
        self.active = 0
        self.pick = {i: ("I", "affirmative") for i in range(len(cj.TENSES))}
        self._scores: dict[str, int] = {}
        self._data: list[dict] = []
        self._cells: dict[int, dict[tuple[str, str], tk.Label]] = {}
        self._tiles: dict[int, tk.Frame] = {}
        self._badges: dict[int, tk.Label] = {}
        self._sizes: list[tuple[int, int]] | None = None
        self._density = -1
        self._shape = (0, 0)
        self._fit_job = None
        self._build()
        self.set_verb(self.slug)
        self.bind("<Configure>", self._schedule_fit)

    # -- сборка ---------------------------------------------------------------
    def _build(self) -> None:
        top = tk.Frame(self, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        top.pack(fill=tk.X)
        row = tk.Frame(top, bg=PANEL)
        row.pack(fill=tk.X, padx=px(12), pady=px(5))
        self.word_lbl = L(row, "", fg=CYAN, size=20, bold=True, mono=True, bg=PANEL)
        self.word_lbl.pack(side=tk.LEFT)
        self.ru_lbl = L(row, "", fg=TEXT, size=11, bg=PANEL)
        self.ru_lbl.pack(side=tk.LEFT, padx=(px(10), 0))
        self.forms_lbl = L(row, "", fg=MUTED, size=9, mono=True, bg=PANEL)
        self.forms_lbl.pack(side=tk.LEFT, padx=(px(10), 0))
        HudButton(row, _t("← НАЗАД"), self.close, height=28, font_size=8,
                  color=AMBER).pack(side=tk.RIGHT, padx=px(3))
        HudButton(row, _t("СЛУЧАЙНЫЙ"), self.random_verb, height=28, font_size=8,
                  color=GREEN).pack(side=tk.RIGHT, padx=px(3))
        self.ctx.audio_button(row, _t("🔊 СЛОВО"), lambda: self.word(), height=28,
                              font_size=8).pack(side=tk.RIGHT, padx=px(3))
        self.count_lbl = L(row, "", fg=MUTED, size=8, bg=PANEL)
        self.count_lbl.pack(side=tk.RIGHT, padx=(px(8), px(8)))
        L(row, _t("O / Esc — назад"), fg=MUTED, size=8, bg=PANEL).pack(side=tk.RIGHT)

        # Плитки 12 и они крупные: прокрутка — только если не влезает даже плотная вёрстка
        self.sf = ScrollFrame(self, bg=BG)
        self.sf.autohide = True
        self.sf.pack(fill=tk.BOTH, expand=True, padx=px(4), pady=px(2))
        self.grid_box = self.sf.inner
        self.sf.canvas.bind("<Configure>", self._schedule_fit, add="+")

        bottom = tk.Frame(self, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        bottom.pack(fill=tk.X, pady=(px(2), 0))
        self.target_lbl = L(bottom, "", fg=CYAN, size=10, bold=True, bg=PANEL)
        self.target_lbl.pack(anchor="w", padx=px(12), pady=(px(3), 0))
        self.example_lbl = L(bottom, "", fg=MUTED, size=9, bg=PANEL)
        self.example_lbl.pack(anchor="w", padx=px(12))
        self.check = SpeechCheck(bottom, self.ctx, self.on_speech, bg=PANEL, compact=True)
        self.check.pack(fill=tk.X, padx=px(10), pady=px(3))
        self.mic = self.check.mic
        self.status = self.check.note

    # -- данные ---------------------------------------------------------------
    def _verb(self) -> dict:
        return verbs.find(self.slug) or verbs.entries()[0]

    def word(self) -> str:
        return self._verb()["word"]

    def sentence(self, i: int) -> str:
        """Фраза плитки, выбранная для микрофона (лицо и форма — по клику)."""
        person, mode = self.pick.get(i, ("I", "affirmative"))
        if not self._data:
            self._data = portal_cells(self._verb())
        return self._data[i]["cells"][mode][person]

    def _score_key(self, i: int) -> str:
        return f"{self.slug}:{i}"

    def _set_scores(self) -> None:
        self._scores = dict(self.ctx.progress.data.get("verb_scores") or {})

    # -- отрисовка ------------------------------------------------------------
    def set_verb(self, slug: str) -> None:
        verb = verbs.find(slug) or verbs.entries()[0]
        self.slug = verb["slug"]
        self._set_scores()
        self.word_lbl.configure(text=verb["word"])
        self.ru_lbl.configure(text=verb["ru"])
        f = verb["forms"]
        self.forms_lbl.configure(text=f"{f['base']}  ·  {f['past']}  ·  {f['pp']}  ·  {f['ing']}")
        self._data = portal_cells(verb)
        self._sizes = None          # у другого глагола другие слова — мерим заново
        self._density = -1
        self._shape = (0, 0)
        self._build_tiles(self._data, 0)
        self._render_target()
        self._render_counts()
        if self.winfo_ismapped():
            self._fit(force=True)

    def _make_tile(self, parent, item: dict, d: dict):
        """Плитка одной плотности: (плитка, ячейки, бейдж с оценкой)."""
        i = item["index"]
        tile = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        head = tk.Frame(tile, bg=PANEL)
        head.pack(fill=tk.X, padx=px(6), pady=(px(3), 0))
        L(head, f"{i + 1:02d} · {item['en']}", fg=CYAN, size=d["name"], bold=True,
          bg=PANEL).pack(side=tk.LEFT)
        badge = L(head, "—", fg=MUTED, size=d["name"], bold=True, mono=True, bg=PANEL)
        badge.pack(side=tk.RIGHT)
        if d["sub"]:
            L(tile, f"{item['ru']} · {item['hint']}", fg=MUTED, size=d["sub"], bg=PANEL,
              anchor="w").pack(fill=tk.X, padx=px(6))
        foot = tk.Frame(tile, bg=PANEL)
        foot.pack(side=tk.BOTTOM, fill=tk.X, padx=px(4), pady=px(3))
        self.ctx.audio_button(foot, _t("🔊 ОЗВУЧИТЬ"), lambda t=i: self.sentence(t),
                              height=d["btn"], font_size=d["bfont"], width=96).pack(side=tk.LEFT)
        HudButton(foot, _t("🎤 ПРОВЕРИТЬ"), lambda t=i: self.check_tile(t), height=d["btn"],
                  font_size=d["bfont"], color=GREEN, width=104).pack(side=tk.RIGHT)
        body = tk.Frame(tile, bg=PANEL)
        body.pack(fill=tk.BOTH, expand=True, padx=px(2))
        top = 2 if d["labels"] else 1
        if d["labels"]:
            for mi, (_key, label) in enumerate(MODES):
                L(body, label, fg=MUTED, size=d["labels"], bg=PANEL, anchor="w").grid(
                    row=1, column=mi, sticky="ew", padx=px(1))
        cells: dict[tuple[str, str], tk.Label] = {}
        for pi, person in enumerate(cj.PERSON_KEYS):
            for mi, mode in enumerate(MODE_KEYS):
                lab = L(body, item["cells"][mode][person], fg=TEXT, size=d["cells"], bg=PANEL,
                        anchor="w", justify="left")
                lab.grid(row=top + pi, column=mi, sticky="ew", padx=px(1), pady=px(d["pady"]))
                lab.bind("<Button-1>", lambda _e, t=i, p=person, m=mode: self.choose(t, p, m))
                cells[(person, mode)] = lab
        # Распорки сверху и снизу: на высоком окне таблица стоит по центру плитки, а не липнет к верху
        body.grid_rowconfigure(0, weight=1)
        body.grid_rowconfigure(top + len(cj.PERSON_KEYS), weight=1)
        return tile, cells, badge

    def _widest_item(self) -> dict:
        """Плитка, которая задаёт ширину колонки: сетка равняет все колонки по самой широкой."""
        def weight(item: dict) -> tuple[int, int]:
            cells = [text for mode in MODE_KEYS for text in item["cells"][mode].values()]
            return max(len(text) for text in cells), len(item["ru"]) + len(item["hint"])
        return max(self._data, key=weight)

    def _probe_sizes(self) -> list[tuple[int, int]]:
        """Замерить плитку на каждой плотности: замер честный, без догадок о шрифтах."""
        if self._sizes is not None:
            return self._sizes
        holder = tk.Frame(self)
        out = []
        item = self._widest_item()
        for d in DENSITIES:
            tile, _cells, _badge = self._make_tile(holder, item, d)
            self.update_idletasks()
            out.append((tile.winfo_reqwidth(), tile.winfo_reqheight()))
            tile.destroy()
        holder.destroy()
        self._sizes = out
        return out

    def _build_tiles(self, data: list[dict], level: int) -> None:
        for child in self.grid_box.winfo_children():
            child.destroy()
        self._cells.clear()
        self._tiles.clear()
        self._badges.clear()
        d = DENSITIES[level]
        for item in data:
            i = item["index"]
            tile, cells, badge = self._make_tile(self.grid_box, item, d)
            self._tiles[i] = tile
            self._cells[i] = cells
            self._badges[i] = badge
        self._density = level
        self.update_idletasks()

    def _layout_tiles(self, cols: int, rows: int) -> None:
        self._shape = (cols, rows)
        for c in range(MAX_COLS):
            if c < cols:
                self.grid_box.grid_columnconfigure(c, weight=1, uniform="tile")
            else:   # uniform у пустой колонки всё равно занимал бы место — снимаем
                self.grid_box.grid_columnconfigure(c, weight=0, uniform="")
        for r in range(len(self._tiles) or 12):
            self.grid_box.grid_rowconfigure(r, weight=1 if r < rows else 0)
        for i, tile in self._tiles.items():
            tile.grid(row=i // cols, column=i % cols, sticky="nsew", padx=px(2), pady=px(2))

    def _schedule_fit(self, _e=None) -> None:
        """Пересчёт вёрстки — после того как окно дорисовано (без дребезга при ресайзе)."""
        if self._fit_job is None:
            self._fit_job = self.after(40, self._fit)

    def _fit(self, force: bool = False) -> None:
        self._fit_job = None
        if not self._data or not self.winfo_ismapped():
            return                                  # портал скрыт — пересчитывать нечего
        w, h = self.sf.canvas.winfo_width(), self.sf.canvas.winfo_height()
        if w < 160 or h < 90:                       # ещё не разложено — попробуем позже
            self._fit_job = self.after(40, self._fit)
            return
        level, cols, rows = plan(w, h, self._probe_sizes(), len(self._data), gap=px(4))
        if force or level != self._density:
            self._build_tiles(self._data, level)
        if force or (cols, rows) != self._shape:
            self._layout_tiles(cols, rows)
        self._paint()
        self.after_idle(self.sf.sync)

    def _paint(self) -> None:
        for i, cells in self._cells.items():
            pick = self.pick.get(i, ("I", "affirmative"))
            for (person, mode), lab in cells.items():
                on = (person, mode) == pick
                try:
                    lab.configure(bg=PANEL_HI if on else PANEL, fg=CYAN if on else TEXT)
                except tk.TclError:
                    return
            tile = self._tiles.get(i)
            if tile is not None:
                tile.configure(highlightbackground=CYAN if i == self.active else LINE)

    def _render_target(self) -> None:
        i = self.active
        person, mode = self.pick[i]
        item = self._data[i] if self._data else portal_cells(self._verb())[i]
        self.target_lbl.configure(
            text=_t("Читаем: {0}").format(f"{item['en']} · {person} · {_t(MODE_LABEL[mode])} — "
                                          f"{item['cells'][mode][person]}"))
        ex = item["example"]
        self.example_lbl.configure(
            text=_t("Пример: {0}").format(f"{ex['en']} — {ex.get('ru') or ''}") if ex
            else _t("Нет настоящего примера в Tatoeba."))

    def _render_counts(self) -> None:
        c = quality.counts(self.ctx.progress, "verb:" + self.slug, "verb", len(cj.TENSES))
        done = sum(1 for i in range(len(cj.TENSES)) if (self._scores.get(self._score_key(i)) or 0) >= 80)
        self.count_lbl.configure(
            text=_t("Проверено примеров: {0}/12 · качество: {1}/{2}").format(done, c["filled"], c["goal"]))
        for i in self._badges:
            self._update_badge(i)

    def _update_badge(self, i: int) -> None:
        badge = self._badges.get(i)
        if badge is None:
            return
        best = self._scores.get(self._score_key(i))
        if best is None:
            badge.configure(text="—", fg=MUTED)
        else:
            col = GREEN if best >= 80 else (AMBER if best >= 60 else RED)
            badge.configure(text=f"{best}%", fg=col)

    # -- действия -------------------------------------------------------------
    def show(self, slug: str = "") -> None:
        if slug and slug != self.slug:
            self.set_verb(slug)
        else:
            self.refresh()
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.lift()
        self.update_idletasks()
        self._fit(force=True)
        try:
            self.focus_set()
        except tk.TclError:
            pass

    def close(self) -> None:
        if self._fit_job is not None:
            try:
                self.after_cancel(self._fit_job)
            except tk.TclError:
                pass
            self._fit_job = None
        self.check.reset()
        self.place_forget()
        if callable(self._on_close):
            self._on_close()

    def refresh(self) -> None:
        self._set_scores()
        self._render_counts()
        self._paint()
        self._render_target()

    def choose(self, i: int, person: str, mode: str) -> None:
        """Выбрать фразу плитки: её озвучивает 🔊, её же проверяет 🎤."""
        self.active = i
        self.pick[i] = (person, mode)
        self._paint()
        self._render_target()

    def check_tile(self, i: int) -> None:
        """🎤 в плитке: она становится целью микрофона, и проверка начинается."""
        self.active = i
        self.pick.setdefault(i, ("I", "affirmative"))
        self._paint()
        self._render_target()
        self.check.toggle()

    def random_verb(self) -> None:
        import random
        choices = [v["slug"] for v in verbs.entries() if v["slug"] != self.slug]
        if choices:
            self.check.reset()
            self.set_verb(random.choice(choices))

    def on_speech(self, alts, self_score) -> None:
        i = self.active
        target = self.sentence(i)
        res = self.check.evaluate(target, alts, self_score, self.word())
        if res is None:
            return
        score = res[0]
        key = self._score_key(i)
        self._scores[key] = max(self._scores.get(key, 0), score)
        self.ctx.progress.data.setdefault("verb_scores", {})[key] = self._scores[key]
        self.ctx.progress.save()
        if passed(score):
            quality.auto(self.ctx.progress, "verb:" + self.slug, "B", score,
                         si=i, kind="verb", n_sents=len(cj.TENSES))
        self.status.configure(text=_t("Пример {0}: {1}%").format(i + 1, score),
                              fg=GREEN if passed(score) else MUTED)
        self._update_badge(i)
        self._render_counts()
        here = (self.slug, i)
        self.check.judge(score, self.next_item, lambda: (self.slug, self.active) == here)

    def _hint_text(self) -> str:
        i = self.active
        item = self._data[i] if self._data else portal_cells(self._verb())[i]
        person, mode = self.pick[i]
        ex = item["example"]
        example = f"{ex['en']} — {ex.get('ru') or ''}" if ex else ""
        return f"{item['ru']} · {item['hint']} · {person}/{_t(MODE_LABEL[mode])}  ·  {example}".strip()

    def next_item(self) -> None:
        """≥80% — следующее время (как в обычном режиме), по кругу."""
        self.active = (self.active + 1) % len(cj.TENSES)
        self._paint()
        self._render_target()

    # -- клавиши --------------------------------------------------------------
    def on_key(self, e) -> bool:
        k = (e.keysym or "").lower()
        if k == "escape" or is_portal_key(e):
            self.close()
            return True
        if is_mic_key(e):
            self.check.toggle()
            return True
        if is_hint_key(e):
            self.check.hint_down(self._hint_text())
            return True
        person, mode = self.pick.get(self.active, ("I", "affirmative"))
        pi, mi = cj.PERSON_KEYS.index(person), MODE_KEYS.index(mode)
        if k == "down":
            pi = min(pi + 1, len(cj.PERSON_KEYS) - 1)
        elif k == "up":
            pi = max(pi - 1, 0)
        elif k == "right":
            mi = min(mi + 1, len(MODE_KEYS) - 1)
        elif k == "left":
            mi = max(mi - 1, 0)
        elif k in ("return", "kp_enter"):
            self.ctx.say(self.sentence(self.active))
            return True
        else:
            return False
        self.choose(self.active, cj.PERSON_KEYS[pi], MODE_KEYS[mi])
        return True

    def on_key_up(self, e) -> None:
        if is_hint_key(e):
            self.check.hint_up()
