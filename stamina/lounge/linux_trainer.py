"""Linux-тренажёр: команды терминала Linux (по образцу Docker-тренажёра).

Наследует игровую механику DockerTrainerGame: терминал, учебник (F2), миссии,
песочница, Backspace-правка, скролл. Подменяет только данные: миссии и каталог
команд Linux, симулятор — фейковый вывод терминала.
"""

from __future__ import annotations

from stamina.i18n import t as _t

import tkinter as tk

from stamina import theme
from stamina.hud import HudButton
from stamina.theme import AMBER, BG, CYAN, GREEN, MUTED, TEXT, px

from .base import GameShell
from . import store
from . import linux_reference as ref
from .docker_ref_panel import DockerReferencePanel
from .terminal_sim import FakeTerminalSimulator


# ─── Mission Data ──────────────────────────────────────────────────────────────

LINUX_MISSIONS = [
    {
        "id": "mission_1",
        "title": "Миссия 1: Первые шаги в Bash",
        "subtitle": "pwd, whoami, id — узнай, где ты и кто ты",
        "desc": "Linux-терминал (Bash) — основной интерфейс сервера. "
                "pwd показывает текущую директорию, whoami — пользователя, "
                "id — uid и группы (по ним видно, есть ли права на sudo и docker).",
        "hint": "Задание: выполни `pwd`, `whoami` и `id`",
        "expected": ["pwd", "whoami", "id"],
        "check": lambda sim, out: "uid=" in out,
        "xp": 50,
    },
    {
        "id": "mission_2",
        "title": "Миссия 2: Файлы и каталоги",
        "subtitle": "ls, cd, cat — навигация и чтение",
        "desc": "ls -la показывает права, владельца, размер и дату. "
                "cd меняет директорию, cat выводит содержимое файла.",
        "hint": "Задание: перейди в /var/log и прочитай syslog: `cd /var/log && cat syslog`",
        "expected": ["cd /var/log && cat syslog"],
        "check": lambda sim, out: "Module boot ok" in out or "boot" in out.lower(),
        "xp": 50,
    },
    {
        "id": "mission_3",
        "title": "Миссия 3: Поиск и фильтрация",
        "subtitle": "find, grep — ищи файлы и строки",
        "desc": "find ищет файлы по имени, размеру, дате. grep ищет текст внутри файлов. "
                "Ключ -i делает поиск нечувствительным к регистру.",
        "hint": "Задание: найди ошибки в syslog: `grep -i error /var/log/syslog`",
        "expected": ["grep -i error /var/log/syslog"],
        "check": lambda sim, out: "error" in out.lower(),
        "xp": 40,
    },
    {
        "id": "mission_4",
        "title": "Миссия 4: Процессы",
        "subtitle": "ps, kill — управление процессами",
        "desc": "ps aux показывает все процессы с PID, CPU, памятью. "
                "kill -9 PID принудительно завершает процесс (по умолчанию -15 — вежливо).",
        "hint": "Задание: посмотри процессы: `ps aux`",
        "expected": ["ps aux"],
        "check": lambda sim, out: "PID" in out,
        "xp": 40,
    },
    {
        "id": "mission_5",
        "title": "Миссия 5: Сеть",
        "subtitle": "ss, ping, curl — проверка связи",
        "desc": "ss -tulpn показывает слушающие порты. ping проверяет доступность хоста. "
                "curl делает HTTP-запросы и показывает код ответа.",
        "hint": "Задание: проверь, кто слушает порт 8080: `ss -tulpn`",
        "expected": ["ss -tulpn"],
        "check": lambda sim, out: "8080" in out,
        "xp": 50,
    },
    {
        "id": "mission_6",
        "title": "Миссия 6: Службы systemd",
        "subtitle": "systemctl — управление сервисами",
        "desc": "systemctl status показывает состояние службы. "
                "start/stop/restart управляют запуском, enable — автозапуском.",
        "hint": "Задание: проверь статус orion: `systemctl status orion`",
        "expected": ["systemctl status orion"],
        "check": lambda sim, out: "active" in out.lower() or "running" in out.lower(),
        "xp": 50,
    },
    {
        "id": "mission_7",
        "title": "Миссия 7: Права доступа",
        "subtitle": "chmod, chown, ls -la — кто может читать файл",
        "desc": "У файла три тройки прав: владелец, группа, остальные. "
                "chmod 640 даёт владельцу rw, группе r, остальным ничего; "
                "chown orion:ship меняет владельца и группу.",
        "hint": "Задание: закрой журнал от посторонних: `chmod 640 /var/log/syslog`, "
                "затем проверь права `ls -la /var/log/syslog`",
        "expected": ["chmod 640 /var/log/syslog", "ls -la /var/log/syslog"],
        "check": lambda sim, out: "-rw-r-----" in out,
        "xp": 50,
    },
    {
        "id": "mission_8",
        "title": "Миссия 8: Архивы и место на диске",
        "subtitle": "tar, df, du — упаковать и проверить",
        "desc": "tar -czf архив.tar.gz папка — создать gzip-архив. "
                "df -h показывает место на дисках, du -sh — размер каталога.",
        "hint": "Задание: собери журналы в архив `tar -czf /tmp/logs.tar.gz /var/log`, "
                "затем посмотри место: `df -h`",
        "expected": ["tar -czf /tmp/logs.tar.gz /var/log", "df -h"],
        "check": lambda sim, out: "Filesystem" in out and any(
            call.startswith("tar -czf /tmp/logs.tar.gz") for call in sim.calls),
        "xp": 50,
    },
    {
        "id": "mission_9",
        "title": "Миссия 9: Конвейеры",
        "subtitle": "| и wc — посчитать, а не листать глазами",
        "desc": "Символ | отдаёт вывод левой команды на вход правой. "
                "grep | wc -l считает строки, grep | sort -u убирает повторы.",
        "hint": "Задание: посчитай ошибки одной строкой: "
                "`grep -i error /var/log/syslog | wc -l`",
        "expected": ["grep -i error /var/log/syslog | wc -l"],
        "check": lambda sim, out: out.strip().isdigit(),
        "xp": 50,
    },
    {
        "id": "mission_10",
        "title": "Миссия 10: Планировщик cron",
        "subtitle": "crontab — задания по расписанию",
        "desc": "Пять полей cron: минута, час, день, месяц, день недели. "
                "Строка `0 3 * * * /usr/local/bin/backup.sh` — каждый день в 03:00.",
        "hint": "Задание: поставь ночной бэкап "
                "`echo \"0 3 * * * /usr/local/bin/backup.sh\" | crontab -`, "
                "затем проверь список `crontab -l`",
        "expected": ['echo "0 3 * * * /usr/local/bin/backup.sh" | crontab -', "crontab -l"],
        "check": lambda sim, out: "backup.sh" in out,
        "xp": 50,
    },
    {
        "id": "mission_11",
        "title": "Миссия 11: Журнал службы",
        "subtitle": "journalctl — что было и почему упало",
        "desc": "journalctl -u <служба> показывает журнал именно этой службы. "
                "-n 20 — последние двадцать строк, --no-pager — без просмотрщика.",
        "hint": "Задание: посмотри журнал orion: `journalctl -u orion -n 20 --no-pager`",
        "expected": ["journalctl -u orion -n 20 --no-pager"],
        "check": lambda sim, out: "orion" in out,
        "xp": 40,
    },
    {
        "id": "mission_12",
        "title": "Миссия 12: Удалённый узел",
        "subtitle": "ssh — одна команда на соседней машине",
        "desc": "ssh orion@10.0.0.5 входит на удалённую машину. "
                "Команда после адреса выполняется там и сразу возвращает вывод.",
        "hint": "Задание: узнай uptime соседнего узла: `ssh orion@10.0.0.5 uptime`",
        "expected": ["ssh orion@10.0.0.5 uptime"],
        "check": lambda sim, out: "up " in out and "10.0.0.5" in out,
        "xp": 40,
    },
    {
        "id": "sandbox",
        "title": "Свободный полёт",
        "subtitle": "Попробуй любые команды из учебника",
        "desc": "Все миссии освоены. Включи режим песочницы (галочка ниже) "
                "и экспериментируй свободно — миссии не проверяются.",
        "hint": "Задание: включи галочку «Песочница · без миссий» "
                "и попробуй `ls -la /var/log | head -n 3`",
        "expected": [],
        "check": lambda sim, out: True,
        "xp": 30,
    },
]


