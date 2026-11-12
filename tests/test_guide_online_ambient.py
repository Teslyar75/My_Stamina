"""ONLINE idle: шутки/факты в чат Ориона при свободном агенте + пул guide_content."""
from __future__ import annotations

import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

from stamina import guide_idle as g
from stamina import orion, pilots

EXPECTED_POOL = 120

def test_pool_counts_and_uniqueness_per_lang():
    langs = g.list_langs()
    assert langs, "ожидается хотя бы один guide_content/<lang>.json"
    for lang in langs:
        c = g.load_content(lang)
        assert len(c["jokes"]) == EXPECTED_POOL, lang
        assert len(c["facts"]) == EXPECTED_POOL, lang
        joke_ids = [x["id"] for x in c["jokes"]]
        fact_ids = [x["id"] for x in c["facts"]]
        assert len(joke_ids) == len(set(joke_ids)), f"{lang}: дубли id шуток"
        assert len(fact_ids) == len(set(fact_ids)), f"{lang}: дубли id фактов"
        joke_texts = [x["text"].strip() for x in c["jokes"]]
        fact_texts = [x["text"].strip() for x in c["facts"]]
        assert all(joke_texts) and all(fact_texts)
        assert len(joke_texts) == len(set(joke_texts)), f"{lang}: дубли текстов шуток"
        assert len(fact_texts) == len(set(fact_texts)), f"{lang}: дубли текстов фактов"
        # структура как раньше
        assert c["jokes"][0]["id"].startswith("joke_")
        assert c["facts"][0]["id"].startswith("fact_")
        assert {"id", "text"} <= set(c["jokes"][0])
        assert {"id", "text"} <= set(c["facts"][0])

def test_can_online_ambient_gates():
    now = 1_000_000.0
    base = dict(
        guide_enabled=True,
        online_enabled=True,
        busy=False,
        has_draft=False,
        waiting=False,
        listening=False,
        pending_answer=False,
        phase_idle=True,
        now=now,
        last_key_at=now - 30,
        last_online_at=0.0,
    )
    assert g.can_online_ambient(**base) is True
    assert g.can_online_ambient(**{**base, "busy": True}) is False
    assert g.can_online_ambient(**{**base, "has_draft": True}) is False
    assert g.can_online_ambient(**{**base, "waiting": True}) is False
    assert g.can_online_ambient(**{**base, "listening": True}) is False
    assert g.can_online_ambient(**{**base, "pending_answer": True}) is False
    assert g.can_online_ambient(**{**base, "phase_idle": False}) is False
    assert g.can_online_ambient(**{**base, "online_enabled": False}) is False
    assert g.can_online_ambient(**{**base, "guide_enabled": False}) is False
    assert g.can_online_ambient(**{**base, "last_key_at": now - 1}) is False
    assert g.can_online_ambient(
        **{**base, "last_online_at": now - 60}
    ) is False
    assert g.can_online_ambient(
        **{**base, "last_online_at": now - (g.ONLINE_COOLDOWN_S + 1)}
    ) is True

class _App:
    def __init__(self, settings=None):
        self.store = SimpleNamespace(settings=dict(settings or {
            "guide_enabled": True,
            "guide_interval": "10-20",
            "guide_online_jokes": True,
            "guide_voice": "male",
        }))
        self.jobs = []
        self.screens = {}

    def after(self, ms, fn=None):
        self.jobs.append((ms, fn))
        return len(self.jobs)

    def after_cancel(self, _job):
        pass

    def bind_all(self, *a, **k):
        pass

    def focus_get(self):
        return None

def _ctrl(tmp_path, settings=None):
    app = _App(settings)
    c = g.GuideController(app, state_path=tmp_path / "s.json", autostart=False)
    c._show_toast = lambda *a, **k: None
    c._duck = c._unduck = lambda: None
    said = []
    c._say = lambda cid, done: (said.append(cid), done and done())
    return c, said, app

def test_online_toggle_off_disables(tmp_path):
    c, _, app = _ctrl(tmp_path, {"guide_enabled": True, "guide_online_jokes": False,
                                 "guide_interval": "10-20", "guide_voice": "male"})
    assert c.online_enabled() is False
    c.schedule_online()
    assert not any(fn == c._online_tick for _, fn in app.jobs if fn)

