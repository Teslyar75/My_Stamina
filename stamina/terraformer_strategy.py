"""Стратегический слой тренажёра терраформера: уровни, отряды, задания, червь.

Модуль без Tk: им пользуется и логика (:mod:`stamina.terraformer_trainer`),
и интерфейс (:mod:`stamina.lounge.trainer`). Здесь живёт всё, что относится
к «стратегии», а не к отдельной клетке грунта:

* лестница уровней A1 … C2 — та же, что у английского (:mod:`stamina.english.cefr`);
* сколько терраформеров и какого уровня положено пилоту;
* задания-сообщения (Alert) и зелёные галочки выполненных;
* выбор рамкой и приказ идти (как в Dune / Red Alert);
* высота зданий и требования к уровню терраформера;
* песчаный червь: след, специя, опасность для техники на песке.

Правила намеренно простые и проверяемые тестами: ни одного Tk-вызова,
никакой сети, все решения детерминированы (кроме генератора карты по сиду).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import random

# ─── лестница уровней ────────────────────────────────────────────────────────
# Порядок и подписи совпадают с английским CEFR (stamina/english/cefr.py),
# чтобы тренажёр говорил с пилотом тем же языком, что и остальные отсеки.
LEVELS: tuple[str, ...] = ("A1", "A2", "B1.1", "B1.2", "B2.1", "B2.2", "C1", "C2")
LEVEL_TITLE: dict[str, str] = {
    "A1": "A1 · ВЫЖИВАНИЕ",
    "A2": "A2 · БЫТ",
    "B1.1": "B1.1 · ПОРОГ",
    "B1.2": "B1.2 · ПОРОГ+",
    "B2.1": "B2.1 · СВОБОДНО",
    "B2.2": "B2.2 · СВОБОДНО+",
    "C1": "C1 · ПРОДВИНУТЫЙ",
    "C2": "C2 · МАСТЕРСТВО",
}
LEVEL_INDEX: dict[str, int] = {name: i for i, name in enumerate(LEVELS)}

# Высота здания, которую умеет строить терраформер уровня.
# A1 — только фундамент и навес; C2 — атмосферные башни.
MAX_BUILD_HEIGHT: dict[str, int] = {
    "A1": 1, "A2": 2, "B1.1": 2, "B1.2": 3,
    "B2.1": 4, "B2.2": 5, "C1": 6, "C2": 8,
}
# Радиус обзора (клетки). Карта большая, видно сначала немного.
SIGHT_RADIUS: dict[str, int] = {
    "A1": 4, "A2": 5, "B1.1": 5, "B1.2": 6,
    "B2.1": 6, "B2.2": 7, "C1": 7, "C2": 9,
}
# Скорость: сколько клеток за тик.
UNIT_SPEED: dict[str, int] = {
    "A1": 1, "A2": 1, "B1.1": 1, "B1.2": 2,
    "B2.1": 2, "B2.2": 2, "C1": 2, "C2": 3,
}
# Урон червя, если техника стоит на песке (не на фундаменте/скале).
WORM_DAMAGE = 34
WORM_TRAIL_TTL = 14          # тиков, пока след виден
WORM_MOVE_EVERY = 3          # тиков между шагами червя
WORM_SPICE_CHANCE = 0.28     # шанс оставить специю на месте гибели/норы
SPICE = "spice"
FOUNDATION_SAFE = "foundation"   # тип клетки, где червь не достаёт технику


def level_index(name: str | None) -> int:
    """Индекс уровня 0…7; неизвестное имя — 0 (A1)."""
    return LEVEL_INDEX.get(str(name or "").strip(), 0)


def level_name(index: int) -> str:
    return LEVELS[max(0, min(len(LEVELS) - 1, int(index)))]


def max_height(level: str | None) -> int:
    return MAX_BUILD_HEIGHT.get(level_name(level_index(level)), 1)


def sight_radius(level: str | None) -> int:
    return SIGHT_RADIUS.get(level_name(level_index(level)), 4)


def unit_speed(level: str | None) -> int:
    return UNIT_SPEED.get(level_name(level_index(level)), 1)


def level_for_height(height: int) -> str:
    """Самый младший уровень терраформера, который построит здание такой высоты."""
    for name in LEVELS:
        if MAX_BUILD_HEIGHT[name] >= int(height):
            return name
    return LEVELS[-1]


def is_developer() -> bool:
    """Капитан-разработчик видит все уровни (см. stamina.roles)."""
    try:
        from stamina import pilots
        return bool(pilots.is_captain())
    except Exception:  # noqa: BLE001
        return False


# ─── прогресс пилота по уровням ──────────────────────────────────────────────

@dataclass
class LevelState:
    """Сколько процентов уровня пройдено и открыт ли он."""

    level: str
    index: int
    pct: int = 0
    unlocked: bool = False

    @property
    def title(self) -> str:
        return LEVEL_TITLE.get(self.level, self.level)


@dataclass
class Standing:
    """Права пилота в тренажёре на текущий момент."""

    levels: list[LevelState] = field(default_factory=list)
    developer: bool = False

    @property
    def current(self) -> LevelState:
        opened = [s for s in self.levels if s.unlocked]
        return opened[-1] if opened else self.levels[0]

    @property
    def current_level(self) -> str:
        return self.current.level

    def pct(self, level: str) -> int:
        for s in self.levels:
            if s.level == level:
                return s.pct
        return 0

    def unlocked(self, level: str) -> bool:
        return self.developer or any(s.unlocked and s.level == level for s in self.levels)

    @property
    def second_unit(self) -> bool:
        """Второй терраформер того же уровня — если пилот идёт с опережением."""
        return self.developer or self.current.pct >= 50

    @property
    def next_unit(self) -> bool:
        """Терраформер следующего уровня — если текущий пройден больше чем на 80 %."""
        return self.developer or self.current.pct > 80

    @property
    def next_level(self) -> str:
        return level_name(self.current.index + 1)

    def allowed_levels(self) -> tuple[str, ...]:
        """Какие уровни терраформеров пилот вправе выставить сейчас."""
        if self.developer:
            return LEVELS
        out = [self.current_level]
        if self.next_unit:
            nxt = self.next_level
            if nxt not in out:
                out.append(nxt)
        return tuple(out)


def _english_pct() -> dict[str, int]:
    """Процент пройденных слов по каждому уровню CEFR (0, если нет данных)."""
    out = {name: 0 for name in LEVELS}
    try:
        from stamina.english import access, cefr
        from stamina.english.progress import Progress
        from stamina import pilots

        progress = Progress(Path(pilots.active_dir()) / "english.json")
        levels = cefr.available()
        for name in levels:
            if name not in out:
                continue
            slugs = cefr.slugs(name)
            if not slugs:
                continue
            out[name] = access.level_pct(slugs, lambda s: bool(access._word_done(progress, s)))
    except Exception:  # noqa: BLE001
        pass
    return out


def standing(game_pct: dict[str, int] | None = None) -> Standing:
    """Текущее положение пилота.

    ``game_pct`` — проценты, заработанные внутри тренажёра (задания уровня).
    Берём максимум из языка и игры: успехи в любом отсеке двигают терраформеры.
    """
    dev = is_developer()
    lang = _english_pct()
    game_pct = game_pct or {}
    states: list[LevelState] = []
    prev_open = True
    for i, name in enumerate(LEVELS):
        pct = max(int(lang.get(name, 0)), int(game_pct.get(name, 0)))
        pct = max(0, min(100, pct))
        unlocked = dev or i == 0 or prev_open
        # следующий уровень открывается, когда предыдущий пройден больше чем на 80 %
        prev_open = dev or pct > 80
        states.append(LevelState(name, i, pct, unlocked))
    return Standing(levels=states, developer=dev)


# ─── задания и сообщения ─────────────────────────────────────────────────────

@dataclass
class Alert:
    """Сообщение пилоту в духе стратегии: тревога, задание, весть о находке."""

    kind: str                 # "mission" | "warn" | "info" | "reward"
    title: str
    body: str = ""
    level: str = "A1"
    read: bool = False
    stamp: float = 0.0

    def to_dict(self) -> dict:
        return {"kind": self.kind, "title": self.title, "body": self.body,
                "level": self.level, "read": self.read, "stamp": self.stamp}

    @classmethod
    def from_dict(cls, d: dict) -> "Alert":
        try:
            return cls(
                kind=str(d.get("kind", "info")),
                title=str(d.get("title", "")),
                body=str(d.get("body", "")),
                level=str(d.get("level", "A1")),
                read=bool(d.get("read", False)),
                stamp=float(d.get("stamp", 0.0)),
            )
        except (TypeError, ValueError):
            return cls("info", "")


@dataclass
class Mission:
    """Задание уровня. Метрика — число из статистики мира."""

    id: str
    level: str
    title: str
    hint: str
    metric: str
    target: int = 1
    reward_credits: int = 0
    done: bool = False

    def progress(self, stats: dict) -> int:
        try:
            return int(stats.get(self.metric, 0) or 0)
        except (TypeError, ValueError):
            return 0

    def evaluate(self, stats: dict) -> bool:
        if not self.done and self.progress(stats) >= self.target:
            self.done = True
        return self.done

    def to_dict(self) -> dict:
        return {"id": self.id, "done": self.done}

    @classmethod
    def from_dict(cls, spec: "Mission", d: dict) -> "Mission":
        m = Mission(**{k: getattr(spec, k) for k in (
            "id", "level", "title", "hint", "metric", "target", "reward_credits")})
        m.done = bool(d.get("done", False))
        return m


def mission_catalog() -> list[Mission]:
    """Три задания на каждый из восьми уровней — от «снять грунт» до «ядро»."""
    rows = [
        # A1
        ("a1-dig", "A1", "Первый грунт", "Сними 5 слоёв грунта пробелом.", "soil_dug", 5, 10),
        ("a1-find", "A1", "Первая находка", "Открой любую находку (Q).", "finds", 1, 15),
        ("a1-platform", "A1", "Первая платформа", "Дострой платформу добычи.", "platforms_complete", 1, 25),
        # A2
        ("a2-water", "A2", "Вода для базы", "Собери 20 единиц воды.", "water", 20, 20),
        ("a2-build", "A2", "Навес", "Построй укрытие (N).", "buildings_complete", 1, 30),
        ("a2-second", "A2", "Второй терраформер", "Получи второй терраформер уровня A2.", "units", 2, 40),
        # B1.1
        ("b11-organic", "B1.1", "Теплица", "Построй теплицу.", "buildings", 2, 30),
        ("b11-income", "B1.1", "Первый доход", "Накопи 100 кредитов.", "credits", 100, 30),
        ("b11-connect", "B1.1", "Связь", "Соедини два здания коммуникацией.", "connected", 1, 40),
        # B1.2
        ("b12-stone", "B1.2", "Каменный пояс", "Добудь 50 камня.", "stone", 50, 30),
        ("b12-worm", "B1.2", "След червя", "Увидь след песчаного червя.", "worm_seen", 1, 40),
        ("b12-spice", "B1.2", "Специя", "Подбери специю, оставленную червём.", "spice", 1, 60),
        # B2.1
        ("b21-height3", "B2.1", "Высота три", "Построй здание высотой 3.", "max_height", 3, 50),
        ("b21-iron", "B2.1", "Металл", "Добудь 30 железа.", "iron", 30, 50),
        ("b21-third", "B2.1", "Третий терраформер", "Доведи отряд до трёх единиц.", "units", 3, 60),
        # B2.2
        ("b22-quartz", "B2.2", "Кварц", "Добудь 30 кварца.", "quartz", 30, 60),
        ("b22-income", "B2.2", "Поток", "Накопи 500 кредитов.", "credits", 500, 60),
        ("b22-worm2", "B2.2", "Охота", "Переживи две атаки червя.", "worm_attacks", 2, 70),
        # C1
        ("c1-height5", "C1", "Высота пять", "Построй здание высотой 5.", "max_height", 5, 80),
        ("c1-connect", "C1", "Сеть", "Соедини четыре здания.", "connected", 4, 80),
        ("c1-spice5", "C1", "Специи", "Собери 5 специй.", "spice", 5, 100),
        # C2
        ("c2-height8", "C2", "Атмосферная башня", "Построй здание высотой 8.", "max_height", 8, 120),
        ("c2-core", "C2", "Ядро", "Построй ядро терраформирования.", "core", 1, 150),
        ("c2-world", "C2", "Новый мир", "Доведи карту до 100×60 клеток.", "map_cells", 6000, 200),
    ]
    return [Mission(*row) for row in rows]


class MissionBook:
    """Задания и лента сообщений. Выполненные задания не повторяются."""

    def __init__(self, missions: list[Mission] | None = None) -> None:
        self.missions = missions or mission_catalog()
        self.alerts: list[Alert] = []
        self.unread = 0

    def stats_pct(self) -> dict[str, int]:
        """Процент выполненных заданий по уровням — вклад игры в Standing."""
        out: dict[str, int] = {}
        for lv in LEVELS:
            items = [m for m in self.missions if m.level == lv]
            if items:
                out[lv] = int(100 * sum(1 for m in items if m.done) / len(items))
        return out

    def evaluate(self, stats: dict, stamp: float = 0.0) -> list[Mission]:
        """Отметить выполненные задания; вернуть те, что закрылись именно сейчас."""
        fresh: list[Mission] = []
        for m in self.missions:
            if m.evaluate(stats):
                if not getattr(m, "_announced", False):
                    m._announced = True
                    fresh.append(m)
                    self.push(Alert("mission", "✓ " + m.title,
                                    m.hint, m.level, stamp=stamp))
        return fresh

    def push(self, alert: Alert) -> Alert:
        self.alerts.append(alert)
        if not alert.read:
            self.unread += 1
        if len(self.alerts) > 60:
            del self.alerts[:-60]
        return alert

    def mark_read(self) -> None:
        for a in self.alerts:
            a.read = True
        self.unread = 0

    def by_level(self, level: str) -> list[Mission]:
        return [m for m in self.missions if m.level == level]

    def done_count(self, level: str | None = None) -> int:
        items = self.missions if level is None else self.by_level(level)
        return sum(1 for m in items if m.done)

    def to_dict(self) -> dict:
        return {
            "missions": [m.to_dict() for m in self.missions],
            "alerts": [a.to_dict() for a in self.alerts[-30:]],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MissionBook":
        book = cls()
        try:
            saved = {str(x.get("id")): bool(x.get("done")) for x in d.get("missions", [])
                     if isinstance(x, dict)}
        except Exception:  # noqa: BLE001
            saved = {}
        for m in book.missions:
            m.done = saved.get(m.id, False)
            m._announced = m.done
        try:
            book.alerts = [Alert.from_dict(x) for x in d.get("alerts", []) if isinstance(x, dict)]
        except Exception:  # noqa: BLE001
            book.alerts = []
        book.unread = sum(1 for a in book.alerts if not a.read)
        return book


# ─── отряд: выбор рамкой, приказы, поиск пути ───────────────────────────────

@dataclass
class Unit:
    """Терраформер-юнит на карте."""

    uid: str
    level: str
    x: int
    y: int
    hp: int = 100
    path: list[tuple[int, int]] = field(default_factory=list)
    target: tuple[int, int] | None = None
    order: str = ""
    serial: int = 1

    @property
    def name(self) -> str:
        return f"{self.level}-{self.serial}"

    @property
    def max_height(self) -> int:
        return max_height(self.level)

    @property
    def sight(self) -> int:
        return sight_radius(self.level)

    @property
    def moving(self) -> bool:
        return bool(self.path)

    def to_dict(self) -> dict:
        return {
            "uid": self.uid, "level": self.level, "x": self.x, "y": self.y,
            "hp": self.hp, "path": [list(p) for p in self.path],
            "target": list(self.target) if self.target else None,
            "order": self.order, "serial": self.serial,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Unit":
        path = []
        for p in d.get("path", []) or []:
            try:
                path.append((int(p[0]), int(p[1])))
            except (TypeError, ValueError, IndexError):
                continue
        target = d.get("target")
        try:
            tgt = (int(target[0]), int(target[1])) if target else None
        except (TypeError, ValueError, IndexError):
            tgt = None
        return cls(
            uid=str(d.get("uid", "unit")), level=str(d.get("level", "A1")),
            x=int(d.get("x", 0)), y=int(d.get("y", 0)), hp=int(d.get("hp", 100)),
            path=path, target=tgt, order=str(d.get("order", "")),
            serial=int(d.get("serial", 1)),
        )


def pathfind(start: tuple[int, int], goal: tuple[int, int], w: int, h: int,
             blocked: set[tuple[int, int]] | None = None,
             limit: int = 6000) -> list[tuple[int, int]]:
    """Кратчайший путь по 4 направлениям (BFS). Пустой список — пути нет.

    ``blocked`` — непроходимые клетки (здания, источники). Цель, даже если она
    в ``blocked``, остаётся доступной: юнит подходит к ней вплотную.
    """
    sx, sy = int(start[0]), int(start[1])
    gx, gy = int(goal[0]), int(goal[1])
    if not (0 <= gx < w and 0 <= gy < h):
        return []
    if (sx, sy) == (gx, gy):
        return []
    blocked = blocked or set()
    from collections import deque

    q = deque([(sx, sy)])
    prev: dict[tuple[int, int], tuple[int, int] | None] = {(sx, sy): None}
    seen = 0
    while q and seen < limit:
        x, y = q.popleft()
        seen += 1
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h):
                continue
            cell = (nx, ny)
            if cell in prev:
                continue
            if cell in blocked and cell != (gx, gy):
                continue
            prev[cell] = (x, y)
            if cell == (gx, gy):
                path: list[tuple[int, int]] = []
                cur: tuple[int, int] | None = cell
                while cur is not None and cur != (sx, sy):
                    path.append(cur)
                    cur = prev[cur]
                path.reverse()
                return path
            q.append(cell)
    return []


def units_in_rect(units: list[Unit], x0: int, y0: int, x1: int, y1: int) -> list[Unit]:
    """Выделение рамкой: клетки включительно, порядок не важен."""
    ax, bx = sorted((int(x0), int(x1)))
    ay, by = sorted((int(y0), int(y1)))
    return [u for u in units if ax <= u.x <= bx and ay <= u.y <= by]


def formation_targets(units: list[Unit], tx: int, ty: int) -> dict[str, tuple[int, int]]:
    """Куда встать каждому юниту, чтобы отряд не толкался в одной клетке."""
    out: dict[str, tuple[int, int]] = {}
    n = len(units)
    if n == 0:
        return out
    if n == 1:
        out[units[0].uid] = (tx, ty)
        return out
    side = 1
    while side * side < n:
        side += 1
    start = -(side // 2)
    for i, u in enumerate(sorted(units, key=lambda u: u.uid)):
        dx = start + (i % side)
        dy = start + (i // side)
        out[u.uid] = (tx + dx, ty + dy)
    return out


def issue_move(units: list[Unit], tx: int, ty: int, w: int, h: int,
               blocked: set[tuple[int, int]] | None = None) -> dict[str, int]:
    """Приказ идти. Возвращает {uid: длина пути}; 0 — пути нет."""
    result: dict[str, int] = {}
    for uid, (gx, gy) in formation_targets(units, tx, ty).items():
        unit = next((u for u in units if u.uid == uid), None)
        if unit is None:
            continue
        gx = max(0, min(w - 1, gx))
        gy = max(0, min(h - 1, gy))
        path = pathfind((unit.x, unit.y), (gx, gy), w, h, blocked)
        unit.path = path
        unit.target = (gx, gy)
        unit.order = "move"
        result[uid] = len(path)
    return result


# ─── здания ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Structure:
    """Чертёж здания: высота, цена, доход, нужный уровень терраформера."""

    key: str
    title: str
    height: int
    cost: int
    income: int
    level: str
    hint: str = ""

    @property
    def min_index(self) -> int:
        return level_index(self.level)


STRUCTURES: dict[str, Structure] = {
    "shelter": Structure("shelter", "Укрытие", 1, 0, 1, "A1",
                         "Навес от пыли. Первый доход базы."),
    "greenhouse": Structure("greenhouse", "Теплица", 2, 40, 2, "A2",
                            "Органика в пищу и рассаду."),
    "energy_panel": Structure("energy_panel", "Энергопанель", 2, 60, 3, "A2",
                              "Питание для насосов и вышек."),
    "refinery": Structure("refinery", "Переработка", 3, 120, 5, "B1.1",
                          "Железо и кварц превращаются в материалы."),
    "habitat": Structure("habitat", "Жилой блок", 4, 200, 7, "B2.1",
                         "Поселенцы платят за жильё."),
    "radar": Structure("radar", "Радар", 5, 320, 9, "B2.2",
                       "Открывает карту вокруг базы."),
    "spire": Structure("spire", "Шпиль связи", 6, 500, 12, "C1",
                       "Коммуникации между колониями."),
    "core": Structure("core", "Ядро терраформирования", 8, 900, 20, "C2",
                      "Меняет биом планеты."),
}


def structure_available(key: str, level: str | None, developer: bool = False) -> bool:
    spec = STRUCTURES.get(key)
    if spec is None:
        return False
    if developer:
        return True
    return level_index(level) >= spec.min_index


# ─── песчаный червь ──────────────────────────────────────────────────────────

@dataclass
class Sandworm:
    """Червь идёт под песком, оставляет след и иногда специю."""

    x: int
    y: int
    heading: int = 0
    trail: dict[tuple[int, int], int] = field(default_factory=dict)
    cooldown: int = 0
    attacks: int = 0
    alive: bool = True

    def to_dict(self) -> dict:
        return {
            "x": self.x, "y": self.y, "heading": self.heading,
            "trail": [[x, y, ttl] for (x, y), ttl in self.trail.items()],
            "cooldown": self.cooldown, "attacks": self.attacks, "alive": self.alive,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Sandworm":
        trail: dict[tuple[int, int], int] = {}
        for item in d.get("trail", []) or []:
            try:
                trail[(int(item[0]), int(item[1]))] = int(item[2])
            except (TypeError, ValueError, IndexError):
                continue
        return cls(
            x=int(d.get("x", 0)), y=int(d.get("y", 0)),
            heading=int(d.get("heading", 0)), trail=trail,
            cooldown=int(d.get("cooldown", 0)), attacks=int(d.get("attacks", 0)),
            alive=bool(d.get("alive", True)),
        )


def worm_step(worm: Sandworm, w: int, h: int, seed: int,
              deposits: set[tuple[int, int]],
              safe: set[tuple[int, int]]) -> tuple[tuple[int, int] | None, bool]:
    """Один шаг червя.

    Возвращает ``(клетка_атаки | None, оставил_специю)``. Червь обходит
    месторождения (``deposits``) и не трогает технику на ``safe``-клетках.
    След удлиняется, старые метки стареют.
    """
    rng = random.Random(f"worm:{seed}:{worm.x}:{worm.y}:{worm.cooldown}")
    # след стареет
    for cell in list(worm.trail):
        worm.trail[cell] -= 1
        if worm.trail[cell] <= 0:
            del worm.trail[cell]
    worm.trail[(worm.x, worm.y)] = WORM_TRAIL_TTL

    dirs = [(1, 0), (0, 1), (-1, 0), (0, -1)]
    worm.heading = (worm.heading + rng.choice((-1, 0, 1))) % 4
    dx, dy = dirs[worm.heading]
    nx, ny = worm.x + dx, worm.y + dy
    if not (0 <= nx < w and 0 <= ny < h) or (nx, ny) in deposits:
        # разворот и попытка в другую сторону
        worm.heading = (worm.heading + 2) % 4
        dx, dy = dirs[worm.heading]
        nx, ny = worm.x + dx, worm.y + dy
        if not (0 <= nx < w and 0 <= ny < h) or (nx, ny) in deposits:
            nx, ny = worm.x, worm.y
    worm.x, worm.y = nx, ny
    spice = False
    if rng.random() < WORM_SPICE_CHANCE:
        spice = True
    return (worm.x, worm.y) if (worm.x, worm.y) not in safe else None, spice


def worm_safe_cells(foundation: set[tuple[int, int]],
                    rocks: set[tuple[int, int]]) -> set[tuple[int, int]]:
    return set(foundation) | set(rocks)


def find_for_cell(seed: int, x: int, y: int) -> tuple[str, int] | None:
    """Детерминированная находка для новой клетки расширяющейся карты.

    Старая часть карты генерируется прежним способом (``generate_finds``),
    поэтому расширение не перетасовывает уже открытые ресурсы.
    """
    rng = random.Random(f"terraformer-edge:{int(seed)}:{int(x)}:{int(y)}")
    if rng.random() >= 0.06:
        return None
    layer = rng.choices((0, 1, 2), weights=(5, 3, 2))[0]
    if layer == 0:
        res = rng.choices(("organic", "quartz", "water"), weights=(6, 2, 2))[0]
    elif layer == 1:
        res = rng.choices(("stone", "quartz"), weights=(7, 3))[0]
    else:
        res = "iron"
    return res, layer


# ─── снимок карты для будущего онлайн-сообщества ────────────────────────────

def community_snapshot(model, pilot: str = "") -> dict:
    """Экспорт карты пилота: задел под «сражения цивилизаций» в онлайне."""
    try:
        data = model.to_blueprint()
    except Exception:  # noqa: BLE001
        data = {}
    data.pop("dug", None)           # рельеф не нужен чужой карте
    data.pop("revealed", None)
    data["pilot"] = pilot
    data["kind"] = "terraformer_community"
    data["levels"] = list(LEVELS)
    return data