# ─── Helper Functions ──────────────────────────────────────────────────────────

def mission_key() -> str:
    return _t("↑/↓ — история · Tab — дописать · F1 — помощь · F2 — учебник · Esc — пауза")


def typed_char(event) -> str:
    """Символ для командной строки — из ``event.char``, а не из ``keysym``."""
    char = getattr(event, "char", "") or ""
    if len(char) != 1 or not char.isprintable():
        return ""
    return char


# ─── Linux Trainer Game ────────────────────────────────────────────────────────

class LinuxTrainerGame(GameShell):
    """Терминал Linux (Bash): миссии, учебник, песочница — как в Док-станции."""

    game_id = "linux_trainer"
    title = _t("LINUX ТРЕНАЖЁР · BASH ТЕРМИНАЛ")
    text_input = True
    tools_row = True
    missions = LINUX_MISSIONS
    reference = ref

    def __init__(self, master, **kw) -> None:
        super().__init__(master, **kw)
        self.sim = FakeTerminalSimulator()
        self.mission_idx = 0
        self.completed_missions: set[int] = set()
        self.history: list[str] = []
        self.history_pos = -1
        self.command_buffer = ""
        self.output_lines: list[tuple[str, str]] = []
        self.output_scroll = 0        # 0 = bottom, >0 = lines scrolled up
        self.pending_mission_check = False
        self.sandbox_mode = False
        self.ref_panel = None
        self.load_progress()
        self._load_mission(0)
        self.set_hint(mission_key())
        self._add_output(_t("Добро пожаловать в Linux-тренажёр!"), CYAN)
        self._add_output(_t("Введи команды bash. F1 — помощь, F2 — учебник команд, Tab — автодополнение."), MUTED)
        self._add_output("", TEXT)
        # Mouse wheel scrolling for terminal output
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", lambda e: self._on_mousewheel_up())
        self.canvas.bind("<Button-5>", lambda e: self._on_mousewheel_down())

    def build_tools(self) -> None:
        """Вторая строка панели: учебник команд и свободный режим."""
        HudButton(self.tools, _t("УЧЕБНИК  F2"), self.toggle_reference, height=30,
                  font_size=9, width=140, color=AMBER).pack(side=tk.LEFT, padx=(0, px(8)))
        self.var_sandbox = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self.tools, text=_t("Песочница · без миссий"),
            variable=self.var_sandbox, command=self._on_sandbox_toggle,
            bg=BG, fg=MUTED, activebackground=BG, activeforeground=TEXT,
            selectcolor="#1E2D3D", highlightthickness=0, bd=0, takefocus=0,
            font=theme.font(9),
        ).pack(side=tk.LEFT)

    def _on_sandbox_toggle(self) -> None:
        """Галка песочницы: заниматься без миссий можно с любого места."""
        self.sandbox_mode = bool(self.var_sandbox.get())
        if self.sandbox_mode:
            self._add_output(_t("Свободный режим: миссии не проверяются, "
                                "пробуй любые команды из учебника (F2)."), CYAN)
        else:
            self._add_output(_t("Снова по миссиям: смотри задание в подсказке внизу."), MUTED)
        self.save_progress()
        self.redraw()
        self.focus_set()

    def _sync_sandbox_var(self) -> None:
        var = getattr(self, "var_sandbox", None)
        if var is not None:
            var.set(bool(self.sandbox_mode))

    # -- учебник команд ----------------------------------------------------------
    def reference_open(self) -> bool:
        return self.ref_panel is not None and self.ref_panel.winfo_ismapped()

    def toggle_reference(self) -> None:
        if self.reference_open():
            self.close_reference()
            return
        if self.ref_panel is None:
            self.ref_panel = DockerReferencePanel(
                self.canvas.master, on_insert=self.insert_from_reference,
                on_run=self.run_from_reference, on_close=self.close_reference,
                ref_source=self.reference,
            )
        self.ref_panel.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.ref_panel.lift()
        self.set_hint(_t("Учебник открыт: тема → команда → «в строку» или «выполнить» · F2 — закрыть"))

    def close_reference(self) -> None:
        if self.ref_panel is not None:
            self.ref_panel.place_forget()
        self.set_hint(mission_key())
        self.focus_set()
        self.redraw()

    def insert_from_reference(self, cmd: str) -> None:
        """Команда из учебника — в строку ввода, без выполнения."""
        self.close_reference()
        self.command_buffer = cmd
        self.history_pos = len(self.history)
        self._add_output(_t("Из учебника в строку: {0}").format(cmd), MUTED)
        self.redraw()

    def run_from_reference(self, cmd: str) -> None:
        """Команда из учебника — сразу в терминал, как будто набрана руками."""
        self.close_reference()
        self.command_buffer = cmd
        self._execute_command()

    def load_progress(self) -> None:
        data = store.load()
        linux_data = data.get("linux_trainer", {})
        self.completed_missions = set(linux_data.get("completed", []))
        self.mission_idx = linux_data.get("current_mission", 0)
        sandbox = linux_data.get("sandbox_state")
        if sandbox:
            try:
                self.sim = FakeTerminalSimulator.from_dict(sandbox)
            except Exception:
                self.sim = FakeTerminalSimulator()
            self.sandbox_mode = True
        if self.mission_idx >= len(self.missions):
            self.mission_idx = len(self.missions) - 1
        self._sync_sandbox_var()

    def save_progress(self) -> None:
        data = store.load()
        data["linux_trainer"] = {
            "completed": list(self.completed_missions),
            "current_mission": self.mission_idx,
            "sandbox_state": self.sim.to_dict() if self.sandbox_mode else None,
        }
        store.save(data)

    def _load_mission(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.missions):
            return
        self.mission_idx = idx
        mission = self.missions[idx]
        self.title = mission["title"]
        self.lbl_title.configure(text=self.title)
        self._add_output("", TEXT)
        self._add_output(f"=== {mission['title']} ===", AMBER)
        self._add_output(mission["desc"], TEXT)
        self._add_output("", TEXT)
        self._add_output(f"> {mission['hint']}", CYAN)
        self._add_output("", TEXT)

    def tick_ms(self) -> int:
        return 100

    def tick(self) -> None:
        pass

    def reset(self) -> None:
        self.close_reference()
        self.sim = FakeTerminalSimulator()
        self.mission_idx = 0
        self.completed_missions.clear()
        self.history.clear()
        self.history_pos = -1
        self.output_lines.clear()
        self.command_buffer = ""
        self.sandbox_mode = False
        self._sync_sandbox_var()
        self.save_progress()
        self._load_mission(0)
        self.set_score(0)

    def stop(self) -> None:
        super().stop()
        self.save_progress()

    def help_level_id(self) -> str | None:
        if getattr(self, "sandbox_mode", False):
            return "sandbox"
        try:
            return self.missions[self.mission_idx]["id"]
        except (IndexError, KeyError, TypeError):
            return "mission_1"

    def on_key(self, e: tk.Event) -> None:
        k = e.keysym
        if self.reference_open():
            if k in ("Escape", "F2"):
                self.close_reference()
            return
        if k == "F2":
            self.toggle_reference()
            return
        if self.handle_help_keys(e):
            return
        state = getattr(e, "state", 0) or 0
        ctrl = bool(state & 0x4)

        if k == "Escape":
            if self.paused or self.over:
                self.restart()
            else:
                self.toggle_pause()
            return
        elif k == "Return":
            self._execute_command()
            return
        elif k == "Up":
            self._history_up()
            return
        elif k == "Down":
            self._history_down()
            return
        elif k == "Tab":
            self._autocomplete()
            return
        elif k == "BackSpace":
            if self.command_buffer:
                self.command_buffer = self.command_buffer[:-1]
                self._redraw_input_line()
            return
        elif k == "F1":
            self.on_help()
            return
        elif ctrl and k == "l":
            self._clear_screen()
            return
        elif ctrl and k == "c":
            self.command_buffer = ""
            self._add_output("^C", MUTED)
            self._redraw_input_line()
            return

        char = typed_char(e)
        if char and not ctrl:
            self.command_buffer += char
            self._redraw_input_line()
            return

    def _execute_command(self) -> None:
        cmd = self.command_buffer.strip()
        if not cmd:
            self._add_output("", TEXT)
            return

        self._add_output(f"$ {cmd}", AMBER)
        self.history.append(cmd)
        self.history_pos = len(self.history)
        self.command_buffer = ""

        out, code = self.sim.execute(cmd)
        if out:
            color = GREEN if code == 0 else AMBER
            for line in out.strip().split("\n"):
                self._add_output(line, color)

        if not self.sandbox_mode:
            mission = self.missions[self.mission_idx]
            if mission["check"](self.sim, out):
                self._complete_mission()

        self._redraw_input_line()
        self.redraw()

    def _complete_mission(self) -> None:
        if self.mission_idx not in self.completed_missions:
            self.completed_missions.add(self.mission_idx)
            xp = self.missions[self.mission_idx].get("xp", 50)
            self.add_score(xp)
            self._add_output("", TEXT)
            self._add_output(_t("✓ Миссия выполнена! +{0} XP").format(xp), GREEN)
            self.save_progress()

        if self.mission_idx + 1 < len(self.missions):
            self.mission_idx += 1
            self._load_mission(self.mission_idx)
        else:
            self._add_output("", TEXT)
            self._add_output(_t("🎉 Все миссии пройдены! Режим песочницы разблокирован."), GREEN)
            self._add_output(_t("Теперь ты можешь свободно экспериментировать с Linux командами."), CYAN)
            self.sandbox_mode = True
            self._sync_sandbox_var()
            self.save_progress()

    def _history_up(self) -> None:
        if self.history and self.history_pos > 0:
            self.history_pos -= 1
            self.command_buffer = self.history[self.history_pos]
            self._redraw_input_line()

    def _history_down(self) -> None:
        if self.history and self.history_pos < len(self.history) - 1:
            self.history_pos += 1
            self.command_buffer = self.history[self.history_pos]
            self._redraw_input_line()
        elif self.history_pos == len(self.history) - 1:
            self.history_pos = len(self.history)
            self.command_buffer = ""
            self._redraw_input_line()

    def _autocomplete(self) -> None:
        """Tab: дописать команду. Список — из учебника."""
        completions = list(self.reference.completions()) + [
            "ls", "cd", "cat", "grep", "find", "ps", "kill", "ss", "netstat",
            "ping", "curl", "systemctl", "service", "tar", "chmod", "chown",
            "crontab", "journalctl", "ssh", "scp", "id", "df", "du", "head",
            "tail", "wc", "sort", "tee", "export", "env", "sudo", "hostname",
            "uname", "uptime", "ip", "free",
            "-la", "-a", "-i", "-r", "-f", "-z", "-c", "-p", "-t", "-u", "-h",
            "aux", "start", "stop", "restart", "status", "enable", "disable",
        ]
        prefix = self.command_buffer.split()[-1] if self.command_buffer else ""
        matches = [c for c in completions if c.startswith(prefix)]
        if len(matches) == 1:
            words = self.command_buffer.split()
            if words:
                words[-1] = matches[0]
                self.command_buffer = " ".join(words) + " "
            else:
                self.command_buffer = matches[0] + " "
            self._redraw_input_line()
        elif len(matches) > 1:
            self._add_output("  " + "  ".join(matches), MUTED)
            self._redraw_input_line()

    def _clear_screen(self) -> None:
        self.output_lines.clear()
        self.output_scroll = 0
        self._redraw_input_line()
        self.redraw()

    def _on_mousewheel(self, e: tk.Event) -> None:
        if e.delta > 0:
            self._on_mousewheel_up()
        else:
            self._on_mousewheel_down()

    def _on_mousewheel_up(self) -> None:
        max_scroll = max(0, len(self.output_lines) - 1)
        if self.output_scroll < max_scroll:
            self.output_scroll += 1
            self.redraw()

    def _on_mousewheel_down(self) -> None:
        if self.output_scroll > 0:
            self.output_scroll -= 1
            self.redraw()
        elif self.output_scroll == 0:
            self.redraw()

    def _add_output(self, text: str, color: str) -> None:
        self.output_lines.append((text, color))
        if self.output_scroll == 0:
            self.output_scroll = 0
        if len(self.output_lines) > 500:
            self.output_lines = self.output_lines[-400:]
            if self.output_scroll > len(self.output_lines):
                self.output_scroll = len(self.output_lines)

    def _redraw_input_line(self) -> None:
        self.redraw()

    def on_help(self) -> bool:
        if getattr(self, "overlay", None):
            self.overlay = None
        return super().on_help()

    def _show_overlay(self, lines: list[str]) -> None:
        self.overlay = lines
        self.redraw()

    def close_overlay(self) -> None:
        self.overlay = None
        self.redraw()

    def _input_box(self, h: int) -> tuple[int, int, int]:
        status_y = h - px(30)
        in_bot = status_y - px(6)
        in_h = max(px(58), px(19) * 3)
        in_top = in_bot - in_h
        return in_top, in_bot, in_top - px(6)

    def redraw(self) -> None:
        c = self.canvas
        c.delete("all")
        w = max(c.winfo_width(), 10)
        h = max(c.winfo_height(), 10)

        c.create_rectangle(0, 0, w, h, fill=BG, outline="")

        in_top, in_bot, term_h = self._input_box(h)
        c.create_rectangle(px(8), px(8), w - px(8), term_h, fill="#0D1117", outline=MUTED, width=1)

        font = theme.font(11, mono=True)
        line_h = px(18)
        max_lines = max(1, (term_h - px(16)) // line_h)
        start_y = term_h - px(8) - line_h

        end_idx = len(self.output_lines) - self.output_scroll
        start_idx = max(0, end_idx - max_lines)
        visible = self.output_lines[start_idx:end_idx]
        y = start_y
        for text, color in reversed(visible):
            if y < px(16):
                break
            if text:
                tid = c.create_text(px(16), y + line_h, text=text, fill=color, anchor="sw", font=font, width=w - px(32))
                bb = c.bbox(tid)
                y = (bb[1] if bb else y) - px(2) - line_h
            else:
                y -= line_h

        if self.output_scroll > 0:
            c.create_text(w - px(16), px(16), text=f"▲ {self.output_scroll}", fill=MUTED, anchor="ne", font=theme.font(9, mono=True))
        elif end_idx < len(self.output_lines):
            c.create_text(w - px(16), px(16), text="▼ new", fill=MUTED, anchor="ne", font=theme.font(9, mono=True))

        c.create_rectangle(px(8), in_top, w - px(8), in_bot, fill="#0D1117", outline=AMBER, width=1)
        in_font = theme.font(14, mono=True)
        c.create_text(px(16), in_top + px(10), text="$", fill=AMBER, anchor="nw", font=in_font)
        c.create_text(px(38), in_top + px(10), text=self.command_buffer + "█", fill=TEXT,
                      anchor="nw", font=in_font, width=w - px(50))

        status_y = h - px(30)
        c.create_rectangle(0, status_y, w, h, fill="#1A1A2E", outline=MUTED)
        c.create_text(px(10), status_y + px(8), text=_t("Миссия {0}/{1}").format(self.mission_idx + 1, len(self.missions)), fill=CYAN, anchor="w", font=theme.font(10, True))
        c.create_text(px(200), status_y + px(8), text=_t("XP: {0}").format(self.score), fill=AMBER, anchor="w", font=theme.font(10, True))
        if self.sandbox_mode:
            c.create_text(px(300), status_y + px(8), text=_t("ПЕСОЧНИЦА"), fill=GREEN, anchor="w", font=theme.font(10, True))

        dot_x = w // 2 - len(self.missions) * px(10)
        for i in range(len(self.missions)):
            color = GREEN if i in self.completed_missions else (AMBER if i == self.mission_idx else MUTED)
            c.create_oval(dot_x + i * px(20), status_y + px(6), dot_x + i * px(20) + px(10), status_y + px(16), fill=color, outline="")

        if hasattr(self, 'overlay') and self.overlay:
            self._draw_overlay(c, w, h)

        if self.paused:
            self.draw_overlay(_t("ПАУЗА"))

    def _draw_overlay(self, c: tk.Canvas, w: int, h: int) -> None:
        overlay_w = min(w - px(40), px(800))
        overlay_h = min(h - px(40), px(500))
        x0 = (w - overlay_w) // 2
        y0 = (h - overlay_h) // 2

        c.create_rectangle(x0, y0, x0 + overlay_w, y0 + overlay_h, fill=BG, outline=AMBER, width=2)
        c.create_text(w // 2, y0 + px(12), text=_t("ПОМОЩЬ"), fill=AMBER, anchor="n", font=theme.font(14, True))

        y = y0 + px(40)
        for line in self.overlay:
            if y > y0 + overlay_h - px(30):
                break
            color = AMBER if line.startswith("===") else (CYAN if line.startswith("  ") or line.startswith("  -") else (GREEN if line.startswith(_t("Доступные")) else TEXT))
            c.create_text(x0 + px(20), y, text=line, fill=color, anchor="nw", font=theme.font(10, mono=True), width=overlay_w - px(40))
            y += px(18)

        c.create_text(w // 2, y0 + overlay_h - px(12), text=_t("F1 или Esc — закрыть"), fill=MUTED, anchor="s", font=theme.font(10, True))


if __name__ == "__main__":
    import tkinter as tk
    root = tk.Tk()
    root.geometry("1000x700")
    game = LinuxTrainerGame(root, on_back=lambda: None, app=None)
    game.pack(fill=tk.BOTH, expand=True)
    game.start()
    root.mainloop()