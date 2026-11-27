"""Тренажёр терраформера A1 — чистая логика без Tk.

Модель поля, камера и сохранение чертежа. Отрисовка живёт в lounge/trainer.py.

Находки: при создании площадки по сиду (он хранится в чертеже) в клетки прячутся
ресурсы — вода, камень, органика, железная руда, кварцевый песок. Находка
открывается один раз, когда робот снимает слой, в котором она лежит; урожай идёт
в отдельный отсек «Находки» и места в отсеке грунта не занимает. Находки в слоях
глубже, чем копает робот, не показываются — их откроют роботы A2+.
"""
from __future__ import annotations

import json
import math
import random
import time
from pathlib import Path
from stamina.i18n import t as _t

from stamina import terraformer_strategy as strategy
from stamina.terraformer_strategy import find_for_cell

GRID_W = 40
GRID_H = 24
LAYERS = ("soil", "clay", "metal")
# Блок фундамента = 5 единиц грунта (было 10). Пресс делает блок из 3.
HOLD_CAP = 5
SITE = (2, 2, 4, 3)          # x, y, width, height — 12 блоков фундамента
BLUEPRINT_NAME = "terraformer_trainer.json"
ARCHIVE_DIR = "terraformer_trainer_archive"
ARCHIVE_KEEP = 20
ZOOM_MIN = 0.5
ZOOM_MAX = 3.0
ZOOM_STEP = 1.25
BASE_CELL = 28

RESOURCES = ("water", "stone", "organic", "iron", "quartz")
# (ресурс, слой, сколько) — ~6 % клеток; A1 (только верхний слой) находит органику,
# кварцевый песок и два источника воды.
FIND_PLAN = (
    ("water", 0, 2), ("water", 1, 1),
    ("organic", 0, 18),
    ("quartz", 0, 3), ("quartz", 1, 3),
    ("stone", 1, 20),
    ("iron", 2, 12),
)

# ─── платформы добычи ────────────────────────────────────────────────────────
# Паттерны клеток относительно центра находки (dx, dy).
# Центр (0,0) — это сама находка, блок там не ставится (насос/шахта строится автоматически).
# Несколько вариантов на ресурс: пилот выбирает в галерее.
PLATFORM_VARIANTS: dict[str, tuple[tuple[tuple[int, int], ...], ...]] = {
    "water": (
        # Вариант 1: Классический 3x3 периметр (8 блоков)
        (
            (-1, -1), (0, -1), (1, -1),
            (-1,  0),          (1,  0),
            (-1,  1), (0,  1), (1,  1),
        ),
        # Вариант 2: Компактный «П-образ» (5 блоков) — только три стороны
        (
            (-1, -1), (0, -1), (1, -1),
            (-1,  0),          (1,  0),
        ),
        # Вариант 3: Расширенный 5x5 с резервуаром (16 блоков) — больше добыча
        (
            (-2, -2), (-1, -2), (0, -2), (1, -2), (2, -2),
            (-2, -1),                                 (2, -1),
            (-2,  0),                                 (2,  0),
            (-2,  1),                                 (2,  1),
            (-2,  2), (-1,  2), (0,  2), (1,  2), (2,  2),
        ),
    ),
    "stone": (
        # Вариант 1: Классический 3x3 (8 блоков)
        (
            (-1, -1), (0, -1), (1, -1),
            (-1,  0),          (1,  0),
            (-1,  1), (0,  1), (1,  1),
        ),
        # Вариант 2: Линейная карьерная (6 блоков в ряд)
        (
            (-3, 0), (-2, 0), (-1, 0), (1, 0), (2, 0), (3, 0),
        ),
        # Вариант 3: Круглый фундамент (12 блоков)
        (
            (-2, -1), (-1, -1), (0, -1), (1, -1), (2, -1),
            (-2,  0),                          (2,  0),
            (-2,  1), (-1,  1), (0,  1), (1,  1), (2,  1),
        ),
    ),
    "organic": (
        # Вариант 1: Классический 3x3 (8 блоков)
        (
            (-1, -1), (0, -1), (1, -1),
            (-1,  0),          (1,  0),
            (-1,  1), (0,  1), (1,  1),
        ),
        # Вариант 2: Тепличный ряд (6 блоков)
        (
            (-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0), (3, 0),
        ),
        # Вариант 3: Компостная куча 3x3 с вентиляцией (8 блоков)
        (
            (-1, -1), (0, -1), (1, -1),
            (-1,  0),          (1,  0),
            (-1,  1),          (1,  1),
        ),
    ),
    "iron": (
        # Вариант 1: Плюс-форма (4 блока) — базовая шахта
        (
            (0, -1), (1, 0), (0, 1), (-1, 0),
        ),
        # Вариант 2: Двойная шахта (6 блоков) — два входа
        (
            (0, -1), (1, 0), (0, 1), (-1, 0),
            (2, 0), (0, 2),
        ),
        # Вариант 3: Промышленный комплекс 5x5 (16 блоков) — конвейер + дробление
        (
            (-2, -2), (-1, -2), (0, -2), (1, -2), (2, -2),
            (-2, -1),                                 (2, -1),
            (-2,  0),                                 (2,  0),
            (-2,  1), (-1,  1), (0,  1), (1,  1), (2,  1),
            (-2,  2), (-1,  2), (0,  2), (1,  2), (2,  2),
        ),
    ),
    "quartz": (
        # Вариант 1: Крест по диагоналям (4 блока) — базовая печь
        (
            (-1, -1), (1, -1), (1, 1), (-1, 1),
        ),
        # Вариант 2: Солнечная решётка (8 блоков) — фотоэлектрика
        (
            (-2, -1), (-1, -1), (0, -1), (1, -1), (2, -1),
            (-2,  1), (-1,  1), (0,  1), (1,  1), (2,  1),
        ),
        # Вариант 3: Кварцевая рефракторная башня (12 блоков) — оптика
        (
            (-2, -2), (-1, -2), (0, -2), (1, -2), (2, -2),
            (-2, -1),                          (2, -1),
            (-2,  0),                          (2,  0),
            (-2,  1),                          (2,  1),
            (-2,  2), (-1,  2), (0,  2), (1,  2), (2,  2),
        ),
    ),
}

# Награда за цикл (тик) для завершённой платформы — зависит от варианта
PLATFORM_YIELD: dict[str, tuple[str, int]] = {
    "water": ("water", 10),
    "stone": ("stone", 5),
    "organic": ("organic", 8),
    "iron": ("iron", 3),
    "quartz": ("quartz", 4),
}

# Множители награды по вариантам (базовый * множитель)
VARIANT_YIELD_MULT: dict[str, tuple[float, ...]] = {
    "water": (1.0, 0.6, 1.8),
    "stone": (1.0, 0.8, 1.5),
    "organic": (1.0, 0.7, 1.3),
    "iron": (1.0, 1.3, 2.0),
    "quartz": (1.0, 1.2, 1.6),
}

# Описания вариантов для галереи
VARIANT_DESC: dict[str, tuple[str, ...]] = {
    "water": (
        _t("Стандартная насосная площадка 3×3. Надёжная, средняя добыча."),
        _t("Компактная П-образная. Быстро строится, меньше вода."),
        _t("Расширенная с резервуаром 5×5. Максимальная добыча, много блоков."),
    ),
    "stone": (
        _t("Классический каменоломный контур 3×3. Сбалансированный."),
        _t("Линейная карьерная полоса. Удобна вдоль склона."),
        _t("Круглый фундамент с дроблённой зоной. Высокая добыча."),
    ),
    "organic": (
        _t("Стандартная компостная площадка 3×3."),
        _t("Тепличный ряд — удобен для длинных грядок."),
        _t("Компостная куча с вентиляцией. Ускоренное перегнивание."),
    ),
    "iron": (
        _t("Базовая шахта плюс-форма. Минимум блоков."),
        _t("Двойная шахта — два входа, лучше вентиляция."),
        _t("Промышленный комплекс с конвейером и дроблением. Максимум руды."),
    ),
    "quartz": (
        _t("Базовая печь крест-накрест. Компактная."),
        _t("Солнечная решётка — использует свет для очистки."),
        _t("Рефракторная башня — оптическое качество кварца."),
    ),
}

# Ресурсы, требующие A2 (глина/металл) для доступа к центру
DEEP_RESOURCES = {"iron", "quartz"}

HOLD_CAP_WITH_UPGRADES = {
    "soil_compactor": 3,
    "default": 5,
}


# ─── система прогрессии: разблокировка вариантов и роботов через язык ─────────
# Лестница та же, что у английского: A1, A2, B1.1, B1.2, B2.1, B2.2, C1, C2.
# Индекс 0…7. Уровень — максимум из языка, успехов в других отсеках и заданий
# тренажёра (см. stamina.terraformer_strategy.standing).
# Пилот видит все варианты в галерее, но строить может только открытые.

