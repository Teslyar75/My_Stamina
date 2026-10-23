"""Бортовой гид: контент, манифест, мешок без повторов, клавиши, справка окна."""
from __future__ import annotations

import random

import pytest

from stamina import guide_idle as g
from stamina import page_help


def test_content_loads_and_counts():
    c = g.load_content("ru")
    intros = sum(len(v) for v in c["intros"].values())
    assert intros >= 40
    assert len(c["jokes"]) >= 50 and len(c["facts"]) >= 50
    ids = [x["id"] for lst in list(c["intros"].values()) + [c["system"], c["jokes"], c["facts"]] for x in lst]
    assert len(ids) == len(set(ids)), "id фраз должны быть уникальны"
    assert all(x["text"].startswith("Капитан") for v in c["intros"].values() for x in v)
    assert {"sys_prompt", "sys_decline"} <= {x["id"] for x in c["system"]}


def test_manifest_matches_content():
    m = g.load_manifest("ru")
    if not m:
        pytest.skip("записи гида не собраны (tools/guide_voice/build.py)")
    c = g.load_content("ru")
    clips = m["clips"]
    for cid, text in g.texts(c).items():
        assert cid in clips, cid
        assert clips[cid]["hash"] == g.text_hash(text), f"{cid}: текст изменён — пересоберите записи"
        assert g.clip_path(m, cid, "male") is not None, cid
    for key in page_help.PAGES:
        assert g.help_clip_id(key) in clips, key
    assert set(m["voices"]) == set(g.VOICES)


def test_bag_no_repeat_and_full_cycle():
    ids = [f"j{i}" for i in range(20)]
    state: dict = {}
    bag = g.ShuffleBag(ids, state, random.Random(1))
    seen = [bag.next() for _ in range(200)]
    assert all(a != b for a, b in zip(seen, seen[1:]))
    for k in range(0, 200, 20):
        assert sorted(seen[k:k + 20]) == sorted(ids)


def test_bag_state_persists(tmp_path):
    p = tmp_path / "st.json"
    s1 = g.GuideState(p)
    c = g.load_content("ru")
    first = [g.pick(c, s1, random.Random(i))[2] for i in range(5)]
    s2 = g.GuideState(p)
    assert s2.data["bags"], "мешки сохраняются"
    nxt = g.pick(c, s2, random.Random(99))[2]
    assert nxt not in first or len(c["jokes"]) < 5


def test_interval_and_slowdown():
    r = random.Random(3)
    for _ in range(50):
        ms = g.interval_ms("10-20", 0, r)
        assert 10 * 60_000 <= ms <= 20 * 60_000
    assert g.interval_ms("off") is None
    assert g.interval_ms("10-20", 3, random.Random(1)) >= 20 * 60_000


def test_help_lookup_and_spoken():
    m = {"clips": {"help.english": {}, "help.english.sets": {}, "help.bridge": {}}}
    assert g.help_lookup("english.sets", m) == "help.english.sets"
    assert g.help_lookup("english.review", m) == "help.english"
    assert g.help_lookup("radio", m) is None
    s = g.spoken_help("Мостик", "• Ctrl+1…8 — зоны · Esc — пауза")
    assert "•" not in s and "Контрол" in s and "Эскейп" in s and s.startswith("Мостик.")


class _App:
    def __init__(self):
        self.store = type("S", (), {"settings": {"guide_enabled": True, "guide_interval": "10-20"}})()
        self.jobs = []

    def after(self, ms, fn=None):
        self.jobs.append((ms, fn))
        return len(self.jobs)

    def after_cancel(self, _job):
        pass

    def bind_all(self, *a, **k):
        pass

    def focus_get(self):
        return None


def _ctrl(tmp_path):
    c = g.GuideController(_App(), state_path=tmp_path / "s.json", autostart=False)
    c._show_toast = lambda *a, **k: None
    c._duck = c._unduck = lambda: None
    said = []
    c._say = lambda cid, done: said.append(cid)
    return c, said


def test_keys_accept(tmp_path):
    c, said = _ctrl(tmp_path)
    assert c.handle_key("Return") is None          # без подсказки Enter не перехватывается
    c.fire(force=True)
    assert c.phase == "intro" and said[0].startswith("intro_")
    c._await_answer()
    assert c.handle_key("Return") == "break"
    assert c.phase == "item" and said[-1].startswith(("joke_", "fact_"))
    assert c.state.data["listened"] == 1
    assert c.handle_key("Escape") == "break" and c.phase == "idle"


def test_keys_decline_and_timer(tmp_path):
    c, said = _ctrl(tmp_path)
    c.fire(force=True)
    assert c.handle_key("Escape") == "break"
    assert said[-1] == "sys_decline" and c.state.data["decline_streak"] == 1
    c.finish()
    assert c.phase == "idle" and c.app.jobs, "после ответа гид снова ставит таймер"


def test_disabled_does_not_schedule(tmp_path):
    c, _ = _ctrl(tmp_path)
    c.app.store.settings["guide_enabled"] = False
    c.schedule()
    assert not c.app.jobs


def test_speak_help_uses_page_key(tmp_path, monkeypatch):
    c, _ = _ctrl(tmp_path)
    played = []
    c.player.play = lambda path, done: played.append(path) or True
    monkeypatch.setattr(c, "_live", lambda text, done: played.append(text))
    key = c.speak_help("english.sets")
    assert key == "english.sets" and played and c.phase == "help"
