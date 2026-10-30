"""СПРАВОЧНИК глаголов: поиск, 12 времён × 5 лиц, утверждение / отрицание / вопрос.

Таблицы строит conjugation.py (не хранятся). Формы, IPA и перевод — Kaikki/Wiktionary,
примеры — Tatoeba (см. data/verbs/*.json). Клавиши: ввод в поиске сразу фильтрует,
Enter открывает глагол, ↑/↓ — лицо (или строка списка в поиске), ←/→ — время,
Ctrl+Enter — «→ в карточку» для выбранной ячейки.
"""
from __future__ import annotations

import re
import tkinter as tk

from stamina import theme as th
from stamina.hud import HudButton, HudPanel
from stamina.i18n import t as _t
from stamina.theme import px

from . import conjugation as cj
from . import verbs
from .check import SpeechCheck
from .speech_std import is_hint_key, is_mic_key, passed
from .ui import L, ScrollFrame, entry

_TOKEN = re.compile(r"[A-Za-z']+|[^A-Za-z']+")


def _tense_ru(name: str) -> str:
    """Литеральные ключи, чтобы tools/i18n_check.py их видел."""
    return {
        "Настоящее простое": _t("Настоящее простое"),
        "Настоящее длительное": _t("Настоящее длительное"),
        "Настоящее совершенное": _t("Настоящее совершенное"),
        "Настоящее совершенное длительное": _t("Настоящее совершенное длительное"),
        "Прошедшее простое": _t("Прошедшее простое"),
        "Прошедшее длительное": _t("Прошедшее длительное"),
        "Прошедшее совершенное": _t("Прошедшее совершенное"),
        "Прошедшее совершенное длительное": _t("Прошедшее совершенное длительное"),
        "Будущее простое": _t("Будущее простое"),
        "Будущее длительное": _t("Будущее длительное"),
        "Будущее совершенное": _t("Будущее совершенное"),
        "Будущее совершенное длительное": _t("Будущее совершенное длительное"),
    }.get(name, name)


def _mode_title(mode: str) -> str:
    return {"affirmative": _t("УТВЕРЖДЕНИЕ"), "negative": _t("ОТРИЦАНИЕ"),
            "question": _t("ВОПРОС")}[mode]


