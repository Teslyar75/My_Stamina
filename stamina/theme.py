"""Палитра, шрифты, масштаб и движок скинов Star Typing.

Цвета живут в модульных константах (AMBER, BG, …) для совместимости с
``from stamina.theme import AMBER``. Смена скина обновляет эти имена и
перекрашивает уже созданные виджеты через remap старых hex → новых.
JSON-скины: ``stamina/themes/<id>.json`` (см. docs/skins/SKINS.md).
"""

from __future__ import annotations

import json
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from typing import Any, Callable

# --- Фон и панели (значения по умолчанию = скин «Звездолёт») ------------
BG = "#03060C"
BG2 = "#060C17"
PANEL = "#081221"
PANEL_HI = "#0D1C33"
LINE = "#15314D"
LINE_HI = "#1F4F7A"

CYAN = "#00E5FF"
CYAN_DIM = "#0B7285"
CYAN_DEEP = "#06303B"
AMBER = "#FFB000"
AMBER_DIM = "#7A5300"
RED = "#FF3B5C"
RED_DIM = "#5E1426"
GREEN = "#3DFF8A"
GREEN_DIM = "#155E36"
PURPLE = "#B76BFF"

TEXT = "#D6F4FF"
MUTED = "#6F90AB"
FAINT = "#2d4964"

ZONE_PINKY = "#FF4FA3"
ZONE_RING = "#FFD84A"
ZONE_MIDDLE = "#4CFF8F"
ZONE_L_INDEX = "#2ED8FF"
ZONE_R_INDEX = "#B76BFF"
ZONE_THUMB = "#8FA6BF"
ZONE_MOD = "#4A6580"

HUD_FAMILY = "Segoe UI"
MONO_FAMILY = "Consolas"

S = 1.0
UI = 1.0
# Ступени крупнее прежних на ~1–1.5 шага (было 0.90 / 1.00 / 1.15 / 1.35)
UI_PRESETS = {"S": 1.05, "M": 1.22, "L": 1.42, "XL": 1.65}

THEMES_DIR = Path(__file__).resolve().parent / "themes"
DEFAULT_THEME_ID = "spaceship"

# JSON color key → module attribute
_COLOR_ATTRS: dict[str, str] = {
    "bg": "BG",
    "bg2": "BG2",
    "panel": "PANEL",
    "panel_hi": "PANEL_HI",
    "line": "LINE",
    "panel_border": "LINE",
    "line_hi": "LINE_HI",
    "cyan": "CYAN",
    "cyan_dim": "CYAN_DIM",
    "cyan_deep": "CYAN_DEEP",
    "accent": "AMBER",
    "accent_dim": "AMBER_DIM",
    "error": "RED",
    "error_dim": "RED_DIM",
    "ok": "GREEN",
    "ok_dim": "GREEN_DIM",
    "purple": "PURPLE",
    "text": "TEXT",
    "muted": "MUTED",
    "faint": "FAINT",
    "zone_pinky": "ZONE_PINKY",
    "zone_ring": "ZONE_RING",
    "zone_middle": "ZONE_MIDDLE",
    "zone_l_index": "ZONE_L_INDEX",
    "zone_r_index": "ZONE_R_INDEX",
    "zone_thumb": "ZONE_THUMB",
    "zone_mod": "ZONE_MOD",
}

_TOKEN_ORDER = (
    "BG", "BG2", "PANEL", "PANEL_HI", "LINE", "LINE_HI",
    "CYAN", "CYAN_DIM", "CYAN_DEEP", "AMBER", "AMBER_DIM",
    "RED", "RED_DIM", "GREEN", "GREEN_DIM", "PURPLE",
    "TEXT", "MUTED", "FAINT",
    "ZONE_PINKY", "ZONE_RING", "ZONE_MIDDLE", "ZONE_L_INDEX",
    "ZONE_R_INDEX", "ZONE_THUMB", "ZONE_MOD",
)

_current: dict[str, Any] = {"id": DEFAULT_THEME_ID}
_listeners: list[Callable[[dict], None]] = []
_root: tk.Misc | None = None


def px(value: float) -> int:
    return int(round(value * S * UI))


