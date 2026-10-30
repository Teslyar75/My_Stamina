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
from stamina.i18n import t as tr_          # окно доступа к GitHub исторически зовёт так
from stamina import archive_view
from stamina import marks

import queue
import math
import re
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import messagebox
from pathlib import Path

from stamina import __version__, compose, nav, orion, owner_key, pilot_pin, pilots, shots, theme
from stamina import task_progress as tprog
from stamina.adapt import make_vscroll
from stamina.hud import HudButton, HudPanel
from stamina.pilot_screens import Modal, PinPad
from stamina.prompt_box import PromptBox, hud_colors
from stamina.suggest import Suggester, dictionary_from
from stamina.theme import (AMBER, BG, BG2, CYAN, GREEN, LINE, MUTED, PANEL, RED, TEXT,
                           blend, px)
from stamina.voice import stt, tts
from stamina.voice.mic import MicControl


def _label(master, text="", *, fg=None, size=10, bold=False, bg=None, **kw):
    fg = TEXT if fg is None else fg  # токен скина — в момент вызова, не при импорте
    bg = PANEL if bg is None else bg  # токен скина — в момент вызова, не при импорте
    return tk.Label(master, text=text, fg=fg, bg=bg, font=theme.font(size, bold), **kw)


# -- справка «где взять токен GitHub» ------------------------------------------
GITHUB_TOKENS_URL = "https://github.com/settings/tokens"

#: Сколько секунд держать на пульте надпись «задача выполнена» после доклада агента.
REPORT_KEEP = 900