class ReferencePanel(tk.Frame):
    """Слева — поиск и список глаголов (замок у закрытых), справа — таблица времени."""

    def __init__(self, master, ctx, on_back=None) -> None:
        super().__init__(master, bg=th.BG)
        self.ctx = ctx
        self.on_back = on_back
        self.mode = "affirmative"
        self.tense = cj.TENSE_KEYS[0]
        self.person_i = 0
        self.list_i = 0
        self.results: list[dict] = []
        verbs_all = verbs.irregular() or verbs.all_pack_verbs()
        self.verb = verbs_all[0] if verbs_all else None
        self._build()
        self.refresh()

    # -- сборка ---------------------------------------------------------------
    def _alt(self) -> bool:
        return getattr(self.winfo_toplevel(), "_alt_view", None) is not None

    def _build(self) -> None:
        left = tk.Frame(self, bg=th.BG, width=px(290 if self._alt() else 270))
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(px(12), px(6)), pady=px(6))
        left.pack_propagate(False)
        lp = HudPanel(left, _t("СПРАВОЧНИК"))
        lp.pack(fill=tk.BOTH, expand=True)
        sbox = tk.Frame(lp.body, bg=th.PANEL)
        sbox.pack(fill=tk.X, padx=px(4), pady=(px(2), px(4)))
        L(sbox, "⌕", fg=th.CYAN, size=12, bold=True, bg=th.PANEL).pack(side=tk.LEFT, padx=(0, px(4)))
        self.q = tk.StringVar()
        self.search = entry(sbox, width=20, size=10)
        self.search.configure(textvariable=self.q)
        self.search.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=px(3))
        self.q.trace_add("write", lambda *_a: self._on_query())
        self.search.bind("<Return>", lambda _e: self._open_selected())
        self.search.bind("<Down>", lambda _e: self._move_list(1))
        self.search.bind("<Up>", lambda _e: self._move_list(-1))
        self.lock_lbl = L(lp.body, "", fg=th.MUTED, size=8, bg=th.PANEL, wraplength=px(240),
                          justify="left")
        self.lock_lbl.pack(fill=tk.X, padx=px(6))
        self.list_sf = ScrollFrame(lp.body, bg=th.PANEL)
        self.list_sf.pack(fill=tk.BOTH, expand=True)

        right = tk.Frame(self, bg=th.BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(px(6), px(12)), pady=px(6))
        head = tk.Frame(right, bg=th.PANEL, highlightthickness=1, highlightbackground=th.LINE)
        head.pack(fill=tk.X)
        top = tk.Frame(head, bg=th.PANEL)
        top.pack(fill=tk.X, padx=px(12), pady=(px(8), 0))
        self.word_lbl = L(top, "", fg=th.CYAN, size=22, bold=True, mono=True, bg=th.PANEL)
        self.word_lbl.pack(side=tk.LEFT)
        self.ipa_lbl = L(top, "", fg=th.MUTED, size=11, mono=True, bg=th.PANEL)
        self.ipa_lbl.pack(side=tk.LEFT, padx=px(10), pady=(px(8), 0))
        if self.on_back is not None:
            HudButton(top, _t("← 12 ВРЕМЁН"), self.on_back, height=28, font_size=8).pack(side=tk.RIGHT)
        self.forms_row = tk.Frame(head, bg=th.PANEL)
        self.forms_row.pack(anchor="w", padx=px(12), pady=(px(2), 0))
        self.ru_lbl = L(head, "", fg=th.TEXT, size=11, bg=th.PANEL)
        self.ru_lbl.pack(anchor="w", padx=px(12), pady=(0, px(4)))

        modes = tk.Frame(head, bg=th.PANEL)
        modes.pack(fill=tk.X, padx=px(10), pady=(0, px(4)))
        self.mode_btns = {}
        for m in cj.MODES:
            b = HudButton(modes, _mode_title(m), lambda mm=m: self.set_mode(mm), height=28, font_size=8)
            b.pack(side=tk.LEFT, padx=px(2))
            self.mode_btns[m] = b
        self.tense_btns = {}
        for row_keys in (cj.TENSE_KEYS[:4], cj.TENSE_KEYS[4:8], cj.TENSE_KEYS[8:]):
            row = tk.Frame(head, bg=th.PANEL)
            row.pack(fill=tk.X, padx=px(10), pady=(0, px(3)))
            for key in row_keys:
                name = next(t[1] for t in cj.TENSES if t[0] == key)
                b = HudButton(row, name.upper(), lambda k=key: self.set_tense(k), height=24, font_size=7)
                b.pack(side=tk.LEFT, padx=px(2))
                self.tense_btns[key] = b

        self.cells = tk.Frame(right, bg=th.PANEL, highlightthickness=1, highlightbackground=th.LINE)
        self.cells.pack(fill=tk.X, pady=(px(4), 0))
        self.example = tk.Frame(right, bg=th.PANEL, highlightthickness=1, highlightbackground=th.LINE)
        self.example.pack(fill=tk.X, pady=(px(4), 0))
        # единый блок проверки — как в сканере: произносим выбранную форму (лицо × время)
        micbar = tk.Frame(right, bg=th.PANEL, highlightthickness=1, highlightbackground=th.LINE)
        micbar.pack(fill=tk.X, pady=(px(4), 0))
        self.check = SpeechCheck(micbar, self.ctx, self.on_speech, bg=th.PANEL)
        self.check.pack(fill=tk.X, padx=px(10), pady=px(6))
        self.mic = self.check.mic
        self.mic_status = self.check.note
        self.mic_status.configure(text=_t("Произнесите выбранную форму: M — микрофон."))
        self.status = L(right, _t("Ctrl+Enter — «→ в карточку» для выбранной строки; ←/→ — время, ↑/↓ — лицо."),
                        fg=th.MUTED, size=8, bg=th.BG, wraplength=px(620), justify="left")
        self.status.pack(fill=tk.X, pady=(px(4), 0))

        self._keys = (("<Left>", lambda: self._step_tense(-1)), ("<Right>", lambda: self._step_tense(1)),
                      ("<Up>", lambda: self._move_person(-1)), ("<Down>", lambda: self._move_person(1)),
                      ("<Control-Return>", self.add_selected))
        self.after_idle(self._bind_keys)

    def _bind_keys(self) -> None:
        """Клавиши вешаем на окно (add="+"), но реагируем только когда справочник виден
        и фокус внутри него; в поле поиска ↑/↓ листают список, ←/→ двигают курсор."""
        try:
            top = self.winfo_toplevel()
        except tk.TclError:
            return
        me = str(self)
        for seq, fn in self._keys:
            def handler(e, f=fn, s=seq):
                try:
                    if not self.winfo_exists() or not self.winfo_ismapped():
                        return None
                except tk.TclError:
                    return None
                w = str(getattr(e, "widget", ""))
                if not (w == me or w.startswith(me + ".") or w == str(top)):
                    return None
                if getattr(e, "widget", None) is self.search and s != "<Control-Return>":
                    return None
                f()
                return "break"
            top.bind(seq, handler, add="+")

    # -- данные ---------------------------------------------------------------
    def _forms(self) -> dict:
        v = self.verb or {}
        return {"v1": v.get("lemma", ""), "v2": v.get("v2", ""), "v3": v.get("v3", ""),
                "s": v.get("s", ""), "ing": v.get("ing", "")}

    def _conj(self, person: str) -> str:
        v = self.verb
        return cj.conjugate(v["lemma"], self.tense, person, self.mode, v.get("v2"), v.get("v3"))

    # -- отрисовка ------------------------------------------------------------
    def refresh(self) -> None:
        self._on_query()
        self._render_verb()

    def _on_query(self) -> None:
        self.results = verbs.search(self.q.get())
        self.list_i = 0
        self._render_list()

    def _render_list(self) -> None:
        for c in self.list_sf.inner.winfo_children():
            c.destroy()
        prog = self.ctx.progress
        closed = verbs.locked_lemmas(prog)
        for i, v in enumerate(self.results):
            locked = v["lemma"] in closed
            on = self.verb is not None and v["lemma"] == self.verb["lemma"]
            sel = i == self.list_i
            label = ("🔒 " if locked else "") + f"{v['lemma']}  ·  {v.get('ru') or '—'}"
            b = HudButton(self.list_sf.inner, label, lambda vv=v: self.open_verb(vv), height=28,
                          font_size=8, width=236, active=on or sel,
                          color=th.MUTED if locked else (th.CYAN if on else None))
            b.pack(fill=tk.X, padx=px(4), pady=px(2))
        left, step = verbs.unlock_hint(prog)
        if left:
            self.lock_lbl.configure(text=_t("🔒 Освойте ещё {0} глаголов — откроется {1} новых.").format(left, step))
        else:
            self.lock_lbl.configure(text="")

    def _render_verb(self) -> None:
        v = self.verb
        if v is None:
            self.word_lbl.configure(text=_t("Нет данных"))
            return
        self.word_lbl.configure(text=v["lemma"])
        self.ipa_lbl.configure(text=v.get("ipa") or "")
        self.ru_lbl.configure(text=v.get("ru") or "—")
        for c in self.forms_row.winfo_children():
            c.destroy()
        irr = cj.irregular_tokens(v["lemma"], v.get("v2"), v.get("v3"))
        for tag, val in (("V1", v["lemma"]), ("V2", v.get("v2", "")), ("V3", v.get("v3", ""))):
            col = th.AMBER if any(p in irr for p in val.split("/")) else th.TEXT
            L(self.forms_row, tag, fg=th.MUTED, size=8, bg=th.PANEL).pack(side=tk.LEFT, padx=(0, px(3)))
            L(self.forms_row, val, fg=col, size=12, bold=True, mono=True,
              bg=th.PANEL).pack(side=tk.LEFT, padx=(0, px(12)))
        for m, b in self.mode_btns.items():
            b.set_active(m == self.mode)
        for k, b in self.tense_btns.items():
            b.set_active(k == self.tense)
        self._render_cells(irr)
        self._render_example()

    def _render_cells(self, irr: set[str]) -> None:
        for c in self.cells.winfo_children():
            c.destroy()
        tname = next(t for t in cj.TENSES if t[0] == self.tense)
        L(self.cells, f"{tname[1]} · {_tense_ru(tname[2])} · {_mode_title(self.mode)}", fg=th.CYAN, size=9,
          bold=True, bg=th.PANEL).pack(anchor="w", padx=px(10), pady=(px(6), px(2)))
        for i, (pk, _subj, label) in enumerate(cj.PERSONS):
            on = i == self.person_i
            bg = th.BG2 if on else th.PANEL
            row = tk.Frame(self.cells, bg=bg, highlightthickness=1,
                           highlightbackground=th.CYAN if on else th.LINE, cursor="hand2")
            row.pack(fill=tk.X, padx=px(6), pady=px(2))
            L(row, label, fg=th.MUTED, size=8, bg=bg, width=12, anchor="w").pack(side=tk.LEFT, padx=px(6))
            text = self._conj(pk)
            line = tk.Frame(row, bg=bg)
            line.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=px(4))
            chunks: list[list] = []          # [текст, подсветка]; знаки препинания липнут к слову
            for tok in _TOKEN.findall(text):
                tok = tok.strip()
                if not tok:
                    continue
                if chunks and not any(ch.isalnum() for ch in tok):
                    chunks[-1][0] += tok
                else:
                    chunks.append([tok, tok.lower() in irr])
            for i_c, (tok, hl) in enumerate(chunks):
                L(line, tok, fg=th.AMBER if hl else th.TEXT, size=12, bold=hl, mono=True,
                  bg=bg).pack(side=tk.LEFT, padx=(0 if i_c == 0 else px(6), 0))
            HudButton(row, _t("→ в карточку"), lambda n=i: self.add_cell(n), height=24, font_size=7,
                      color=th.GREEN).pack(side=tk.RIGHT, padx=px(4), pady=px(2))
            self.ctx.audio_button(row, _t("🔊"), lambda s=text: s, height=24, font_size=8,
                                  width=34).pack(side=tk.RIGHT, padx=px(2))
            for w in (row, line):
                w.bind("<Button-1>", lambda _e, n=i: self.select_person(n))

    def _render_example(self) -> None:
        for c in self.example.winfo_children():
            c.destroy()
        ex = verbs.example_for(self.verb, self.tense)
        if not ex:
            L(self.example, _t("Нет настоящего примера в Tatoeba."), fg=th.MUTED, size=9,
              bg=th.PANEL).pack(anchor="w", padx=px(10), pady=px(6))
            return
        L(self.example, _t("ПРИМЕР ИЗ TATOEBA"), fg=th.MUTED, size=7, bold=True,
          bg=th.PANEL).pack(anchor="w", padx=px(10), pady=(px(6), 0))
        L(self.example, ex["en"], fg=th.TEXT, size=11, bg=th.PANEL, wraplength=px(620),
          justify="left").pack(anchor="w", padx=px(10))
        L(self.example, ex.get("ru") or "", fg=th.MUTED, size=9, bg=th.PANEL, wraplength=px(620),
          justify="left").pack(anchor="w", padx=px(10))
        L(self.example, f"tatoeba.org #{ex['source_id']} · {ex.get('license', '')}", fg=th.MUTED, size=7,
          bg=th.PANEL).pack(anchor="w", padx=px(10), pady=(0, px(6)))

    # -- действия -------------------------------------------------------------
    def open_verb(self, v: dict) -> None:
        if verbs.is_locked(self.ctx.progress, v["lemma"]):
            left, step = verbs.unlock_hint(self.ctx.progress)
            self.status.configure(
                text=_t("🔒 «{0}» пока закрыт: освойте ещё {1} глаголов из открытых.").format(v["lemma"], left),
                fg=th.AMBER)
            return
        self.verb = v
        self.person_i = 0
        self._render_list()
        self._render_verb()
        self.focus_set()

    def _open_selected(self):
        if self.results:
            self.open_verb(self.results[min(self.list_i, len(self.results) - 1)])
        return "break"

    def _move_list(self, d: int):
        if self.results:
            self.list_i = max(0, min(len(self.results) - 1, self.list_i + d))
            self._render_list()
        return "break"

    def on_key(self, e) -> None:
        if getattr(e, "widget", None) is self.search:
            return
        if is_mic_key(e):
            self.check.toggle()
        elif is_hint_key(e):
            self.check.hint_down(self._hint_text())

    def on_key_up(self, e) -> None:
        if is_hint_key(e):
            self.check.hint_up()

    def _hint_text(self) -> str:
        if self.verb is None:
            return ""
        v = self.verb
        parts = [f"V1 {v['lemma']} · V2 {v.get('v2', '')} · V3 {v.get('v3', '')}", v.get("ru") or ""]
        ex = verbs.example_for(v, self.tense)
        if ex:
            parts.append(f"{ex['en']} — {ex.get('ru') or ''}")
        return "\n".join(p for p in parts if p)

    def on_speech(self, alts, self_score) -> None:
        """Проверка выбранной формы (лицо × время) по стандарту сканера; ≥80% — следующая форма,
        после последнего лица — следующее время; ниже — остаёмся."""
        if self.verb is None:
            return
        target = self._conj(cj.PERSON_KEYS[self.person_i])
        res = self.check.evaluate(target, alts, self_score, self.verb["lemma"])
        if res is None:
            return
        score = res[0]
        self.mic_status.configure(text=_t("Форма «{0}»: {1}%").format(target, score),
                                  fg=th.GREEN if passed(score) else th.MUTED)
        here = (self.verb["lemma"], self.tense, self.person_i)
        self.check.judge(score, self.next_form,
                         lambda: (self.verb["lemma"], self.tense, self.person_i) == here)

    def next_form(self) -> None:
        if self.person_i < len(cj.PERSONS) - 1:
            self.select_person(self.person_i + 1)
        else:
            self.person_i = 0
            self._step_tense(1)

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self._render_verb()

    def set_tense(self, key: str) -> None:
        if key != self.tense:
            self.check.clear()
        self.tense = key
        self._render_verb()

    def _step_tense(self, d: int) -> None:
        i = cj.TENSE_KEYS.index(self.tense)
        self.set_tense(cj.TENSE_KEYS[(i + d) % len(cj.TENSE_KEYS)])

    def _move_person(self, d: int) -> None:
        self.select_person((self.person_i + d) % len(cj.PERSONS))

    def select_person(self, i: int) -> None:
        if i != self.person_i:
            self.check.clear()
        self.person_i = i
        self._render_cells(cj.irregular_tokens(self.verb["lemma"], self.verb.get("v2"), self.verb.get("v3")))

    def add_selected(self) -> None:
        self.add_cell(self.person_i)

    def add_cell(self, i: int) -> None:
        if self.verb is None:
            return
        self.person_i = i
        pk = cj.PERSON_KEYS[i]
        text = self._conj(pk)
        ok = verbs.add_to_card(self.ctx.progress, getattr(self.ctx, "vocab", None), self.verb,
                               self.tense, pk, self.mode, text)
        if ok:
            msg, col = _t("«{0}» — на складе карточек.").format(text), th.GREEN
        else:
            msg, col = _t("«{0}» сохранено; на склад попадёт, когда слово будет в словаре.").format(text), th.AMBER
        self.status.configure(text=msg, fg=col)
        try:
            self.ctx.status(msg, col)
            self.ctx.changed()
        except Exception:  # noqa: BLE001
            pass
