"""Docker Trainer — interactive Docker CLI tutorial game for the Lounge.

Teaches Docker commands through progressive missions in a terminal-style interface.
"""
from __future__ import annotations

from stamina.i18n import t as _t

import tkinter as tk

from stamina import theme
from stamina.hud import HudButton
from stamina.theme import AMBER, BG, BG2, CYAN, GREEN, MUTED, PANEL, TEXT, px

from .base import GameShell
from . import store
from . import docker_reference as ref
from .docker_ref_panel import DockerReferencePanel
from .docker_sim import DockerSimulator


# ─── Mission Data ──────────────────────────────────────────────────────────────

MISSIONS = [
    {
        "id": "mission_1",
        "title": _t("Миссия 1: Первые шаги"),
        "subtitle": _t("Запусти контейнер и проверь, что он работает"),
        "desc": _t("Docker — это платформа для запуска приложений в изолированных контейнерах.\n"
                   "Первая команда — `docker run`. Флаг `-d` запускает в фоне (detached)."),
        "hint": _t("Задание: запусти контейнер ship/radio в фоне командой `docker run -d ship/radio`"),
        "expected": ["docker run -d ship/radio"],
        # Имя контейнера генерируется (ship_<id>), а образ называется ship/radio:
        # прежняя проверка «ship_radio в containers» и «image == radio» не срабатывала
        # никогда — первая миссия была непроходимой.
        "check": lambda sim, out: any(c.image.name == "ship/radio" for c in sim.containers.values()),
        "xp": 50,
    },
    {
        "id": "mission_2",
        "title": _t("Миссия 2: Порты и имена"),
        "subtitle": _t("Опубликуй порт и задай имя контейнеру"),
        "desc": _t("Флаг `-p HOST:CONTAINER` пробрасывает порт с хоста в контейнер.\n"
                   "Флаг `--name` задаёт понятное имя вместо случайного ID."),
        "hint": _t("Задание: запусти ship/orion на порту 9000 с именем my_orion: `docker run -d -p 9000:9000 --name my_orion ship/orion`"),
        "expected": ["docker run -d -p 9000:9000 --name my_orion ship/orion"],
        "check": lambda sim, out: any(c.name == "my_orion" and any(p.host_port == 9000 for p in c.ports) for c in sim.containers.values()),
        "xp": 50,
    },
    {
        "id": "mission_3",
        "title": _t("Миссия 3: Список контейнеров"),
        "subtitle": _t("Посмотри, какие контейнеры запущены"),
        "desc": _t("Команда `docker ps` показывает запущенные контейнеры.\n"
                   "Флаг `-a` (или `--all`) показывает все, включая остановленные."),
        "hint": _t("Задание: выполни `docker ps` и проверь, что my_orion в списке"),
        "expected": ["docker ps"],
        "check": lambda sim, out: "my_orion" in out,
        "xp": 30,
    },
    {
        "id": "mission_4",
        "title": _t("Миссия 4: Логи контейнера"),
        "subtitle": _t("Посмотри вывод работы контейнера"),
        "desc": _t("Команда `docker logs <container>` показывает stdout/stderr контейнера.\n"
                   "Можно использовать имя или ID контейнера."),
        "hint": _t("Задание: посмотри логи my_orion командой `docker logs my_orion`"),
        "expected": ["docker logs my_orion"],
        "check": lambda sim, out: "Module ready" in out or "Agent" in out,
        "xp": 30,
    },
    {
        "id": "mission_5",
        "title": _t("Миссия 5: Остановка и удаление"),
        "subtitle": _t("Останови контейнер и удали его"),
        "desc": _t("`docker stop <container>` — мягкая остановка (SIGTERM, затем SIGKILL).\n"
                   "`docker rm <container>` — удаляет остановленный контейнер.\n"
                   "Флаг `-f` (force) позволяет удалить запущенный контейнер сразу."),
        "hint": _t("Задание: останови my_orion (`docker stop my_orion`), затем удали (`docker rm my_orion`)"),
        "expected": ["docker stop my_orion", "docker rm my_orion"],
        "check": lambda sim, out: not any(c.name == "my_orion" for c in sim.containers.values()),
        "xp": 50,
    },
    {
        "id": "mission_6",
        "title": _t("Миссия 6: Образы и тома"),
        "subtitle": _t("Посмотри локальные образы и создай том для данных"),
        "desc": _t("`docker images` — список локальных образов.\n"
                   "`docker volume create <name>` — создаёт именованный том для персистентных данных.\n"
                   "Тома выживают после удаления контейнеров."),
        "hint": _t("Задание: выполни `docker images`, затем создай том `docker volume create ship_data`"),
        "expected": ["docker images", "docker volume create ship_data"],
        "check": lambda sim, out: "ship_data" in sim.volumes,
        "xp": 40,
    },
    {
        "id": "mission_7",
        "title": _t("Миссия 7: Сети и Docker Compose"),
        "subtitle": _t("Создай сеть и запусти стек через compose"),
        "desc": _t("`docker network create <name>` — создаёт пользовательскую сеть.\n"
                   "`docker compose up -d` — запускает сервисы из compose.yml в фоне.\n"
                   "Сервисы в одной сети видят друг друга по имени сервиса."),
        "hint": _t("Задание: создай сеть `docker network create shipnet`, затем `docker compose up -d orion lab base`"),
        "expected": ["docker network create shipnet", "docker compose up -d orion lab base"],
        "check": lambda sim, out: "shipnet" in sim.networks and len([c for c in sim.containers.values() if c.name.startswith("compose_")]) >= 3,
        "xp": 60,
    },
    {
        "id": "mission_8",
        "title": _t("Миссия 8: Очистка и приведение в порядок"),
        "subtitle": _t("Удали всё лишнее одной командой"),
        "desc": _t("`docker system prune` — удаляет остановленные контейнеры, неиспользуемые образы, тома и сети.\n"
                   "Флаг `-a` удаляет также неиспользуемые образы (не только dangling).\n"
                   "`--volumes` удаляет неиспользуемые тома."),
        "hint": _t("Задание: выполни `docker system prune` для очистки"),
        "expected": ["docker system prune"],
        "check": lambda sim, out: "Deleted" in out or "reclaimed" in out,
        "xp": 50,
    },
    {
        "id": "mission_9",
        "title": "Миссия 9: Данные в томе",
        "subtitle": "Том переживает контейнер",
        "desc": "`docker volume create <name>` создаёт том, `-v имя:/путь` монтирует его внутрь.\n"
                "Данные в томе останутся, даже если контейнер удалить.",
        "hint": "Задание: создай том `docker volume create radio_data`, затем запусти "
                "`docker run -d -v radio_data:/data --name radio_store ship/radio`",
        "expected": ["docker volume create radio_data",
                     "docker run -d -v radio_data:/data --name radio_store ship/radio"],
        "check": lambda sim, out: any(
            c.name == "radio_store"
            and any(vm.source == "radio_data" and vm.target == "/data" for vm in c.volumes)
            for c in sim.containers.values()
        ),
        "xp": 50,
    },
    {
        "id": "mission_10",
        "title": "Миссия 10: Переменные окружения",
        "subtitle": "-e передаёт настройку внутрь контейнера",
        "desc": "Флаг `-e KEY=VALUE` задаёт переменную окружения контейнера.\n"
                "Так приложение узнаёт режим работы, уровень логов и адреса баз.",
        "hint": "Задание: запусти `docker run -d -e LOG_LEVEL=debug --name radio_fm ship/radio`",
        "expected": ["docker run -d -e LOG_LEVEL=debug --name radio_fm ship/radio"],
        "check": lambda sim, out: any(
            c.name == "radio_fm" and c.env.get("LOG_LEVEL") == "debug"
            for c in sim.containers.values()
        ),
        "xp": 40,
    },
    {
        "id": "mission_11",
        "title": "Миссия 11: Порт и диагностика",
        "subtitle": "docker port — куда ведёт проброс",
        "desc": "`docker port <container>` показывает, какой порт хоста смотрит внутрь.\n"
                "Если снаружи «не открывается», сначала проверяют именно это.",
        "hint": "Задание: запусти `docker run -d -p 8090:8080 --name radio_web ship/radio`, "
                "затем `docker port radio_web`",
        "expected": ["docker run -d -p 8090:8080 --name radio_web ship/radio",
                     "docker port radio_web"],
        "check": lambda sim, out: "8090" in out,
        "xp": 40,
    },
    {
        "id": "mission_12",
        "title": "Миссия 12: Сборка образа",
        "subtitle": "docker build -t имя:тег .",
        "desc": "`docker build -t ship/app:1.0 .` собирает образ из Dockerfile в текущем каталоге.\n"
                "Тег — это версия: без него образ получит latest.",
        "hint": "Задание: собери образ `docker build -t ship/app:1.0 .`",
        "expected": ["docker build -t ship/app:1.0 ."],
        "check": lambda sim, out: "Successfully tagged" in out,
        "xp": 50,
    },
    {
        "id": "mission_13",
        "title": "Миссия 13: Свернуть проект",
        "subtitle": "docker compose ps и down",
        "desc": "`docker compose ps` показывает состояние сервисов проекта.\n"
                "`docker compose down` останавливает и удаляет их — стенд остаётся чистым.",
        "hint": "Задание: посмотри `docker compose ps`, затем сверни проект: `docker compose down`",
        "expected": ["docker compose ps", "docker compose down"],
        "check": lambda sim, out: not any(c.name.startswith("compose_") for c in sim.containers.values()),
        "xp": 50,
    },
    {
        "id": "sandbox",
        "title": "Свободный полёт",
        "subtitle": "Попробуй любые команды из учебника",
        "desc": "Все миссии освоены. Включи режим песочницы (галочка ниже) "
                "и экспериментируй свободно — миссии не проверяются.",
        "hint": "Задание: включи галочку «Песочница · без миссий» "
                "и попробуй `docker run -d ship/lab`, затем `docker ps`",
        "expected": [],
        "check": lambda sim, out: True,
        "xp": 30,
    },
]


