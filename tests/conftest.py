"""Test isolation for process-global UI state.

stamina.theme (UI scale, fonts, skin colours, listeners) and the colour aliases it
copies into other stamina modules are process-global. A test that builds a full
Cockpit applies the pilot's UI scale (1.42) and skin, and every later Tk test
silently inherited them, which made layout tests order-dependent.
"""
import copy
import pathlib
import sys

import pytest

# DPI awareness must be set before the first Tk window of the process, exactly like
# stamina/app.py does. Set later (inside one test) Windows ignores it once another
# test already created a window, so at 125% scaling layout tests saw a virtualised
# 96-dpi window and failed depending on test order.
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass

# PurePath: storage.DATA_DIR/SETTINGS_PATH follow the activated pilot and leaked the
# previous test's pilot (with its UI scale) into the next Cockpit.
_SIMPLE = (int, float, str, bool, tuple, type(None), pathlib.PurePath)


def _snapshot():
    snap = {}
    for name, mod in list(sys.modules.items()):
        if not name.startswith("stamina") or mod is None:
            continue
        for k, v in list(vars(mod).items()):
            if k.startswith("__"):
                continue
            if isinstance(v, _SIMPLE) or (name == "stamina.theme" and isinstance(v, (dict, list))):
                snap[(name, k)] = copy.copy(v)
    return snap


@pytest.fixture(autouse=True)
def _isolate_stamina_globals():
    saved = _snapshot()
    yield
    for (name, k), v in saved.items():
        mod = sys.modules.get(name)
        if mod is not None:
            setattr(mod, k, v)
    hud = sys.modules.get("stamina.hud")
    for cache in ("_FIT_CACHE", "_MEASURE_CACHE", "_FONT_OBJS"):
        c = getattr(hud, cache, None)
        if isinstance(c, dict):
            c.clear()
