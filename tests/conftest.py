"""Test isolation for process-global UI state.

stamina.theme (UI scale, fonts, skin colours, listeners) and the colour aliases it
copies into other stamina modules are process-global. A test that builds a full
Cockpit applies the pilot's UI scale (1.42) and skin, and every later Tk test
silently inherited them, which made layout tests order-dependent.
"""
import copy
import pathlib
import sys

import os
import pytest

# Сторож замираний пишет stall.log в профиль пилота — в тестах он не нужен.
os.environ.setdefault("STAR_TYPING_NO_STALL_WATCH", "1")
# Тесты не должны говорить вслух через espeak-ng / spd-say на Linux.
os.environ.setdefault("STAR_TYPING_NO_LINUX_TTS", "1")
# Тесты не должны включать звуки пульта и голос Ориона (обычный запуск приложения не затрагивается).
os.environ.setdefault("STAR_TYPING_SILENT", "1")

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
# Modules whose dict/list globals are UI state, not caches. stamina.i18n holds the skin's
# voice pack (`_voice`, set by theme.apply_skin through set_voice) and the language table:
# a Cockpit test applying the "old_england" skin made later tests read «ФЛИТ-СТРИТ» for «МОСТИК».
_DICT_STATE = ("stamina.theme", "stamina.i18n")


def _snapshot():
    snap = {}
    for name, mod in list(sys.modules.items()):
        if not name.startswith("stamina") or mod is None:
            continue
        for k, v in list(vars(mod).items()):
            if k.startswith("__"):
                continue
            if isinstance(v, _SIMPLE) or (name in _DICT_STATE and isinstance(v, (dict, list))):
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


class _MemoryCredStore:
    """Credential Manager stand-in: tests never write to the real Windows vault."""

    def __init__(self):
        self.d = {}

    def set_password(self, svc, user, pw):
        self.d[svc] = pw

    def get_password(self, svc, user):
        return self.d.get(svc)

    def delete_password(self, svc, user):
        self.d.pop(svc, None)


@pytest.fixture(autouse=True)
def _isolate_agent_store(monkeypatch, tmp_path_factory):
    """Agent profiles, Orion history/characters and keys go to a temp dir, not %APPDATA%\\Stamina.

    Tests that call pilots.reset_root(tmp) keep their own root; only the real root is redirected.
    """
    from stamina import agent_connect, orion, pilots
    real = pathlib.Path(pilots._root())
    tmp = tmp_path_factory.mktemp("orion_root")
    orig = orion._root

    def _root():
        cur = pathlib.Path(orig())
        return tmp if cur == real else cur

    monkeypatch.setattr(orion, "_root", _root)
    store = _MemoryCredStore()
    monkeypatch.setattr(agent_connect, "_backend", lambda: ("keyring", store))


@pytest.fixture(autouse=True)
def _gc_on_main_thread():
    """Мусор прошлых окон Tk собираем здесь, в главном потоке, — иначе его подберёт
    фоновый поток следующего теста и Tcl на Linux упадёт (Illegal instruction)."""
    import gc
    yield
    gc.collect()


@pytest.fixture(autouse=True)
def _cockpit_bootstrapped(monkeypatch):
    """Кабина достраивается через after(60). В тестах старт идёт синхронно в конце
    конструктора (иначе стартовая миссия перебивает show() теста), а повторный
    after(60) уже ничего не делает. Ожидание update()+sleep убрано: на CI оно
    растягивалось до 3 с на каждый тест и давало шанс сетевой проверке обновлений."""
    try:
        from stamina.cockpit import Cockpit
    except Exception:  # noqa: BLE001
        yield
        return
    # GitHub Releases в тестах не дёргаем через after(2500) после старта кабины.
    # fetch_latest / run_auto_update не трогаем: их проверяет tests/test_auto_update.py.
    monkeypatch.setattr(Cockpit, "_check_updates_bg", lambda self: None)
    orig_init = Cockpit.__init__
    orig_bootstrap = Cockpit._bootstrap

    def bootstrap(self):
        if getattr(self, "_bootstrapped", False):
            return
        orig_bootstrap(self)

    def init(self, *a, **k):
        orig_init(self, *a, **k)
        bootstrap(self)

    monkeypatch.setattr(Cockpit, "_bootstrap", bootstrap)
    monkeypatch.setattr(Cockpit, "__init__", init)
    yield


@pytest.fixture(autouse=True)
def _close_english_tts(monkeypatch):
    """Голос не должен поднимать powershell/edge-tts по тесту: на CI это дорого,
    а в Windows копии процессов копятся и тормозят весь прогон."""
    try:
        from stamina.english import tts as etts
    except Exception:  # noqa: BLE001
        yield
        return
    made = []
    orig = etts.TTS.__init__

    def init(self, *a, **k):
        orig(self, *a, **k)
        made.append(self)

    monkeypatch.setattr(etts.TTS, "__init__", init)
    monkeypatch.setattr(etts.TTS, "_ensure", lambda self: False)
    monkeypatch.setattr(etts.tts_edge, "ready", lambda: False)
    yield
    for t in made:
        try:
            t.close()
        except Exception:  # noqa: BLE001
            pass