def init(root: tk.Tk) -> None:
    """DPI + шрифты. Вызывать один раз при старте."""
    global S, HUD_FAMILY, MONO_FAMILY, _root
    _root = root
    try:
        S = max(1.0, float(root.winfo_fpixels("1i")) / 96.0)
    except tk.TclError:
        S = 1.0
    _pick_fonts(root)


def _pick_fonts(root: tk.Misc | None = None) -> None:
    global HUD_FAMILY, MONO_FAMILY
    try:
        families = set(tkfont.families(root)) if root is not None else set()
    except tk.TclError:
        families = set()
    ui_prefs = list((_current.get("fonts") or {}).get("ui") or []) + [
        "Bahnschrift", "Segoe UI", "Noto Sans", "DejaVu Sans", "Ubuntu",
        "Liberation Sans", "Cantarell", "Helvetica",
    ]
    mono_prefs = list((_current.get("fonts") or {}).get("typing") or []) + [
        "Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Noto Sans Mono",
        "Ubuntu Mono", "Liberation Mono", "Courier New",
    ]
    for name in ui_prefs:
        if not families or name in families:
            HUD_FAMILY = name
            break
    for name in mono_prefs:
        if not families or name in families:
            MONO_FAMILY = name
            break


def set_ui_scale(key: str) -> str:
    global UI
    key = (key or "M").upper()
    if key not in UI_PRESETS:
        key = "M"
    UI = UI_PRESETS[key]
    return key


def font(size: int, bold: bool = False, mono: bool = False) -> tuple:
    family = MONO_FAMILY if mono else HUD_FAMILY
    scaled = max(6, int(round(size * UI)))
    return (family, scaled, "bold") if bold else (family, scaled)