def test_online_no_inject_when_busy(tmp_path, monkeypatch):
    root = Path(tempfile.mkdtemp())
    pilots.reset_root(root)
    try:
        c, said, app = _ctrl(tmp_path)
        scr = SimpleNamespace(
            _busy=True, _draft_text="", entry=SimpleNamespace(get=lambda: ""),
            _await_task=False, _pending=None, _pending_task="", _listening=False,
        )
        app.screens["orion"] = scr
        monkeypatch.setattr("stamina.ship_chat.waiting", lambda *_a, **_k: False)
        assert c.maybe_online_ambient() is False
        assert said == []
        assert orion.history("orion")["messages"] == []
    finally:
        pilots.reset_root()

def test_online_no_inject_when_typing_draft(tmp_path, monkeypatch):
    root = Path(tempfile.mkdtemp())
    pilots.reset_root(root)
    try:
        c, said, app = _ctrl(tmp_path)
        scr = SimpleNamespace(
            _busy=False, _draft_text="миссия набрать отчёт",
            entry=SimpleNamespace(get=lambda: "миссия набрать отчёт"),
            _await_task=False, _pending=None, _pending_task="", _listening=False,
        )
        app.screens["orion"] = scr
        monkeypatch.setattr("stamina.ship_chat.waiting", lambda *_a, **_k: False)
        assert c.maybe_online_ambient() is False
        assert orion.history("orion")["messages"] == []
    finally:
        pilots.reset_root()

def test_online_no_inject_when_waiting(tmp_path, monkeypatch):
    root = Path(tempfile.mkdtemp())
    pilots.reset_root(root)
    try:
        c, said, app = _ctrl(tmp_path)
        scr = SimpleNamespace(
            _busy=False, _draft_text="", entry=SimpleNamespace(get=lambda: ""),
            _await_task=False, _pending=None, _pending_task="", _listening=False,
        )
        app.screens["orion"] = scr
        monkeypatch.setattr("stamina.ship_chat.waiting", lambda *_a, **_k: True)
        assert c.maybe_online_ambient() is False
        assert orion.history("orion")["messages"] == []
    finally:
        pilots.reset_root()

def test_online_inject_persists_in_history(tmp_path, monkeypatch):
    root = Path(tempfile.mkdtemp())
    pilots.reset_root(root)
    try:
        c, said, app = _ctrl(tmp_path)
        rendered = []
        scr = SimpleNamespace(
            _busy=False, _draft_text="", entry=SimpleNamespace(get=lambda: ""),
            _await_task=False, _pending=None, _pending_task="", _listening=False,
            _render_feed=lambda: rendered.append(1),
        )
        app.screens["orion"] = scr
        monkeypatch.setattr("stamina.ship_chat.waiting", lambda *_a, **_k: False)
        # недавний набор не должен мешать: отодвинем last_key
        c._last_key = time.monotonic() - 30
        ok = c.maybe_online_ambient(force=True)
        assert ok is True
        msgs = orion.history("orion")["messages"]
        assert len(msgs) == 1
        assert msgs[0]["role"] == "orion"
        assert msgs[0]["kind"] in ("joke", "fact")
        assert msgs[0].get("clip_id", "").startswith(msgs[0]["kind"])
        assert msgs[0]["text"]
        # переживает «перезапуск» — читаем историю снова с диска
        again = orion.history("orion")["messages"]
        assert again[0]["id"] == msgs[0]["id"]
        assert again[0]["kind"] == msgs[0]["kind"]
        assert c.state.data.get("last_online_at", 0) > 0
        # повтор сразу упирается в кулдаун
        assert c.maybe_online_ambient() is False
    finally:
        pilots.reset_root()

def test_content_lazy_load_unchanged_api():
    """Ленивая загрузка: load_content читает JSON по запросу, структура прежняя."""
    c1 = g.load_content("ru")
    c2 = g.load_content("ru")
    assert c1["lang"] == "ru"
    assert set(c1) >= {"intros", "system", "jokes", "facts"}
    assert len(c1["jokes"]) == len(c2["jokes"]) == EXPECTED_POOL
