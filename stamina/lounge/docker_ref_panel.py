"""Панель-учебник Docker: темы, прокручиваемый список команд, пример и кнопки.

Открывается по F2 или кнопкой «УЧЕБНИК» прямо в игре. Команду можно положить
в строку ввода («→ В СТРОКУ») или сразу выполнить в песочнице («▶ ВЫПОЛНИТЬ»).
Содержимое — `docker_reference`, здесь только интерфейс.
"""
from __future__ import annotations

from stamina.i18n import t as _t

import tkinter as tk
from typing import Callable

from stamina import theme
from stamina.hud import HudButton
from stamina.theme import AMBER, BG, BG2, CYAN, GREEN, MUTED, TEXT, px

from . import docker_reference as ref
from .ref_list import ScrollList


#: Список строк общий с другими учебниками (см. ref_list).
_ScrollList = ScrollList


class DockerReferencePanel(tk.Frame):
    """Три колонки: темы, команды, карточка выбранной команды."""

    def __init__(self, master, *, ref_source=None, on_insert: Callable[[str], None],
                 on_run: Callable[[str], None], on_close: Callable[[], None]) -> None:
        super().__init__(master, bg=BG, highlightthickness=1, highlightbackground=AMBER, bd=0)
        self.on_insert = on_insert
        self.on_run = on_run
        self.on_close = on_close
        self.ref = ref_source if ref_source is not None else ref
        self._topic = self.ref.topics()[0]["id"]
        self._item: dict | None = None
        self._build()
        self._fill_topics()
        self._fill_commands()

    # -- сборка -------------------------------------------------------------
    def _build(self) -> None:
        head = tk.Frame(self, bg=BG)
        head.pack(fill=tk.X, padx=px(8), pady=(px(6), px(4)))
        tk.Label(head, text=getattr(self.ref, "PANEL_TITLE", _t("УЧЕБНИК DOCKER · КОМАНДЫ")),
                 bg=BG, fg=AMBER, font=theme.font(13, True)).pack(side=tk.LEFT)
        tk.Label(head, text=_t("темы и команды прокручиваются колесом"), bg=BG, fg=MUTED,
                 font=theme.font(9)).pack(side=tk.LEFT, padx=px(10))
        HudButton(head, _t("✕ ЗАКРЫТЬ  F2"), self.on_close, height=28, font_size=9,
                  width=130, color=AMBER).pack(side=tk.RIGHT)

        body = tk.Frame(self, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=px(8), pady=(0, px(8)))

        left = tk.Frame(body, bg=BG, width=px(150))
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)
        tk.Label(left, text=_t("ТЕМЫ"), bg=BG, fg=CYAN,
                 font=theme.font(9, True)).pack(anchor="w", pady=(0, px(2)))
        self.topics = _ScrollList(left)
        self.topics.pack(fill=tk.BOTH, expand=True)

        right = tk.Frame(body, bg=BG, width=px(255))
        right.pack(side=tk.RIGHT, fill=tk.Y)
        right.pack_propagate(False)
        self._build_card(right)

        mid = tk.Frame(body, bg=BG)
        mid.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=px(8))
        top = tk.Frame(mid, bg=BG)
        top.pack(fill=tk.X)
        tk.Label(top, text=_t("КОМАНДЫ"), bg=BG, fg=CYAN,
                 font=theme.font(9, True)).pack(side=tk.LEFT, pady=(0, px(2)))
        self.var_query = tk.StringVar()
        self.entry = tk.Entry(top, textvariable=self.var_query, bg=BG2, fg=TEXT,
                              insertbackground=TEXT, relief=tk.FLAT, width=16,
                              font=theme.font(10, mono=True))
        self.entry.pack(side=tk.RIGHT)
        tk.Label(top, text=_t("поиск:"), bg=BG, fg=MUTED,
                 font=theme.font(9)).pack(side=tk.RIGHT, padx=px(4))
        self.var_query.trace_add("write", lambda *_a: self._fill_commands())
        self.entry.bind("<Escape>", self._clear_query)

        # Теория темы: короткие тезисы над списком команд.
        self.lbl_theory = tk.Label(mid, text="", bg=BG, fg=TEXT, font=theme.font(9),
                                   anchor="w", justify="left", wraplength=px(360))
        self.lbl_theory.pack(fill=tk.X, pady=(0, px(6)))
        mid.bind("<Configure>", self._on_mid_configure)

        self.commands = _ScrollList(mid)
        self.commands.pack(fill=tk.BOTH, expand=True)

    def _build_card(self, right: tk.Frame) -> None:
        tk.Label(right, text=_t("КОМАНДА"), bg=BG, fg=CYAN,
                 font=theme.font(9, True)).pack(anchor="w")
        self.lbl_cmd = tk.Label(right, text="—", bg=BG, fg=AMBER, font=theme.font(11, mono=True),
                                anchor="w", justify="left", wraplength=px(245))
        self.lbl_cmd.pack(fill=tk.X, pady=(px(2), px(4)))
        self.lbl_desc = tk.Label(right, text=_t("Выберите команду в списке слева."), bg=BG,
                                 fg=TEXT, font=theme.font(10), anchor="w", justify="left",
                                 wraplength=px(245))
        self.lbl_desc.pack(fill=tk.X)
        self.lbl_ex = tk.Label(right, text="", bg=BG, fg=MUTED, font=theme.font(9, mono=True),
                               anchor="w", justify="left", wraplength=px(245))
        self.lbl_ex.pack(fill=tk.X, pady=(px(4), 0))
        self.lbl_sim = tk.Label(right, text="", bg=BG, fg=MUTED, font=theme.font(9),
                                anchor="w", justify="left", wraplength=px(245))
        self.lbl_sim.pack(fill=tk.X, pady=(px(4), 0))

        btns = tk.Frame(right, bg=BG)
        btns.pack(side=tk.BOTTOM, fill=tk.X)
        HudButton(btns, _t("→ В СТРОКУ"), self.insert_selected, height=30, font_size=9,
                  width=130, color=CYAN).pack(fill=tk.X, pady=(0, px(3)))
        HudButton(btns, _t("▶ ВЫПОЛНИТЬ"), self.run_selected, height=30, font_size=9,
                  width=130, color=GREEN).pack(fill=tk.X)

    # -- данные -------------------------------------------------------------
    def _clear_query(self, _e=None) -> str:
        self.var_query.set("")
        return "break"

    def _on_mid_configure(self, event) -> None:
        """Тезисы теории переносить по фактической ширине средней колонки."""
        width = max(px(180), int(getattr(event, "width", 0)) - px(8))
        if getattr(self, "_theory_wrap", 0) != width:
            self._theory_wrap = width
            self.lbl_theory.configure(wraplength=width)

    def _fill_theory(self) -> None:
        """Тема → её блиц-теория: что важно понять до команд."""
        item = self.ref.topic(self._topic) or {}
        blurb = str(item.get("blurb") or "").strip()
        bullets = [str(x).strip() for x in (item.get("theory") or []) if str(x).strip()]
        parts = [blurb] if blurb else []
        parts.extend(f"• {line}" for line in bullets)
        self.lbl_theory.configure(text="\n".join(parts))

    def visible_theory(self) -> str:
        """Для тестов: текст теории текущей темы."""
        return self.lbl_theory.cget("text")

    def _fill_topics(self) -> None:
        self.topics.clear()
        for topic in self.ref.topics():
            count = len(topic["commands"])
            self.topics.add(topic["id"], topic["title"],
                            _t("{0} команд").format(count), self.select_topic)
        self.topics.select(self._topic)

    def _fill_commands(self) -> None:
        query = self.var_query.get().strip()
        items = self.ref.search(query, topic_id=None) if query else self.ref.commands(self._topic)
        self._fill_theory()
        self.commands.clear()
        for item in items:
            self.commands.add(item["cmd"], item["cmd"], item["desc"], self.select_command,
                             color=GREEN if item["sim"] else TEXT)
        if items:
            self.select_command(items[0]["cmd"])
        else:
            self._item = None
            self.lbl_cmd.configure(text="—")
            self.lbl_desc.configure(text=_t("Ничего не найдено — измените запрос."))
            self.lbl_ex.configure(text="")
            self.lbl_sim.configure(text="")

    def select_topic(self, topic_id: str) -> None:
        self._topic = topic_id
        self.topics.select(topic_id)
        if self.var_query.get().strip():
            self.var_query.set("")
            return                          # set() сам перезаполнит список
        self._fill_commands()

    def select_command(self, cmd: str) -> None:
        item = next((c for c in self.ref.commands() if c["cmd"] == cmd), None)
        if item is None:
            return
        self._item = item
        self.commands.select(cmd)
        self.lbl_cmd.configure(text=item["cmd"])
        self.lbl_desc.configure(text=item["desc"])
        self.lbl_ex.configure(text=f"$ {item['example']}")
        if item["sim"]:
            self.lbl_sim.configure(text=getattr(self.ref, "SIM_HINT", _t("✓ выполняется в тренажёре")),
                                   fg=GREEN)
        else:
            self.lbl_sim.configure(
                text=getattr(self.ref, "REAL_HINT", _t("· только в настоящем Docker")), fg=MUTED)

    # -- кнопки -------------------------------------------------------------
    def selected_command(self) -> str:
        return self._item["cmd"] if self._item else ""

    def insert_selected(self) -> None:
        cmd = self.selected_command()
        if cmd:
            self.on_insert(cmd)

    def run_selected(self) -> None:
        cmd = self.selected_command()
        if cmd:
            self.on_run(cmd)

    # -- для тестов и игры --------------------------------------------------
    def visible_commands(self) -> list[str]:
        return [key for key in self.commands.keys()]

    def set_query(self, text: str) -> None:
        self.var_query.set(text)

    def open_search(self) -> None:
        """Фокус в поиск — чтобы сразу печатать запрос."""
        self.entry.focus_set()
