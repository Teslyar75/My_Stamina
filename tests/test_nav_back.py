"""Центральный Backspace: стек отсеков, не срабатывает в полях ввода и на корне."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from stamina.nav_back import (
    BackStack,
    Place,
    backspace_edits_text,
    is_back_key,
    snapshot_screen,
)


def _key(sym="BackSpace", state=0, widget=None):
    return SimpleNamespace(keysym=sym, state=state, widget=widget, char="\x08")


class TestBackStack:
    def test_first_arrive_does_not_push(self):
        s = BackStack()
        a = Place("bridge")
        s.arrive(a)
        assert s.here == a
        assert s.empty()
        assert s.back() is None

    def test_back_returns_previous(self):
        s = BackStack()
        s.arrive(Place("bridge"))
        s.arrive(Place("missions"))
        s.arrive(Place("english", sub="grammar"))
        assert s.back() == Place("missions")
        assert s.here == Place("missions")
        assert s.back() == Place("bridge")
        assert s.empty()
        assert s.back() is None
        assert s.here == Place("bridge")

    def test_same_place_is_not_pushed(self):
        s = BackStack()
        s.arrive(Place("english", sub="overview"))
        s.arrive(Place("english", sub="overview"))
        assert s.empty()
        s.arrive(Place("english", sub="grammar"))
        assert not s.empty()
        assert s.back() == Place("english", sub="overview")

    def test_limit_drops_oldest(self):
        s = BackStack(limit=3)
        for name in ("a", "b", "c", "d", "e"):
            s.arrive(Place(name))
        seen = []
        while True:
            p = s.back()
            if p is None:
                break
            seen.append(p.screen)
        assert seen == ["d", "c", "b"]


class TestKeys:
    def test_is_back_key(self):
        assert is_back_key(_key("BackSpace"))
        assert is_back_key(_key("Backspace"))
        assert not is_back_key(_key("Escape"))
        assert not is_back_key(_key("BackSpace", state=0x4))
        assert not is_back_key(_key("BackSpace", state=0x20000))

    def test_edits_text_in_entry(self):
        tk = pytest.importorskip("tkinter")
        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("нет дисплея")
        try:
            entry = tk.Entry(root)
            entry.pack()
            entry.focus_set()
            root.update()
            app = SimpleNamespace(current="settings", screens={}, zen=None)
            assert backspace_edits_text(app, _key(widget=entry))
            assert not backspace_edits_text(app, _key(widget=root))
        finally:
            root.destroy()

    def test_edits_text_readonly_text_is_not_typing(self):
        tk = pytest.importorskip("tkinter")
        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("нет дисплея")
        try:
            box = tk.Text(root, state="disabled")
            box.pack()
            root.update()
            app = SimpleNamespace(current="docs", screens={}, zen=None)
            assert not backspace_edits_text(app, _key(widget=box))
        finally:
            root.destroy()

    def test_edits_text_on_bridge_run(self):
        app = SimpleNamespace(
            current="bridge",
            screens={"bridge": SimpleNamespace(state="run")},
            zen=None,
        )
        assert backspace_edits_text(app, _key())
        app.screens["bridge"].state = "idle"
        assert not backspace_edits_text(app, _key())

    def test_edits_text_when_zen_typist_on(self):
        app = SimpleNamespace(current="bridge", screens={}, zen=SimpleNamespace(on=True))
        assert backspace_edits_text(app, _key())
        app.zen.on = False
        app.screens = {"bridge": SimpleNamespace(state="idle")}
        assert not backspace_edits_text(app, _key())


class FakeScreen:
    def __init__(self, name, sub=""):
        self.name = name
        self.current = sub
        self.closed = 0

    def handle_back(self) -> bool:
        if self.closed == 0 and self.name == "english" and self.current == "grammar":
            self.closed += 1
            return True
        return False

    def snapshot_place(self):
        return Place(screen=self.name, sub=self.current)

    def restore_place(self, place: Place) -> None:
        self.current = place.sub


class FakeApp:
    def __init__(self):
        from stamina.nav_back import BackStack

        self.current = "bridge"
        self.screens = {
            "bridge": FakeScreen("bridge"),
            "english": FakeScreen("english", "overview"),
            "missions": FakeScreen("missions"),
        }
        self.back_stack = BackStack()
        self._back_restoring = False
        self.zen = None

    def snapshot_place(self):
        from stamina.nav_back import snapshot_screen

        return snapshot_screen(self.current, self.screens.get(self.current))

    def record_place(self) -> None:
        if self._back_restoring:
            return
        place = self.snapshot_place()
        if place is not None:
            self.back_stack.arrive(place)

    def show(self, name: str) -> None:
        self.current = name
        self.record_place()

    def restore_place(self, place: Place) -> None:
        self._back_restoring = True
        try:
            if self.current != place.screen:
                self.show(place.screen)
            scr = self.screens.get(place.screen)
            if scr is not None and hasattr(scr, "restore_place"):
                scr.restore_place(place)
            self.back_stack.here = place
        finally:
            self._back_restoring = False

    def go_back(self, event=None) -> bool:
        if event is not None and backspace_edits_text(self, event):
            return False
        scr = self.screens.get(self.current)
        handle = getattr(scr, "handle_back", None)
        if callable(handle) and handle():
            return True
        place = self.back_stack.back()
        if place is None:
            return False
        self.restore_place(place)
        return True


class TestGoBackFlow:
    def test_root_is_noop(self):
        app = FakeApp()
        app.record_place()
        assert app.go_back() is False
        assert app.current == "bridge"

    def test_returns_to_previous_screen(self):
        app = FakeApp()
        app.record_place()
        app.show("missions")
        assert app.go_back() is True
        assert app.current == "bridge"
        assert app.go_back() is False

    def test_handle_back_before_stack(self):
        app = FakeApp()
        app.record_place()
        app.show("english")
        app.screens["english"].current = "grammar"
        app.record_place()
        assert app.go_back() is True
        assert app.current == "english"
        assert app.screens["english"].closed == 1
        # после закрытия подпанели стек ещё хранит вкладку, затем отсек
        assert app.go_back() is True
        assert app.current == "english"
        assert app.screens["english"].current == "overview"
        assert app.go_back() is True
        assert app.current == "bridge"

    def test_does_not_fire_while_typing(self):
        tk = pytest.importorskip("tkinter")
        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("нет дисплея")
        try:
            entry = tk.Entry(root)
            entry.pack()
            entry.insert(0, "ab")
            entry.focus_set()
            root.update()
            app = FakeApp()
            app.record_place()
            app.show("missions")
            assert app.go_back(_key(widget=entry)) is False
            assert app.current == "missions"
        finally:
            root.destroy()

    def test_snapshot_uses_current_tab(self):
        scr = SimpleNamespace(current_tab="sound")
        assert snapshot_screen("settings", scr) == Place("settings", sub="sound")
