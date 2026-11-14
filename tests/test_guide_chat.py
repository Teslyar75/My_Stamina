"""Шутка или факт бортового гида остаётся в переписке с Орионом одной строкой."""
from stamina import guide_idle as g
from stamina import orion


class FakeState:
    def answered(self, listened: bool) -> None:
        pass


class FakeScreen:
    def __init__(self) -> None:
        self.refreshed = 0

    def refresh(self) -> None:
        self.refreshed += 1


class FakeApp:
    def __init__(self) -> None:
        self.screens: dict = {}


def _ctrl(app, *, item: str = "j1") -> g.GuideController:
    c = object.__new__(g.GuideController)
    c.app = app
    c.texts = {"j1": "Капитан, шутка про вакуум.", "f1": "Капитан, факт."}
    c.state = FakeState()
    c.current = ("joke", "i1", item)
    c.phase = "prompt"
    c._cancel_prompt = lambda: None
    c._show_toast = lambda *a, **k: None
    c._say = lambda *a, **k: None
    return c


def test_joke_is_written_to_orion_history(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(orion, "active", lambda: {"id": "orion"})
    monkeypatch.setattr(orion, "remember",
                        lambda aid, role, text, **k: calls.append((aid, role, text, k)))
    c = _ctrl(FakeApp())

    c._to_chat(c.texts["j1"])

    assert calls == [("orion", "orion", "Капитан, шутка про вакуум.", {"kind": "guide"})]


def test_accept_puts_the_single_joke_into_chat(monkeypatch):
    seen: list[str] = []
    c = _ctrl(FakeApp())
    c._to_chat = lambda text: seen.append(text)

    c.accept()

    assert seen == ["Капитан, шутка про вакуум."]
    assert c.phase == "item"


def test_open_chat_refreshes_immediately(monkeypatch):
    monkeypatch.setattr(orion, "active", lambda: {"id": "orion"})
    monkeypatch.setattr(orion, "remember", lambda *a, **k: None)
    screen = FakeScreen()
    app = FakeApp()
    app.screens["orion"] = screen

    _ctrl(app)._to_chat("Капитан, факт.")

    assert screen.refreshed == 1


def test_empty_text_is_skipped(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(orion, "remember", lambda *a, **k: calls.append(a))

    _ctrl(FakeApp())._to_chat("   ")

    assert calls == []