_ALL_VARIANTS = {res: (0, 1, 2) for res in RESOURCES}

PROGRESSION_TIERS = {
    0: {  # A1 · Высадка
        "platform_variants": {res: (0,) for res in RESOURCES},
        "robots": ("A1",),
        "upgrades": (),
        "description": _t("A1: базовые платформы и робот A1. Копайте грунт, ставьте первые блоки."),
    },
    1: {  # A2 · быт
        "platform_variants": {res: (0, 1) for res in RESOURCES},
        "robots": ("A1", "A2"),
        "upgrades": ("soil_compactor",),
        "description": _t("A2: компактные платформы, робот A2 и пресс для грунта (блок из 3 единиц)."),
    },
    2: {  # B1.1 · порог
        "platform_variants": dict(_ALL_VARIANTS),
        "robots": ("A1", "A2", "B1.1"),
        "upgrades": ("soil_compactor", "auto_unloader", "water_purifier"),
        "description": _t("B1.1: все варианты платформ, робот B1.1, автовыгрузка и очистка воды."),
    },
    3: {  # B1.2 · порог+
        "platform_variants": dict(_ALL_VARIANTS),
        "robots": ("A1", "A2", "B1.1", "B1.2"),
        "upgrades": ("soil_compactor", "auto_unloader", "water_purifier", "yield_booster"),
        "description": _t("B1.2: робот B1.2, усилитель добычи +50% и быстрый шаг по карте."),
    },
    4: {  # B2.1 · свободно
        "platform_variants": dict(_ALL_VARIANTS),
        "robots": ("A1", "A2", "B1.1", "B1.2", "B2.1"),
        "upgrades": ("soil_compactor", "auto_unloader", "water_purifier", "yield_booster", "remote_control"),
        "description": _t("B2.1: робот B2.1, дистанционное управление отрядом и здания высотой 4."),
    },
    5: {  # B2.2 · свободно+
        "platform_variants": dict(_ALL_VARIANTS),
        "robots": ("A1", "A2", "B1.1", "B1.2", "B2.1", "B2.2"),
        "upgrades": ("soil_compactor", "auto_unloader", "water_purifier", "yield_booster",
                     "remote_control", "logistics_network"),
        "description": _t("B2.2: робот B2.2, логистическая сеть и здания высотой 5."),
    },
    6: {  # C1 · продвинутый
        "platform_variants": dict(_ALL_VARIANTS),
        "robots": ("A1", "A2", "B1.1", "B1.2", "B2.1", "B2.2", "C1"),
        "upgrades": ("soil_compactor", "auto_unloader", "water_purifier", "yield_booster",
                     "remote_control", "logistics_network", "auto_builder"),
        "description": _t("C1: робот C1, автостроитель и шпили высотой 6."),
    },
    7: {  # C2 · мастерство
        "platform_variants": dict(_ALL_VARIANTS),
        "robots": tuple(strategy.LEVELS),
        "upgrades": ("soil_compactor", "auto_unloader", "water_purifier", "yield_booster",
                     "remote_control", "logistics_network", "auto_builder", "terraform_core"),
        "description": _t("C2: робот C2, ядро терраформирования и башни высотой 8."),
    },
}

# Высота готового здания по варианту платформы. Фундамент ниже, башни выше.
PLATFORM_HEIGHT: dict[str, tuple[int, ...]] = {
    "water": (1, 2, 4),
    "stone": (1, 2, 3),
    "organic": (1, 2, 3),
    "iron": (2, 3, 6),
    "quartz": (2, 4, 8),
}


def platform_height(resource: str, variant_index: int = 0) -> int:
    heights = PLATFORM_HEIGHT.get(resource, (1,))
    return heights[max(0, min(len(heights) - 1, int(variant_index)))]


_standing_cache: tuple[float, int, "strategy.Standing"] | None = None


def current_standing(refresh: bool = False) -> "strategy.Standing":
    """Положение пилота с кэшем на 5 секунд (редро каждый тик не должен грузить словарь)."""
    global _standing_cache
    now = time.monotonic()
    if not refresh and _standing_cache is not None and now - _standing_cache[0] < 5.0:
        return _standing_cache[2]
    st = strategy.standing()
    _standing_cache = (now, id(st), st)
    return st


def get_language_level_from_tiers(language_level: int) -> int:
    """Индекс уровня 0…7 для PROGRESSION_TIERS."""
    return max(0, min(len(strategy.LEVELS) - 1, int(language_level)))