def github_token_help() -> str:
    """Пошаговая справка для пилота, который не каждый день в GitHub.

    Отдельно — про другой компьютер: там корабль не подскажет автоматически,
    токен придётся получить заново (или взять прежний, если срок не истёк).
    """
    steps = [
        _t("1. Войдите на github.com под своим аккаунтом."),
        _t("2. Справа вверху — аватар → Settings."),
        _t("3. Внизу левого столбца — Developer settings."),
        _t("4. Personal access tokens → Tokens (classic) → Generate new token (classic)."),
        _t("5. Имя: Star Typing. Срок: 90 дней (или без срока, если корабль только ваш)."),
        _t("6. Поставьте галочку repo — этого хватает для обновлений корабля."),
        _t("7. Generate token и скопируйте ghp_… — показывается он один раз."),
        _t("8. Вставьте токен сюда и нажмите «ПРОВЕРИТЬ»."),
    ]
    notes = [
        _t("Придирчивым: Personal access tokens → Fine-grained tokens, доступ только к "
           "репозиторию Teslyar75/My_Stamina, Contents: Read and write."),
        _t("Токен — как ключ от шлюза: никому его не пересылайте. Корабль хранит его "
           "только на этом компьютере."),
        _t("На другом компьютере токен придётся получить заново тем же путём — "
           "или взять прежний, если срок ещё не истёк."),
    ]
    return "\n".join(steps + [""] + notes)


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
        _label(self.body, tr_("Есть ли у тебя доступ к аккаунту разработчика на GitHub?\n"
                        "Можешь ли ты отправлять обновления и изменять состояние проекта?"),
          fg=MUTED, size=10).pack(anchor="w", pady=(px(4), px(8)))
        self.token_entry = tk.Entry(self.body, bg=BG2, fg=TEXT, insertbackground=CYAN,
                                    relief=tk.FLAT, font=theme.font(10),
                                    highlightthickness=1, highlightbackground=LINE,
                                    highlightcolor=CYAN, show="*")
        self.token_entry.pack(fill=tk.X, ipady=px(4))
        _label(self.body, tr_("Токен GitHub (ghp_... или github_pat_...)"),
          fg=MUTED, size=8).pack(anchor="w", pady=(px(4), px(8)))
        self.msg = _label(self.body, "", fg=RED, size=9, bold=True)
        self.msg.pack(anchor="w")
        btns = tk.Frame(self.body, bg=PANEL)
        btns.pack(fill=tk.X, pady=(px(8), 0))
        HudButton(btns, tr_("ПРОВЕРИТЬ"), self.check, color=GREEN, height=36,
                  font_size=10).pack(side=tk.LEFT)
        HudButton(btns, tr_("ПРОПУСТИТЬ"), self.skip, height=36, font_size=9).pack(side=tk.LEFT, padx=px(6))
        HudButton(btns, tr_("КАК ПОЛУЧИТЬ ТОКЕН"), self.toggle_help, height=36, font_size=9,
                  color=AMBER).pack(side=tk.LEFT, padx=px(6))
        HudButton(btns, tr_("ОТКРЫТЬ GITHUB"), self.open_tokens_page, height=36, font_size=9,
                  color=CYAN).pack(side=tk.LEFT, padx=px(6))
        # справка для тех, кто не каждый день в GitHub: показывается по кнопке
        self.help_label = _label(self.body, github_token_help(), fg=MUTED, size=9, justify="left",
                                 anchor="w", wraplength=px(620))
        self.help_shown = False
        self.result = False

    def toggle_help(self) -> None:
        """Справка «где взять токен» — по шагам, для не-знатока GitHub."""
        if self.help_shown:
            self.help_label.pack_forget()
        else:
            self.help_label.pack(anchor="w", pady=(px(8), 0))
        self.help_shown = not self.help_shown

    def open_tokens_page(self) -> None:
        """Открыть в браузере страницу создания токена — искать её глазами не надо."""
        try:
            webbrowser.open(GITHUB_TOKENS_URL)
        except Exception:  # noqa: BLE001
            self.msg.configure(text=tr_("Откройте вручную: {0}").format(GITHUB_TOKENS_URL),
                               fg=AMBER)

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

    TABS = (("chat", "ЧАТ"), ("agents", "АГЕНТЫ"), ("archive", "АРХИВ"))

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
        store = getattr(self.app, "store", None)
        self.ui_mode = str(getattr(store, "settings", {}).get("orion_ui") or "chat")
        self._sent_log: list[str] = []     # что уже отправляли — для истории по ↑
        self._pending_quotes: list[str] = []   # темы из архива, ждущие отправки
        self._archive_rows: list[dict] = []
        self._archive_picked: list[str] = []
        self._archive_tag_ids: dict[str, str] = {}
        self._archive_images: list = []
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
        self._build_archive(self.tabs["archive"][0])

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
        # вид чата: «Чат» для разговора, «Ремонтный отсек» — для работы руками
        self.mode_btn = HudButton(bar, self._mode_title(), self._toggle_mode, height=30,
                                  font_size=9, color=CYAN)
        self.mode_btn.pack(side=tk.RIGHT, padx=(px(4), 0))

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
        # Лента только для чтения, но текст выделяется мышью и копируется:
        # Ctrl+C (в любой раскладке), Ctrl+A, правый клик — меню «Копировать».
        self.text.configure(cursor="xterm", exportselection=True,
                            selectbackground=CYAN, selectforeground=BG,
                            inactiveselectbackground=LINE)
        self.text.bind("<Button-3>", self._feed_menu)
        self.text.bind("<Control-KeyPress>", self._feed_key)
        self.text.bind("<<Copy>>", self._copy_text)
        self.text.bind("<Button-1>", self._select_text)
        self._msg_texts: list[str] = []

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

        def _wrap_strip(e, box=sbody) -> None:
            wl = max(px(120), e.width - px(8))
            for w in box.winfo_children():
                if isinstance(w, tk.Label) and int(w.cget("wraplength") or 0) != wl:
                    w.configure(wraplength=wl)
        sbody.bind("<Configure>", _wrap_strip, add="+")

        bottom = tk.Frame(page, bg=BG)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, pady=(px(6), 0))
        self.bottom = bottom

        self.hint = _label(bottom, "", fg=MUTED, size=9, bg=BG, anchor="w", justify="left",
                           wraplength=px(900))
        self.hint.pack(fill=tk.X)

        # Шкала занятости: видно, что Орион работает, а не молчит
        self._build_activity(bottom)

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

        # Приложенный снимок экрана: виден до отправки, снимается крестиком.
        # Пилот хочет обсуждать картинку, а не имя файла, — потому миниатюра, не путь.
        self.shot_row = tk.Frame(bottom, bg=BG)
        # миниатюры всех приложенных картинок: клик — посмотреть, ✕ — снять одну
        self.shot_tray = compose.ShotTray(self.shot_row, bg=BG, size=72,
                                          on_open=self._open_shot, on_drop=self._drop_shot)
        self.shot_icon = self.shot_tray.frame
        self.shot_icon.pack(side=tk.LEFT)
        self.shot_label = _label(self.shot_row, "", fg=CYAN, size=9, bg=BG, anchor="w",
                                 justify="left", wraplength=px(760))
        self.shot_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(px(10), 0))
        HudButton(self.shot_row, "✕", self._clear_shots, height=28, font_size=10,
                  width=28, color=MUTED).pack(side=tk.RIGHT, padx=(px(6), 0))
        self._pending_shots: list[str] = []
        self._shot_previews: list = []          # Tk не держит ссылки на картинки сам

        row = tk.Frame(bottom, bg=BG)
        row.pack(fill=tk.X, pady=(px(4), 0))
        # Поле, микрофон, вложение и ОТПРАВИТЬ — одна строка, которую нельзя сворачивать
        # в выпадающий список: иначе кнопки уезжают в «⋯ ЕЩЁ» и отправить нечем.
        row._alt_nocompact = True
        self.input_row = row
        self.suggester = Suggester()
        self._suggest_seen = -1
        self._draft_text = ""
        self.entry = PromptBox(row, on_send=self._send, font=theme.font(11),
                               colors=hud_colors(), suggester=self.suggester,
                               on_draft=self._draft_note)
        self.entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, px(8)))
        self.entry.bind_text("<Control-v>", self._paste_text)
        self.entry.bind_text("<Control-V>", self._paste_text)
        # Снимок без кнопки: Ctrl+Shift+S — активное окно в поле набора
        self.entry.bind_text("<Control-Shift-S>", self._grab_window_shot)
        self.entry.bind_text("<Control-Shift-s>", self._grab_window_shot)
        self.entry.bind_text("<Button-3>", self._context_menu)
        # 📎 — приложить картинки с диска (как в чатах ИИ); Ctrl+V — из буфера
        self.attach_btn = HudButton(row, "📎", self._pick_images, height=36, font_size=11,
                                    width=36, color=CYAN)
        self.mic = MicControl(row, on_text=self._insert_text, on_status=self._mic_status,
                              label=_t("ГОЛОС"), height=36, font_size=11,
                              settings=self.app.store.settings,
                              save=self.app.store.save_settings)
        # Кнопки справа: ОТПРАВИТЬ — крупная и последняя перед «СТОП», чтобы
        # последовательность читалась слева направо: наберите → проверьте → отправьте.
        self.stop_btn = HudButton(row, _t("■ СТОП"), self._stop_work, height=36, font_size=10,
                                  width=76, color=RED)
        self.stop_btn.pack(side=tk.RIGHT, padx=(px(6), 0))
        self.stop_btn.pack_forget()          # виден только пока агент работает
        self.stop_btn.set_enabled(False)
        self.send_btn = HudButton(row, _t("ОТПРАВИТЬ") + " ↵", self._send, height=36, font_size=11,
                                  color=GREEN)
        self.send_btn.pack(side=tk.RIGHT, padx=(px(6), 0))
        self.mic.hold_button.pack(side=tk.RIGHT, padx=(px(6), 0))
        self.mic.button.pack(side=tk.RIGHT)
        self.attach_btn.pack(side=tk.RIGHT, padx=(0, px(6)))
        # поле ввода — последним в порядке pack: иначе на узком окне (alt 1280×720)
        # растянутое поле съедает место, и кнопки справа (📎) сжимаются в ноль
        self.entry.pack_forget()
        self.entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, px(8)))
        self.composer_hint = _label(bottom, "", fg=MUTED, size=8, bg=BG, anchor="w")
        self.composer_hint.pack(fill=tk.X, pady=(px(2), 0))
        # Простая панель общения: микрофон, ввод, отправка
        self._apply_mode()

        self._apply_tags()
        self._set_board(False)

    def _wheel(self, e) -> str:
        self.text.yview_scroll(int(-e.delta / 120) * 3, "units")
        return "break"

    def _select_text(self, e) -> None:
        """Клик в ленте: фокус в ленту (иначе Ctrl+C не дойдёт), выделение — штатное Tk."""
        try:
            self.text.focus_set()
        except tk.TclError:
            pass
        return None

    def _feed_key(self, e) -> str | None:
        """Ctrl+C / Ctrl+A по коду клавиши — работает и в русской раскладке."""
        code = getattr(e, "keycode", 0)
        key = (getattr(e, "keysym", "") or "").lower()
        if code == 67 or key in ("c", "cyrillic_es"):
            return self._copy_text(e)
        if code == 65 or key in ("a", "cyrillic_ef"):
            return self._select_all_feed()
        return None

    def _select_all_feed(self) -> str:
        self.text.tag_remove(tk.SEL, "1.0", tk.END)
        self.text.tag_add(tk.SEL, "1.0", "end-1c")
        return "break"

    def _msg_at(self, index: str) -> str:
        """Текст реплики под курсором (по меткам msgN), пусто — если не на реплике."""
        for tag in self.text.tag_names(index):
            if tag.startswith("msg") and tag[3:].isdigit():
                n = int(tag[3:])
                if n < len(self._msg_texts):
                    return self._msg_texts[n]
        return ""

    def _feed_menu(self, e) -> str:
        """Правый клик по ленте: Копировать / Копировать сообщение / Выделить всё."""
        idx = self.text.index(f"@{e.x},{e.y}")
        has_sel = bool(self.text.tag_ranges(tk.SEL))
        msg = self._msg_at(idx)
        menu = tk.Menu(self, tearoff=0, bg=PANEL, fg=TEXT,
                       activebackground=CYAN, activeforeground=BG)
        menu.add_command(label=_t("Копировать"), accelerator="Ctrl+C",
                         command=lambda: self._copy_text(None),
                         state=tk.NORMAL if has_sel else tk.DISABLED)
        menu.add_command(label=_t("Копировать сообщение"),
                         command=lambda m=msg: self._copy_plain(m),
                         state=tk.NORMAL if msg else tk.DISABLED)
        menu.add_command(label=_t("Выделить всё"), accelerator="Ctrl+A",
                         command=self._select_all_feed)
        self._feed_menu_widget = menu
        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _copy_plain(self, text: str) -> None:
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self._hint(_t("Текст скопирован"), GREEN)

    def _paste_text(self, _e) -> str:
        """Вставить из буфера: сначала снимок экрана, потом текст."""
        if self._grab_clipboard_shot():
            return "break"
        text = compose.clipboard_text(self)
        if text:
            self.entry.paste(text)
            self.entry.focus_set()
        return "break"

    # -- снимки экрана -------------------------------------------------------
    def _grab_clipboard_shot(self) -> bool:
        """Картинка из буфера обмена (Win+Shift+S или файл из Проводника) → к сообщению."""
        if not shots.available():
            self._hint(_t(compose.NO_PILLOW), RED)
            return False
        image = compose.clipboard_image()
        if image is None:
            return False
        return self._attach_image(image, _t("снимок из буфера"))

    def _grab_window_shot(self, _e=None) -> str:
        """Ctrl+Shift+S: снять активное окно прямо в поле набора. Отдельной кнопки нет — пилот её не захотел."""
        if not shots.available():
            self._hint(_t(compose.NO_PILLOW), RED)
            return "break"
        image = compose.window_image()
        if image is None:
            self._hint(_t("Снять не удалось. Нажмите Win+Shift+S, затем Ctrl+V здесь."), RED)
            return "break"
        self._attach_image(image, _t("снимок окна"))
        return "break"

    def _attach_image(self, image, source: str) -> bool:
        """Сохранить снимок на борт и показать его в строке приложенного."""
        try:
            path = shots.save_image(image)
        except Exception as exc:  # noqa: BLE001
            self._hint(_t("Снимок не сохранился: {0}").format(exc), RED)
            return False
        self._pending_shots.append(str(path))
        self._refresh_shot_row()
        self._hint(_t("Снимок приложен ({0}). Орион увидит его вместе с сообщением.")
                   .format(source), CYAN)
        return True

    IMAGE_TYPES = compose.IMAGE_TYPES

    def _pick_images(self) -> None:
        """Кнопка 📎: выбрать одну или несколько картинок — копии уходят на борт."""
        self.attach_paths(compose.pick_image_files(self))

    def attach_paths(self, names) -> int:
        """Приложить файлы-картинки к сообщению. → сколько приложено."""
        pics = compose.image_paths(names)
        added = 0
        for taken in shots.adopt(pics):
            if str(taken) not in self._pending_shots:
                self._pending_shots.append(str(taken))
                added += 1
        if added:
            self._refresh_shot_row()
            self._hint(_t("Приложено картинок: {0}. Орион увидит их вместе с сообщением.")
                       .format(added), CYAN)
        elif names:
            self._hint(_t("Это не картинка (png, jpg, gif, bmp, webp)"), AMBER)
        return added

    def _refresh_shot_row(self) -> None:
        """Строка приложенного снимка над полем ввода: миниатюра, имя, крестик."""
        if not hasattr(self, "shot_row"):
            return
        if self._pending_shots:
            n = len(self._pending_shots)
            self.shot_label.configure(
                text=_t("📷 Приложено: {0}").format(n) + "\n"
                     + _t("Картинки уйдут Ориону вместе с сообщением."))
            self._draw_shot_preview(self._pending_shots)
            self.shot_row.pack(fill=tk.X, pady=(px(4), 0), before=self.input_row)
        else:
            self.shot_label.configure(text="")
            self._draw_shot_preview([])
            self.shot_row.pack_forget()

    def _draw_shot_preview(self, paths) -> None:
        """Миниатюры приложенного перед отправкой — пилот видит картинки, а не имена."""
        self.shot_tray.draw(paths)
        self._shot_previews = self.shot_tray.previews

    def _drop_shot(self, path: str) -> str:
        if path in self._pending_shots:
            self._pending_shots.remove(path)
        self._refresh_shot_row()
        return "break"

    def _clear_shots(self) -> None:
        """Убрать снимок из сообщения, файл на борту оставить (история уже его знает)."""
        self._pending_shots.clear()
        self._refresh_shot_row()
        self._hint(_t("Снимок снят с сообщения"), MUTED)

    def _open_shot(self, path: str) -> str:
        """Клик по миниатюре — открыть снимок целиком."""
        if not compose.open_image(self, path):
            self._hint(_t("Не удалось открыть снимок: {0}").format(Path(path).name), RED)
        return "break"

    def _context_menu(self, _e) -> str:
        """Контекстное меню для строки сообщения: Вставить."""
        menu = tk.Menu(self, tearoff=0, bg=PANEL, fg=TEXT,
                       activebackground=CYAN, activeforeground=BG)
        menu.add_command(label=_t("Вставить"), command=self._paste_from_menu)
        menu.add_command(label=_t("Копировать"), command=self._copy_from_menu)
        try:
            menu.tk_popup(_e.x_root, _e.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _paste_from_menu(self) -> None:
        try:
            text = self.clipboard_get()
            if text:
                self.entry.paste(text)
        except tk.TclError:
            pass

    def _copy_from_menu(self) -> None:
        try:
            selected = self.entry.selected()
            if selected:
                self.clipboard_clear()
                self.clipboard_append(selected)
        except tk.TclError:
            pass

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
        # Подчинённый агент — не пассажир: он не заселяется отдельно, а работает
        # по ТЗ, которое Орион составляет из слов пилота и пометок мышью.
        _label(lp.body,
               _t("ПОДЧИНЁННЫЙ: {0} — ТЗ ему даю я").format(_t("ИСПОЛНИТЕЛЬ")),
               fg=MUTED, size=8, anchor="w", justify="left").pack(fill=tk.X, pady=(px(6), 0))

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
        self.voice_mode_btn = HudButton(form, "—", self._cycle_voice, height=38, font_size=12,
                                        color=GREEN)
        self.voice_mode_btn.pack(anchor="w")
        self.voice_hint = _label(form, "", fg=MUTED, size=8, anchor="w", justify="left",
                                 wraplength=px(620))
        self.voice_hint.pack(fill=tk.X)

        self.enabled_btn = HudButton(form, "—", self._toggle_enabled, height=32, font_size=10,
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
        bp.pack(fill=tk.BOTH, expand=True, pady=(px(10), 0))
        bbody = tk.Frame(bp.body, bg=PANEL)
        bbody.pack(fill=tk.BOTH, expand=True)

        self.boarding_code = orion.make_boarding_code()
        code_row = tk.Frame(bbody, bg=PANEL)
        code_row.pack(fill=tk.X, pady=(px(10), 0))
        _label(code_row, _t("КОД ДЛЯ ЗАСЕЛЕНИЯ"), fg=MUTED, size=11, bold=True).pack(anchor="w")
        self.code_label = _label(code_row, self.boarding_code, fg=GREEN, size=28, bold=True, bg=PANEL)
        self.code_label.pack(anchor="w", pady=(px(6), 0))
        _label(code_row, _t("Введите этот код в OpenCode CLI при заселении агента."),
               fg=MUTED, size=10, anchor="w", justify="left",
               wraplength=px(800)).pack(anchor="w")

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

    # -- вкладка АРХИВ -----------------------------------------------------
    def _build_archive(self, page: tk.Frame) -> None:
        """Архив: вся переписка борта, поиск по дате, времени и словам, перенос тем в чат."""
        bar = tk.Frame(page, bg=BG)
        bar.pack(fill=tk.X, pady=(0, px(4)))
        _label(bar, _t("АРХИВ — ПОИСК ПО ПЕРЕПИСКЕ"), fg=CYAN, size=11, bold=True,
               bg=BG).pack(side=tk.LEFT)
        self.arch_found = _label(bar, "", fg=MUTED, size=9, bg=BG)
        self.arch_found.pack(side=tk.RIGHT)

        row = tk.Frame(page, bg=BG)
        row.pack(fill=tk.X)
        self.arch_entry = tk.Entry(row, bg=PANEL, fg=TEXT, relief=tk.FLAT, font=theme.font(11),
                                   insertbackground=CYAN, highlightthickness=1,
                                   highlightbackground=LINE, highlightcolor=CYAN)
        self.arch_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=px(6), padx=(0, px(8)))
        self.arch_entry.bind("<Return>", lambda _e: self._archive_search())
        HudButton(row, _t("НАЙТИ"), self._archive_search, height=36, font_size=10,
                  color=CYAN).pack(side=tk.LEFT, padx=(0, px(6)))
        HudButton(row, _t("СБРОС"), self._archive_reset, height=36, font_size=10,
                  color=MUTED).pack(side=tk.LEFT)

        acts = tk.Frame(page, bg=BG)
        acts.pack(fill=tk.X, pady=(px(6), px(4)))
        HudButton(acts, _t("ПЕРЕНЕСТИ В ЧАТ"), self._archive_to_chat, height=32, font_size=9,
                  color=GREEN).pack(side=tk.LEFT, padx=(0, px(6)))
        HudButton(acts, _t("В ПОЛЕ ВВОДА"), self._archive_to_input, height=32, font_size=9,
                  color=CYAN).pack(side=tk.LEFT, padx=(0, px(6)))
        HudButton(acts, _t("ВЫДЕЛИТЬ ВСЁ"), self._archive_pick_all, height=32, font_size=9,
                  color=MUTED).pack(side=tk.LEFT, padx=(0, px(6)))
        HudButton(acts, _t("СНЯТЬ ВЫДЕЛЕНИЕ"), self._archive_unpick, height=32, font_size=9,
                  color=MUTED).pack(side=tk.LEFT)

        _label(page, _t("Ищите по дате (19.10.2026), времени (22:15) или словам. Клик по "
                        "находке — сообщение целиком; ☐ — отметить для переноса в чат."),
               fg=MUTED, size=9, bg=BG, anchor="w", justify="left",
               wraplength=px(900)).pack(fill=tk.X, pady=(0, px(4)))

        self.arch = HudPanel(page, title=_t("НАЙДЕННЫЕ СООБЩЕНИЯ"))
        self.arch.pack(fill=tk.BOTH, expand=True)        # раньше панель не вставала — находки были не видны
        # подробный вид: панель навигации над тем же местом, где список
        self.arch_nav = tk.Frame(self.arch.body, bg=PANEL)
        HudButton(self.arch_nav, _t("← К СПИСКУ"), self._archive_back, height=30, font_size=9,
                  color=CYAN).pack(side=tk.LEFT, padx=(0, px(6)))
        HudButton(self.arch_nav, "◀", lambda: self._archive_step(-1), height=30, font_size=10,
                  color=MUTED).pack(side=tk.LEFT, padx=(0, px(4)))
        HudButton(self.arch_nav, "▶", lambda: self._archive_step(1), height=30, font_size=10,
                  color=MUTED).pack(side=tk.LEFT, padx=(0, px(8)))
        self.arch_pos = _label(self.arch_nav, "", fg=MUTED, size=9, bg=PANEL)
        self.arch_pos.pack(side=tk.LEFT)
        self.arch_pick_btn = HudButton(self.arch_nav, _t("ОТМЕТИТЬ ДЛЯ ПЕРЕНОСА"),
                                       self._archive_detail_pick, height=30, font_size=9,
                                       color=GREEN)
        self.arch_pick_btn.pack(side=tk.RIGHT)
        abody = tk.Frame(self.arch.body, bg=PANEL)
        abody.pack(fill=tk.BOTH, expand=True)
        self.arch_abody = abody
        asb = make_vscroll(abody)
        asb.pack(side=tk.RIGHT, fill=tk.Y)
        self.arch_sb = asb
        self.arch_text = tk.Text(abody, wrap=tk.WORD, bg=PANEL, fg=TEXT, relief=tk.FLAT,
                                 font=theme.font(10), padx=px(8), pady=px(6), cursor="arrow",
                                 state=tk.DISABLED, highlightthickness=0, bd=0,
                                 yscrollcommand=asb.set, spacing1=px(1), spacing3=px(1))
        self.arch_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.arch_detail = tk.Text(abody, wrap=tk.WORD, bg=PANEL, fg=TEXT, relief=tk.FLAT,
                                   font=theme.font(10), padx=px(10), pady=px(8),
                                   cursor="xterm", state=tk.DISABLED, highlightthickness=0,
                                   bd=0, yscrollcommand=asb.set, spacing3=px(2),
                                   selectbackground=CYAN, selectforeground=BG,
                                   inactiveselectbackground=LINE)
        asb.configure(command=self._archive_yview)
        for w in (self.arch_text, self.arch_detail, abody):
            w.bind("<MouseWheel>", lambda e: self._wheel_in(self._archive_view(), e))
        for t in (self.arch_text, self.arch_detail):
            for tag, color in (("when", MUTED), ("who", CYAN), ("body", TEXT), ("shot", AMBER),
                               ("dim", MUTED), ("chk", GREEN)):
                t.tag_configure(tag, foreground=color)
            t.tag_configure("hit", background=AMBER, foreground=BG)
            t.tag_raise("hit")
        self.arch_text.tag_configure("snip", lmargin1=px(22), lmargin2=px(22))
        self.arch_detail.tag_configure("focus", lmargin1=px(10), lmargin2=px(10),
                                       background=BG2)
        self.arch_detail.tag_configure("hitcur", background=GREEN, foreground=BG)
        self.arch_detail.tag_raise("hitcur")
        self.arch_detail.bind("<Escape>", lambda _e: self._archive_back())
        self.arch_detail.bind("<Left>", lambda _e: self._archive_step(-1))
        self.arch_detail.bind("<Right>", lambda _e: self._archive_step(1))
        self.arch_detail.bind("<Button-1>", lambda _e: self.arch_detail.focus_set())
        self.arch_detail.bind("<Control-KeyPress>", self._archive_detail_key)
        self._archive_detail_idx = -1

    def _wheel_in(self, widget: tk.Text, e) -> str:
        widget.yview_scroll(int(-e.delta / 120) * 3, "units")
        return "break"

    def _archive_search(self) -> None:
        """Найти в переписке в фоне: пустой запрос — последние сообщения борта.

        Большой архив читается в потоке; экран не замирает. Пришёл ответ на старый
        запрос (пилот уже ищет другое) — выбрасываем.
        """
        query = self.arch_entry.get().strip()
        self._arch_gen = getattr(self, "_arch_gen", 0) + 1
        gen = self._arch_gen
        self._arch_words = tuple(orion.parse_query(query).words)
        self._arch_started = time.perf_counter()
        self.arch_found.configure(text=_t("Ищу…"))
        box: dict = {}

        def work() -> None:
            try:
                rows = orion.archive(query, limit=500)
                box["rows"] = rows
                box["snips"] = archive_view.prepare(rows, self._arch_words)
            except Exception as exc:  # noqa: BLE001
                box["error"] = exc
            box["done"] = True                       # последним: ответ собран целиком

        threading.Thread(target=work, name="orion-archive", daemon=True).start()
        self._archive_poll(gen, box)

    def _archive_poll(self, gen: int, box: dict) -> None:
        if gen != getattr(self, "_arch_gen", 0):
            return                                   # запрос устарел
        if "done" not in box:
            self.after(20, lambda: self._archive_poll(gen, box))
            return
        if "error" in box:
            self._hint(_t("Архив не прочитался: {0}").format(box["error"]), AMBER)
            box = {"rows": [], "snips": [], "done": True}
        self._archive_rows = box["rows"]
        self._archive_snips = box["snips"]
        self._archive_picked = []
        self._archive_tags = {}
        self._archive_tag_ids = {}
        self._archive_ctx = {}
        self._archive_back()
        self._render_archive()
        self._archive_prefetch(gen)
        self._archive_ms = (time.perf_counter() - self._arch_started) * 1000
        self._hint(_t("Найдено: {0}").format(len(self._archive_rows)) if self._archive_rows
                   else _t("Ничего не найдено — попробуйте другие слова или дату."),
                   CYAN if self._archive_rows else MUTED)

    def _archive_prefetch(self, gen: int) -> None:
        """Соседей для подробного вида читаем в фоне, когда список уже на экране."""
        cache = self._archive_ctx
        agents = list(dict.fromkeys(str(m.get("agent") or "") for m in self._archive_rows))

        def work() -> None:
            for agent in agents:
                if not agent or agent in cache or gen != getattr(self, "_arch_gen", 0):
                    continue
                try:
                    cache[agent] = orion.archive_messages(agent)
                except Exception:  # noqa: BLE001
                    pass

        threading.Thread(target=work, name="orion-archive-ctx", daemon=True).start()

    def _archive_reset(self) -> None:
        self.arch_entry.delete(0, tk.END)
        self._archive_search()

    def _render_archive(self) -> None:
        """Список находок: шапка и фрагмент вокруг совпадения, слово подсвечено."""
        t = self.arch_text
        t.configure(state=tk.NORMAL)
        t.delete("1.0", tk.END)
        self._archive_images = []
        if not self._archive_rows:
            t.insert(tk.END, _t("Ничего не найдено — попробуйте другие слова или дату.")
                     + "\n", "when")
        snips = getattr(self, "_archive_snips", None) or archive_view.prepare(
            self._archive_rows, getattr(self, "_arch_words", ()))
        for idx, msg in enumerate(self._archive_rows):
            tag = f"pick{idx}"
            self._archive_tag_ids[tag] = str(msg.get("id") or f"_{idx}")
            when = orion.when_text(float(msg.get("ts") or 0.0))
            who = orion.role_name(str(msg.get("role") or "")).upper()
            t.mark_set(f"chk{idx}", tk.END + "-1c")
            t.mark_gravity(f"chk{idx}", tk.LEFT)
            t.insert(tk.END, "☐ ", ("chk", f"box{idx}"))
            t.insert(tk.END, f"{when}  ·  {who}", ("when", tag))
            agent_name = str(msg.get("agent_name") or "")
            if agent_name:
                t.insert(tk.END, f"  ·  {agent_name.upper()}", ("who", tag))
            if msg.get("shot"):
                t.insert(tk.END, "  📷", ("shot", tag))
            t.insert(tk.END, "\n", tag)
            text, spans = snips[idx]
            if str(msg.get("kind") or "") == "quote":
                text = "📎 " + text
                spans = [(a + 2, b + 2) for a, b in spans]
            start = t.index(tk.END + "-1c")
            t.insert(tk.END, text, ("body", "snip", tag))
            for a, b in spans:
                t.tag_add("hit", f"{start}+{a}c", f"{start}+{b}c")
            t.insert(tk.END, "\n\n", tag)
            t.tag_bind(tag, "<Button-1>", lambda _e, i=idx: self._archive_open(i))
            t.tag_bind(f"box{idx}", "<Button-1>",
                       lambda _e, tg=tag: self._archive_toggle(tg))
            t.tag_bind(tag, "<Enter>", lambda _e: t.configure(cursor="hand2"))
            t.tag_bind(tag, "<Leave>", lambda _e: t.configure(cursor="arrow"))
        t.tag_raise("hit")                           # подсветка поверх фона выделения
        t.configure(state=tk.DISABLED)
        self._archive_highlight()

    # -- подробный вид находки ----------------------------------------------
    def _archive_view(self) -> tk.Text:
        return self.arch_detail if self._archive_detail_idx >= 0 else self.arch_text

    def _archive_yview(self, *args) -> None:
        self._archive_view().yview(*args)

    def _archive_messages(self, agent: str) -> list[dict]:
        cache = getattr(self, "_archive_ctx", None)
        if cache is None:
            cache = self._archive_ctx = {}
        if agent not in cache:
            try:
                cache[agent] = orion.archive_messages(agent)
            except Exception:  # noqa: BLE001
                cache[agent] = []
        return cache[agent]

    def _archive_open(self, idx: int) -> str:
        """Клик по находке: сообщение целиком в разговоре, слово подсвечено."""
        if not (0 <= idx < len(self._archive_rows)):
            return "break"
        if self._archive_detail_idx < 0:
            self._archive_list_y = self.arch_text.yview()[0]
            self.arch_text.pack_forget()
            self.arch_nav.pack(fill=tk.X, before=self.arch_abody, pady=(0, px(4)))
            self.arch_detail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._archive_detail_idx = idx
        msg = self._archive_rows[idx]
        mid = str(msg.get("id") or "")
        window, pos = archive_view.context(self._archive_messages(str(msg.get("agent") or "")),
                                           mid) if mid else ([], -1)
        if pos < 0:
            window, pos = [msg], 0
        d = self.arch_detail
        d.configure(state=tk.NORMAL)
        d.delete("1.0", tk.END)
        self._archive_images = []
        first_hit = None
        for n, m in enumerate(window):
            own = n == pos
            when = orion.when_text(float(m.get("ts") or 0.0))
            who = orion.role_name(str(m.get("role") or "")).upper()
            d.insert(tk.END, f"{when}  ·  {who}\n", ("who" if own else "dim",)
                     + (("focus",) if own else ()))
            text = str(m.get("text") or "")
            start = d.index(tk.END + "-1c")
            d.insert(tk.END, text + "\n", ("body", "focus") if own else ("dim",))
            if own:
                for a, b in archive_view.hit_spans(text, getattr(self, "_arch_words", ())):
                    d.tag_add("hit", f"{start}+{a}c", f"{start}+{b}c")
                    if first_hit is None:
                        first_hit = f"{start}+{a}c"
                        d.tag_add("hitcur", f"{start}+{a}c", f"{start}+{b}c")
                if m.get("shot"):
                    self._archive_detail_shot(str(m["shot"]))
                anchor = start
            d.insert(tk.END, "\n")
        d.tag_raise("hit")
        d.tag_raise("hitcur")
        d.configure(state=tk.DISABLED)
        d.see(first_hit or anchor)
        d.focus_set()
        self.arch_pos.configure(text=_t("Находка {0} из {1}").format(
            idx + 1, len(self._archive_rows)))
        self._archive_detail_mark()
        return "break"

    def _archive_detail_shot(self, path: str) -> None:
        pic_path = Path(path)
        pic = shots.thumbnail(pic_path, size=160) if pic_path.is_file() else None
        if pic is None:
            return
        try:
            from PIL import ImageTk
            photo = ImageTk.PhotoImage(pic, master=self.arch_detail)
        except Exception:  # noqa: BLE001
            return
        self._archive_images.append(photo)
        name = self.arch_detail.image_create(tk.END, image=photo, padx=px(10), pady=px(4))
        self.arch_detail.insert(tk.END, "\n")
        self.arch_detail.tag_bind(name, "<Button-1>",
                                  lambda _e, p=str(pic_path): self._open_shot(p))

    def _archive_step(self, delta: int) -> str:
        if self._archive_detail_idx >= 0 and self._archive_rows:
            nxt = self._archive_detail_idx + delta
            if 0 <= nxt < len(self._archive_rows):
                self._archive_open(nxt)
        return "break"

    def _archive_back(self) -> str:
        if getattr(self, "_archive_detail_idx", -1) < 0:
            return "break"
        self._archive_detail_idx = -1
        self.arch_detail.pack_forget()
        self.arch_nav.pack_forget()
        self.arch_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.arch_text.yview_moveto(getattr(self, "_archive_list_y", 0.0))
        return "break"

    def _archive_detail_pick(self) -> None:
        if self._archive_detail_idx >= 0:
            self._archive_toggle(f"pick{self._archive_detail_idx}")
            self._archive_detail_mark()

    def _archive_detail_mark(self) -> None:
        mid = self._archive_tag_ids.get(f"pick{self._archive_detail_idx}", "")
        on = mid in self._archive_picked
        try:
            self.arch_pick_btn.set_text(_t("✓ ОТМЕЧЕНО") if on else _t("ОТМЕТИТЬ ДЛЯ ПЕРЕНОСА"))
        except Exception:  # noqa: BLE001
            pass

    def _archive_detail_key(self, e) -> str | None:
        key = str(getattr(e, "keysym", "")).lower()
        if getattr(e, "keycode", 0) == 67 or key in ("c", "cyrillic_es"):
            try:
                text = self.arch_detail.get(tk.SEL_FIRST, tk.SEL_LAST)
            except tk.TclError:
                return "break"
            self.clipboard_clear()
            self.clipboard_append(text)
            return "break"
        return None

    def _archive_shot(self, path: str, tag: str) -> None:
        """Миниатюра снимка в найденном сообщении: клик открывает картинку целиком."""
        pic_path = Path(path)
        pic = shots.thumbnail(pic_path, size=72) if pic_path.is_file() else None
        if pic is None:
            self.arch_text.insert(tk.END, _t("📷 снимок не открылся: {0}")
                                  .format(pic_path.name) + "\n", "shot")
            return
        try:
            from PIL import ImageTk
            photo = ImageTk.PhotoImage(pic, master=self.arch_text)
        except Exception:  # noqa: BLE001
            return
        self._archive_images.append(photo)
        name = self.arch_text.image_create(tk.END, image=photo, padx=px(4), pady=px(4),
                                           align="bottom")
        self.arch_text.insert(tk.END, "\n")
        self.arch_text.tag_add(tag, name)
        self.arch_text.tag_bind(name, "<Button-1>", lambda _e, p=str(pic_path): self._open_shot(p))

    def _archive_toggle(self, tag: str) -> str:
        """Клик по сообщению — взять его в перенос или снять с переноса."""
        mid = self._archive_tag_ids.get(tag, "")
        if not mid:
            return "break"
        if mid in self._archive_picked:
            self._archive_picked.remove(mid)
        else:
            self._archive_picked.append(mid)
        self._archive_highlight()
        return "break"

    def _archive_highlight(self) -> None:
        picked = set(self._archive_picked)
        t = self.arch_text
        t.configure(state=tk.NORMAL)
        for tag, mid in self._archive_tag_ids.items():
            on = mid in picked
            t.tag_configure(tag, background=BG2 if on else PANEL)
            mark = "chk" + tag[4:]
            if mark in t.mark_names() and t.get(mark) != ("☑" if on else "☐"):
                t.delete(mark)
                t.insert(mark, "☑" if on else "☐", ("chk", "box" + tag[4:]))
        t.configure(state=tk.DISABLED)
        label = _t("Найдено: {0}").format(len(self._archive_rows))
        if picked:
            label += " · " + _t("Выделено: {0}").format(len(picked))
        self.arch_found.configure(text=label)

    def _archive_pick_all(self) -> None:
        self._archive_picked = [str(m.get("id") or "") for m in self._archive_rows
                                if m.get("id")]
        self._archive_highlight()

    def _archive_unpick(self) -> None:
        self._archive_picked = []
        self._archive_highlight()

    def _archive_picked_rows(self) -> list[dict]:
        """Выделенные сообщения в том порядке, как они шли в разговоре."""
        if not self._archive_picked:
            return []
        wanted = set(self._archive_picked)
        return [m for m in reversed(self._archive_rows) if str(m.get("id") or "") in wanted]

    def _quote_text(self, msg: dict) -> str:
        """Строка цитаты из архива: бортовое время, автор, текст."""
        return (f"{orion.when_text(float(msg.get('ts') or 0.0))} · "
                f"{orion.role_name(str(msg.get('role') or ''))}: {msg.get('text', '')}")

    def _archive_to_chat(self) -> None:
        """Перенести выделенное в чат: реплики встают в разговор и уходят Ориону."""
        rows = self._archive_picked_rows()
        if not rows:
            self._hint(_t("Сначала выделите сообщения в архиве — щёлкните по ним"), AMBER)
            return
        rec = self._rec()
        quotes = [self._quote_text(m) for m in rows]
        for quote in quotes:
            orion.remember(rec["id"], "system", quote, kind="quote")
        self._pending_quotes = quotes
        self._render_feed()
        self.show_tab("chat")
        self._hint(_t("Из архива перенесено сообщений: {0}. Напишите, что с ними делать.")
                   .format(len(rows)), GREEN)

    def _archive_to_input(self) -> None:
        """Скопировать выделенное в поле ввода — править и отправлять как своё."""
        rows = self._archive_picked_rows()
        if not rows:
            self._hint(_t("Сначала выделите сообщения в архиве — щёлкните по ним"), AMBER)
            return
        self.entry.set("\n\n".join(self._quote_text(m) for m in rows))
        self.show_tab("chat")
        self._hint(_t("Текст из архива — в поле ввода: правьте и отправляйте"), CYAN)

    # -- подвкладки --------------------------------------------------------
    def tab_keys(self) -> list[str]:
        return [k for k, _ in self.TABS]

    def show_tab(self, key: str) -> None:
        if key not in self.tabs:
            key = self.tabs and next(iter(self.tabs))
        self.current_tab = key
        page, btn = self.tabs[key]
        # в ячейке только текущая вкладка: высота отсека = её высота, а не самой высокой
        for k, (p, _b) in self.tabs.items():
            if k != key:
                p.grid_remove()
        page.grid()
        page.tkraise()
        for k, b in self.tab_btns.items():
            b.set_active(k == key)
        hook = getattr(self.app, "_alt_page_hook", None)
        if callable(hook):
            hook()
        if key == "archive" and not self._archive_rows:
            self._archive_search()        # архив открыли — сразу показываем свежее

    def page_help_key(self) -> str:
        return "orion." + getattr(self, "current_tab", "chat")

    def on_key(self, _e) -> None:
        """Клавиши раздела: поле ввода само принимает набор и Enter."""

    def focus_input(self) -> None:
        if self.entry.state() != "disabled":
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
        self._feed_images = []          # Tk не держит ссылки на картинки сам
        if not ok:
            self.text.insert(tk.END, _t("OpenCode не найден: Орион на связи не будет. "
                                        "Установите opencode и перезапустите корабль.") + "\n", "hint")
        if not msgs:
            self.text.insert(tk.END, _t("Канал свободен. Скажите Ориону первое слово — "
                                        "письменно или голосом.") + "\n", "hint")
        self._msg_texts = []
        for m in msgs:
            when = orion.when_text(float(m.get("ts", 0.0)))
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
            elif m.get("kind") == "quote":
                name = "📎 " + name
            # Визуальное разделение реплик
            self.text.insert(tk.END, "─" * 40 + "\n", "separator")
            self.text.insert(tk.END, prefix + name, tag)
            self.text.insert(tk.END, f"  {when}\n", "time")
            mtag = f"msg{len(self._msg_texts)}"
            self._msg_texts.append(str(m.get("text", "")))
            self.text.insert(tk.END, f"{m.get('text', '')}\n", ("body", mtag))
            self._insert_shot(m.get("shot"))
        self.text.configure(state=tk.DISABLED)
        self.text.see(tk.END)
        self._render_strip(msgs, rec)
        self._refresh_suggest(msgs)

    def _insert_shot(self, path: str | None) -> None:
        """Миниатюра снимка под репликой. Клик — открыть снимок целиком."""
        if not path:
            return
        pic_path = Path(path)
        if not pic_path.is_file():
            self.text.insert(tk.END, _t("📷 снимок потерян: {0}").format(pic_path.name) + "\n",
                             "time")
            return
        pic = shots.thumbnail(pic_path)
        if pic is None:
            self.text.insert(tk.END, _t("📷 снимок не открылся: {0}").format(pic_path.name) + "\n",
                             "time")
            return
        try:
            from PIL import ImageTk
            photo = ImageTk.PhotoImage(pic, master=self.text)
        except Exception:  # noqa: BLE001
            return
        self._feed_images.append(photo)
        name = self.text.image_create(tk.END, image=photo, padx=px(4), pady=px(6), align="bottom")
        self.text.insert(tk.END, "\n")
        self.text.tag_bind(name, "<Button-1>", lambda _e, p=str(pic_path): self._open_shot(p))

    def _refresh_suggest(self, msgs: list[dict] | None = None) -> None:
        """Пульт учится на переписке: подсказки из того, что пилот уже писал."""
        if not hasattr(self, "entry"):
            return
        if msgs is None:
            msgs = orion.history(self._rec()["id"])["messages"]
        if len(msgs) == self._suggest_seen:
            return
        self._suggest_seen = len(msgs)
        texts = [str(m.get("text") or "") for m in msgs[-400:] if m.get("role") == "pilot"]
        texts += [str(t.get("text") or "") for t in orion.tasks()[-100:]]
        self.suggester = Suggester(dictionary_from(texts))
        self.entry.set_suggester(self.suggester)

    def _render_strip(self, msgs: list[dict], rec: dict) -> None:
        """Живая линия: последняя реплика пилота и последний ответ Ориона."""
        last_pilot = next((m for m in reversed(msgs) if m.get("role") == "pilot"), None)
        last_orion = next((m for m in reversed(msgs) if m.get("role") == "orion"), None)
        name = str(rec.get("name") or "ОРИОН").upper()
        def _clip(t: str, n: int = 280) -> str:
            t = " ".join(str(t).split())
            return t if len(t) <= n else t[:n - 1].rstrip() + "…"
        self.strip_pilot.configure(text=(_t("ПИЛОТ: {0}").format(_clip(last_pilot["text"]))
                                         if last_pilot else _t("ПИЛОТ: —")))
        self.strip_orion.configure(text=(f"{name}: {_clip(last_orion['text'])}" if last_orion
                                         else _t("{0}: слушаю, пилот").format(name)))

    # -- доска: скрыта или открыта -----------------------------------------
    def _set_board(self, visible: bool) -> None:
        """Показать доску переписки или свернуть её в живую линию."""
        self.board_visible = visible
        if visible:
            self.strip.pack_forget()
            self.board.pack(fill=tk.BOTH, expand=True, after=self.bottom)
            self.board_btn.set_text(_t("ДОСКА: ОТКРЫТА"))
            self.board_btn.set_color(GREEN)
        else:
            self.board.pack_forget()
            self.strip.pack(fill=tk.BOTH, expand=True, after=self.bottom)
            self.board_btn.set_text(_t("ДОСКА: СКРЫТА"))
            self.board_btn.set_color(AMBER)

    def _toggle_board(self) -> None:
        self._set_board(not self.board_visible)

    def listen(self) -> None:
        """Слушать пилота (кнопка ОРИОН / Home): голос превращается в обращение."""
        self.show_tab("chat")
        if not self.mic.busy:
            self.mic.start()

    def _mic_status(self, text: str, color=None) -> None:
        """Индикатор микрофона: показывает что микрофон работает."""
        color = MUTED if color is None else color  # токен скина — в момент вызова, не при импорте
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
    # -- шкала работы --------------------------------------------------------
    def _build_activity(self, parent) -> None:
        """Панель работы: по строке на каждую задачу агента (план → процент → цвет).

        Проценты — из плана самого агента (`_orion/tasks/<id>.json`, протокол в
        `stamina/task_progress.py`): вес закрытых шагов к весу всех. Старый доклад
        `_orion/progress.json` — ещё одна строка. Нет докладов — одна строка
        «работаю» с честной оценкой по времени (замирает у 97) или «свободен».
        """
        self.work_box = tk.Frame(parent, bg=BG)
        self.work_box.pack(fill=tk.X, pady=(px(2), 0))
        self.work_row = tk.Frame(self.work_box, bg=BG)
        self.work_label = _label(self.work_row, "", fg=MUTED, size=9, bg=BG, anchor="w")
        self.work_label.pack(side=tk.LEFT)
        self.work_bar = tk.Canvas(self.work_row, width=px(170), height=px(10), bg=BG,
                                  highlightthickness=0, bd=0)
        self.work_bar.pack(side=tk.LEFT, padx=(px(8), px(8)))
        self.work_pct = _label(self.work_row, "", fg=MUTED, size=9, bg=BG, anchor="w", width=4)
        self.work_pct.pack(side=tk.LEFT)
        self.work_row.pack(fill=tk.X)
        self.task_rows: list[dict] = []   # пул строк задач: {frame, label, bar, pct, key}
        self._work_started = 0.0
        self._work_tick = 0
        self._report: dict = {}          # старый доклад v1 (читаем не чаще раза в секунду)
        self._tasks: list[dict] = []     # задачи v2 + v1
        self._report_read = 0.0
        self._tick_activity()

    def _report_view(self) -> dict:
        """Доклады агента о работе. Файлы на диске — читаем не чаще раза в секунду."""
        now = time.time()
        if now - self._report_read >= 1.0:
            self._report_read = now
            try:
                self._report = orion.progress_view(now)
                self._tasks = tprog.active(now, legacy=orion.read_progress())
            except OSError:               # диск отвлёкся — показываем, что было
                self._report, self._tasks = {}, []
        return self._report

    def _time_percent(self) -> int:
        """Оценка хода по времени — когда агент не оставил доклада."""
        spent = max(0.0, time.time() - self._work_started)
        return min(97, int(99 * (1 - math.exp(-spent / 40.0))) + 1)

    def _task_row(self, i: int) -> dict:
        while len(self.task_rows) <= i:
            fr = tk.Frame(self.work_box, bg=BG)
            bar = tk.Canvas(fr, width=px(170), height=px(10), bg=BG, highlightthickness=0, bd=0)
            pct = _label(fr, "", fg=MUTED, size=9, bg=BG, anchor="e", width=5)
            lab = _label(fr, "", fg=MUTED, size=9, bg=BG, anchor="w")
            pct.pack(side=tk.RIGHT)
            bar.pack(side=tk.RIGHT, padx=(px(8), px(4)))
            lab.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.task_rows.append({"frame": fr, "label": lab, "bar": bar, "pct": pct,
                                   "key": None, "shown": False})
        return self.task_rows[i]

    def _task_text(self, t: dict, spin: str) -> tuple[str, str]:
        title = str(t.get("title") or "")
        if len(title) > 60:
            title = title[:59] + "…"
        state = t.get("state")
        if state == "done":
            return "✓ " + title, GREEN
        if state in ("failed", "stopped"):
            word = _t("сорвалась") if state == "failed" else _t("остановлена")
            return "✕ " + title + " · " + word, AMBER
        if not t.get("total"):
            return f"{spin} " + title + " · " + _t("оцениваю объём…"), CYAN
        title += " · " + _t("шаг {0} из {1}").format(t["done"], t["total"])
        if t.get("stale"):            # агент молчит — пилоту честно об этом
            return "⚠ " + title + " · " + _t("доклад не обновлялся"), AMBER
        return f"{spin} " + title, CYAN

    def _show_tasks(self, tasks: list[dict], spin: str) -> None:
        for i, t in enumerate(tasks):
            row = self._task_row(i)
            text, fg = self._task_text(t, spin)
            pct = int(t.get("percent") or 0)
            key = (text, fg, pct)
            if key != row["key"]:
                row["key"] = key
                row["label"].configure(text=text, fg=fg)
                row["pct"].configure(text=f"{pct}%", fg=tprog.color_for(pct))
                self._draw_bar(row["bar"], pct, tprog.color_for(pct))
            if not row["shown"]:
                row["frame"].pack(fill=tk.X)
                row["shown"] = True
        for row in self.task_rows[len(tasks):]:
            if row["shown"]:
                row["frame"].pack_forget()
                row["shown"] = False

    def _tick_activity(self) -> None:
        """Шаг панели: строки задач по их планам, оценка по времени или «свободен»."""
        try:
            self._report_view()
            busy = getattr(self, "_busy", False)
            spin = "⣾⣽⣻⢿⡿⣟⣯⣷"[self._work_tick % 8]
            self._work_tick += 1
            tasks = self._tasks
            self._show_tasks(tasks, spin)
            working = any(t.get("state") not in tprog.FINAL for t in tasks)
            if busy and not self._work_started:
                self._work_started = time.time()
            if not busy:
                self._work_started = 0.0
            if tasks and (working or not busy):
                if self.work_row.winfo_manager():
                    self.work_row.pack_forget()
            else:
                if not self.work_row.winfo_manager():
                    self.work_row.pack(fill=tk.X, before=self.task_rows[0]["frame"]
                                       if self.task_rows else None)
                if busy:
                    pct = self._time_percent()
                    self.work_label.configure(text=f"{spin} " + _t("ОРИОН РАБОТАЕТ"), fg=CYAN)
                    self.work_pct.configure(text=f"{pct}%", fg=tprog.color_for(pct))
                    self._draw_work_bar(pct, tprog.color_for(pct))
                else:
                    self.work_label.configure(text="○ " + _t("ОРИОН СВОБОДЕН — можно обращаться"),
                                              fg=GREEN)
                    self.work_pct.configure(text="")
                    self._draw_work_bar(0, LINE)
        except tk.TclError:          # окно закрыли — шкале больше некуда рисовать
            return
        self.after(140, self._tick_activity)

    def _draw_work_bar(self, pct: int, color: str) -> None:
        self._draw_bar(self.work_bar, pct, color)

    def _draw_bar(self, bar, pct: int, color: str) -> None:
        w = bar.winfo_width()
        w = w if w > 1 else px(170)
        h = bar.winfo_height()
        h = h if h > 1 else px(10)
        bar.delete("all")
        bar.create_rectangle(0, 0, w, h, fill=BG2, outline=LINE)
        fill = int((w - 2) * max(0, min(100, pct)) / 100)
        if fill > 0:
            bar.create_rectangle(1, 1, 1 + fill, h - 1, fill=color, outline="")

    def _hint(self, text: str, color=None) -> None:
        color = MUTED if color is None else color  # токен скина — в момент вызова, не при импорте
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
        self.entry.insert_text(text)
        self.send_btn.set_enabled(True)

    def _clear_input(self) -> None:
        """Опустошить поле набора и снять приложенные снимки — только после отправки."""
        self.entry.clear()
        self._draft_text = ""
        self._pending_shots.clear()
        self._refresh_shot_row()

    def _draft_note(self, text: str) -> None:
        """Пилот на минуту замолчал — запомнить черновик (для «Орион видит черновик»)."""
        self._draft_text = text

    def _send(self) -> None:
        rec = self._rec()
        text = " ".join(self.entry.get().split())
        shot_paths = list(getattr(self, "_pending_shots", []))
        if not text and shot_paths:
            text = _t("Посмотри снимок.")
        # Пилот написал путь к снимку словами — забираем файл внутрь корабля,
        # иначе агент не имеет права читать чужую папку (OneDrive, рабочий стол)
        typed = shots.image_paths_in(text)
        if typed:
            for taken in shots.adopt(typed):
                if str(taken) not in shot_paths:
                    shot_paths.append(str(taken))
        if self._busy:
            self._hint(_t("Орион ещё думает — дождитесь ответа или нажмите ■"), AMBER)
            return
        if not text:
            return
        # «@grok, что думаешь?» — зовём гостя по имени, не переключая вкладки руками
        who, rest = orion.split_mention(text)
        if who and who != rec["id"] and orion.set_active(who):
            self.refresh()
            rec = self._rec()
            text = rest
            self._hint(_t("Обращаюсь к {0}").format(str(rec.get("name") or who).upper()), CYAN)
            if not text:
                return
        # короткий разговор о записи задания — «да»/«нет» или сам текст задания
        if self._await_task:
            self._clear_input()
            self._take_task(text)
            return
        if self._pending_task and orion.is_yes(text):
            self._clear_input()
            self._confirm_task(True)
            return
        if self._pending_task and orion.is_no(text):
            self._clear_input()
            self._confirm_task(False)
            return
        # Связь проверяем ДО того, как стереть поле: иначе при отсутствии OpenCode
        # набранный текст исчезал впустую (жалоба «куда делся текст из окна»)
        ok, _exe = orion.available()
        if not ok:
            self._hint(_t("OpenCode не найден: установите opencode и перезапустите корабль.")
                       + " " + _t("Текст остался в поле."), RED)
            return
        self._clear_input()
        orion.remember(rec["id"], "pilot", text,
                       shot=shot_paths[0] if shot_paths else "")
        self._sent_log.append(text)
        if len(self._sent_log) > 50:
            del self._sent_log[:-50]
        self.entry.set_history(self._sent_log)
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
        self._run(rec, text, second=False, shot=shot_paths)

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
            self.ask_row.pack(side=tk.TOP, fill=tk.X, pady=(px(4), 0), before=self.input_row)
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
        row = orion.add_task(task, author=str((self.app.pilot or {}).get("callsign") or ""),
                             agent=rec["id"])
        orion.remember(rec["id"], "system", _t("📌 ЗАДАНИЕ В ДОКУМЕНТ: {0}").format(task),
                       kind="task")
        self._set_board(True)          # доска чата открывается — пилот видит запись
        self._render_feed()
        self.ask_label.configure(text="")
        self._hint(_t("Задание записано в документ борта"), GREEN)
        if self._answer_voice and tts.available():
            tts.speak(_t("Записал в документ заданий"), role="dev")
        if not self._busy:
            # Пожелание пилота + карта места → ТЗ → подчинённому исполнителю (в фон)
            brief = self._task_brief_for(task)
            self._marks_sent = marks.last_id()
            self._dispatch(rec, brief, str(row.get("id") or ""))

    def _dispatch(self, rec: dict, brief: str, task_id: str = "") -> None:
        """Отдать ТЗ исполнителю в фоне: он работает, а мы с пилотом разговариваем."""
        if getattr(self, "_job_busy", False):
            self._hint(_t("Исполнитель ещё работает — дождитесь его доклада"), AMBER)
            return
        self._job_busy = True
        # Строка на панели задач: исполнитель сам распишет план и закроет шаги.
        self._exec_task = "exec-" + (task_id or str(int(time.time())))
        try:
            gist = (brief.splitlines() or [""])[0]
            for line in brief.splitlines()[3:6]:
                if line.strip() and not line[:2].strip().rstrip(".").isdigit():
                    gist = line.strip()
                    break
            tprog.plan(self._exec_task, _t("Исполнитель: {0}").format(gist[:80]),
                       state="planning")
            brief = brief + "\n" + tprog.brief_block(self._exec_task)
            self._report_read = 0.0
        except OSError:
            pass
        ctx = self._context()
        session = orion.profile_session(rec["id"], orion.EXECUTOR_PROFILE) or ""
        threading.Thread(target=self._executor_worker,
                         args=(rec, brief, session, ctx, task_id), daemon=True).start()
        self._hint(_t("Исполнитель взял ТЗ. Разговариваем дальше — доложу, когда закончит."), GREEN)

    def _executor_worker(self, rec: dict, brief: str, session: str, ctx: str,
                         task_id: str) -> None:
        try:
            res = orion.run_profile(rec, brief, profile=orion.EXECUTOR_PROFILE,
                                    context=ctx, session=session)
        except Exception as exc:  # noqa: BLE001
            res = orion.Result(error="spawn", detail=str(exc), profile=orion.EXECUTOR_PROFILE)
        self._queue.put(("executor", res, rec, task_id))

    def _on_executor(self, res, rec: dict, task_id: str) -> None:
        """Доклад исполнителя: пришёл отдельным событием, чат при этом не запирался."""
        self._job_busy = False
        try:
            tprog.finish(getattr(self, "_exec_task", "") or "exec",
                         "stopped" if res.error == "stopped" else ("failed" if res.error else "done"))
            self._report_read = 0.0
        except OSError:
            pass
        if res.error == "stopped":
            note = _t("Исполнитель остановлен — задание осталось открытым")
            orion.remember(rec["id"], "system", note)
            self._render_feed()
            self._hint(note, AMBER)
            return
        if res.error:
            note = self._error_text(res)
            orion.remember(rec["id"], "system", note)
            self._render_feed()
            self._hint(note, RED)
            return
        if res.reply:
            orion.remember(rec["id"], "orion", res.reply, kind="executor")
        if task_id:
            orion.close_task(task_id, status="done")
        head = (res.reply or "").strip().splitlines()
        short = head[0][:160] if head else _t("без отчёта")
        note = _t("Исполнитель закончил: {0}").format(short)
        orion.remember(rec["id"], "system", note)
        self._render_feed()
        self._hint(note, GREEN)
        if self._answer_voice and tts.available():
            tts.speak(_t("Исполнитель закончил работу"), role="dev")
        try:
            self.app.set_status(note, GREEN)
        except Exception:  # noqa: BLE001
            pass

    def _task_brief_for(self, wish: str) -> str:
        """Собрать ТЗ для исполнителя: отсек, подвкладка, пометки мышью."""
        zone = ""
        try:
            zone = self.app._zone_title(getattr(self.app, "current", ""))
        except Exception:  # noqa: BLE001
            zone = str(getattr(self.app, "current", "") or "")
        brief = orion.task_brief(
            wish,
            marks_block=marks.context_block(0),
            zone=zone,
            subtab=str(getattr(self, "current_tab", "") or ""),
            author=str((self.app.pilot or {}).get("callsign") or ""),
        )
        rec = self._rec()
        orion.remember(rec["id"], "system",
                       _t("📐 ТЗ для исполнителя: {0}").format(brief.splitlines()[0]),
                       kind="task")
        return brief

    def _run(self, rec: dict, text: str, *, second: bool, shot: list[str] | None = None,
             session: str = "", profile_hint: str = "") -> None:
        first, follow = orion.profiles(rec)
        # Капитан (commander) — сразу полные права, без запроса разрешения
        if profile_hint:
            profile = profile_hint           # явно: задание уходит исполнителю
        elif rec.get("access") == "commander" and not second:
            profile = follow or first
        else:
            profile = (follow or first) if second else first
        self._busy = True
        self._work_started = time.time()
        self.send_btn.set_enabled(False)
        self.stop_btn.set_enabled(True)
        self._show_stop(True)
        self._pending = (rec, text)
        if second:
            self._hide_permission()
        self._hint(_t("Орион думает… (■ остановит его, чтобы вы уточнили задачу)"), AMBER)
        ctx = self._context()
        # При втором проходе — передаём разрешение в промпт
        if second:
            text = _t("РАЗРЕШЕНИЕ: Командир разрешил изменения. Выполни работу целиком.") + "\n\n" + text
        # Снимки пилота: путь в запросе — агент читает файл своим инструментом
        notes = "\n".join(orion.shot_note(p) for p in (shot or []) if p)
        if notes:
            text = notes + "\n\n" + text
        # Реплики из архива: агент видит их как прошлые сообщения борта, а не как задание
        if self._pending_quotes:
            text = (_t("ИЗ АРХИВА — прошлые сообщения борта:") + "\n"
                    + "\n".join(self._pending_quotes) + "\n\n" + text)
            self._pending_quotes = []
        # Первый проход — сессия профиля recon, второй — сессия Командира
        if not session and not second:
            base = profile if profile_hint else "orion-recon"
            session = orion.profile_session(rec["id"], base) or orion.last_session(rec["id"])
        threading.Thread(target=self._worker,
                         args=(rec, text, profile, session, ctx, second), daemon=True).start()

    def _show_stop(self, on: bool) -> None:
        """«■ СТОП» появляется только пока агент работает — в покое не пугает пилота."""
        if on and not self.stop_btn.winfo_manager():
            self.stop_btn.pack(side=tk.RIGHT, padx=(px(6), 0), before=self.send_btn)
        elif not on and self.stop_btn.winfo_manager():
            self.stop_btn.pack_forget()

    def _stop_work(self) -> None:
        """Квадратик «стоп»: оборвать агента на середине — пилот хочет уточнить задачу."""
        rec = self._rec()
        if orion.stop_run(rec["id"]):
            self._hint(_t("Останавливаю… сейчас можно дописать уточнение"), AMBER)
            self.entry.focus_set()
        else:
            self.stop_btn.set_enabled(False)
            self._show_stop(False)
            self._hint(_t("Орион уже не работает"), MUTED)

    # -- вид чата: разговор или ремонтный отсек ------------------------------
    def _mode_title(self) -> str:
        return _t("РЕЖИМ: ПРО") if getattr(self, "ui_mode", "chat") == "pro" else _t("РЕЖИМ: ЧАТ")

    def _toggle_mode(self) -> None:
        """Пилот выбирает вид: разговорный чат или «ремонтный отсек» для работы руками."""
        self.ui_mode = "pro" if self.ui_mode == "chat" else "chat"
        self._apply_mode()
        store = getattr(self.app, "store", None)
        if store is not None:
            try:
                store.settings["orion_ui"] = self.ui_mode
                store.save_settings()
            except Exception:  # noqa: BLE001
                pass
        self._hint(_t("Вид: {0}").format(_t("РЕМОНТНЫЙ ОТСЕК") if self.ui_mode == "pro"
                                         else _t("ЧАТ")), CYAN)

    def _apply_mode(self) -> None:
        """Ремонтный отсек: моноширинный вывод, `Ctrl+Enter`, история по `↑`."""
        if not hasattr(self, "mode_btn"):
            return
        pro = self.ui_mode == "pro"
        self.mode_btn.set_text(self._mode_title())
        mono = ("Consolas", 10) if pro else theme.font(10)
        for widget, tags in ((self.text, ("body", "orion", "pilot", "system", "hint")),):
            try:
                widget.configure(font=mono)
                for tag in tags:
                    widget.tag_configure(tag, font=mono)
            except tk.TclError:
                pass
        try:
            self.entry.set_ctrl_enter(pro)
            self.entry.set_history(self._sent_log)
        except tk.TclError:
            pass
        hint = getattr(self, "composer_hint", None)
        if hint is not None:
            hint.configure(text=(
                _t("Ctrl+Enter — отправить · Enter — новая строка · ↑ — история")
                if pro else
                _t("Enter — отправить · Shift+Enter — новая строка · 📎 — картинка")))

    def _worker(self, rec: dict, text: str, profile: str, session: str, ctx: str,
                second: bool) -> None:
        try:
            res = orion.run_profile(rec, text, profile=profile, context=ctx, session=session)
        except Exception as exc:  # noqa: BLE001
            res = orion.Result(error="spawn", detail=str(exc), profile=profile)
        self._queue.put(("answer", res, rec, second))

    def _stop_thinking(self) -> None:
        """Остановить зависший поток Орина."""
        self._busy = False
        self.send_btn.set_enabled(True)
        self._show_stop(False)
        self._hide_permission()
        self._hint(_t("Орион остановлен. Пopробуйте ещё раз."), MUTED)

    def _emergency_call(self) -> None:
        """Экстренная связь: остановить зависший процесс и уведомить агента."""
        rec = self._rec()
        self._busy = False
        self.send_btn.set_enabled(True)
        self._show_stop(False)
        self._hide_permission()
        # Останавливаем зависший процесс
        orion.stop_run(rec["id"])
        self._hint(_t("Экстренная связь: Орион уведомлён, что вы ждёте ответа"), AMBER)
        # Отправляем короткий сигнал агента
        emergency = _t("ЭКСТРЕННАЯ СВЯЗЬ: Капитан ждёт ответа. Доложи что ты делаешь.")
        orion.remember(rec["id"], "system", emergency)
        self._render_feed()
        self._run(rec, emergency, second=False)

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
        tts.speak(res.reply, role="dev")

    def _on_answer(self, res, rec: dict, second: bool) -> None:
        self._busy = False
        self.send_btn.set_enabled(True)
        self.stop_btn.set_enabled(False)
        self._show_stop(False)
        if res.error == "stopped":
            # остаток ответа не выбрасываем: пилот увидит, на чём Орион остановился
            if res.reply:
                orion.remember(rec["id"], "orion", res.reply, session=res.session)
            note = _t("Остановлено пилотом — уточните задачу, разговор продолжится с того же места")
            orion.remember(rec["id"], "system", note)
            self._render_feed()
            self._hint(note, AMBER)
            self.entry.focus_set()
            return
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
        # Капитан (commander) — полные права сразу, без запроса разрешения
        if res.needs_permission and not second and rec.get("access") != "commander":
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
            self.perm_row.pack(side=tk.TOP, fill=tk.X, pady=(px(4), 0), before=self.input_row)

    def _hide_permission(self) -> None:
        if self.perm_row.winfo_manager():
            self.perm_row.pack_forget()

    def _approve(self) -> None:
        """Командир разрешил — второй проход: Орион делает работу целиком."""
        if self._pending is None or self._busy:
            return
        rec, text = self._pending
        # Второй проход продолжает ту же сессию, но профилем Командира
        first_session = orion.last_session(rec["id"])
        orion.remember(rec["id"], "system", _t("Командир разрешил действия"))
        self._render_feed()
        self._run(rec, text, second=True, session=first_session)

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
        # Места, которые пилот показал правой кнопкой мыши: агенту нужен адрес,
        # а не «где-то в интерфейсе». Отдаём только новые пометки — прежние уже в истории.
        mark_block = marks.context_block(getattr(self, "_marks_sent", 0))
        if mark_block:
            ctx = (ctx + "\n\n" + mark_block) if ctx else mark_block
            self._marks_sent = marks.last_id()
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
            tts.speak(chunk, role="dev")
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
            tts.speak(chunk, role="dev")
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
                elif ev[0] == "executor":
                    self._on_executor(ev[1], ev[2], ev[3])
        except queue.Empty:
            pass
        try:
            self.mic.poll()
        except Exception:  # noqa: BLE001
            pass
        self.after(140, self._pump)
