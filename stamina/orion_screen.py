"""Экран «ОРИОН» — бортовой разум: чат с агентом и заселение агентов на борт.

Две подвкладки:

- **ЧАТ** — разговор с активным пассажиром (агентом). Пилот пишет или говорит
  (микрофон), Орион отвечает письменно и вслух. Если поручение требует изменений,
  Орион просит разрешение — корабль показывает кнопку «ВЫПОЛНИТЬ».
- **АГЕНТЫ** — заселение: имя, права (выдаются на входе), голос, модель, заметка
  и **документ манер** — поведение агента пилот пишет сам на борту.

Права и манеры — разное: права получают **на входе** (уровень доступа; права Командира —
только по коду владельца корабля, `stamina/owner_key.py`), а манеры пилот правит на борту.

Данные и вызов агента — `stamina/orion.py`; голос — `stamina/voice/`.
"""

from __future__ import annotations

from stamina.i18n import t as _t

import queue
import re
import threading
import time
import tkinter as tk
from tkinter import messagebox

from stamina import __version__, nav, orion, owner_key, pilot_pin, pilots, theme
from stamina.adapt import make_vscroll
from stamina.hud import HudButton, HudPanel
from stamina.pilot_screens import Modal, PinPad
from stamina.theme import (AMBER, BG, BG2, CYAN, GREEN, LINE, MUTED, PANEL, RED, TEXT,
                           blend, px)
from stamina.voice import stt, tts
from stamina.voice.mic import MicControl


def _label(master, text="", *, fg=TEXT, size=10, bold=False, bg=PANEL, **kw):
    return tk.Label(master, text=text, fg=fg, bg=bg, font=theme.font(size, bold), **kw)


class _OwnerCodeDialog(Modal):
    """Выдача прав Командира по коду владельца корабля.

    result = True — код верный; если кода ещё не было, пилот задаёт его здесь
    (двумя вводами) и становится владельцем.
    """

    def __init__(self, master, name: str = "") -> None:
        super().__init__(master, _t("КОД ВЛАДЕЛЬЦА"), AMBER)
        self.setup = not owner_key.is_set()      # кода нет — задаём впервые
        self.stage = 1
        self.first = ""
        self.who = name

        _label(self.body, _t("ВЫДАТЬ ПРАВА КОМАНДИРА"), fg=AMBER, size=12, bold=True).pack(anchor="w")
        self.hint = _label(self.body, self._hint_text(), fg=MUTED, size=9, bold=True,
                           anchor="w", justify="left", wraplength=px(380))
        self.hint.pack(fill=tk.X, pady=(px(4), 0))
        self.pad = PinPad(self.body, self.submit)
        self.pad.pack(pady=px(8))
        self.msg = _label(self.body, "", fg=RED, size=9, bold=True, anchor="w", justify="left",
                          wraplength=px(380))
        self.msg.pack(fill=tk.X)
        row = tk.Frame(self.body, bg=PANEL)
        row.pack(fill=tk.X, pady=(px(8), 0))
        HudButton(row, _t("ВЫДАТЬ"), self.submit, color=AMBER, height=38).pack(side=tk.LEFT)
        HudButton(row, _t("ОТМЕНА"), self.cancel, height=38).pack(side=tk.LEFT, padx=px(6))
        self.bind("<Key>", lambda e: self.pad.key(e))

    def _hint_text(self) -> str:
        if self.setup:
            return _t("Кода владельца ещё нет: задайте его — он останется у владельца корабля.")
        return _t("Введите код владельца, чтобы выдать агенту права Командира.")

    def submit(self) -> None:
        code = self.pad.code
        if not pilot_pin.valid_code(code):
            self.msg.configure(text=_t("Код — от 4 до 8 цифр"))
            self.pad.clear(RED)
            return
        if self.setup:
            if self.stage == 1:
                self.first, self.stage = code, 2
                self.hint.configure(text=_t("ПОВТОРИТЕ КОД"))
                self.msg.configure(text="")
                self.pad.clear()
                return
            if code != self.first:
                self.first, self.stage = "", 1
                self.hint.configure(text=self._hint_text())
                self.msg.configure(text=_t("Коды не совпали"))
                self.pad.clear(RED)
                return
            owner_key.set_code(code)
            self.result = True
            self.destroy()
            return
        ok, text = owner_key.verify(code)
        if ok:
            self.result = True
            self.destroy()
            return
        self.msg.configure(text=text)
        self.pad.clear(RED)


class _GitHubAccessDialog(Modal):
    """Проверка GitHub-доступа для прав Командира.

    Агент спрашивает у локального агента (OpenCode CLI), есть ли доступ к
    аккаунту разработчика на GitHub. Если да — проверяем токен через API.
    """

    def __init__(self, master) -> None:
        super().__init__(master, tr_("ДОСТУП К GITHUB"), GREEN)
        L(self.body, tr_("Есть ли у тебя доступ к аккаунту разработчика на GitHub?\n"
                        "Можешь ли ты отправлять обновления и изменять состояние проекта?"),
          fg=MUTED, size=10).pack(anchor="w", pady=(px(4), px(8)))
        self.token_entry = tk.Entry(self.body, bg=BG2, fg=TEXT, insertbackground=CYAN,
                                    relief=tk.FLAT, font=theme.font(10),
                                    highlightthickness=1, highlightbackground=LINE,
                                    highlightcolor=CYAN, show="*")
        self.token_entry.pack(fill=tk.X, ipady=px(4))
        L(self.body, tr_("Токен GitHub (ghp_... или github_pat_...)"),
          fg=MUTED, size=8).pack(anchor="w", pady=(px(4), px(8)))
        self.msg = L(self.body, "", fg=RED, size=9, bold=True)
        self.msg.pack(anchor="w")
        btns = tk.Frame(self.body, bg=PANEL)
        btns.pack(fill=tk.X, pady=(px(8), 0))
        HudButton(btns, tr_("ПРОВЕРИТЬ"), self.check, color=GREEN, height=36,
                  font_size=10).pack(side=tk.LEFT)
        HudButton(btns, tr_("ПРОПУСТИТЬ"), self.skip, height=36, font_size=9).pack(side=tk.LEFT, padx=px(6))
        self.result = False

    def check(self) -> None:
        from stamina import orion
        token = self.token_entry.get().strip()
        if not token:
            self.msg.configure(text=tr_("Введите токен GitHub"))
            return
        self.msg.configure(text=tr_("Проверяю токен…"), fg=AMBER)
        self.update_idletasks()
        ok, err = orion.check_github_access(token)
        if ok:
            self.result = True
            self.destroy()
        else:
            self.msg.configure(text=tr_("Ошибка: {0}").format(err), fg=RED)

    def skip(self) -> None:
        self.result = False
        self.destroy()