def _language_xp(path: Path) -> int:
    """Читает XP из файла прогресса языка."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("xp", {}).get("total", 0)
    except Exception:
        return 0


def get_language_level() -> int:
    """Текущий уровень пилота 0…7 (A1 … C2).

    Учитывает английский CEFR, немецкий XP, задания тренажёра и роль капитана.
    """
    try:
        return current_standing().current.index
    except Exception:  # noqa: BLE001
        return 0


def get_level_name(index: int | None = None) -> str:
    if index is None:
        index = get_language_level()
    return strategy.level_name(index)


def _tier_index(language_level: int | None = None) -> int:
    if language_level is None:
        language_level = get_language_level()
    return get_language_level_from_tiers(language_level)


def get_unlocked_variants(resource: str, language_level: int | None = None) -> tuple[int, ...]:
    """Возвращает индексы разблокированных вариантов для ресурса."""
    tier_idx = _tier_index(language_level)
    tier = PROGRESSION_TIERS[tier_idx]
    return tier["platform_variants"].get(resource, (0,))


def get_unlocked_robots(language_level: int | None = None) -> tuple[str, ...]:
    tier_idx = _tier_index(language_level)
    tier = PROGRESSION_TIERS[tier_idx]
    return tier["robots"]


def get_unlocked_upgrades(language_level: int | None = None) -> tuple[str, ...]:
    tier_idx = _tier_index(language_level)
    tier = PROGRESSION_TIERS[tier_idx]
    return tier["upgrades"]


def get_tier_description(language_level: int | None = None) -> str:
    if language_level is None:
        language_level = get_language_level()
    tier = PROGRESSION_TIERS.get(get_language_level_from_tiers(language_level), PROGRESSION_TIERS[0])
    return tier["description"]


def get_next_tier_preview(language_level: int | None = None) -> dict | None:
    """Что откроется на следующем уровне — для мотивации в галерее."""
    if language_level is None:
        language_level = get_language_level()
    next_level = min(language_level + 1, len(strategy.LEVELS) - 1)
    if next_level == language_level:
        return None
    return PROGRESSION_TIERS.get(next_level)


# Для совместимости со старым кодом — берём первый вариант как дефолт
PLATFORM_PATTERNS: dict[str, tuple[tuple[int, int], ...]] = {
    res: variants[0] for res, variants in PLATFORM_VARIANTS.items()
}

# Награда за цикл (тик) для завершённой платформы
PLATFORM_YIELD: dict[str, tuple[str, int]] = {
    "water": ("water", 10),
    "stone": ("stone", 5),
    "organic": ("organic", 8),
    "iron": ("iron", 3),
    "quartz": ("quartz", 4),
}

# Ресурсы, требующие A2 (глина/металл) для доступа к центру
DEEP_RESOURCES = {"iron", "quartz"}

from dataclasses import dataclass, field


@dataclass
class PlatformBlueprint:
    """Чертеж платформы добычи вокруг находки."""
    resource: str
    center: tuple[int, int]          # координаты находки
    pattern: tuple[tuple[int, int], ...]  # относительные клетки для блоков
    built: set[tuple[int, int]] = field(default_factory=set)  # уже уложенные блоки
    complete: bool = False
    priority: int = 0                # 0 = неактивен, >0 = приоритет (больше = важнее)
    requires_a2: bool = False        # центр недоступен без A2
    variant_index: int = 0           # какой вариант из PLATFORM_VARIANTS выбран
    height: int = 1                  # высота готового здания
    required_level: str = "A1"       # младший терраформер, который его построит

    def total_cells(self) -> int:
        return len(self.pattern)

    def built_count(self) -> int:
        return len(self.built)

    def progress_pct(self) -> int:
        if self.total_cells() == 0:
            return 100
        return int(100 * self.built_count() / self.total_cells())

    def cell_abs(self, rel: tuple[int, int]) -> tuple[int, int]:
        return (self.center[0] + rel[0], self.center[1] + rel[1])

    def all_cells_abs(self) -> list[tuple[int, int]]:
        return [self.cell_abs(r) for r in self.pattern]

    def is_cell_part(self, x: int, y: int) -> bool:
        return (x, y) in self.all_cells_abs()

    def try_add_block(self, x: int, y: int) -> bool:
        """Пытается добавить блок в эту платформу. Возвращает True, если блок принят."""
        if self.complete:
            return False
        if (x, y) not in self.all_cells_abs():
            return False
        if (x, y) in self.built:
            return False
        self.built.add((x, y))
        if self.built_count() >= self.total_cells():
            self.complete = True
        return True


def new_seed() -> int:
    return random.SystemRandom().randrange(1, 2 ** 31)


def generate_finds(seed: int, w: int, h: int, exclude=()) -> dict:
    """{(x, y): (ресурс, слой)} — детерминированно по сиду и размеру поля.

    Для малых карт (≤ 40×24) использует фиксированный FIND_PLAN.
    Для больших карт — масштабированную генерацию с плотностью ~6%.
    """
    # Порог для «большой» карты: больше старой GRID_W×GRID_H = 40×24 = 960 клеток
    if w * h <= GRID_W * GRID_H:
        # Старая логика для обратной совместимости
        rng = random.Random(f"terraformer-trainer:{int(seed)}:{int(w)}x{int(h)}")
        skip = set(exclude)
        cells = [(x, y) for y in range(h) for x in range(w) if (x, y) not in skip]
        rng.shuffle(cells)
        out: dict = {}
        i = 0
        for res, layer, n in FIND_PLAN:
            for _ in range(n):
                if i >= len(cells):
                    return out
                out[cells[i]] = (res, layer)
                i += 1
        return out

    # Большие карты: используем ту же логику, что find_for_cell, для всех клеток
    return generate_finds_scaled(seed, w, h, exclude)


def generate_finds_scaled(seed: int, w: int, h: int, exclude=()) -> dict:
    """Генерация находок для большой карты с плотностью ~6%."""
    skip = set(exclude)
    out: dict = {}
    for y in range(h):
        for x in range(w):
            if (x, y) in skip:
                continue
            f = find_for_cell(seed, x, y)
            if f:
                out[(x, y)] = f
    return out


def deposit_is_visible(model: "TrainerModel", x: int, y: int) -> bool:
    """Check if a deposit at (x, y) should be drawn/rendered.

    A deposit is visible for rendering if:
    1. It's in the revealed set (found and shown to player), OR
    2. It sits on a built platform center that's complete.
    """
    # Check if deposit exists at this position
    if (x, y) not in model.finds:
        return False

    # 1. Revealed deposits are always visible
    if (x, y) in model.revealed:
        return True

    # 2. Check if there's a complete platform at this location
    for platform in model.platforms:
        if platform.center == (x, y) and platform.complete:
            return True

    return False


class TrainerModel:
    """Поле, робот, отсеки и фундамент учебной смены."""

    def __init__(self, w: int = GRID_W, h: int = GRID_H, depth: int | None = None,
                 seed: int | None = None) -> None:
        self.w = max(1, int(w))
        self.h = max(1, int(h))
        lang_level = get_language_level()
        if depth is None:
            if lang_level >= 3:
                self.depth = 3
            elif lang_level >= 2:
                self.depth = 2
            else:
                self.depth = 1
        else:
            self.depth = max(1, min(int(depth), len(LAYERS) + 2))
        self.dug = [[0] * self.w for _ in range(self.h)]
        self._robot = [self.w // 2, self.h // 2]
        self.site: tuple[int, int, int, int] = SITE
        self.facing = (1, 0)
        self.holds = {name: 0 for name in LAYERS}
        # расширяем отсеки для ресурсов платформ
        for r in RESOURCES:
            self.holds.setdefault(r, 0)
        self.active_hold = "soil"
        self.upgrades: tuple[str, ...] = get_unlocked_upgrades()
        self.blocks: list[tuple[int, int]] = []          # блоки на фундаменте (старая система)
        self.platform_blocks: set[tuple[int, int]] = set()  # все блоки платформ (для отрисовки)
        self.walls_open = False
        self.buildings: list[BuildingBlueprint] = []
        self.seed = int(seed) if seed is not None else new_seed()
        exclude = set(self.site_cells()) | {tuple(self.robot)}
        self.finds = generate_finds(self.seed, self.w, self.h, exclude)
        self.revealed: set[tuple[int, int]] = set()
        self.finds_count = {name: 0 for name in RESOURCES}
        self.last_find: dict | None = None
        # платформы добычи
        self.platforms: list[PlatformBlueprint] = []
        self._platform_priority_counter = 0
        # ── стратегический слой ──────────────────────────────────────────────
        self.developer = strategy.is_developer()
        self.standing = current_standing()
        self.credits = 0
        self.mission_book = strategy.MissionBook()
        self.holds[strategy.SPICE] = 0
        self.units: list[strategy.Unit] = []
        self.selected: set[str] = set()
        self.explored: set[tuple[int, int]] = set()
        self.worm = strategy.Sandworm(max(0, self.w - 6), max(0, self.h - 6))
        self.worm_seen = False
        self.worm_attacks = 0
        self.max_build_height = 1
        self.connected = 0
        self._tick_count = 0
        self._init_units()
        self._update_explored()

    @classmethod
    def for_level(cls, level: str | None = None, depth: int | None = None,
                  seed: int | None = None) -> "TrainerModel":
        """Новая стратегическая смена: карта размером под уровень пилота.

        Обычный ``TrainerModel()`` остаётся 40×24 (так его строят тесты и
        старые чертежи); размер по уровню берётся только здесь.
        """
        name = level if level is not None else current_standing().current_level
        w, h = strategy.map_size(name)
        return cls(w, h, depth=depth, seed=seed)

    # -- находки ---------------------------------------------------------------
    @property
    def springs(self) -> set:
        """Открытые источники воды: эти клетки дальше не копают."""
        return {c for c in self.revealed if self.finds.get(c, ("",))[0] == "water"}

    def found_types(self) -> list[str]:
        return [r for r in RESOURCES if self.finds_count.get(r, 0) > 0]

    # -- отряд, выбор и приказы ------------------------------------------------
    @property
    def main_unit(self) -> strategy.Unit:
        if not self.units:
            self._init_units()
        return self.units[0]

    @property
    def robot(self) -> list[int]:
        """Позиция робота, синхронизированная с main_unit."""
        if hasattr(self, 'units') and self.units:
            return [self.main_unit.x, self.main_unit.y]
        return self._robot

    @robot.setter
    def robot(self, value: list[int] | tuple[int, int]) -> None:
        x, y = int(value[0]), int(value[1])
        x = max(0, min(self.w - 1, x))
        y = max(0, min(self.h - 1, y))
        self._robot = [x, y]
        if self.units:
            self.main_unit.x = x
            self.main_unit.y = y

    def _init_units(self) -> None:
        """Первый терраформер всегда есть; его клетка — прежний self.robot."""
        if self.units:
            return
        level = self.standing.current_level if not self.developer else self.standing.current_level
        self.units = [strategy.Unit("u1", level, int(self.robot[0]), int(self.robot[1]), serial=1)]
        self.selected = {"u1"}

    def add_unit(self, level: str | None = None, x: int | None = None,
                 y: int | None = None) -> strategy.Unit:
        """Добавить терраформера. Место — рядом с главным, если не указано."""
        level = strategy.level_name(strategy.level_index(level or self.standing.current_level))
        if x is None or y is None:
            mx, my = self.main_unit.x, self.main_unit.y
            spots = ((1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1))
            x, y = mx, my
            for dx, dy in spots:
                nx, ny = max(0, min(self.w - 1, mx + dx)), max(0, min(self.h - 1, my + dy))
                if not any(u.x == nx and u.y == ny for u in self.units):
                    x, y = nx, ny
                    break
        serial = sum(1 for u in self.units if u.level == level) + 1
        uid = f"u{len(self.units) + 1}"
        while any(u.uid == uid for u in self.units):
            uid += "x"
        unit = strategy.Unit(uid, level, int(x), int(y), serial=serial)
        self.units.append(unit)
        self.mission_book.push(strategy.Alert(
            "reward", _t("Новый терраформер {0}").format(unit.name),
            _t("Уровень {0} · высота зданий до {1}").format(level, unit.max_height), level))
        return unit

    def sync_units(self) -> list[strategy.Unit]:
        """Выдать положенные терраформеры: второй того же уровня и следующий.

        Правило пилота: второй — если идём с опережением (≥50 % уровня),
        следующий — если текущий пройден больше чем на 80 %.
        Разработчику доступны все восемь уровней.
        """
        added: list[strategy.Unit] = []
        if not self.units:
            self._init_units()
        st = self.standing
        if self.developer:
            have = {u.level for u in self.units}
            for lv in strategy.LEVELS:
                if lv not in have:
                    added.append(self.add_unit(lv))
            return added
        # текущий уровень: хотя бы один
        if not any(u.level == st.current_level for u in self.units):
            added.append(self.add_unit(st.current_level))
        # второй того же уровня
        same = [u for u in self.units if u.level == st.current_level]
        if st.second_unit and len(same) < 2:
            added.append(self.add_unit(st.current_level))
        # следующий уровень
        if st.next_unit and not any(u.level == st.next_level for u in self.units):
            added.append(self.add_unit(st.next_level))
        return added

    def unit_at(self, x: int, y: int) -> strategy.Unit | None:
        for u in self.units:
            if u.x == x and u.y == y:
                return u
        return None

    def selected_units(self) -> list[strategy.Unit]:
        return [u for u in self.units if u.uid in self.selected]

    def select_rect(self, x0: int, y0: int, x1: int, y1: int) -> list[strategy.Unit]:
        picked = strategy.units_in_rect(self.units, x0, y0, x1, y1)
        self.selected = {u.uid for u in picked}
        return picked

    def clear_selection(self) -> None:
        self.selected.clear()

    def select_all(self) -> list[strategy.Unit]:
        self.selected = {u.uid for u in self.units}
        return list(self.units)

    def _blocked_cells(self) -> set[tuple[int, int]]:
        blocked = set(self.springs)
        # Блоки фундамента и платформ — непроходимы
        blocked.update(self.blocks)
        blocked.update(self.platform_blocks)
        # Здания — центр здания и все клетки, которые занимает здание по высоте
        for b in self.buildings:
            blocked.add(tuple(b.center))
            # Здание занимает клетки вокруг центра в зависимости от высоты
            # Для простоты блокируем квадрат height x height вокруг центра
            h = max(1, b.height)
            cx, cy = b.center
            for dy in range(-(h - 1), h):
                for dx in range(-(h - 1), h):
                    bx, by = cx + dx, cy + dy
                    if 0 <= bx < self.w and 0 <= by < self.h:
                        blocked.add((bx, by))
        # Ямы (dug > 0) непроходимы — роботы/юниты не могут по ним ходить
        for y in range(self.h):
            for x in range(self.w):
                if self.dug[y][x] > 0:
                    blocked.add((x, y))
        return blocked

    def command_move(self, tx: int, ty: int) -> dict[str, int]:
        """Приказ выделенным идти. Пустая рамка — приказ главному."""
        units = self.selected_units() or [self.main_unit]
        result = strategy.issue_move(units, tx, ty, self.w, self.h, self._blocked_cells())
        if not any(result.values()):
            self.mission_book.push(strategy.Alert(
                "warn", _t("Путь закрыт"),
                _t("Клетка {0},{1} недоступна — обойдите преграду.").format(tx, ty),
                units[0].level))
        return result

    def tick_units(self) -> bool:
        """Шаг отряда по маршрутам. True — кто-то сдвинулся."""
        moved_any = False
        for u in self.units:
            steps = strategy.unit_speed(u.level)
            for _ in range(steps):
                if not u.path:
                    break
                nx, ny = u.path.pop(0)
                if 0 <= nx < self.w and 0 <= ny < self.h:
                    u.x, u.y = nx, ny
                    moved_any = True
            if moved_any:
                self.explored.update(self._visible_from(u))
        if moved_any:
            self._robot = [self.main_unit.x, self.main_unit.y]
            self._maybe_expand()
        return moved_any

    def _maybe_expand(self) -> bool:
        """Если юнит подошёл к краю — карта растёт вокруг него."""
        for u in self.units:
            if u.x < 3 or u.y < 3 or u.x > self.w - 4 or u.y > self.h - 4:
                if self.expand_around(u.x, u.y):
                    return True
        return False

    def expand_around(self, x: int, y: int, pad: int = 4) -> bool:
        """Расширить карту на ``pad`` клеток с той стороны, где стоит юнит."""
        left = pad if x < pad else 0
        right = pad if x > self.w - 1 - pad else 0
        top = pad if y < pad else 0
        bottom = pad if y > self.h - 1 - pad else 0
        if not (left or right or top or bottom):
            return False
        old_w, old_h = self.w, self.h
        new_w, new_h = old_w + left + right, old_h + top + bottom
        if new_w > 400 or new_h > 400:
            return False
        self._shift_world(left, top, new_w, new_h)
        # новые клетки получают детерминированные находки
        for ny in range(new_h):
            for nx in range(new_w):
                if left <= nx < left + old_w and top <= ny < top + old_h:
                    continue
                cell = (nx, ny)
                if cell in self.finds or self.on_site(nx, ny):
                    continue
                f = strategy.find_for_cell(self.seed, nx, ny)
                if f:
                    self.finds[cell] = f
        self._update_explored()
        self.mission_book.push(strategy.Alert(
            "info", _t("Карта расширена"),
            _t("Теперь {0}×{1} клеток.").format(new_w, new_h),
            self.standing.current_level))
        return True

    def _shift_world(self, dx: int, dy: int, new_w: int, new_h: int) -> None:
        """Сдвинуть все координаты при расширении влево/вверх."""
        new_dug = [[0] * new_w for _ in range(new_h)]
        for y, row in enumerate(self.dug):
            for x, value in enumerate(row):
                nx, ny = x + dx, y + dy
                if 0 <= nx < new_w and 0 <= ny < new_h:
                    new_dug[ny][nx] = value
        self.dug = new_dug

        def sc(cell: tuple[int, int]) -> tuple[int, int]:
            return (int(cell[0]) + dx, int(cell[1]) + dy)

        self.finds = {sc(c): v for c, v in self.finds.items()}
        self.revealed = {sc(c) for c in self.revealed}
        self.explored = {sc(c) for c in self.explored}
        self.platform_blocks = {sc(c) for c in self.platform_blocks}
        self.blocks = [sc(c) for c in self.blocks]
        for p in self.platforms:
            p.center = sc(p.center)
            p.built = {sc(c) for c in p.built}
        for b in self.buildings:
            b.center = sc(b.center)
        for u in self.units:
            u.x += dx
            u.y += dy
            u.path = [sc(c) for c in u.path]
            if u.target:
                u.target = sc(u.target)
        self._robot = [self._robot[0] + dx, self._robot[1] + dy]
        sx, sy, sw, sh = self.site
        self.site = (sx + dx, sy + dy, sw, sh)
        self.worm.x += dx
        self.worm.y += dy
        self.worm.trail = {sc(c): ttl for c, ttl in self.worm.trail.items()}
        self.w = new_w
        self.h = new_h

    # -- туман войны -----------------------------------------------------------
    def _visible_from(self, unit: strategy.Unit) -> set[tuple[int, int]]:
        r = unit.sight
        out: set[tuple[int, int]] = set()
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy > r * r + r:
                    continue
                x, y = unit.x + dx, unit.y + dy
                if 0 <= x < self.w and 0 <= y < self.h:
                    out.add((x, y))
        return out

    def _visible_from_structure(self, building: BuildingBlueprint) -> set[tuple[int, int]]:
        """Vision radius from structures. Only radar grants vision for now."""
        if building.type != "radar":
            return set()
        # Radar at B2.2 level: large vision radius
        r = 10
        out: set[tuple[int, int]] = set()
        bx, by = building.center
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy > r * r + r:
                    continue
                x, y = bx + dx, by + dy
                if 0 <= x < self.w and 0 <= y < self.h:
                    out.add((x, y))
        return out

    def visible_cells(self) -> set[tuple[int, int]]:
        out: set[tuple[int, int]] = set()
        for u in self.units:
            out |= self._visible_from(u)
        for b in self.buildings:
            if b.built:
                out |= self._visible_from_structure(b)
        return out

    def _update_explored(self) -> None:
        self.explored |= self.visible_cells()

    def is_visible(self, x: int, y: int, visible: set | None = None) -> bool:
        return (x, y) in (visible if visible is not None else self.visible_cells())

    def is_explored(self, x: int, y: int) -> bool:
        return (x, y) in self.explored

    # -- экономика и здания ----------------------------------------------------
    def _update_connections(self) -> int:
        """Коммуникация: здание связано, если рядом другое здание или база."""
        centers = [tuple(b.center) for b in self.buildings] + [tuple(self.site[:2])]
        n = 0
        for b in self.buildings:
            bx, by = b.center
            b.connected = any(
                (abs(bx - ox) + abs(by - oy)) <= 6 and (ox, oy) != (bx, by)
                for ox, oy in centers
            )
            if b.connected:
                n += 1
        self.connected = n
        return n

    def tick_income(self) -> int:
        """Завершённые и связанные здания приносят кредиты каждый тик."""
        self._update_connections()
        gain = 0
        for b in self.buildings:
            if b.built and b.connected:
                gain += int(b.income)
        if gain:
            self.credits += gain
        return gain

    def build_structure(self, key: str, x: int | None = None, y: int | None = None,
                        unit: strategy.Unit | None = None) -> tuple[bool, str]:
        """Построить здание из каталога. Высота ограничена уровнем терраформера."""
        spec = strategy.STRUCTURES.get(key)
        if spec is None:
            return False, _t("Неизвестное здание")
        unit = unit or (self.selected_units() or [self.main_unit])[0]
        if not strategy.structure_available(key, unit.level, self.developer):
            need = strategy.level_name(spec.min_index)
            return False, _t("Нужен терраформер {0} (высота {1})").format(need, spec.height)
        if self.credits < spec.cost:
            return False, _t("Нужно {0} кредитов (есть {1})").format(spec.cost, self.credits)
        x = unit.x if x is None else int(x)
        y = unit.y if y is None else int(y)
        if not (0 <= x < self.w and 0 <= y < self.h):
            return False, _t("за пределами поля")
        if any(b.center == (x, y) for b in self.buildings):
            return False, _t("Здесь уже есть здание")
        self.credits -= spec.cost
        b = BuildingBlueprint(key, (x, y))
        b.height = spec.height
        b.income = spec.income
        b.built = True
        self.buildings.append(b)
        self.max_build_height = max(self.max_build_height, spec.height)
        self._update_connections()
        self.mission_book.push(strategy.Alert(
            "reward", _t("Построено: {0}").format(spec.title),
            _t("Высота {0} · доход {1}/тик").format(spec.height, spec.income), unit.level))
        return True, _t("{0} построено (высота {1})").format(spec.title, spec.height)

    # -- песчаный червь --------------------------------------------------------
    def tick_worm(self) -> dict | None:
        """Шаг червя: след, специя, атака техники на песке."""
        self._tick_count += 1
        if not self.worm.alive or self._tick_count % strategy.WORM_MOVE_EVERY:
            return None
        deposits = set(self.finds)
        rocks = {c for c, f in self.finds.items() if f[0] == "stone"}
        safe = strategy.worm_safe_cells(self.platform_blocks | set(self.blocks), rocks)
        cell, spice = strategy.worm_step(self.worm, self.w, self.h, self.seed, deposits, safe)
        self.worm_seen = True
        event: dict = {"cell": cell, "spice": spice, "attacked": None}
        if spice:
            self.holds[strategy.SPICE] = self.holds.get(strategy.SPICE, 0) + 1
            self.mission_book.push(strategy.Alert(
                "reward", _t("Специя!"),
                _t("Червь оставил специю. Соберите её в отсек находок."),
                self.standing.current_level))
        if cell is not None:
            victim = self.unit_at(*cell)
            if victim is not None:
                victim.hp = max(0, victim.hp - strategy.WORM_DAMAGE)
                self.worm_attacks += 1
                event["attacked"] = victim.uid
                self.mission_book.push(strategy.Alert(
                    "warn", _t("Атака червя!"),
                    _t("{0} повреждён: {1} HP. Уходите на фундамент.").format(victim.name, victim.hp),
                    victim.level))
                if victim.hp <= 0 and victim.uid != self.main_unit.uid:
                    self.units.remove(victim)
                    self.selected.discard(victim.uid)
                elif victim.uid == self.main_unit.uid and victim.hp <= 0:
                    victim.hp = 10
        return event

    # -- задания и статистика --------------------------------------------------
    def stats(self) -> dict:
        return {
            "soil_dug": int(sum(sum(row) for row in self.dug)),
            "finds": int(sum(self.finds_count.values())),
            "platforms_complete": sum(1 for p in self.platforms if p.complete),
            "buildings": len(self.buildings),
            "buildings_complete": sum(1 for b in self.buildings if b.built),
            "credits": int(self.credits),
            "units": len(self.units),
            "connected": int(self.connected),
            "worm_seen": 1 if self.worm_seen else 0,
            "worm_attacks": int(self.worm_attacks),
            "spice": int(self.holds.get(strategy.SPICE, 0)),
            "max_height": int(self.max_build_height),
            "core": 1 if any(b.type == "core" and b.built for b in self.buildings) else 0,
            "map_cells": int(self.w * self.h),
            **{res: int(self.holds.get(res, 0)) for res in RESOURCES},
        }

    def refresh_standing(self) -> list[strategy.Unit]:
        """Пересчитать права по заданиям и выдать новых терраформеров."""
        game_pct = self.mission_book.stats_pct()
        self.standing = strategy.standing(game_pct)
        return self.sync_units()

    def evaluate_missions(self) -> list[strategy.Mission]:
        fresh = self.mission_book.evaluate(self.stats(), stamp=time.time())
        if fresh:
            self.credits += sum(m.reward_credits for m in fresh)
        return fresh

    def _reveal(self, x: int, y: int, layer: int) -> dict | None:
        cell = (x, y)
        f = self.finds.get(cell)
        if not f or f[1] != layer or cell in self.revealed:
            return None
        res = f[0]
        self.revealed.add(cell)
        self.explored.add(cell)
        first = self.finds_count.get(res, 0) == 0
        self.finds_count[res] = self.finds_count.get(res, 0) + 1
        self.last_find = {"res": res, "first": first, "cell": cell, "layer": layer}
        # создаём платформу для этой находки, если её ещё нет
        self._ensure_platform(res, cell)
        return self.last_find

    def _ensure_platform(self, resource: str, center: tuple[int, int]) -> PlatformBlueprint | None:
        """Создаёт платформу для ресурса, если её ещё нет. Возвращает платформу или None."""
        for p in self.platforms:
            if p.resource == resource and p.center == center:
                return p
        # выбираем лучший доступный вариант по уровню языка
        unlocked = get_unlocked_variants(resource)
        variant_idx = max(unlocked) if unlocked else 0
        variants = PLATFORM_VARIANTS.get(resource, ())
        pattern = variants[variant_idx] if variant_idx < len(variants) else variants[0]
        if not pattern:
            return None
        requires_a2 = resource in DEEP_RESOURCES
        height = platform_height(resource, variant_idx)
        bp = PlatformBlueprint(
            resource=resource,
            center=center,
            pattern=pattern,
            requires_a2=requires_a2,
            variant_index=variant_idx,
            height=height,
            required_level=strategy.level_for_height(height),
        )
        self.platforms.append(bp)
        # автоматически назначаем приоритет первой незавершённой платформе
        self._assign_next_priority()
        return bp

    def _assign_next_priority(self) -> None:
        """Назначает приоритет следующей незавершённой платформе без приоритета."""
        self._platform_priority_counter += 1
        for p in self.platforms:
            if not p.complete and p.priority == 0:
                p.priority = self._platform_priority_counter
                break

    def set_platform_priority(self, resource: str, center: tuple[int, int], priority: int) -> bool:
        """Устанавливает приоритет платформы. 0 = снять приоритет."""
        for p in self.platforms:
            if p.resource == resource and p.center == center:
                old = p.priority
                p.priority = max(0, priority)
                if old == 0 and p.priority > 0:
                    self._platform_priority_counter = max(self._platform_priority_counter, p.priority)
                elif old > 0 and p.priority == 0:
                    self._assign_next_priority()
                return True
        return False

    def get_priority_platform(self) -> PlatformBlueprint | None:
        """Возвращает платформу с наивысшим приоритетом среди незавершённых."""
        best = None
        best_prio = -1
        for p in self.platforms:
            if not p.complete and p.priority > best_prio:
                best_prio = p.priority
                best = p
        return best

    # -- размещение блоков ------------------------------------------------------
    def _hold_cap(self) -> int:
        """Возвращает текущую вместимость отсека с учетом апгрейдов."""
        if "soil_compactor" in self.upgrades:
            return HOLD_CAP_WITH_UPGRADES["soil_compactor"]
        return HOLD_CAP_WITH_UPGRADES["default"]

    def try_place_block(self, x: int, y: int,
                        unit: "strategy.Unit | None" = None) -> tuple[bool, str]:
        """
        Пытается поставить блок в клетку (x, y).
        Возвращает (success, message).
        Блок тратится из отсека грунта (по умолчанию 5, или 3 с прессом).
        Высокое здание строит только терраформер подходящего уровня.
        """
        if not (0 <= x < self.w and 0 <= y < self.h):
            return False, _t("за пределами поля")
        cap = self._hold_cap()
        if self.holds.get("soil", 0) < cap:
            return False, _t("отсек грунта не полон")
        # проверяем, принадлежит ли клетка какой-то платформе
        target_platform = None
        for p in self.platforms:
            if not p.complete and p.is_cell_part(x, y):
                target_platform = p
                break
        # также разрешаем ставить на старую стройплощадку, если стены ещё не открыты
        on_foundation = self.on_site(x, y) and not self.walls_open
        if not target_platform and not on_foundation:
            return False, _t("здесь нет чертежа платформы")
        builder = unit or (self.selected_units() or [self.main_unit])[0]
        if target_platform and not self.developer:
            if builder.max_height < target_platform.height:
                return False, _t("Нужен терраформер {0}: здание высотой {1}").format(
                    target_platform.required_level, target_platform.height)
        # тратим грунт
        self.holds["soil"] = 0
        self.platform_blocks.add((x, y))
        if target_platform:
            target_platform.try_add_block(x, y)
            if target_platform.complete:
                self._assign_next_priority()
                self.max_build_height = max(self.max_build_height, target_platform.height)
                return True, _t("платформа {0} готова!").format(target_platform.resource)
            return True, _t("блок уложен на платформу {0} ({1}%)").format(target_platform.resource, target_platform.progress_pct())
        else:
            # старая система фундамента
            self.blocks.append((x, y))
            if len(self.blocks) >= len(self.site_cells()):
                self.walls_open = True
                return True, _t("фундамент готов — стены открыты!")
            return True, _t("блок уложен на фундамент ({0}/{1})").format(len(self.blocks), len(self.site_cells()))

    # -- автодобыча за тик ------------------------------------------------------
    def tick_extraction(self) -> dict[str, int]:
        """Вызывается каждый тик для завершённых платформ. Возвращает словарь наград."""
        gained: dict[str, int] = {}
        yield_mult = 1.5 if "yield_booster" in self.upgrades else 1.0
        for p in self.platforms:
            if p.complete:
                res, base_amount = PLATFORM_YIELD.get(p.resource, (p.resource, 0))
                if base_amount > 0:
                    mult = 1.0
                    if p.variant_index < len(VARIANT_YIELD_MULT.get(p.resource, (1.0,))):
                        mult = VARIANT_YIELD_MULT[p.resource][p.variant_index]
                    amount = int(base_amount * mult * yield_mult)
                    self.holds[res] = self.holds.get(res, 0) + amount
                    gained[res] = gained.get(res, 0) + amount
        return gained

    # -- стройплощадка -------------------------------------------------------
    def site_cells(self) -> list[tuple[int, int]]:
        x, y, w, h = self.site
        return [(cx, cy) for cy in range(y, y + h) for cx in range(x, x + w)]

    def on_site(self, x: int, y: int) -> bool:
        sx, sy, sw, sh = self.site
        return sx <= x < sx + sw and sy <= y < sy + sh

    # -- действия робота -----------------------------------------------------
    def move(self, dx: int, dy: int) -> bool:
        self.facing = (dx, dy)
        x = max(0, min(self.w - 1, self.robot[0] + dx))
        y = max(0, min(self.h - 1, self.robot[1] + dy))
        moved = (x, y) != (self.robot[0], self.robot[1])
        self.robot = [x, y]
        if moved:
            main = self.main_unit
            main.path = []
            self.explored.update(self._visible_from(main))
            self._maybe_expand()
        # auto_unloader: авто-укладка блока при заезде на клетку схемы
        if "auto_unloader" in self.upgrades and moved:
            builder = self.main_unit
            for p in self.platforms:
                if not p.complete and p.is_cell_part(x, y):
                    if not self.developer and builder.max_height < p.height:
                        continue
                    success = p.try_add_block(x, y)
                    if success:
                        self.platform_blocks.add((x, y))
                        if p.built_count() >= p.total_cells():
                            p.complete = True
                            self._assign_next_priority()
        return moved

    def dig(self) -> str:
        """ok | hold_full | too_deep | site | spring. Находка — в self.last_find."""
        return self.dig_at(self.robot[0], self.robot[1])

    def dig_at(self, x: int, y: int) -> str:
        """Dig at specific coordinates. Returns result string."""
        self.last_find = None
        if self.on_site(x, y):
            return "site"
        if (x, y) in self.springs:
            return "spring"
        layers = self.dug[y][x]
        if layers >= self.depth or layers >= len(LAYERS):
            return "too_deep"
        hold = LAYERS[layers]
        # находка уходит в свой отсек, даже если отсек грунта полон
        self._reveal(x, y, layers)
        if self.holds[hold] >= HOLD_CAP:
            return "hold_full"
        self.dug[y][x] = layers + 1
        self.holds[hold] += 1
        return "ok"

    def hold_full(self, name: str = "soil") -> bool:
        return self.holds.get(name, 0) >= HOLD_CAP

    def switch_hold(self) -> str:
        try:
            idx = LAYERS.index(self.active_hold)
        except ValueError:
            idx = 0
        self.active_hold = LAYERS[(idx + 1) % len(LAYERS)]
        return self.active_hold

    def unload(self) -> str:
        if self.holds.get("soil", 0) < HOLD_CAP:
            return "not_full"
        site = self.site_cells()
        if len(self.blocks) >= len(site):
            return "done"
        free = next((cell for cell in site if cell not in self.blocks), None)
        if free is None:
            return "done"
        self.blocks.append(free)
        self.holds["soil"] = 0
        if len(self.blocks) >= len(site):
            self.walls_open = True
            return "complete"
        return "ok"

    def _check_resources(self, resource: str, amount: int) -> bool:
        """Проверяет, достаточно ли ресурса."""
        return self.holds.get(resource, 0) >= amount

    def build_shelter(self) -> str | None:
        """Строит укрытие (стена) из kamienia + воды. Возвращает сообщение или None."""
        if not self.walls_open:
            return None
        if not self._check_resources("stone", 1):
            return _t("Не хватает камня")
        if not self._check_resources("water", 1):
            return _t("Не хватает воды")
        self.holds["stone"] = 0
        self.holds["water"] = 0
        center = None
        for p in self.platforms:
            if not p.complete:
                center = p.center
                break
        if center is None:
            # если платформ нет, используем текущую позицию робота
            center = tuple(self.robot)
        self.buildings.append(BuildingBlueprint(_BUILDING_SHELTER, center))
        self.buildings[-1].built = True
        self._update_connections()
        return _t("Укрытие построено! +10 очков")

    def build_greenhouse(self) -> str | None:
        """Строит теплицу из органики + воды. Возвращает сообщение или None."""
        if not self.walls_open:
            return None
        if not self._check_resources("organic", 1):
            return _t("Не хватает органики")
        if not self._check_resources("water", 1):
            return _t("Не хватает воды")
        self.holds["organic"] = 0
        self.holds["water"] = 0
        center = None
        for p in self.platforms:
            if not p.complete:
                center = p.center
                break
        if center is None:
            center = tuple(self.robot)
        self.buildings.append(BuildingBlueprint(_BUILDING_GREENHOUSE, center))
        self.buildings[-1].built = True
        self._update_connections()
        return _t("Теплица построена! +15 очков")

    def build_energy_panel(self) -> str | None:
        """Строит энергопанель из кварца + железа. Возвращает сообщение или None."""
        if not self.walls_open:
            return None
        if not self._check_resources("quartz", 1):
            return _t("Не хватает кварца")
        if not self._check_resources("iron", 1):
            return _t("Не хватает железа")
        self.holds["quartz"] = 0
        self.holds["iron"] = 0
        center = None
        for p in self.platforms:
            if not p.complete:
                center = p.center
                break
        if center is None:
            center = tuple(self.robot)
        self.buildings.append(BuildingBlueprint(_BUILDING_ENERGY_PANEL, center))
        self.buildings[-1].built = True
        self._update_connections()
        return _t("Энергопанель построена! +20 очков")

    def progress(self) -> tuple[int, int]:
        return len(self.blocks), len(self.site_cells())

    def layer_left(self, x: int, y: int) -> int:
        if not (0 <= x < self.w and 0 <= y < self.h):
            return 0
        total = min(self.depth, len(LAYERS))
        return max(0, total - self.dug[y][x])

    # -- чертёж --------------------------------------------------------------
    def to_blueprint(self) -> dict:
        platforms_data = []
        for p in self.platforms:
            platforms_data.append({
                "resource": p.resource,
                "center": list(p.center),
                "built": [[x, y] for x, y in sorted(p.built)],
                "complete": p.complete,
                "priority": p.priority,
                "variant_index": p.variant_index,
            })
        buildings_data = []
        for b in self.buildings:
            buildings_data.append({
                "type": b.type,
                "center": list(b.center),
                "built": b.built,
                "score": b.score,
                "height": b.height,
                "income": b.income,
                "connected": b.connected,
            })
        return {
            "kind": "terraformer_trainer",
            "version": 4,
            "w": self.w,
            "h": self.h,
            "depth": self.depth,
            "dug": [row[:] for row in self.dug],
            "robot": list(self.robot),
            "holds": dict(self.holds),
            "blocks": [[x, y] for x, y in self.blocks],
            "platform_blocks": [[x, y] for x, y in sorted(self.platform_blocks)],
            "walls_open": bool(self.walls_open),
            "seed": self.seed,
            "revealed": [[x, y] for x, y in sorted(self.revealed)],
            "explored": [[x, y] for x, y in sorted(self.explored)],
            "finds_count": dict(self.finds_count),
            "platforms": platforms_data,
            "buildings": buildings_data,
            "site": list(self.site),
            "credits": int(self.credits),
            "units": [
                {**u.to_dict(), **({"x": self.robot[0], "y": self.robot[1]} if i == 0 else {})}
                for i, u in enumerate(self.units)
            ],
            "selected": sorted(self.selected),
            "missions": self.mission_book.to_dict(),
            "worm": self.worm.to_dict(),
            "worm_seen": bool(self.worm_seen),
            "worm_attacks": int(self.worm_attacks),
            "max_build_height": int(self.max_build_height),
            "connected": int(self.connected),
        }

    @classmethod
    def from_blueprint(cls, d: dict) -> "TrainerModel":
        if not isinstance(d, dict) or d.get("kind") != "terraformer_trainer":
            return cls()
        try:
            w = int(d.get("w", GRID_W))
            h = int(d.get("h", GRID_H))
        except (TypeError, ValueError):
            return cls()
        if not (1 <= w <= 1000 and 1 <= h <= 1000):
            return cls()
        try:
            depth = int(d.get("depth", 1))
        except (TypeError, ValueError):
            depth = 1
        try:
            seed = int(d["seed"])          # старые чертежи без сида получают новый
        except (KeyError, TypeError, ValueError):
            seed = None
        model = cls(w, h, depth, seed=seed)

        dug = d.get("dug")
        if not isinstance(dug, list) or len(dug) != h:
            return cls()
        cap = min(model.depth, len(LAYERS))
        for y, row in enumerate(dug):
            if not isinstance(row, list) or len(row) != w:
                return cls()
            for x, value in enumerate(row):
                try:
                    v = int(value)
                except (TypeError, ValueError):
                    v = 0
                model.dug[y][x] = max(0, min(cap, v))

        robot = d.get("robot")
        if isinstance(robot, (list, tuple)) and len(robot) >= 2:
            try:
                rx, ry = int(robot[0]), int(robot[1])
            except (TypeError, ValueError):
                rx, ry = model.w // 2, model.h // 2
            model.robot = [max(0, min(model.w - 1, rx)), max(0, min(model.h - 1, ry))]

        holds = d.get("holds")
        if isinstance(holds, dict):
            for name in LAYERS:
                try:
                    value = int(holds.get(name, 0))
                except (TypeError, ValueError):
                    value = 0
                model.holds[name] = max(0, min(HOLD_CAP, value))

        blocks = d.get("blocks")
        if isinstance(blocks, list):
            seen: set[tuple[int, int]] = set()
            for item in blocks:
                if not isinstance(item, (list, tuple)) or len(item) < 2:
                    continue
                try:
                    bx, by = int(item[0]), int(item[1])
                except (TypeError, ValueError):
                    continue
                if 0 <= bx < model.w and 0 <= by < model.h:
                    seen.add((bx, by))
            model.blocks = list(seen)

        revealed = d.get("revealed")
        if isinstance(revealed, list):
            for item in revealed:
                try:
                    cell = (int(item[0]), int(item[1]))
                except (TypeError, ValueError, IndexError, KeyError):
                    continue
                if cell in model.finds:
                    model.revealed.add(cell)
        counts = d.get("finds_count")
        if isinstance(counts, dict):
            for name in RESOURCES:
                try:
                    model.finds_count[name] = max(0, int(counts.get(name, 0)))
                except (TypeError, ValueError):
                    pass
        else:                              # нет счётчика — считаем по открытым клеткам
            for cell in model.revealed:
                res = model.finds[cell][0]
                model.finds_count[res] = model.finds_count.get(res, 0) + 1
        # восстанавливаем платформы
        platforms_data = d.get("platforms")
        if isinstance(platforms_data, list):
            max_prio = 0
            for pd in platforms_data:
                try:
                    resource = pd.get("resource")
                    center = tuple(pd.get("center", (0, 0)))
                    built = {tuple(c) for c in pd.get("built", [])}
                    complete = bool(pd.get("complete", False))
                    priority = int(pd.get("priority", 0))
                    variant_index = int(pd.get("variant_index", 0))
                    if resource not in PLATFORM_VARIANTS:
                        continue
                    variants = PLATFORM_VARIANTS[resource]
                    pattern = variants[variant_index] if variant_index < len(variants) else variants[0]
                    requires_a2 = resource in DEEP_RESOURCES
                    bp = PlatformBlueprint(
                        resource=resource,
                        center=center,
                        pattern=pattern,
                        built=built,
                        complete=complete,
                        priority=priority,
                        requires_a2=requires_a2,
                        variant_index=variant_index,
                        height=platform_height(resource, variant_index),
                        required_level=strategy.level_for_height(platform_height(resource, variant_index)),
                    )
                    model.platforms.append(bp)
                    model.platform_blocks.update(built)
                    if priority > max_prio:
                        max_prio = priority
                except Exception:  # noqa: BLE001
                    continue
            model._platform_priority_counter = max_prio
        # платформ-блоки из старой версии
        pblocks = d.get("platform_blocks")
        if isinstance(pblocks, list):
            for item in pblocks:
                try:
                    model.platform_blocks.add((int(item[0]), int(item[1])))
                except Exception:  # noqa: BLE001
                    pass
        # восстанавливаем объекты базы
        buildings_data = d.get("buildings")
        if isinstance(buildings_data, list):
            for bd in buildings_data:
                try:
                    btype = str(bd.get("type", ""))
                    center = tuple(bd.get("center", (0, 0)))
                    built = bool(bd.get("built", False))
                    score = int(bd.get("score", 0))
                    b = BuildingBlueprint(btype, center)
                    b.built = built
                    b.score = score
                    b.height = int(bd.get("height", b.height))
                    b.income = int(bd.get("income", b.income))
                    b.connected = bool(bd.get("connected", False))
                    model.buildings.append(b)
                except Exception:  # noqa: BLE001
                    pass
        # также восстанавливаем holds для ресурсов платформ
        for r in RESOURCES:
            model.holds.setdefault(r, 0)
        model.holds.setdefault(strategy.SPICE, 0)
        if isinstance(holds, dict):
            for name in list(model.holds):
                try:
                    model.holds[name] = max(0, int(holds.get(name, model.holds[name])))
                except (TypeError, ValueError):
                    pass
        # ── стратегический слой: площадка, туман, отряд, задания, червь ──────
        site = d.get("site")
        if isinstance(site, (list, tuple)) and len(site) >= 4:
            try:
                model.site = tuple(int(v) for v in site[:4])  # type: ignore[assignment]
            except (TypeError, ValueError):
                model.site = SITE
        explored = d.get("explored")
        if isinstance(explored, list):
            for item in explored:
                try:
                    model.explored.add((int(item[0]), int(item[1])))
                except (TypeError, ValueError, IndexError):
                    continue
        else:
            model.explored = set(model.revealed) | model.visible_cells()
        try:
            model.credits = max(0, int(d.get("credits", 0)))
        except (TypeError, ValueError):
            model.credits = 0
        units_data = d.get("units")
        if isinstance(units_data, list) and units_data:
            restored: list[strategy.Unit] = []
            for ud in units_data:
                if not isinstance(ud, dict):
                    continue
                try:
                    u = strategy.Unit.from_dict(ud)
                except Exception:  # noqa: BLE001
                    continue
                u.x = max(0, min(model.w - 1, u.x))
                u.y = max(0, min(model.h - 1, u.y))
                restored.append(u)
            if restored:
                model.units = restored
                model.robot = [restored[0].x, restored[0].y]
        else:
            model._init_units()
            model.main_unit.x, model.main_unit.y = model.robot[0], model.robot[1]
        selected = d.get("selected")
        if isinstance(selected, list):
            model.selected = {str(x) for x in selected if any(u.uid == str(x) for u in model.units)}
        missions = d.get("missions")
        if isinstance(missions, dict):
            model.mission_book = strategy.MissionBook.from_dict(missions)
        worm = d.get("worm")
        if isinstance(worm, dict):
            try:
                model.worm = strategy.Sandworm.from_dict(worm)
            except Exception:  # noqa: BLE001
                pass
        model.worm_seen = bool(d.get("worm_seen", False))
        try:
            model.worm_attacks = max(0, int(d.get("worm_attacks", 0)))
        except (TypeError, ValueError):
            model.worm_attacks = 0
        try:
            model.max_build_height = max(1, int(d.get("max_build_height", 1)))
        except (TypeError, ValueError):
            model.max_build_height = 1
        try:
            model.connected = max(0, int(d.get("connected", 0)))
        except (TypeError, ValueError):
            model.connected = 0
        if model.units:
            model.units[0].x, model.units[0].y = model.robot[0], model.robot[1]
        return model


# объекты базы (построенные сооружения)
_BUILDING_SHELTER = "shelter"
_BUILDING_GREENHOUSE = "greenhouse"
_BUILDING_ENERGY_PANEL = "energy_panel"


class BuildingBlueprint:
    """Чертеж объекта базы: высота, доход и связь с коммуникацией."""

    type: str
    center: tuple[int, int]
    built: bool = False
    score: int = 0
    height: int = 1
    income: int = 0
    connected: bool = False

    def __init__(self, btype: str, center: tuple[int, int]) -> None:
        self.type = btype
        self.center = center
        spec = strategy.STRUCTURES.get(btype)
        if spec is not None:
            self.score = spec.income
            self.height = spec.height
            self.income = spec.income
            return
        if btype == _BUILDING_SHELTER:
            self.score = 10
        elif btype == _BUILDING_GREENHOUSE:
            self.score = 15
        elif btype == _BUILDING_ENERGY_PANEL:
            self.score = 20
        else:
            self.score = 0


class Camera:
    """Простая камера: центр в координатах клеток, масштаб в пикселях."""

    def __init__(self, w: int, h: int) -> None:
        self.w = max(1, int(w))
        self.h = max(1, int(h))
        self.zoom = 1.0
        self.cx = self.w / 2.0
        self.cy = self.h / 2.0
        self.follow = True
        self._clamp()

    def resize(self, w: int, h: int) -> None:
        """Карта выросла — камера не должна упираться в старые границы."""
        self.w = max(1, int(w))
        self.h = max(1, int(h))
        self._clamp()

    def _clamp(self) -> None:
        self.cx = max(0.0, min(float(self.w), self.cx))
        self.cy = max(0.0, min(float(self.h), self.cy))

    def cell_px(self) -> float:
        return BASE_CELL * self.zoom

    def zoom_in(self) -> float:
        self.zoom = min(ZOOM_MAX, self.zoom * ZOOM_STEP)
        return self.zoom

    def zoom_out(self) -> float:
        self.zoom = max(ZOOM_MIN, self.zoom / ZOOM_STEP)
        return self.zoom

    def zoom_at(self, direction: int, sx: float, sy: float, width: int, height: int) -> float:
        """Ctrl+колесо: масштаб вокруг указателя мыши (клетка под курсором стоит)."""
        old = self.cell_px()
        wx = self.cx + (sx - width / 2.0) / old
        wy = self.cy + (sy - height / 2.0) / old
        if direction < 0:
            self.zoom_in()
        elif direction > 0:
            self.zoom_out()
        new = self.cell_px()
        self.cx = wx - (sx - width / 2.0) / new
        self.cy = wy - (sy - height / 2.0) / new
        self.follow = False
        self._clamp()
        return self.zoom

    def to_cell(self, sx: float, sy: float, width: int, height: int) -> tuple[int, int]:
        """Экранная точка → клетка карты."""
        cell = self.cell_px()
        x = self.cx + (sx - width / 2.0) / cell
        y = self.cy + (sy - height / 2.0) / cell
        return int(math.floor(x)), int(math.floor(y))

    def pan(self, dx_cells: float, dy_cells: float) -> None:
        self.follow = False
        self.cx += dx_cells
        self.cy += dy_cells
        self._clamp()

    def center_on(self, x: float, y: float) -> None:
        """Поставить камеру в клетку (миникарта, переход) и снять слежение."""
        self.cx = float(x)
        self.cy = float(y)
        self.follow = False
        self._clamp()

    def reset(self, x: float, y: float) -> None:
        self.zoom = 1.0
        self.cx = x + 0.5
        self.cy = y + 0.5
        self.follow = True
        self._clamp()

    def track(self, x: float, y: float) -> None:
        if not self.follow:
            return
        self.cx = x + 0.5
        self.cy = y + 0.5
        self._clamp()

    def to_screen(self, x: float, y: float, width: int, height: int) -> tuple[float, float]:
        cell = self.cell_px()
        return (
            width / 2.0 + (x - self.cx) * cell,
            height / 2.0 + (y - self.cy) * cell,
        )


# ─── миникарта ───────────────────────────────────────────────────────────────
# Чистая геометрия без Tk: прямоугольник миникарты на экране и пересчёт
# «клик ↔ клетка карты». Рисует и принимает клики уже lounge/trainer.py.

def minimap_rect(canvas_w: int, canvas_h: int, map_w: int, map_h: int,
                 margin: int = 10, bottom: int = 34,
                 max_w: int = 190, max_h: int = 150) -> tuple[int, int, int, int]:
    """Прямоугольник миникарты в правом нижнем углу, с сохранением пропорций."""
    canvas_w = max(1, int(canvas_w))
    canvas_h = max(1, int(canvas_h))
    map_w = max(1, int(map_w))
    map_h = max(1, int(map_h))
    scale = min(max_w / map_w, max_h / map_h)
    mw = max(24, int(round(map_w * scale)))
    mh = max(18, int(round(map_h * scale)))
    x1 = canvas_w - max(0, int(margin))
    y1 = canvas_h - max(0, int(bottom))
    return (x1 - mw, y1 - mh, x1, y1)


def world_to_minimap(gx: float, gy: float, rect: tuple[int, int, int, int],
                     map_w: int, map_h: int) -> tuple[float, float]:
    """Клетка карты → точка на миникарте."""
    x0, y0, x1, y1 = rect
    fx = float(gx) / max(1, int(map_w))
    fy = float(gy) / max(1, int(map_h))
    return (x0 + fx * (x1 - x0), y0 + fy * (y1 - y0))


def minimap_click_to_world(sx: float, sy: float, rect: tuple[int, int, int, int],
                           map_w: int, map_h: int) -> tuple[float, float]:
    """Клик по миникарте → клетка карты (дробная, с зажимом в границы)."""
    x0, y0, x1, y1 = rect
    mw = max(1, x1 - x0)
    mh = max(1, y1 - y0)
    fx = (float(sx) - x0) / mw
    fy = (float(sy) - y0) / mh
    fx = max(0.0, min(1.0, fx))
    fy = max(0.0, min(1.0, fy))
    map_w = max(1, int(map_w))
    map_h = max(1, int(map_h))
    return (fx * map_w, fy * map_h)


def point_in_rect(x: float, y: float, rect: tuple[int, int, int, int] | None) -> bool:
    """Попал ли клик в прямоугольник (None — мимо)."""
    if rect is None:
        return False
    x0, y0, x1, y1 = rect
    return x0 <= x <= x1 and y0 <= y <= y1


def blueprint_path() -> Path:
    from stamina import pilots

    return Path(pilots.active_dir()) / BLUEPRINT_NAME


def save_blueprint(model: TrainerModel, path: Path | None = None) -> bool:
    target = Path(path) if path is not None else blueprint_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(json.dumps(model.to_blueprint(), ensure_ascii=False, indent=1),
                       encoding="utf-8")
        tmp.replace(target)
        return True
    except OSError:
        return False


def archive_blueprint(path: Path | None = None, keep: int = ARCHIVE_KEEP,
                      stamp: str | None = None) -> Path | None:
    """Копия текущего чертежа в <папка пилота>/terraformer_trainer_archive/<ГГГГММДД-ЧЧММСС>.json.

    Хранятся последние ``keep`` копий; удаляются только старые *.json из этой папки архива.
    Нет чертежа — None.
    """
    src = Path(path) if path is not None else blueprint_path()
    try:
        data = src.read_bytes()
    except OSError:
        return None
    folder = src.parent / ARCHIVE_DIR
    name = stamp or time.strftime("%Y%m%d-%H%M%S")
    try:
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / f"{name}.json"
        n = 1
        while dest.exists():
            dest = folder / f"{name}-{n}.json"
            n += 1
        dest.write_bytes(data)
        old = sorted(folder.glob("*.json"), key=lambda p: (p.stat().st_mtime, p.name))
        for extra in old[:max(0, len(old) - max(1, int(keep)))]:
            try:
                extra.unlink()
            except OSError:
                pass
        return dest
    except OSError:
        return None


def load_blueprint(path: Path | None = None) -> TrainerModel | None:
    target = Path(path) if path is not None else blueprint_path()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict) or data.get("kind") != "terraformer_trainer":
        return None
    return TrainerModel.from_blueprint(data)
