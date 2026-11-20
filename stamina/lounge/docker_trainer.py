"""Docker Trainer — interactive Docker CLI tutorial game for the Lounge.

Teaches Docker commands through progressive missions in a terminal-style interface.
"""
from __future__ import annotations

from stamina.i18n import t as _t

import tkinter as tk

from stamina import theme
from stamina.theme import AMBER, BG, BG2, CYAN, GREEN, MUTED, TEXT, px

from .base import GameShell
from . import store
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
        "check": lambda sim, out: "ship_radio" in sim.containers or any(c.image.name == "radio" for c in sim.containers.values()),
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
]


# ─── Helper Functions ──────────────────────────────────────────────────────────

def mission_key() -> str:
    return _t("↑/↓ — история команд · Tab — дописать · F1 — помощь · Esc — пауза")


# ─── Docker Trainer Game ───────────────────────────────────────────────────────

class DockerTrainerGame(GameShell):
    game_id = "docker_trainer"
    title = _t("DOCKER ТРЕНАЖЁР · ДОК-СТАНЦИЯ")

    def __init__(self, master, **kw) -> None:
        super().__init__(master, **kw)
        self.sim = DockerSimulator()
        self.mission_idx = 0
        self.completed_missions: set[int] = set()
        self.history: list[str] = []
        self.history_pos = -1
        self.command_buffer = ""
        self.output_lines: list[tuple[str, str]] = []  # (text, color)
        self.pending_mission_check = False
        self.sandbox_mode = False
        self.load_progress()
        self._load_mission(0)
        self.set_hint(mission_key())
        self._add_output(_t("Добро пожаловать на Док-станцию!"), CYAN)
        self._add_output(_t("Введи команды docker. F1 — помощь, Tab — автодополнение."), MUTED)
        self._add_output("", TEXT)

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
        if self.mission_idx >= len(MISSIONS):
            self.mission_idx = len(MISSIONS) - 1

    def save_progress(self) -> None:
        data = store.load()
        data["docker_trainer"] = {
            "completed": list(self.completed_missions),
            "current_mission": self.mission_idx,
            "sandbox_state": self.sim.to_dict() if self.sandbox_mode else None,
        }
        store.save(data)

    def _load_mission(self, idx: int) -> None:
        if idx < 0 or idx >= len(MISSIONS):
            return
        self.mission_idx = idx
        mission = MISSIONS[idx]
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
        self.sim = DockerSimulator()
        self.mission_idx = 0
        self.completed_missions.clear()
        self.history.clear()
        self.history_pos = -1
        self.output_lines.clear()
        self.command_buffer = ""
        self.sandbox_mode = False
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
            return MISSIONS[self.mission_idx]["id"]
        except (IndexError, KeyError, TypeError):
            return "mission_1"

    def on_key(self, e: tk.Event) -> None:
        if self.handle_help_keys(e):
            return
        k = e.keysym
        state = getattr(e, "state", 0) or 0
        ctrl = bool(state & 0x4)
        shift = bool(state & 0x1)

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

        # Printable characters
        if len(k) == 1 and k.isprintable():
            self.command_buffer += k
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

        # Check mission completion
        mission = MISSIONS[self.mission_idx]
        if mission["check"](self.sim, out):
            self._complete_mission()

        self._redraw_input_line()
        self.redraw()

    def _complete_mission(self) -> None:
        if self.mission_idx not in self.completed_missions:
            self.completed_missions.add(self.mission_idx)
            xp = MISSIONS[self.mission_idx].get("xp", 50)
            self.add_score(xp)
            self._add_output("", TEXT)
            self._add_output(_t("✓ Миссия выполнена! +{0} XP").format(xp), GREEN)
            self.save_progress()

        if self.mission_idx + 1 < len(MISSIONS):
            self.mission_idx += 1
            self._load_mission(self.mission_idx)
        else:
            self._add_output("", TEXT)
            self._add_output(_t("🎉 Все миссии пройдены! Режим песочницы разблокирован."), GREEN)
            self._add_output(_t("Теперь ты можешь свободно экспериментировать с Docker командами."), CYAN)
            self.sandbox_mode = True
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
        """Simple tab completion for docker commands."""
        completions = [
            "docker run", "docker ps", "docker logs", "docker stop", "docker rm",
            "docker images", "docker pull", "docker build", "docker port",
            "docker volume", "docker network", "docker compose", "docker system",
            "ship/radio", "ship/orion", "ship/lab", "ship/scanner", "ship/base",
            "-d", "-p", "--name", "-v", "-e", "--label", "-t", "--detach",
            "create", "ls", "rm", "prune", "up", "down", "port",
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
        self._redraw_input_line()
        self.redraw()

    def _add_output(self, text: str, color: str) -> None:
        self.output_lines.append((text, color))
        # Limit history
        if len(self.output_lines) > 500:
            self.output_lines = self.output_lines[-400:]

    def _redraw_input_line(self) -> None:
        pass  # Handled in redraw

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

    def redraw(self) -> None:
        c = self.canvas
        c.delete("all")
        w = max(c.winfo_width(), 10)
        h = max(c.winfo_height(), 10)

        # Background
        c.create_rectangle(0, 0, w, h, fill=BG, outline="")

        # Terminal area (most of screen)
        term_h = h - px(60)
        c.create_rectangle(px(8), px(8), w - px(8), term_h, fill="#0D1117", outline=MUTED, width=1)

        # Output lines
        font = theme.font(11, mono=True)
        line_h = px(18)
        max_lines = (term_h - px(16)) // line_h
        start_y = term_h - px(8) - line_h

        # Show last N lines
        visible = self.output_lines[-max_lines:] if len(self.output_lines) > max_lines else self.output_lines
        y = start_y
        for text, color in visible:
            if y < px(16):
                break
            if text:
                c.create_text(px(16), y, text=text, fill=color, anchor="nw", font=font, width=w - px(32))
            y -= line_h

        # Input line
        input_y = term_h + px(4)
        c.create_text(px(16), input_y, text="$", fill=AMBER, anchor="nw", font=font)
        c.create_text(px(30), input_y, text=self.command_buffer + "█", fill=TEXT, anchor="nw", font=font, width=w - px(40))

        # Status bar
        status_y = h - px(40)
        c.create_rectangle(0, status_y, w, h, fill=BG2, outline=MUTED)
        c.create_text(px(10), status_y + px(8), text=_t("Миссия {0}/{1}").format(self.mission_idx + 1, len(MISSIONS)), fill=CYAN, anchor="w", font=theme.font(10, True))
        c.create_text(px(200), status_y + px(8), text=_t("XP: {0}").format(self.score), fill=AMBER, anchor="w", font=theme.font(10, True))
        if self.sandbox_mode:
            c.create_text(px(300), status_y + px(8), text=_t("ПЕСОЧНИЦА"), fill=GREEN, anchor="w", font=theme.font(10, True))
        c.create_text(w - px(10), status_y + px(8), text=mission_key(), fill=MUTED, anchor="e", font=theme.font(9))

        # Mission progress dots
        dot_x = w // 2 - len(MISSIONS) * px(10)
        for i in range(len(MISSIONS)):
            color = GREEN if i in self.completed_missions else (AMBER if i == self.mission_idx else MUTED)
            c.create_oval(dot_x + i * px(20), status_y + px(6), dot_x + i * px(20) + px(10), status_y + px(16), fill=color, outline="")

        # Overlay (help)
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
            color = AMBER if line.startswith("===") else (CYAN if line.startswith("  docker") or line.startswith("  -") else (GREEN if line.startswith("Доступные") else TEXT))
            c.create_text(x0 + px(20), y, text=line, fill=color, anchor="nw", font=theme.font(10, mono=True), width=overlay_w - px(40))
            y += px(18)

        c.create_text(w // 2, y0 + overlay_h - px(12), text=_t("F1 или Esc — закрыть"), fill=MUTED, anchor="s", font=theme.font(10, True))


if __name__ == "__main__":
    import tkinter as tk
    root = tk.Tk()
    root.geometry("1000x700")
    game = DockerTrainerGame(root, on_back=lambda: None, app=None)
    game.pack(fill=tk.BOTH, expand=True)
    game.start()
    root.mainloop()