def _rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def blend(c1: str, c2: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = _rgb(c1)
    r2, g2, b2 = _rgb(c2)
    return "#{:02X}{:02X}{:02X}".format(
        int(r1 + (r2 - r1) * t),
        int(g1 + (g2 - g1) * t),
        int(b1 + (b2 - b1) * t),
    )


def chamfer(x1: float, y1: float, x2: float, y2: float, c: float) -> list[float]:
    return [x1 + c, y1, x2, y1, x2, y2 - c, x2 - c, y2, x1, y2, x1, y1 + c]


HEAT_FULL = 0.25   # 25 % ошибок и выше — полностью красная клавиша


def heat_fill(error_rate: float) -> str:
    """Цвет клавиши по доле ошибок 0..1: зелёный → янтарь (12 %) → красный (≥25 %)."""
    return heat_color(min(1.0, max(0.0, error_rate) / HEAT_FULL))


def heat_color(rate: float) -> str:
    if rate <= 0:
        return blend(PANEL, GREEN_DIM, 0.6)
    if rate < 0.5:
        return blend(GREEN_DIM, AMBER, rate * 2)
    return blend(AMBER, RED, (rate - 0.5) * 2)


# ---------------------------------------------------------------------------
# Движок скинов
# ---------------------------------------------------------------------------

def themes_dir() -> Path:
    return THEMES_DIR


def list_themes() -> list[dict[str, Any]]:
    """Список скинов: [{id, name, path}, …], spaceship первым."""
    out: list[dict[str, Any]] = []
    if not THEMES_DIR.is_dir():
        return out
    for path in sorted(THEMES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        tid = str(data.get("id") or path.stem)
        out.append({"id": tid, "name": data.get("name") or {"en": tid}, "path": path, "data": data})
    out.sort(key=lambda x: (0 if x["id"] == DEFAULT_THEME_ID else 1, x["id"]))
    return out


def current() -> dict[str, Any]:
    return dict(_current)


def theme_id() -> str:
    return str(_current.get("id") or DEFAULT_THEME_ID)


def c(key: str, default: str | None = None) -> str:
    """Цвет по ключу JSON (`accent`, `bg`, …) или имени атрибута (`AMBER`)."""
    attr = _COLOR_ATTRS.get(key, key.upper() if key.islower() else key)
    g = globals()
    if attr in g and isinstance(g[attr], str) and g[attr].startswith("#"):
        return g[attr]
    if default is not None:
        return default
    return TEXT


def on_change(cb: Callable[[dict], None]) -> None:
    if cb not in _listeners:
        _listeners.append(cb)


def off_change(cb: Callable[[dict], None]) -> None:
    try:
        _listeners.remove(cb)
    except ValueError:
        pass


def _snapshot() -> dict[str, str]:
    g = globals()
    return {name: g[name] for name in _TOKEN_ORDER if isinstance(g.get(name), str)}


def _apply_colors(colors: dict[str, str]) -> None:
    g = globals()
    for key, attr in _COLOR_ATTRS.items():
        val = colors.get(key)
        if isinstance(val, str) and val.startswith("#"):
            g[attr] = val.upper() if len(val) == 7 else val
    # недостающие dim — затемнение базовых
    if "accent_dim" not in colors:
        g["AMBER_DIM"] = blend(g["AMBER"], "#000000", 0.55)
    if "error_dim" not in colors:
        g["RED_DIM"] = blend(g["RED"], "#000000", 0.55)
    if "ok_dim" not in colors:
        g["GREEN_DIM"] = blend(g["GREEN"], "#000000", 0.55)
    if "cyan_dim" not in colors:
        g["CYAN_DIM"] = blend(g["CYAN"], "#000000", 0.55)
    if "cyan_deep" not in colors:
        g["CYAN_DEEP"] = blend(g["CYAN"], "#000000", 0.75)
    if "bg2" not in colors:
        g["BG2"] = blend(g["BG"], g["PANEL"], 0.35)
    if "panel_hi" not in colors:
        g["PANEL_HI"] = blend(g["PANEL"], g["LINE"], 0.35)
    if "line_hi" not in colors:
        g["LINE_HI"] = blend(g["LINE"], g["TEXT"], 0.25)
    if "faint" not in colors:
        g["FAINT"] = blend(g["MUTED"], g["BG"], 0.55)


def load_theme(theme_id_: str, *, apply_ui: bool = True, root: tk.Misc | None = None) -> dict[str, Any]:
    """Загрузить скин по id. Возвращает данные темы."""
    global _current
    tid = (theme_id_ or DEFAULT_THEME_ID).strip() or DEFAULT_THEME_ID
    path = THEMES_DIR / f"{tid}.json"
    if not path.is_file():
        path = THEMES_DIR / f"{DEFAULT_THEME_ID}.json"
        tid = DEFAULT_THEME_ID
    data: dict[str, Any] = {"id": tid}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["id"] = str(data.get("id") or tid)
    except (OSError, ValueError, UnicodeDecodeError):
        data = {"id": DEFAULT_THEME_ID, "colors": {}}

    old = _snapshot()
    _register_font_files(data)
    try:
        from stamina import i18n as _i18n
        _i18n.set_voice(data.get("voice"))
    except Exception:  # noqa: BLE001
        pass
    colors = dict(data.get("colors") or {})
    if colors:
        _apply_colors(colors)
    _current = data
    _pick_fonts(root or _root)
    new = _snapshot()

    _sync_imported_aliases()
    if apply_ui:
        target = root or _root
        if target is not None:
            remap_widgets(target, old, new)
        for cb in list(_listeners):
            try:
                cb(data)
            except Exception:  # noqa: BLE001
                pass
    return data


def _sync_imported_aliases() -> None:
    """Обновить AMBER/BG/… в модулях, которые сделали ``from stamina.theme import BG``.

    Иначе новые виджеты после смены скина создаются со старыми цветами.
    """
    import sys

    g = globals()
    names = tuple(_TOKEN_ORDER)
    for mod in list(sys.modules.values()):
        if mod is None:
            continue
        try:
            name = getattr(mod, "__name__", "") or ""
        except Exception:  # noqa: BLE001
            continue
        if not name.startswith("stamina"):
            continue
        for attr in names:
            if hasattr(mod, attr) and attr in g:
                try:
                    # только если это «наш» hex-цвет (не чужая константа)
                    cur = getattr(mod, attr)
                    if isinstance(cur, str) and cur.startswith("#"):
                        setattr(mod, attr, g[attr])
                except Exception:  # noqa: BLE001
                    pass


_registered_fonts: set[str] = set()


def _register_font_files(data: dict) -> None:
    """OFL-шрифты скина (fonts.files) — в процесс без установки в систему (Windows: AddFontResourceEx)."""
    files = (data.get("fonts") or {}).get("files") or []
    if not files:
        return
    import sys
    root = Path(__file__).resolve().parents[1]
    for rel in files:
        path = root / str(rel)
        key = str(path)
        if key in _registered_fonts or not path.is_file():
            continue
        _registered_fonts.add(key)
        if sys.platform.startswith("win"):
            try:
                import ctypes
                FR_PRIVATE = 0x10
                ctypes.windll.gdi32.AddFontResourceExW(key, FR_PRIVATE, 0)
            except Exception:  # noqa: BLE001
                pass


def skin_rank(rank: str) -> str:
    """Звание в мире скина: базовое (переведённое) звание → ranks_i18n[lang][i]; иначе как есть."""
    if not rank:
        return rank
    data = _current
    by_lang = data.get("ranks_i18n") or {}
    base = data.get("base_ranks") or []
    if not by_lang or not base:
        return rank
    try:
        from stamina import i18n as _i18n
        lang = _i18n.language()
        tr = _i18n._table  # noqa: SLF001
    except Exception:  # noqa: BLE001
        lang, tr = "ru", {}
    for i, b in enumerate(base):
        if rank in (b, tr.get(b, b)):
            lst = by_lang.get(lang) or by_lang.get("en") or by_lang.get("ru") or []
            return lst[i] if i < len(lst) else rank
    return rank


def skin_sound_dir() -> Path | None:
    """Папка звуков скина (sounds.dir) или None — тогда звуки «Звездолёта»."""
    rel = ((_current.get("sounds") or {}).get("dir")) or ""
    if not rel:
        return None
    path = Path(__file__).resolve().parents[1] / rel
    return path if path.is_dir() else None


def theme_display_name(data: dict | None = None, lang: str = "ru") -> str:
    data = data or _current
    names = data.get("name") or {}
    if isinstance(names, dict):
        return str(names.get(lang) or names.get("en") or data.get("id") or "")
    return str(names)


def remap_widgets(root: tk.Misc, old: dict[str, str], new: dict[str, str]) -> None:
    """Перекрасить дерево виджетов: старые hex → новые по токенам."""
    mapping: dict[str, str] = {}
    for name in _TOKEN_ORDER:
        o, n = old.get(name), new.get(name)
        if o and n and o.upper() != n.upper():
            mapping[o.upper()] = n
            mapping[o] = n
    if not mapping:
        return

    def map_color(val: str) -> str:
        if not val:
            return val
        return mapping.get(val) or mapping.get(val.upper()) or val

    def walk(w: tk.Misc) -> None:
        try:
            for opt in ("bg", "fg", "highlightbackground", "highlightcolor",
                        "activebackground", "activeforeground", "insertbackground",
                        "selectbackground", "selectforeground", "troughcolor"):
                try:
                    cur = w.cget(opt)
                except tk.TclError:
                    continue
                if isinstance(cur, str) and cur in mapping or (isinstance(cur, str) and cur.upper() in mapping):
                    try:
                        w.configure(**{opt: map_color(cur)})
                    except tk.TclError:
                        pass
            # Canvas / HudButton
            if isinstance(w, tk.Canvas):
                try:
                    w.configure(bg=map_color(w.cget("bg")))
                except tk.TclError:
                    pass
                if hasattr(w, "color") and isinstance(getattr(w, "color"), str):
                    w.color = map_color(w.color)
                if hasattr(w, "_draw") and callable(w._draw):
                    try:
                        w._draw()
                    except Exception:  # noqa: BLE001
                        pass
                else:
                    try:
                        for item in w.find_all():
                            for opt in ("fill", "outline"):
                                try:
                                    cur = w.itemcget(item, opt)
                                except tk.TclError:
                                    continue
                                if cur and cur not in ("", "none"):
                                    mapped = map_color(cur)
                                    if mapped != cur:
                                        try:
                                            w.itemconfigure(item, **{opt: mapped})
                                        except tk.TclError:
                                            pass
                    except tk.TclError:
                        pass
        except tk.TclError:
            pass
        try:
            for child in w.winfo_children():
                walk(child)
        except tk.TclError:
            pass

    walk(root)


def theme_icon_path(tid: str | None = None) -> Path | None:
    """Путь к иконке скина (jpg/png) или None."""
    data = None
    for t in list_themes():
        if t["id"] == (tid or theme_id()):
            data = t["data"]
            break
    if not data:
        return None
    assets = data.get("assets") or {}
    rel = assets.get("icon") or ""
    if not rel:
        return None
    root = Path(__file__).resolve().parents[1]
    path = root / rel
    return path if path.is_file() else None
