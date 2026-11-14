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
import random
import time
from pathlib import Path
from stamina.i18n import t as _t

GRID_W = 40
GRID_H = 24
LAYERS = ("soil", "clay", "metal")
HOLD_CAP = 10
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

# ─── система прогрессии: разблокировка вариантов и роботов через язык ─────────
# Уровни владения языком (0-5): 0=новичок, 1=базовый, 2=средний, 3=продвинутый, 4=эксперт, 5=мастер
# Пилот видит все варианты в галерее, но может строить только разблокированные.
# Это создаёт желание учить язык, чтобы получить доступ к лучшим постройкам.

PROGRESSION_TIERS = {
    0: {  # Новичок — только база
        "platform_variants": {"water": (0,), "stone": (0,), "organic": (0,), "iron": (0,), "quartz": (0,)},
        "robots": ("A1",),
        "upgrades": (),
        "description": _t("Базовые платформы. Робот A1. Учите язык, чтобы разблокировать продвинутые постройки."),
    },
    1: {  # Базовый — вторые варианты
        "platform_variants": {"water": (0, 1), "stone": (0, 1), "organic": (0, 1), "iron": (0, 1), "quartz": (0, 1)},
        "robots": ("A1",),
        "upgrades": ("soil_compactor",),
        "description": _t("Компактные варианты платформ. Доступен пресс для грунта (блоки из 5 грунта)."),
    },
    2: {  # Средний — третьи варианты + A2
        "platform_variants": {"water": (0, 1, 2), "stone": (0, 1, 2), "organic": (0, 1, 2), "iron": (0, 1, 2), "quartz": (0, 1, 2)},
        "robots": ("A1", "A2"),
        "upgrades": ("soil_compactor", "auto_unloader", "water_purifier"),
        "description": _t("Все варианты платформ! Робот A2 копет глину и металл. Автовыгрузка и очистка воды."),
    },
    3: {  # Продвинутый — эффективность + A3
        "platform_variants": {"water": (0, 1, 2), "stone": (0, 1, 2), "organic": (0, 1, 2), "iron": (0, 1, 2), "quartz": (0, 1, 2)},
        "robots": ("A1", "A2", "A3"),
        "upgrades": ("soil_compactor", "auto_unloader", "water_purifier", "yield_booster", "remote_control"),
        "description": _t("Робот A3 — автономная добыча. Усилитель добычи +50%. Дистанционное управление."),
    },
    4: {  # Эксперт — автоматизация + A4
        "platform_variants": {"water": (0, 1, 2), "stone": (0, 1, 2), "organic": (0, 1, 2), "iron": (0, 1, 2), "quartz": (0, 1, 2)},
        "robots": ("A1", "A2", "A3", "A4"),
        "upgrades": ("soil_compactor", "auto_unloader", "water_purifier", "yield_booster", "remote_control", "logistics_network", "auto_builder"),
        "description": _t("Робот A4 — строительство платформ за вас. Логистическая сеть доставляет ресурсы."),
    },
    5: {  # Мастер — всё, включая экспериментальное
        "platform_variants": {"water": (0, 1, 2), "stone": (0, 1, 2), "organic": (0, 1, 2), "iron": (0, 1, 2), "quartz": (0, 1, 2)},
        "robots": ("A1", "A2", "A3", "A4", "A5"),
        "upgrades": ("soil_compactor", "auto_unloader", "water_purifier", "yield_booster", "remote_control", "logistics_network", "auto_builder", "terraform_core"),
        "description": _t("Робот A5 — полная терраформация. Ядро терраформирования меняет биом планеты."),
    },
}

def get_language_level() -> int:
    """Возвращает текущий уровень языка пилота (0-5).
    Основан на XP модуля «Английский»: уровень = floor(sqrt(XP/50)) + 1.
    Ограничен диапазоном 0-5 для прогрессии терраформера."""
    try:
        from stamina.english.progress import Progress
        from stamina import pilots
        pilot_dir = pilots.active_dir()
        prog = Progress(pilot_dir / "english.json")
        lvl, _, _ = prog.level()
        return max(0, min(5, lvl - 1))  # уровень 1 = 0, уровень 6 = 5
    except Exception:
        pass
    return 0