# ─── Helper Functions ──────────────────────────────────────────────────────────

def mission_key() -> str:
    return "↑/↓ — история · Tab — дописать · F1 — помощь · F2 — учебник · Esc — пауза"


def typed_char(event) -> str:
    """Символ для командной строки — из ``event.char``, а не из ``keysym``.

    У пробела и знаков keysym многословный («space», «minus», «slash», «colon»),
    поэтому проверка «len(keysym) == 1» съедала ровно то, без чего не набрать ни
    ``docker run -d ship/radio``, ни ``-p 9000:9000``. ``char`` даёт готовый
    символ с учётом Shift, раскладки и AltGr; служебные клавиши (Return, Tab,
    стрелки) отсекаются: их char непечатаемый.
    """
    char = getattr(event, "char", "") or ""
    if len(char) != 1 or not char.isprintable():
        return ""
    return char


# ─── Docker Trainer Game ───────────────────────────────────────────────────────

class DockerTrainerGame(GameShell):
    game_id = "docker_trainer"
    title = "DOCKER ТРЕНАЖЁР · ДОК-СТАНЦИЯ"
    text_input = True      # в панели появляется галка «⌫ Backspace — стирать»
    tools_row = True       # вторая строка: учебник и песочница
    # Миссии и источник команд учебника — атрибуты экземпляра (класса): новые
    # терминальные тренажёры (PowerShell, Linux) наследуют это поведение и
    # подменяют под свои данные через классовые атрибуты.
    missions = MISSIONS
    reference = ref

    def __init__(self, master, **kw) -> None:
        super().__init__(master, **kw)
        self.sim = DockerSimulator()
        self.mission_idx = 0
        self.completed_missions: set[int] = set()
        self.history: list[str] = []
        self.history_pos = -1
        self.command_buffer = ""
        self.output_lines: list[tuple[str, str]] = []  # (text, color)
        self.output_scroll = 0        # 0 = bottom, >0 = lines scrolled up
        self.pending_mission_check = False
        self.sandbox_mode = False
        self.ref_panel = None          # панель-учебник создаётся по F2
        self.load_progress()
        self._load_mission(0)
        self.set_hint(mission_key())
        self._add_output("Добро пожаловать на Док-станцию!", CYAN)
        self._add_output(_t("Введи команды docker. F1 — помощь, F2 — учебник команд, "
                            "Tab — автодополнение."), MUTED)
        self._add_output("", TEXT)
        # Mouse wheel scrolling for terminal output
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", lambda e: self._on_mousewheel_up())
        self.canvas.bind("<Button-5>", lambda e: self._on_mousewheel_down())

    def build_tools(self) -> None:
        """Вторая строка панели: учебник команд и свободный режим."""
        HudButton(self.tools, "УЧЕБНИК  F2", self.toggle_reference, height=30,
                  font_size=9, width=140, color=AMBER).pack(side=tk.LEFT, padx=(0, px(8)))
        self.var_sandbox = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self.tools, text="Песочница · без миссий",
            variable=self.var_sandbox, command=self._on_sandbox_toggle,
            bg=BG, fg=MUTED, activebackground=BG, activeforeground=TEXT,
            selectcolor=PANEL, highlightthickness=0, bd=0, takefocus=0,
            font=theme.font(9),
        ).pack(side=tk.LEFT)

    def _on_sandbox_toggle(self) -> None:
        """Галка песочницы: заниматься без миссий можно с любого места."""
        self.sandbox_mode = bool(self.var_sandbox.get())
        if self.sandbox_mode:
            self._add_output(_t("Свободный режим: миссии не проверяются, "
                                "пробуй любые команды из учебника (F2)."), CYAN)
        else:
            self._add_output("Снова по миссиям: смотри задание в подсказке внизу.", MUTED)
        self.save_progress()
        self.redraw()
        self.focus_set()

    def _sync_sandbox_var(self) -> None:
        var = getattr(self, "var_sandbox", None)
        if var is not None:
            var.set(bool(self.sandbox_mode))

    # -- учебник команд ------------------------------------------------------
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
            )
        self.ref_panel.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.ref_panel.lift()
        self.set_hint("Учебник открыт: тема → команда → «в строку» или «выполнить» · F2 — закрыть")

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
        self._add_output("Из учебника в строку: {0}".format(cmd), MUTED)
        self.redraw()

    def run_from_reference(self, cmd: str) -> None:
        """Команда из учебника — сразу в терминал, как будто набрана руками."""
        self.close_reference()
        self.command_buffer = cmd
        self._execute_command()

    def load_progress(self) -> None:
        data = store.load()
        docker_data = data.get("docker_trainer", {})
        self.completed_missions = set(docker_data.get("completed", []))
        self.mission_idx = docker_data.get("current_mission", 0)
        sandbox = docker_data.get("sandbox_state")
        if sandbox:
            try:
                self.sim = DockerSimulator.from_dict(sandbox)
            except Exception:
                self.sim = DockerSimulator()
            self.sandbox_mode = True
        if self.mission_idx >= len(self.missions):
            self.mission_idx = len(self.missions) - 1
        self._sync_sandbox_var()

    def save_progress(self) -> None:
        data = store.load()
        data["docker_trainer"] = {
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
        self.sim = DockerSimulator()
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
        # Учебник открыт — клавиатура принадлежит ему: Esc/F2 закрывают,
        # остальное не должно печататься в скрытый терминал.
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

        # Printable characters: берём char, иначе не набрать пробел и «-», «/», «:»
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

        # Execute in simulator
        out, code = self.sim.execute(cmd)
        if out:
            color = GREEN if code == 0 else AMBER
            for line in out.strip().split("\n"):
                self._add_output(line, color)

        # Check mission completion — только когда идём по миссиям
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
            self._add_output("✓ Миссия выполнена! +{0} XP".format(xp), GREEN)
            self.save_progress()

        if self.mission_idx + 1 < len(self.missions):
            self.mission_idx += 1
            self._load_mission(self.mission_idx)
        else:
            self._add_output("", TEXT)
            self._add_output("🎉 Все миссии пройдены! Режим песочницы разблокирован.", GREEN)
            self._add_output("Теперь ты можешь свободно экспериментировать с Docker командами.", CYAN)
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
        """Tab: дописать команду. Список — из учебника, чтобы не расходился с ним."""
        completions = list(self.reference.completions()) + [
            "ship/radio", "ship/orion", "ship/lab", "ship/scanner", "ship/base",
            "-d", "-p", "--name", "-v", "-e", "--label", "-t", "--detach",
            "create", "ls", "rm", "prune", "up", "down", "port", "volume", "network",
            "compose", "system",
        ]
        prefix = self.command_buffer.split()[-1] if self.command_buffer else ""
        matches = [c for c in completions if c.startswith(prefix)]
        if len(matches) == 1:
            # Complete the word
            words = self.command_buffer.split()
            if words:
                words[-1] = matches[0]
                self.command_buffer = " ".join(words) + " "
            else:
                self.command_buffer = matches[0] + " "
            self._redraw_input_line()
        elif len(matches) > 1:
            # Show options
            self._add_output("  " + "  ".join(matches), MUTED)
            self._redraw_input_line()

    def _clear_screen(self) -> None:
        self.output_lines.clear()
        self.output_scroll = 0
        self._redraw_input_line()
        self.redraw()

    def _on_mousewheel(self, e: tk.Event) -> None:
        # Scroll up/down in terminal output
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
        # If we scroll to bottom, auto-follow new output
        elif self.output_scroll == 0:
            self.redraw()

    def _add_output(self, text: str, color: str) -> None:
        self.output_lines.append((text, color))
        # Auto-scroll to bottom if user was at bottom
        if self.output_scroll == 0:
            self.output_scroll = 0
        # Limit history
        if len(self.output_lines) > 500:
            self.output_lines = self.output_lines[-400:]
            # Adjust scroll if we trimmed lines before the viewport
            if self.output_scroll > len(self.output_lines):
                self.output_scroll = len(self.output_lines)

    def _redraw_input_line(self) -> None:
        # Терминал рисуется на холсте: без перерисовки набранное видно только
        # со следующим тиком (раз в 100 мс) — буквы «отставали» от клавиш.
        self.redraw()

    def on_help(self) -> bool:
        """F1 / «?»: общий оверлей справки по текущей миссии."""
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
        """Границы строки ввода: (верх, низ, низ терминала).

        Строка ввода — три строки моноширинного текста (было полторы): длинные
        команды и примеры из учебника переносятся, а не уезжают за край.
        """
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

        # Background
        c.create_rectangle(0, 0, w, h, fill=BG, outline="")

        in_top, in_bot, term_h = self._input_box(h)
        c.create_rectangle(px(8), px(8), w - px(8), term_h, fill="#0D1117", outline=MUTED, width=1)

        # Output lines
        font = theme.font(11, mono=True)
        line_h = px(18)
        max_lines = max(1, (term_h - px(16)) // line_h)
        start_y = term_h - px(8) - line_h

        # Show lines with scroll offset
        # output_scroll = 0 means show last max_lines (bottom)
        # output_scroll > 0 means show earlier lines
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

        # Scroll indicator
        if self.output_scroll > 0:
            c.create_text(w - px(16), px(16), text=f"▲ {self.output_scroll}", fill=MUTED, anchor="ne", font=theme.font(9, mono=True))
        elif end_idx < len(self.output_lines):
            c.create_text(w - px(16), px(16), text="▼ new", fill=MUTED, anchor="ne", font=theme.font(9, mono=True))

        # Input box: слева приглашение, дальше набранное с курсором
        c.create_rectangle(px(8), in_top, w - px(8), in_bot, fill="#0D1117", outline=AMBER, width=1)
        in_font = theme.font(14, mono=True)
        c.create_text(px(16), in_top + px(10), text="$", fill=AMBER, anchor="nw", font=in_font)
        c.create_text(px(38), in_top + px(10), text=self.command_buffer + "█", fill=TEXT,
                      anchor="nw", font=in_font, width=w - px(50))

        # Status bar
        status_y = h - px(30)
        c.create_rectangle(0, status_y, w, h, fill=BG2, outline=MUTED)
        c.create_text(px(10), status_y + px(8), text="Миссия {0}/{1}".format(self.mission_idx + 1, len(self.missions)), fill=CYAN, anchor="w", font=theme.font(10, True))
        c.create_text(px(200), status_y + px(8), text="XP: {0}".format(self.score), fill=AMBER, anchor="w", font=theme.font(10, True))
        if self.sandbox_mode:
            c.create_text(px(300), status_y + px(8), text="ПЕСОЧНИЦА", fill=GREEN, anchor="w", font=theme.font(10, True))

        # Mission progress dots
        dot_x = w // 2 - len(self.missions) * px(10)
        for i in range(len(self.missions)):
            color = GREEN if i in self.completed_missions else (AMBER if i == self.mission_idx else MUTED)
            c.create_oval(dot_x + i * px(20), status_y + px(6), dot_x + i * px(20) + px(10), status_y + px(16), fill=color, outline="")

        # Overlay (help)
        if hasattr(self, 'overlay') and self.overlay:
            self._draw_overlay(c, w, h)

        if self.paused:
            self.draw_overlay("ПАУЗА")

    def _draw_overlay(self, c: tk.Canvas, w: int, h: int) -> None:
        overlay_w = min(w - px(40), px(800))
        overlay_h = min(h - px(40), px(500))
        x0 = (w - overlay_w) // 2
        y0 = (h - overlay_h) // 2

        c.create_rectangle(x0, y0, x0 + overlay_w, y0 + overlay_h, fill=BG, outline=AMBER, width=2)
        c.create_text(w // 2, y0 + px(12), text="ПОМОЩЬ", fill=AMBER, anchor="n", font=theme.font(14, True))

        y = y0 + px(40)
        for line in self.overlay:
            if y > y0 + overlay_h - px(30):
                break
            color = AMBER if line.startswith("===") else (CYAN if line.startswith("  docker") or line.startswith("  -") else (GREEN if line.startswith("Доступные") else TEXT))
            c.create_text(x0 + px(20), y, text=line, fill=color, anchor="nw", font=theme.font(10, mono=True), width=overlay_w - px(40))
            y += px(18)

        c.create_text(w // 2, y0 + overlay_h - px(12), text="F1 или Esc — закрыть", fill=MUTED, anchor="s", font=theme.font(10, True))


if __name__ == "__main__":
    import tkinter as tk
    root = tk.Tk()
    root.geometry("1000x700")
    game = DockerTrainerGame(root, on_back=lambda: None, app=None)
    game.pack(fill=tk.BOTH, expand=True)
    game.start()
    root.mainloop()