class OrionScreen(tk.Frame):
    """Чат с бортовым разумом и интерфейс заселения агентов."""

    TABS = (("chat", "ЧАТ"), ("agents", "АГЕНТЫ"))

    def __init__(self, master, app) -> None:
        super().__init__(master, bg=BG)
        self.app = app
        self.tabs: dict[str, tuple[tk.Frame, HudButton]] = {}
        self.tab_btns: dict[str, HudButton] = {}
        self.current_tab = "chat"

        self._queue: queue.Queue = queue.Queue()
        self._busy = False
        self._answer_voice = True          # читать ответы вслух
        self._pending: tuple[dict, str] | None = None   # поручение для второго прохода
        self._pending_task = ""            # задание, ждущее подтверждения записи
        self._await_task = False           # ждём, что именно записать
        self._draft_id = orion.DEFAULT_AGENT["id"]      # карточка, которую правим
        self._is_new = False               # True — заселяем нового (права выбираются здесь)
        self._access = "crew"
        self._voice_mode = "ship"
        self._enabled = True
        self.board_visible = False         # доска чата скрыта, разговор идёт как контекст
        self._master_mode = False          # режим активного ока (мастер)
        self._last_mouse_pos = None
        self._last_hint_time = 0

        self._build()
        self.show_tab("chat")
        self.refresh()
        self._pump()

    # -- каркас ------------------------------------------------------------
    def _build(self) -> None:
        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(14), pady=(px(8), px(2)))
        _label(top, _t("ОРИОН — БОРТОВОЙ РАЗУМ"), size=16, bold=True, bg=BG).pack(side=tk.LEFT)
        self.info = _label(top, "", fg=MUTED, size=9, bg=BG)
        self.info.pack(side=tk.LEFT, padx=(px(10), px(6)))
        HudButton(top, "?", lambda: self.app.open_help(), height=32, font_size=10,
                  width=32, color=AMBER).pack(side=tk.RIGHT)

        tabs_row = tk.Frame(self, bg=BG)
        tabs_row.pack(fill=tk.X, padx=px(14), pady=(px(2), px(4)))
        for key, title in self.TABS:
            b = HudButton(tabs_row, _t(title), lambda k=key: self.show_tab(k), height=30, font_size=10)
            b.pack(side=tk.LEFT, padx=(0, px(6)))
            self.tab_btns[key] = b

        holder = tk.Frame(self, bg=BG)
        holder.pack(fill=tk.BOTH, expand=True, padx=px(14), pady=(0, px(10)))
        holder.grid_rowconfigure(0, weight=1)
        holder.grid_columnconfigure(0, weight=1)
        for key, _title in self.TABS:
            page = tk.Frame(holder, bg=BG)
            page.grid(row=0, column=0, sticky="nsew")
            self.tabs[key] = (page, self.tab_btns[key])
        self._build_chat(self.tabs["chat"][0])
        self._build_agents(self.tabs["agents"][0])

    # -- вкладка ЧАТ -------------------------------------------------------
    def _build_chat(self, page: tk.Frame) -> None:
        bar = tk.Frame(page, bg=BG)
        bar.pack(fill=tk.X, pady=(0, px(4)))
        self.who = _label(bar, "", fg=CYAN, size=10, bold=True, bg=BG)
        self.who.pack(side=tk.LEFT)
        HudButton(bar, _t("СМЕНИТЬ"), self._cycle_agent, height=30, font_size=9,
                  color=CYAN).pack(side=tk.RIGHT, padx=(px(4), 0))
        self.voice_btn = HudButton(bar, _t("ОЗВУЧКА: ВКЛ"), self._toggle_voice, height=30,
                                   font_size=9, color=GREEN)
        self.voice_btn.pack(side=tk.RIGHT, padx=(px(4), 0))
        self.board_btn = HudButton(bar, _t("ДОСКА: СКРЫТА"), self._toggle_board, height=30,
                                   font_size=9, color=AMBER)
        self.board_btn.pack(side=tk.RIGHT, padx=(px(4), 0))
        HudButton(bar, _t("ОЧИСТИТЬ"), self._clear, height=30, font_size=9,
                  color=AMBER).pack(side=tk.RIGHT, padx=(px(4), 0))
        self.mic_indicator = _label(bar, "", fg=MUTED, size=10, bold=True, bg=BG)
        self.mic_indicator.pack(side=tk.RIGHT, padx=(px(6), 0))
        HudButton(bar, _t("ЧИТАТЬ КНИГУ"), self._read_book, height=30, font_size=9,
                  color=GREEN).pack(side=tk.RIGHT, padx=(px(4), 0))

        # Доска — вся переписка. По умолчанию скрыта: Орион ведёт запись как контекст
        # и открывает доску сам, когда пилот диктует задание в документ.
        self.board = HudPanel(page, title=_t("ДОСКА ЧАТА — ОРИОН И ПИЛОТ"))
        body = tk.Frame(self.board.body, bg=PANEL)
        body.pack(fill=tk.BOTH, expand=True)
        sb = make_vscroll(body)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text = tk.Text(body, wrap=tk.WORD, bg=PANEL, fg=TEXT, relief=tk.FLAT,
                            font=theme.font(10), padx=px(8), pady=px(6), cursor="arrow",
                            height=6, state=tk.DISABLED, highlightthickness=0, bd=0,
                            yscrollcommand=sb.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.configure(command=self.text.yview)
        for w in (self.text, body):
            w.bind("<MouseWheel>", self._wheel)
            w.bind("<Button-4>", lambda _e: self.text.yview_scroll(-3, "units"))
            w.bind("<Button-5>", lambda _e: self.text.yview_scroll(3, "units"))
        # Копирование текста из чата — правый клик или Ctrl+C
        self.text.bind("<Button-3>", self._copy_text)
        self.text.bind("<Control-c>", self._copy_text)
        # Разрешаем выделение текста
        self.text.configure(state=tk.NORMAL)
        self.text.bind("<Button-1>", self._select_text)
        self.text.bind("<B1-Motion>", self._select_text)
        self.text.configure(state=tk.DISABLED)

        # Живая линия — вместо доски: последняя реплика пилота и ответ Ориона
        self.strip = HudPanel(page, title=_t("ЖИВАЯ ЛИНИЯ"), accent=GREEN)
        sbody = tk.Frame(self.strip.body, bg=PANEL)
        sbody.pack(fill=tk.BOTH, expand=True)
        self.strip_pilot = _label(sbody, "", fg=CYAN, size=11, bold=True, bg=PANEL, anchor="w",
                                  justify="left", wraplength=px(880))
        self.strip_pilot.pack(fill=tk.X, pady=(px(6), px(4)))
        self.strip_orion = _label(sbody, "", fg=TEXT, size=11, bg=PANEL, anchor="w",
                                  justify="left", wraplength=px(880))
        self.strip_orion.pack(fill=tk.X)
        _label(sbody, _t("Доска скрыта: разговор идёт как контекст. Скажите «запиши задание» — "
                         "или нажмите «ДОСКА»."), fg=MUTED, size=8, bg=PANEL, anchor="w",
               justify="left", wraplength=px(880)).pack(fill=tk.X, pady=(px(10), 0))

        bottom = tk.Frame(page, bg=BG)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, pady=(px(6), 0))
        self.bottom = bottom

        self.hint = _label(bottom, "", fg=MUTED, size=9, bg=BG, anchor="w", justify="left",
                           wraplength=px(900))
        self.hint.pack(fill=tk.X)

        # «Записать задание в документ?» — спрашивает корабль голосом Ориона
        self.ask_row = tk.Frame(bottom, bg=BG)
        self.ask_label = _label(self.ask_row, "", fg=GREEN, size=10, bold=True, bg=BG,
                                anchor="w", justify="left", wraplength=px(780))
        self.ask_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        HudButton(self.ask_row, _t("ДА, ЗАПИСАТЬ"), lambda: self._confirm_task(True), height=34,
                  font_size=10, color=GREEN).pack(side=tk.RIGHT, padx=(px(6), 0))
        HudButton(self.ask_row, _t("НЕТ"), lambda: self._confirm_task(False), height=34,
                  font_size=9, color=MUTED).pack(side=tk.RIGHT, padx=(px(6), 0))

        # «Орион просит разрешение» — появляется только когда нужно добро командира
        self.perm_row = tk.Frame(bottom, bg=BG)
        self.perm_label = _label(self.perm_row, "", fg=AMBER, size=10, bold=True, bg=BG,
                                 anchor="w", justify="left", wraplength=px(820))
        self.perm_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        HudButton(self.perm_row, _t("✔ ВЫПОЛНИТЬ"), self._approve, height=34, font_size=10,
                  color=GREEN).pack(side=tk.RIGHT, padx=(px(6), 0))
        HudButton(self.perm_row, _t("ОТМЕНА"), self._deny, height=34, font_size=9,
                  color=MUTED).pack(side=tk.RIGHT, padx=(px(6), 0))

        row = tk.Frame(bottom, bg=BG)
        row.pack(fill=tk.X, pady=(px(4), 0))
        self.entry = tk.Entry(row, bg=BG2, fg=TEXT, insertbackground=CYAN, relief=tk.FLAT,
                              font=theme.font(11), highlightthickness=1, highlightbackground=LINE,
                              highlightcolor=CYAN, selectbackground=CYAN, selectforeground=BG)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=px(6), padx=(0, px(8)))
        self.entry.bind("<Return>", lambda _e: (self._send(), "break")[1])
        self.entry.bind("<KP_Enter>", lambda _e: (self._send(), "break")[1])
        self.mic = MicControl(row, on_text=self._insert_text, on_status=self._mic_status,
                              label=_t("ГОЛОС"), height=36, font_size=11)
        self.mic.button.pack(side=tk.LEFT)
        self.send_btn = HudButton(row, _t("ОТПРАВИТЬ"), self._send, height=36, font_size=11)
        self.send_btn.pack(side=tk.LEFT, padx=(px(6), 0))

        self._apply_tags()
        self._set_board(False)

    def _wheel(self, e) -> str:
        self.text.yview_scroll(int(-e.delta / 120) * 3, "units")
        return "break"

    def _select_text(self, e) -> str:
        """Разрешить выделение текста в чате."""
        return None

    def _copy_text(self, _e) -> str:
        """Копировать выделенный текст из чата в буфер обмена."""
        try:
            selected = self.text.get(tk.SEL_FIRST, tk.SEL_LAST)
            if selected:
                self.clipboard_clear()
                self.clipboard_append(selected)
                self._hint(_t("Текст скопирован"), GREEN)
        except tk.TclError:
            pass
        return "break"

    def _apply_tags(self) -> None:
        self.text.tag_configure("pilot", foreground=CYAN, font=theme.font(10, True))
        self.text.tag_configure("orion", foreground=GREEN, font=theme.font(10, True))
        self.text.tag_configure("system", foreground=AMBER, font=theme.font(9, True))
        self.text.tag_configure("time", foreground=MUTED, font=theme.font(8))
        self.text.tag_configure("body", foreground=TEXT, font=theme.font(10))
        self.text.tag_configure("hint", foreground=MUTED, font=theme.font(10))
        self.text.tag_configure("separator", foreground=LINE, font=theme.font(8))

    # -- вкладка АГЕНТЫ ----------------------------------------------------
    def _build_agents(self, page: tk.Frame) -> None:
        left = tk.Frame(page, bg=BG)
        left.pack(side=tk.LEFT, fill=tk.Y)
        right = tk.Frame(page, bg=BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(px(10), 0))

        lp = HudPanel(left, title=_t("ПАССАЖИРЫ БОРТА"))
        lp.pack(fill=tk.BOTH, expand=True)
        lp.configure(width=px(260))
        self.crew_box = tk.Frame(lp.body, bg=PANEL)
        self.crew_box.pack(fill=tk.BOTH, expand=True)
        HudButton(lp.body, _t("＋ ЗАСЕЛИТЬ НОВОГО"), self._new_agent, height=32,
                  font_size=10, color=GREEN).pack(fill=tk.X, pady=(px(6), 0))

        rp = HudPanel(right, title=_t("КАРТОЧКА ПАССАЖИРА"))
        rp.pack(fill=tk.X)
        form = tk.Frame(rp.body, bg=PANEL)
        form.pack(fill=tk.BOTH, expand=True)

        self.name_var = tk.StringVar()
        self.model_var = tk.StringVar()
        self.note_var = tk.StringVar()
        for title, var, hint in ((_t("ИМЯ"), self.name_var, _t("Как звать агента (Орион, Пилот-2, Сова…)")),
                                 (_t("МОДЕЛЬ"), self.model_var, _t("Пусто — модель OpenCode по умолчанию")),
                                 (_t("ЗАМЕТКА"), self.note_var, _t("Для чего заселён"))):
            _label(form, title, fg=MUTED, size=9, bold=True).pack(anchor="w", pady=(px(6), 0))
            e = tk.Entry(form, textvariable=var, bg=BG2, fg=TEXT, insertbackground=CYAN,
                         relief=tk.FLAT, font=theme.font(10), highlightthickness=1,
                         highlightbackground=LINE, highlightcolor=CYAN)
            e.pack(fill=tk.X, ipady=px(4))
            _label(form, hint, fg=MUTED, size=8).pack(anchor="w")

        # Права выдаются НА ВХОДЕ — кнопками, а не перебором. Права Командира обычный
        # пилот «просто так» не получает: их выдаёт владелец корабля по своему коду.
        _label(form, _t("ПРАВА НА ВХОДЕ"), fg=MUTED, size=9, bold=True).pack(anchor="w", pady=(px(8), 0))
        self.access_row = tk.Frame(form, bg=PANEL)
        self.access_row.pack(anchor="w")
        self.access_btns: dict[str, HudButton] = {}
        for key, title in (("crew", "ЭКИПАЖ"), ("observer", "НАБЛЮДАТЕЛЬ"),
                           ("commander", "КОМАНДИР")):
            b = HudButton(self.access_row, _t(title), lambda k=key: self._pick_access(k),
                          height=32, font_size=9, color=CYAN)
            b.pack(side=tk.LEFT, padx=(0, px(6)))
            self.access_btns[key] = b
        self.access_hint = _label(form, "", fg=MUTED, size=8, anchor="w", justify="left",
                                  wraplength=px(620))
        self.access_hint.pack(fill=tk.X)

        _label(form, _t("ГОЛОС"), fg=MUTED, size=9, bold=True).pack(anchor="w", pady=(px(8), 0))
        self.voice_mode_btn = HudButton(form, "", self._cycle_voice, height=32, font_size=10,
                                        color=GREEN)
        self.voice_mode_btn.pack(anchor="w")
        self.voice_hint = _label(form, "", fg=MUTED, size=8, anchor="w", justify="left",
                                 wraplength=px(620))
        self.voice_hint.pack(fill=tk.X)

        self.enabled_btn = HudButton(form, "", self._toggle_enabled, height=32, font_size=10,
                                     color=GREEN)
        self.enabled_btn.pack(anchor="w", pady=(px(10), 0))

        btns = tk.Frame(form, bg=PANEL)
        btns.pack(fill=tk.X, pady=(px(10), 0))
        HudButton(btns, _t("СОХРАНИТЬ"), self._save_agent, height=34, font_size=10,
                  color=GREEN).pack(side=tk.LEFT)
        HudButton(btns, _t("СДЕЛАТЬ АКТИВНЫМ"), self._make_active, height=34, font_size=9,
                  color=CYAN).pack(side=tk.LEFT, padx=(px(6), 0))
        HudButton(btns, _t("УБРАТЬ С БОРТА"), self._remove_agent, height=34, font_size=9,
                  color=RED).pack(side=tk.LEFT, padx=(px(6), 0))

        # ПРИВЯЗКА К OPENCODY: код для заселения, токен, статус связи
        bp = HudPanel(form, title=_t("ПРИВЯЗКА К OPENCODY"), accent=GREEN)
        bp.pack(fill=tk.X, pady=(px(10), 0))
        bbody = tk.Frame(bp.body, bg=PANEL)
        bbody.pack(fill=tk.X)

        self.boarding_code = orion.make_boarding_code()
        code_row = tk.Frame(bbody, bg=PANEL)
        code_row.pack(fill=tk.X, pady=(px(6), 0))
        _label(code_row, _t("КОД ДЛЯ ЗАСЕЛЕНИЯ"), fg=MUTED, size=9, bold=True).pack(anchor="w")
        self.code_label = _label(code_row, self.boarding_code, fg=GREEN, size=16, bold=True, bg=PANEL)
        self.code_label.pack(anchor="w")
        _label(code_row, _t("Введите этот код в OpenCode CLI при заселении агента."),
               fg=MUTED, size=8, anchor="w", justify="left",
               wraplength=px(620)).pack(anchor="w")

        oc_row = tk.Frame(bbody, bg=PANEL)
        oc_row.pack(fill=tk.X, pady=(px(8), 0))
        _label(oc_row, _t("ТОКЕН OPENCODY"), fg=MUTED, size=9, bold=True).pack(anchor="w")
        self.token_entry = tk.Entry(oc_row, bg=BG2, fg=TEXT, insertbackground=CYAN,
                                    relief=tk.FLAT, font=theme.font(10),
                                    highlightthickness=1, highlightbackground=LINE,
                                    highlightcolor=CYAN, show="*")
        self.token_entry.pack(fill=tk.X, ipady=px(4))
        self.oc_status = _label(oc_row, "", fg=MUTED, size=8, anchor="w", justify="left",
                                wraplength=px(620))
        self.oc_status.pack(fill=tk.X)

        gh_row = tk.Frame(bbody, bg=PANEL)
        gh_row.pack(fill=tk.X, pady=(px(8), 0))
        _label(gh_row, _t("ТОКЕН GITHUB (ДЛЯ КОМАНДИРА)"), fg=MUTED, size=9, bold=True).pack(anchor="w")
        self.gh_entry = tk.Entry(gh_row, bg=BG2, fg=TEXT, insertbackground=CYAN,
                                 relief=tk.FLAT, font=theme.font(10),
                                 highlightthickness=1, highlightbackground=LINE,
                                 highlightcolor=CYAN, show="*")
        self.gh_entry.pack(fill=tk.X, ipady=px(4))
        self.gh_status = _label(gh_row, "", fg=MUTED, size=8, anchor="w", justify="left",
                                wraplength=px(620))
        self.gh_status.pack(fill=tk.X)

        bind_row = tk.Frame(bbody, bg=PANEL)
        bind_row.pack(fill=tk.X, pady=(px(8), 0))
        HudButton(bind_row, _t("ПРОВЕРИТЬ СВЯЗЬ"), self._check_binding, height=32,
                  font_size=10, color=GREEN).pack(side=tk.LEFT)
        HudButton(bind_row, _t("СОХРАНИТЬ ПРИВЯЗКУ"), self._save_binding, height=32,
                  font_size=9, color=CYAN).pack(side=tk.LEFT, padx=(px(6), 0))
        HudButton(bind_row, _t("ЗАБЫТЬ ПРИВЯЗКУ"), self._clear_binding, height=32,
                  font_size=9, color=RED).pack(side=tk.LEFT, padx=(px(6), 0))

        self.bind_status = _label(bbody, "", fg=MUTED, size=9, bold=True, anchor="w",
                                  justify="left", wraplength=px(620))
        self.bind_status.pack(fill=tk.X, pady=(px(6), px(8)))

        # ЭВОЛЮЦИЯ ХАРАКТЕРА — иллюзия развития ИИ
        ep = HudPanel(form, title=_t("ЭВОЛЮЦИЯ ХАРАКТЕРА"), accent=AMBER)
        ep.pack(fill=tk.X, pady=(px(10), 0))
        ebody = tk.Frame(ep.body, bg=PANEL)
        ebody.pack(fill=tk.X)
        self.evo_label = _label(ebody, "", fg=AMBER, size=10, bold=True, anchor="w",
                                justify="left", wraplength=px(620))
        self.evo_label.pack(fill=tk.X, pady=(px(6), 0))
        self.evo_hint = _label(ebody, "", fg=MUTED, size=8, anchor="w", justify="left",
                               wraplength=px(620))
        self.evo_hint.pack(fill=tk.X, pady=(px(4), px(6)))

        # МАНЕРЫ АГЕНТА — документ корабля: поведение агента пилот пишет сам
        mp = HudPanel(right, title=_t("МАНЕРЫ АГЕНТА"), accent=CYAN)
        mp.pack(fill=tk.BOTH, expand=True, pady=(px(8), 0))
        mbody = tk.Frame(mp.body, bg=PANEL)
        mbody.pack(fill=tk.BOTH, expand=True)
        msb = make_vscroll(mbody)
        msb.pack(side=tk.RIGHT, fill=tk.Y)
        self.char_text = tk.Text(mbody, wrap=tk.WORD, bg=BG2, fg=TEXT, relief=tk.FLAT,
                                 font=theme.font(10), padx=px(6), pady=px(4), height=6,
                                 insertbackground=CYAN, highlightthickness=1,
                                 highlightbackground=LINE, highlightcolor=CYAN,
                                 yscrollcommand=msb.set)
        self.char_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        msb.configure(command=self.char_text.yview)
        self.char_hint = _label(mp.body, "", fg=MUTED, size=8, anchor="w", justify="left",
                                wraplength=px(620))
        self.char_hint.pack(fill=tk.X, pady=(px(4), px(6)))
        HudButton(mp.body, _t("СОХРАНИТЬ МАНЕРЫ"), self._save_character, height=32,
                  font_size=10, color=CYAN).pack(anchor="w")

    # -- подвкладки --------------------------------------------------------
    def tab_keys(self) -> list[str]:
        return [k for k, _ in self.TABS]

    def show_tab(self, key: str) -> None:
        if key not in self.tabs:
            key = self.tabs and next(iter(self.tabs))
        self.current_tab = key
        page, btn = self.tabs[key]
        page.tkraise()
        for k, b in self.tab_btns.items():
            b.set_active(k == key)

    def page_help_key(self) -> str:
        return "orion." + getattr(self, "current_tab", "chat")

    def on_key(self, _e) -> None:
        """Клавиши раздела: поле ввода само принимает набор и Enter."""

    def focus_input(self) -> None:
        if str(self.entry.cget("state")) != tk.DISABLED:
            self.entry.focus_set()

    # -- данные ------------------------------------------------------------
    def _rec(self) -> dict:
        return orion.active()

    def refresh(self) -> None:
        """Перечитать реестр и историю (вызывается при входе в раздел)."""
        self._apply_tags()
        self._refresh_who()
        self._render_feed()
        self._refresh_crew()

    def _refresh_who(self) -> None:
        rec = self._rec()
        self.who.configure(text=_t("ПАССАЖИР: {0} · ДОСТУП: {1} · ГОЛОС: {2}").format(
            str(rec.get("name") or "—").upper(), self._access_label(rec.get("access", "crew")),
            self._voice_label(rec.get("voice", "ship"))))
        ok, exe = orion.available()
        total = len(orion.history(rec["id"])["messages"])
        self.info.configure(text=_t("Реплик: {0}").format(total) + ("" if ok else
                                                                    _t(" · нет OpenCode")))
        voice_ok = tts.available()
        self.voice_btn.set_enabled(voice_ok)
        self.voice_btn.set_text(_t("ОЗВУЧКА: ВКЛ") if (self._answer_voice and voice_ok)
                                else _t("ОЗВУЧКА: ВЫКЛ"))

    def _render_feed(self) -> None:
        rec = self._rec()
        msgs = orion.history(rec["id"])["messages"]
        ok, _exe = orion.available()
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        if not ok:
            self.text.insert(tk.END, _t("OpenCode не найден: Орион на связи не будет. "
                                        "Установите opencode и перезапустите корабль.") + "\n", "hint")
        if not msgs:
            self.text.insert(tk.END, _t("Канал свободен. Скажите Ориону первое слово — "
                                        "письменно 或 голосом.") + "\n", "hint")
        for m in msgs:
            when = time.strftime("%H:%M", time.localtime(float(m.get("ts", 0.0))))
            role = m.get("role", "orion")
            if role == "pilot":
                tag, name = "pilot", _t("ПИЛОТ")
                prefix = "▸ "
            elif role == "orion":
                tag, name = "orion", str(rec.get("name") or _t("ОРИОН")).upper()
                prefix = "◂ "
            else:
                tag, name = "system", _t("КОРАБЛЬ")
                prefix = ""
            if m.get("kind") == "task":
                name = "📌 " + name
            # Визуальное разделение реплик
            self.text.insert(tk.END, "─" * 40 + "\n", "separator")
            self.text.insert(tk.END, prefix + name, tag)
            self.text.insert(tk.END, f"  {when}\n", "time")
            self.text.insert(tk.END, f"{m.get('text', '')}\n", "body")
        self.text.configure(state=tk.DISABLED)
        self.text.see(tk.END)
        self._render_strip(msgs, rec)

    def _render_strip(self, msgs: list[dict], rec: dict) -> None:
        """Живая линия: последняя реплика пилота и последний ответ Ориона."""
        last_pilot = next((m for m in reversed(msgs) if m.get("role") == "pilot"), None)
        last_orion = next((m for m in reversed(msgs) if m.get("role") == "orion"), None)
        name = str(rec.get("name") or "ОРИОН").upper()
        self.strip_pilot.configure(text=(_t("ПИЛОТ: {0}").format(last_pilot["text"])
                                         if last_pilot else _t("ПИЛОТ: —")))
        self.strip_orion.configure(text=(f"{name}: {last_orion['text']}" if last_orion
                                         else _t("{0}: слушаю, пилот").format(name)))

    # -- доска: скрыта или открыта -----------------------------------------
    def _set_board(self, visible: bool) -> None:
        """Показать доску переписки или свернуть её в живую линию."""
        self.board_visible = visible
        if visible:
            self.strip.pack_forget()
            self.board.pack(fill=tk.BOTH, expand=True, before=self.bottom)
            self.board_btn.set_text(_t("ДОСКА: ОТКРЫТА"))
            self.board_btn.set_color(GREEN)
        else:
            self.board.pack_forget()
            self.strip.pack(fill=tk.BOTH, expand=True, before=self.bottom)
            self.board_btn.set_text(_t("ДОСКА: СКРЫТА"))
            self.board_btn.set_color(AMBER)

    def _toggle_board(self) -> None:
        self._set_board(not self.board_visible)

    def listen(self) -> None:
        """Слушать пилота (кнопка ОРИОН / Home): голос превращается в обращение."""
        self.show_tab("chat")
        if not self.mic.busy:
            self.mic.start()

    def _mic_status(self, text: str, color=MUTED) -> None:
        """Индикатор микрофона: показывает что микрофон работает."""
        self.mic_indicator.configure(text=("🎤 " + text) if text else "", fg=color)
        self._hint(text, color)

    # -- переводы подписей -------------------------------------------------
    def _access_label(self, access: str) -> str:
        if access == "commander":
            return _t("КОМАНДИР")
        if access == "observer":
            return _t("НАБЛЮДАТЕЛЬ")
        return _t("ЭКИПАЖ")

    def _access_hint(self, access: str) -> str:
        if access == "commander":
            return _t("Полные права: сначала доклад, изменения — после вашего разрешения.")
        if access == "observer":
            return _t("Только чтение: читает корабль и докладывает, менять не может.")
        return _t("Только беседа: ни файлов, ни команд, ни интернета.")

    def _voice_label(self, mode: str) -> str:
        if mode == "agent":
            return _t("САМ")
        if mode == "off":
            return _t("ВЫКЛ")
        return _t("КОРАБЛЬ")

    def _voice_hint(self, mode: str) -> str:
        if mode == "agent":
            return _t("Агент говорит сам (у него есть своя озвучка).")
        if mode == "off":
            return _t("Молча — только текст.")
        return _t("Корабль читает ответ агента вслух голосом Windows.")

    # -- чат ---------------------------------------------------------------
    def _hint(self, text: str, color=MUTED) -> None:
        self.hint.configure(text=text, fg=color)

    def _insert_text(self, text: str) -> None:
        """Текст из микрофона. Пока ждём подтверждения записи — «да»/«нет» без Enter."""
        if not text:
            return
        if self._await_task:
            self._take_task(text)
            return
        if self._pending_task:
            if orion.is_yes(text):
                self._confirm_task(True)
                return
            if orion.is_no(text):
                self._confirm_task(False)
                return
        # Режим мастера: пилот позвал Ориона-мастера
        if orion.detect_master_call(text):
            self._enter_master_mode()
            return
        tail = self.entry.get()
        self.entry.insert(tk.END, (" " if tail and not tail.endswith(" ") else "") + text)
        self.entry.focus_set()
        self.send_btn.set_enabled(True)

    def _send(self) -> None:
        rec = self._rec()
        text = " ".join(self.entry.get().split())
        if not text or self._busy:
            return
        self.entry.delete(0, tk.END)
        # короткий разговор о записи задания — «да»/«нет» или сам текст задания
        if self._await_task:
            self._take_task(text)
            return
        if self._pending_task and orion.is_yes(text):
            self._confirm_task(True)
            return
        if self._pending_task and orion.is_no(text):
            self._confirm_task(False)
            return
        ok, _exe = orion.available()
        if not ok:
            self._hint(_t("OpenCode не найден: установите opencode и перезапустите корабль."), RED)
            return
        orion.remember(rec["id"], "pilot", text)
        self._render_feed()
        found, task = orion.detect_task(text)
        if found:
            if task:
                self._ask_task(task)
            else:
                self._await_task = True
                self._hint(_t("Что записать, пилот? Скажите или напишите задание"), GREEN)
                if self._answer_voice and tts.available():
                    tts.speak(_t("Что записать, пилот?"))
                if not self.mic.busy:
                    self.mic.start()
            return
        self._run(rec, text, second=False)

    # -- задание в документ ------------------------------------------------
    def _take_task(self, text: str) -> None:
        """Пилот сказал, что именно записать (второй шаг после «запиши»)."""
        self._await_task = False
        task = " ".join(text.split())
        if not task:
            self._hint(_t("Задание не расслышал — повторите"), MUTED)
            return
        rec = self._rec()
        orion.remember(rec["id"], "pilot", task)
        self._render_feed()
        self._ask_task(task)

    def _ask_task(self, task: str) -> None:
        """Корабль спрашивает голосом Ориона: записать ли это задание в документ."""
        self._pending_task = task
        self.ask_label.configure(text=_t("Записать в документ заданий: «{0}»?").format(task[:200]))
        if not self.ask_row.winfo_manager():
            self.ask_row.pack(side=tk.TOP, fill=tk.X, pady=(px(4), 0), before=self.entry.master)
        self._hint(_t("Подтвердите: «да» голосом или кнопкой «ДА, ЗАПИСАТЬ»"), GREEN)
        if self._answer_voice and tts.available():
            tts.speak(_t("Вы хотите, чтобы я записал это в документ?"))
        if not self.mic.busy:
            self.mic.start()

    def _confirm_task(self, agree: bool) -> None:
        task, self._pending_task = self._pending_task, ""
        self._await_task = False
        if self.ask_row.winfo_manager():
            self.ask_row.pack_forget()
        rec = self._rec()
        if not task:
            return
        if not agree:
            orion.remember(rec["id"], "system", _t("Запись задания отменена"))
            self._render_feed()
            self._hint(_t("Задание не записано"), MUTED)
            return
        orion.add_task(task, author=str((self.app.pilot or {}).get("callsign") or ""),
                       agent=rec["id"])
        orion.remember(rec["id"], "system", _t("📌 ЗАДАНИЕ В ДОКУМЕНТ: {0}").format(task),
                       kind="task")
        self._set_board(True)          # доска чата открывается — пилот видит запись
        self._render_feed()
        self.ask_label.configure(text="")
        self._hint(_t("Задание записано в документ борта"), GREEN)
        if self._answer_voice and tts.available():
            tts.speak(_t("Записал в документ заданий"))
        if not self._busy:
            self._run(rec, task, second=False)

    def _run(self, rec: dict, text: str, *, second: bool) -> None:
        first, follow = orion.profiles(rec)
        profile = (follow or first) if second else first
        self._busy = True
        self.send_btn.set_enabled(False)
        self._pending = (rec, text)
        if second:
            self._hide_permission()
        self._hint(_t("Орион думает…"), AMBER)
        ctx = self._context()
        # При втором проходе — передаём разрешение в промпт
        if second:
            text = _t("РАЗРЕШЕНИЕ: Командир разрешил изменения. Выполни работу целиком.") + "\n\n" + text
        session = orion.last_session(rec["id"])
        threading.Thread(target=self._worker,
                         args=(rec, text, profile, session, ctx, second), daemon=True).start()

    def _worker(self, rec: dict, text: str, profile: str, session: str, ctx: str,
                second: bool) -> None:
        try:
            res = orion.run_profile(rec, text, profile=profile, context=ctx, session=session)
        except Exception as exc:  # noqa: BLE001
            res = orion.Result(error="spawn", detail=str(exc), profile=profile)
        self._queue.put(("answer", res, rec, second))

    def _context(self) -> str:
        """Отметка корабля для агента: где пилот и что было открыто до Ориона."""
        app = self.app
        cur = app.current or ""
        zone = nav.zone_of(cur)
        was = getattr(app, "_prev_screen", None)
        was_zone = nav.zone_of(was) if was else None
        was_title = ""
        if was and was != "orion":
            was_title = _t(nav.ZONE_TITLES.get(was_zone, "") or nav.EXTRA_TITLES.get(was, was.upper()))
        scr = app.screens.get(cur)
        sub = ""
        if scr is not None and hasattr(scr, "current_tab"):
            titles = dict(getattr(scr, "TABS", ()))
            sub = _t(titles.get(scr.current_tab, str(scr.current_tab)))
        rec = self._rec()
        return orion.context_line(zone=self._zone_title(cur), subtab=sub,
                                  pilot=str((app.pilot or {}).get("callsign") or ""),
                                  access=self._access_label(rec.get("access", "crew")),
                                  version=__version__, geometry=self._geometry(),
                                  was=was_title)

    def _zone_title(self, screen: str) -> str:
        zone = nav.zone_of(screen)
        if zone:
            return _t(nav.ZONE_TITLES.get(zone, ""))
        return _t(nav.EXTRA_TITLES.get(screen, screen.upper())) if screen else ""

    def _geometry(self) -> str:
        try:
            return f"{self.app.winfo_width()}x{self.app.winfo_height()}"
        except tk.TclError:
            return ""

    def _toggle_voice(self) -> None:
        self._answer_voice = not self._answer_voice
        if not self._answer_voice:
            tts.stop()
        self._refresh_who()

    def _clear(self) -> None:
        rec = self._rec()
        if not messagebox.askyesno(_t("ОЧИСТИТЬ КАНАЛ"),
                                   _t("Стереть переписку с {0}? Прежний разговор агент забудет.")
                                   .format(rec.get("name") or "—")):
            return
        tts.stop()
        orion.clear_history(rec["id"])
        self._hide_permission()
        self._hint(_t("Канал очищен — разговор начинается заново"), MUTED)
        self.refresh()

    def _cycle_agent(self) -> None:
        reg = orion.registry()
        ids = [a["id"] for a in reg["agents"]]
        if len(ids) < 2:
            self.show_tab("agents")
            return
        i = ids.index(reg["active"]) if reg["active"] in ids else -1
        orion.set_active(ids[(i + 1) % len(ids)])
        tts.stop()
        self._hide_permission()
        self.refresh()
        self._hint(_t("Теперь на связи: {0}").format(self._rec().get("name") or ""), CYAN)

    def _speak(self, res) -> None:
        if not self._answer_voice or not tts.available():
            return
        rec = self._rec()
        if rec.get("voice") == "off":
            return
        if getattr(res, "spoke", False):     # агент озвучил себя сам — не повторяем
            return
        tts.speak(res.reply)

    def _on_answer(self, res, rec: dict, second: bool) -> None:
        self._busy = False
        self.send_btn.set_enabled(True)
        if res.error:
            note = self._error_text(res)
            orion.remember(rec["id"], "system", note)
            self._render_feed()
            self._hint(note, RED)
            return
        orion.remember(rec["id"], "orion", res.reply, session=res.session)
        self._render_feed()
        # Разбор служебных команд радио и книг
        radio_cmd = orion.parse_radio_command(res.reply)
        if radio_cmd:
            cmd, arg = radio_cmd
            ok, err = orion.execute_radio_command(cmd, arg)
            if ok:
                self._hint(_t("Радио: {0} выполнено").format(cmd), GREEN)
            else:
                self._hint(_t("Радио: ошибка — {0}").format(err), RED)
        book_cmd = orion.parse_book_command(res.reply)
        if book_cmd:
            if book_cmd.lower() == "read":
                self._read_book()
            else:
                books = orion.library_books()
                found = next((b for b in books if book_cmd.lower() in b.get("title", "").lower()), None)
                if found:
                    chunks = orion.book_text_for_reading(found["id"])
                    if chunks:
                        from stamina.voice import tts
                        if tts.available():
                            tts.speak(_t("Читаю: {0}").format(found["title"]))
                        self._hint(_t("Читаю: {0}").format(found["title"]), GREEN)
                    else:
                        self._hint(_t("Книга пуста"), MUTED)
                else:
                    self._hint(_t("Книга не найдена: {0}").format(book_cmd), RED)
        if res.needs_permission and not second:
            self._show_permission(res.request or _t("Нужно ваше разрешение на изменения"))
            self._hint(_t("Орион просит разрешение: нажмите «ВЫПОЛНИТЬ» — он сделает работу"),
                       AMBER)
        else:
            self._hide_permission()
            self._hint(_t("Ответ получен ({0})").format(_t("действия выполнены") if second
                                                        else _t("доклад")), GREEN)
        self._speak(res)

    def _error_text(self, res) -> str:
        detail = f": {res.detail}" if res.detail else ""
        if res.error == "no_cli":
            return _t("OpenCode не найден: установите opencode и перезапустите корабль.")
        if res.error == "timeout":
            return _t("Орион не ответил вовремя — попробуйте короче или повторите.")
        if res.error == "spawn":
            return _t("Сбой запуска агента") + detail
        if res.error == "empty":
            return _t("Пустое сообщение.")
        return _t("Сбой связи с Орионом") + detail

    def _show_permission(self, note: str) -> None:
        self.perm_label.configure(text=_t("Орион просит разрешение: {0}").format(note))
        if not self.perm_row.winfo_manager():
            self.perm_row.pack(side=tk.TOP, fill=tk.X, pady=(px(4), 0), before=self.entry.master)

    def _hide_permission(self) -> None:
        if self.perm_row.winfo_manager():
            self.perm_row.pack_forget()

    def _approve(self) -> None:
        """Командир разрешил — второй проход: Орион делает работу целиком."""
        if self._pending is None or self._busy:
            return
        rec, text = self._pending
        orion.remember(rec["id"], "system", _t("Командир разрешил действия"))
        self._render_feed()
        self._run(rec, text, second=True)

    def _deny(self) -> None:
        self._hide_permission()
        rec = self._rec()
        orion.remember(rec["id"], "system", _t("Командир отменил действия"))
        self._render_feed()
        self._hint(_t("Орион остаётся в режиме доклада"), MUTED)
        self._pending = None

    # -- заселение ---------------------------------------------------------
    def _refresh_crew(self) -> None:
        for w in self.crew_box.winfo_children():
            w.destroy()
        reg = orion.registry()
        for a in reg["agents"]:
            active = a["id"] == reg["active"]
            color = CYAN if active else (GREEN if a.get("enabled", True) else MUTED)
            b = HudButton(self.crew_box, ("▸ " if active else "") + str(a.get("name") or a["id"]),
                          lambda k=a["id"]: self._edit_agent(k), height=32, font_size=9,
                          color=color)
            b.pack(fill=tk.X, pady=px(2))
            _label(self.crew_box, self._access_label(a.get("access", "crew")), fg=MUTED,
                   size=8).pack(anchor="w", pady=(0, px(2)))
        if self._draft_id not in {a["id"] for a in reg["agents"]}:
            self._draft_id = reg["agents"][0]["id"]
        self._fill_form(orion.get(self._draft_id) or dict(orion.DEFAULT_AGENT))

    def _edit_agent(self, agent_id: str) -> None:
        self._draft_id = agent_id
        rec = orion.get(agent_id)
        if rec is not None:
            self._fill_form(rec, is_new=False)
        self.show_tab("agents")

    def _new_agent(self) -> None:
        self._draft_id = ""
        self._fill_form({"id": "", "name": "", "access": "crew", "voice": "ship",
                         "model": "", "note": "", "enabled": True}, is_new=True)

    def _fill_form(self, rec: dict, *, is_new: bool | None = None) -> None:
        rid = str(rec.get("id") or "")
        self._is_new = (orion.get(rid) is None) if is_new is None else is_new
        self._access = str(rec.get("access") or "crew")
        self._voice_mode = str(rec.get("voice") or "ship")
        self._enabled = bool(rec.get("enabled", True))
        self.name_var.set(str(rec.get("name") or ""))
        self.model_var.set(str(rec.get("model") or ""))
        self.note_var.set(str(rec.get("note") or ""))
        self._load_character(rid)
        self._paint_form()
        self._refresh_binding()
        self._refresh_evolution()

    def _load_character(self, agent_id: str) -> None:
        """Показать документ манер: у заселённого — его документ, у нового — заготовку."""
        on_board = orion.get(agent_id) is not None
        text = orion.read_character(agent_id) if on_board else ""
        if not text.strip():
            text = orion.default_character(self.name_var.get())
        self.char_text.delete("1.0", tk.END)
        self.char_text.insert("1.0", text)
        target = agent_id if on_board else (self.name_var.get().strip() or "agent")
        self.char_hint.configure(
            text=_t("Документ корабля: {0}").format(str(orion.character_path(target))))

    def _paint_form(self) -> None:
        for key, btn in self.access_btns.items():
            chosen = key == self._access
            btn.set_active(chosen)
            btn.set_color(GREEN if chosen else (AMBER if key == "commander" else CYAN))
            btn.set_enabled(self._is_new)          # на борту права не меняют — только при входе
        if not self._is_new:
            hint = _t("Права выдаёт владелец корабля на входе. Здесь их не меняют — "
                      "только новое заселение.")
        elif self._access == "commander":
            hint = _t("🔒 Права Командира — только по коду владельца")
        else:
            hint = self._access_hint(self._access)
        self.access_hint.configure(text=hint)
        self.voice_mode_btn.set_text(_t("ГОЛОС: {0}").format(self._voice_label(self._voice_mode)))
        self.voice_hint.configure(text=self._voice_hint(self._voice_mode))
        self.enabled_btn.set_text(_t("НА БОРТУ: {0}").format(_t("ДА") if self._enabled
                                                             else _t("НЕТ")))
        self.enabled_btn.set_color(GREEN if self._enabled else MUTED)

    def _pick_access(self, access: str) -> None:
        """Права выбираются на входе. Командир — по коду владельца + GitHub-доступ."""
        if not self._is_new:
            self._hint(_t("Права выдаёт владелец корабля на входе. Здесь их не меняют — "
                          "только новое заселение."), AMBER)
            self.show_tab("agents")
            return
        access = access if access in orion.ACCESSES else "crew"
        if access == "commander":
            # Шаг 1: код владельца корабля
            if not _OwnerCodeDialog(self, self.name_var.get()).run():
                self._hint(_t("Права Командира не выданы"), MUTED)
                self.show_tab("agents")
                return
            # Шаг 2: проверка GitHub-доступа (спрашиваем у локального агента)
            if not _GitHubAccessDialog(self).run():
                self._hint(_t("Права Командира не выданы: нужен доступ к GitHub"), MUTED)
                self.show_tab("agents")
                return
            self._hint(_t("Права Командира выданы"), GREEN)
        self._access = access
        self._paint_form()

    def _save_character(self) -> None:
        if orion.get(self._draft_id) is None:
            self._hint(_t("Сначала заселите агента — документ манер создаётся при входе на борт"),
                       AMBER)
            self.show_tab("agents")
            return
        orion.save_character(self._draft_id, self.char_text.get("1.0", tk.END))
        self.char_hint.configure(
            text=_t("Документ корабля: {0}").format(str(orion.character_path(self._draft_id))))
        self._hint(_t("Манеры агента сохранены"), GREEN)
        self.show_tab("agents")

    def _cycle_voice(self) -> None:
        order = list(orion.VOICE_MODES)
        i = order.index(self._voice_mode) if self._voice_mode in order else 0
        self._voice_mode = order[(i + 1) % len(order)]
        self._paint_form()

    def _toggle_enabled(self) -> None:
        self._enabled = not self._enabled
        self._paint_form()

    def _save_agent(self) -> None:
        name = " ".join(self.name_var.get().split())
        if not name:
            self._hint(_t("Дайте агенту имя — иначе его не позвать"), AMBER)
            self.show_tab("agents")
            return
        saved = orion.upsert({
            "id": self._draft_id if orion.get(self._draft_id) else "",
            "name": name,
            "access": self._access,
            "voice": self._voice_mode,
            "model": self.model_var.get(),
            "note": self.note_var.get(),
            "enabled": self._enabled,
        })
        orion.save_character(saved["id"], self.char_text.get("1.0", tk.END))
        self._draft_id = saved["id"]
        self._is_new = False
        self.refresh()
        self._hint(_t("Пассажир заселён на борт: {0}").format(saved["name"]), GREEN)

    def _make_active(self) -> None:
        if not self._draft_id:
            return
        if orion.set_active(self._draft_id):
            self.refresh()
            self._hint(_t("На связи: {0}").format(self._rec().get("name") or ""), CYAN)

    def _remove_agent(self) -> None:
        rec = orion.get(self._draft_id)
        if rec is None:
            return
        if not messagebox.askyesno(_t("УБРАТЬ С БОРТА"),
                                   _t("Убрать пассажира «{0}» с корабля?")
                                   .format(rec.get("name") or "—")):
            return
        if not orion.remove(self._draft_id):
            self._hint(_t("Бортовой разум Орион остаётся на борту — его можно только отключить"),
                       AMBER)
            return
        orion.clear_binding(self._draft_id)
        self._draft_id = orion.DEFAULT_AGENT["id"]
        self.refresh()
        self._hint(_t("Пассажир убран с борта"), MUTED)

    # -- привязка к OpenCode ---------------------------------------------------
    def _refresh_binding(self) -> None:
        """Показать статус привязки агента к OpenCode."""
        rec = orion.get(self._draft_id) if self._draft_id else None
        if rec is None:
            self.bind_status.configure(text=_t("Сначала заселите агента — привязка создаётся при входе"),
                                       fg=MUTED)
            self.oc_status.configure(text="")
            self.gh_status.configure(text="")
            return
        status = orion.binding_status(rec["id"])
        if status["access_ok"]:
            self.bind_status.configure(text=_t("✔ Привязка активна — агент готов к работе"), fg=GREEN)
        elif status["linked"]:
            self.bind_status.configure(text=_t("◐ Привязка неполная — проверьте токены"), fg=AMBER)
        else:
            self.bind_status.configure(text=_t("✖ Привязка не настроена"), fg=RED)
        # OpenCode
        if status["opencode"]:
            self.oc_status.configure(text=_t("✔ OpenCode токен сохранён"), fg=GREEN)
        else:
            self.oc_status.configure(text=_t("Введите токен OpenCode CLI"), fg=MUTED)
        # GitHub (только для Командира)
        if self._access == "commander":
            if status["github"]:
                self.gh_status.configure(text=_t("✔ GitHub токен сохранён"), fg=GREEN)
            else:
                self.gh_status.configure(text=_t("Для Командира нужен GitHub-токен"), fg=AMBER)
        else:
            self.gh_status.configure(text="")
            self.gh_entry.configure(state=tk.DISABLED)
            return
        self.gh_entry.configure(state=tk.NORMAL)

    def _check_binding(self) -> None:
        """Проверить токены OpenCode и GitHub (для Командира)."""
        rec = orion.get(self._draft_id) if self._draft_id else None
        if rec is None:
            self._hint(_t("Сначала заселите агента"), AMBER)
            self.show_tab("agents")
            return
        token = self.token_entry.get().strip()
        if not token:
            self._hint(_t("Введите токен OpenCode CLI"), AMBER)
            self.show_tab("agents")
            return
        self.bind_status.configure(text=_t("Проверяю токен OpenCode…"), fg=AMBER)
        self.update_idletasks()
        ok, err = orion.check_opencode_token(token)
        if not ok:
            self.bind_status.configure(text=_t("✖ OpenCode: {0}").format(
                {"no_cli": _t("OpenCode CLI не найден"),
                 "timeout": _t("Таймаут — попробуйте ещё раз"),
                 "spawn": _t("Ошибка запуска")}.get(err, err)), fg=RED)
            return
        self.oc_status.configure(text=_t("✔ OpenCode токен работает"), fg=GREEN)
        # Для Командира проверяем GitHub
        if self._access == "commander":
            gh_token = self.gh_entry.get().strip()
            if not gh_token:
                self.gh_status.configure(text=_t("Для Командира нужен GitHub-токен"), fg=AMBER)
                return
            self.bind_status.configure(text=_t("Проверяю GitHub-токен…"), fg=AMBER)
            self.update_idletasks()
            ok_gh, err_gh = orion.check_github_access(gh_token)
            if not ok_gh:
                self.gh_status.configure(text=_t("✖ GitHub: {0}").format(
                    "no_push" if err_gh == "no_push" else err_gh), fg=RED)
                return
            self.gh_status.configure(text=_t("✔ GitHub-токен работает"), fg=GREEN)
        self.bind_status.configure(text=_t("✔ Связь проверена"), fg=GREEN)

    def _save_binding(self) -> None:
        """Сохранить привязку агента (токены)."""
        rec = orion.get(self._draft_id) if self._draft_id else None
        if rec is None:
            self._hint(_t("Сначала заселите агента"), AMBER)
            self.show_tab("agents")
            return
        orion.save_binding(rec["id"],
                           opencode_token=self.token_entry.get().strip(),
                           github_token=self.gh_entry.get().strip() if self._access == "commander" else "")
        self._refresh_binding()
        self._hint(_t("Привязка сохранена"), GREEN)

    def _clear_binding(self) -> None:
        """Забыть привязку агента."""
        rec = orion.get(self._draft_id) if self._draft_id else None
        if rec is None:
            return
        orion.clear_binding(rec["id"])
        self.token_entry.delete(0, tk.END)
        self.gh_entry.delete(0, tk.END)
        self._refresh_binding()
        self._hint(_t("Привязка забыта"), MUTED)

    # -- режим мастера (активный ок) -------------------------------------------
    def _enter_master_mode(self) -> None:
        """Пилот позвал мастера — Орион следит за мышью и анализирует действия."""
        rec = self._rec()
        self._master_mode = True
        self._last_mouse_pos = None
        self._last_hint_time = 0
        self._hint(_t("Режим мастера: Орион смотрит за тобой. Скажи «стоп» чтобы выйти."),
                   GREEN)
        # Запускаем отслеживание мыши
        self._track_mouse()

    def _track_mouse(self) -> None:
        """Отслеживание мыши в режиме мастера."""
        if not getattr(self, "_master_mode", False):
            return
        try:
            x = self.app.winfo_pointerx() - self.app.winfo_rootx()
            y = self.app.winfo_pointery() - self.app.winfo_rooty()
        except Exception:  # noqa: BLE001
            x, y = 0, 0
        # Если мышь переместилась — анализируем
        pos = (x, y)
        if pos != self._last_mouse_pos:
            self._last_mouse_pos = pos
            self._analyze_mouse_position(x, y)
        # Продолжаем отслеживание
        self.after(500, self._track_mouse)

    def _analyze_mouse_position(self, x: int, y: int) -> None:
        """Анализ позиции мыши — что под курсором."""
        screen = self.app.current or ""
        screen_name = self._zone_title(screen)
        # Получаем текст под курсором (примерный)
        element = self._element_at(x, y)
        hint = _t("Курсор на ({0}, {1}) · раздел «{2}» · элемент: {3}").format(
            x, y, screen_name, element or _t("неизвестно"))
        self._hint(hint, CYAN)
        # Раз в 10 секунд — запускаем анализ через агента
        now = time.time()
        if now - getattr(self, "_last_hint_time", 0) > 10:
            self._last_hint_time = now
            rec = self._rec()
            mouse_ctx = orion.mouse_position_text(x, y, screen_name)
            ctx = self._context()
            prompt = (f"Пилот позвал мастера. Режим активного ока.\n"
                      f"{mouse_ctx}\n"
                      f"Элемент под курсором: {element or 'неизвестно'}\n"
                      f"Проанализируй что пилот делает на корабле и дай подсказку.")
            # Запускаем в отдельном потоке
            threading.Thread(target=self._master_worker,
                             args=(rec, prompt, ctx), daemon=True).start()

    def _master_worker(self, rec: dict, prompt: str, ctx: str) -> None:
        """Фоновый анализ в режиме мастера."""
        try:
            res = orion.run_profile(rec, prompt, profile="orion-recon", context=ctx)
        except Exception:  # noqa: BLE001
            return
        if res.reply:
            self._queue.put(("master_hint", res))

    def _element_at(self, x: int, y: int) -> str:
        """Определение элемента под курсором (упрощённо)."""
        try:
            widget = self.app.winfo_containing(x, y)
            if widget is None:
                return ""
            # Получаем текст виджета
            try:
                text = widget.cget("text")
                if text:
                    return str(text)[:50]
            except Exception:  # noqa: BLE001
                pass
            # Для кнопок и меток
            try:
                text = widget.cget("label")
                if text:
                    return str(text)[:50]
            except Exception:  # noqa: BLE001
                pass
            return ""
        except Exception:  # noqa: BLE001
            return ""

    def _read_book(self) -> None:
        """Орион читает вслух книгу из библиотеки."""
        rec = self._rec()
        from stamina.voice import tts
        if not tts.available():
            self._hint(_t("Озвучка не доступна"), RED)
            return
        books = orion.library_books()
        if not books:
            self._hint(_t("Библиотека пуста"), MUTED)
            return
        book = books[0]
        chunks = orion.book_text_for_reading(book["id"])
        if not chunks:
            self._hint(_t("Книга пуста"), MUTED)
            return
        self._hint(_t("Читаю: {0}").format(book["title"]), GREEN)
        for chunk in chunks[:3]:
            tts.speak(chunk)
            time.sleep(0.5)

    def _read_book(self) -> None:
        """Орион читает вслух книгу из библиотеки."""
        rec = self._rec()
        from stamina.voice import tts
        if not tts.available():
            self._hint(_t("Озвучка не доступна"), RED)
            return
        books = orion.library_books()
        if not books:
            self._hint(_t("Библиотека пуста"), MUTED)
            return
        book = books[0]
        chunks = orion.book_text_for_reading(book["id"])
        if not chunks:
            self._hint(_t("Книга пуста"), MUTED)
            return
        self._hint(_t("Читаю: {0}").format(book["title"]), GREEN)
        for chunk in chunks[:3]:
            tts.speak(chunk)
            time.sleep(0.5)

    def _exit_master_mode(self) -> None:
        """Выйти из режима мастера."""
        self._master_mode = False
        self._last_mouse_pos = None
        self._hint(_t("Режим мастера выключен"), MUTED)

    def on_show(self) -> None:
        """Орион приветствует пилота при входе в зону."""
        rec = self._rec()
        name = str(rec.get("name") or "ОРИОН").upper()
        greeting = _t("{0} на связи. Готов к общению, пилот.").format(name)
        self._hint(greeting, GREEN)
        from stamina.voice import tts
        if self._answer_voice and tts.available():
            tts.speak(greeting)

    def on_zone_enter(self, zone: str, subtab: str = "") -> None:
        """Орион — гид: при входе в любой отсек рассказывает что происходит.

        Использует page_help.py для получения описания отсека.
        """
        from stamina import page_help
        from stamina.voice import tts
        rec = self._rec()
        name = str(rec.get("name") or "ОРИОН").upper()
        # Получаем описание отсека из page_help
        key = zone
        if subtab:
            key = f"{zone}.{subtab}"
        info = page_help.PAGES.get(zone) or page_help.PAGES.get(key)
        if info:
            title, text = info
            summary = text.split("\n")[0] if text else title
            greeting = _t("{0}: {1}").format(name, summary)
        else:
            greeting = _t("{0}: открыт раздел «{1}»").format(name, zone)
        self._hint(greeting, CYAN)
        if self._answer_voice and tts.available():
            tts.speak(greeting)

    # -- эволюция характера ---------------------------------------------------
    def _refresh_evolution(self) -> None:
        """Показать текущий уровень развития Ориона."""
        rec = orion.get(self._draft_id) if self._draft_id else None
        if rec is None:
            self.evo_label.configure(text="")
            self.evo_hint.configure(text="")
            return
        status = orion.evolution_status(rec["id"])
        level = status["level"]
        name = status["name"]
        count = status["count"]
        remaining = status["remaining"]
        self.evo_label.configure(text=_t("УРОВЕНЬ {0} · {1} · Реплик: {2}").format(
            level, name.upper(), count))
        if remaining > 0:
            self.evo_hint.configure(text=_t(
                "Орион развивается от общения с тобой. До следующего уровня: {0} репилок").format(remaining))
        else:
            self.evo_hint.configure(text=_t("Орион достиг максимума — он стал твоим спутником."))

    # -- события -----------------------------------------------------------
    def _pump(self) -> None:
        """Собирать события: ответы агента и распознанную речь (в потоке)."""
        try:
            while True:
                ev = self._queue.get_nowait()
                if ev[0] == "answer":
                    self._on_answer(ev[1], ev[2], ev[3])
        except queue.Empty:
            pass
        try:
            self.mic.poll()
        except Exception:  # noqa: BLE001
            pass
        self.after(140, self._pump)