def get_unlocked_variants(resource: str, language_level: int | None = None) -> tuple[int, ...]:
    """Возвращает индексы разблокированных вариантов для ресурса."""
    if language_level is None:
        language_level = get_language_level()
    tier = PROGRESSION_TIERS.get(min(language_level, 5), PROGRESSION_TIERS[0])
    return tier["platform_variants"].get(resource, (0,))


def get_unlocked_robots(language_level: int | None = None) -> tuple[str, ...]:
    if language_level is None:
        language_level = get_language_level()
    tier = PROGRESSION_TIERS.get(min(language_level, 5), PROGRESSION_TIERS[0])
    return tier["robots"]


def get_unlocked_upgrades(language_level: int | None = None) -> tuple[str, ...]:
    if language_level is None:
        language_level = get_language_level()
    tier = PROGRESSION_TIERS.get(min(language_level, 5), PROGRESSION_TIERS[0])
    return tier["upgrades"]


def get_tier_description(language_level: int | None = None) -> str:
    if language_level is None:
        language_level = get_language_level()
    tier = PROGRESSION_TIERS.get(min(language_level, 5), PROGRESSION_TIERS[0])
    return tier["description"]


def get_next_tier_preview(language_level: int | None = None) -> dict | None:
    """Что откроется на следующем уровне — для мотивации в галерее."""
    if language_level is None:
        language_level = get_language_level()
    next_level = min(language_level + 1, 5)
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
    """{(x, y): (ресурс, слой)} — детерминированно по сиду и размеру поля."""
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


class TrainerModel:
    """Поле, робот, отсеки и фундамент учебной смены."""

    def __init__(self, w: int = GRID_W, h: int = GRID_H, depth: int = 1,
                 seed: int | None = None) -> None:
        self.w = max(1, int(w))
        self.h = max(1, int(h))
        self.depth = max(1, min(int(depth), len(LAYERS)))
        self.dug = [[0] * self.w for _ in range(self.h)]
        self.robot = [self.w // 2, self.h // 2]
        self.facing = (1, 0)
        self.holds = {name: 0 for name in LAYERS}
        # расширяем отсеки для ресурсов платформ
        for r in RESOURCES:
            self.holds.setdefault(r, 0)
        self.active_hold = "soil"
        self.blocks: list[tuple[int, int]] = []          # блоки на фундаменте (старая система)
        self.platform_blocks: set[tuple[int, int]] = set()  # все блоки платформ (для отрисовки)
        self.walls_open = False
        self.seed = int(seed) if seed is not None else new_seed()
        exclude = set(self.site_cells()) | {tuple(self.robot)}
        self.finds = generate_finds(self.seed, self.w, self.h, exclude)
        self.revealed: set[tuple[int, int]] = set()
        self.finds_count = {name: 0 for name in RESOURCES}
        self.last_find: dict | None = None
        # платформы добычи
        self.platforms: list[PlatformBlueprint] = []
        self._platform_priority_counter = 0

    # -- находки ---------------------------------------------------------------
    @property
    def springs(self) -> set:
        """Открытые источники воды: эти клетки дальше не копают."""
        return {c for c in self.revealed if self.finds.get(c, ("",))[0] == "water"}

    def found_types(self) -> list[str]:
        return [r for r in RESOURCES if self.finds_count.get(r, 0) > 0]

    def _reveal(self, x: int, y: int, layer: int) -> dict | None:
        cell = (x, y)
        f = self.finds.get(cell)
        if not f or f[1] != layer or cell in self.revealed:
            return None
        res = f[0]
        self.revealed.add(cell)
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
        bp = PlatformBlueprint(
            resource=resource,
            center=center,
            pattern=pattern,
            requires_a2=requires_a2,
            variant_index=variant_idx,
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
    def try_place_block(self, x: int, y: int) -> tuple[bool, str]:
        """
        Пытается поставить блок в клетку (x, y).
        Возвращает (success, message).
        Блок тратится из отсека грунта (нужно 10).
        """
        if not (0 <= x < self.w and 0 <= y < self.h):
            return False, "за пределами поля"
        if self.holds.get("soil", 0) < HOLD_CAP:
            return False, "отсек грунта не полон"
        # проверяем, принадлежит ли клетка какой-то платформе
        target_platform = None
        for p in self.platforms:
            if not p.complete and p.is_cell_part(x, y):
                target_platform = p
                break
        # также разрешаем ставить на старую стройплощадку, если стены ещё не открыты
        on_foundation = self.on_site(x, y) and not self.walls_open
        if not target_platform and not on_foundation:
            return False, "здесь нет чертежа платформы"
        # тратим грунт
        self.holds["soil"] = 0
        self.platform_blocks.add((x, y))
        if target_platform:
            target_platform.try_add_block(x, y)
            if target_platform.complete:
                self._assign_next_priority()
                return True, f"платформа {target_platform.resource} готова!"
            return True, f"блок уложен на платформу {target_platform.resource} ({target_platform.progress_pct()}%)"
        else:
            # старая система фундамента
            self.blocks.append((x, y))
            if len(self.blocks) >= len(self.site_cells()):
                self.walls_open = True
                return True, "фундамент готов — стены открыты!"
            return True, f"блок уложен на фундамент ({len(self.blocks)}/{len(self.site_cells())})"

    # -- автодобыча за тик ------------------------------------------------------
    def tick_extraction(self) -> dict[str, int]:
        """Вызывается каждый тик для завершённых платформ. Возвращает словарь наград."""
        gained: dict[str, int] = {}
        for p in self.platforms:
            if p.complete:
                res, base_amount = PLATFORM_YIELD.get(p.resource, (p.resource, 0))
                if base_amount > 0:
                    mult = 1.0
                    if p.variant_index < len(VARIANT_YIELD_MULT.get(p.resource, (1.0,))):
                        mult = VARIANT_YIELD_MULT[p.resource][p.variant_index]
                    amount = int(base_amount * mult)
                    self.holds[res] = self.holds.get(res, 0) + amount
                    gained[res] = gained.get(res, 0) + amount
        return gained

    # -- стройплощадка -------------------------------------------------------
    def site_cells(self) -> list[tuple[int, int]]:
        x, y, w, h = SITE
        return [(cx, cy) for cy in range(y, y + h) for cx in range(x, x + w)]

    def on_site(self, x: int, y: int) -> bool:
        sx, sy, sw, sh = SITE
        return sx <= x < sx + sw and sy <= y < sy + sh

    # -- действия робота -----------------------------------------------------
    def move(self, dx: int, dy: int) -> bool:
        self.facing = (dx, dy)
        x = max(0, min(self.w - 1, self.robot[0] + dx))
        y = max(0, min(self.h - 1, self.robot[1] + dy))
        moved = (x, y) != (self.robot[0], self.robot[1])
        self.robot = [x, y]
        return moved

    def dig(self) -> str:
        """ok | hold_full | too_deep | site | spring. Находка — в self.last_find."""
        self.last_find = None
        x, y = self.robot
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
        return {
            "kind": "terraformer_trainer",
            "version": 3,
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
            "finds_count": dict(self.finds_count),
            "platforms": platforms_data,
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
                cell = (bx, by)
                if model.on_site(bx, by) and cell not in seen:
                    seen.add(cell)
                    model.blocks.append(cell)

        model.walls_open = bool(d.get("walls_open")) or len(model.blocks) >= len(model.site_cells())

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
        # также восстанавливаем holds для ресурсов платформ
        for r in RESOURCES:
            model.holds.setdefault(r, 0)
        return model


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

    def pan(self, dx_cells: float, dy_cells: float) -> None:
        self.follow = False
        self.cx += dx_cells
        self.cy += dy_cells
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
