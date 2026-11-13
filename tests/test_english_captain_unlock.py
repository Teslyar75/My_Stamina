"""Капитан (GitHub-разработчик) видит все уровни CEFR и весь пак глаголов; ученик открывает по мере курса."""
import pytest

from stamina import pilots
from stamina.english import access, cefr, verbs
from stamina.english.progress import Progress


@pytest.fixture
def root(tmp_path):
    pilots.reset_root(tmp_path)
    yield tmp_path
    pilots._active = None
    pilots.reset_root()


def _activate(p):
    pilots._active = p


def test_no_registry_is_not_captain(root):
    pilots._active = None
    assert not pilots.is_captain()
    assert not access.is_captain()


def test_migrated_from_and_role_are_not_captain(root):
    from stamina import roles
    roles._FORCE_FILE_STORE = True
    a = pilots.create("Alpha")
    b = pilots.create("Bravo")
    assert not pilots.is_captain(a)
    # перенос старых данных и поле role сами по себе капитана не дают
    pilots.update_pilot(a["id"], migrated_from="C:/old")
    assert not pilots.is_captain(pilots.get(a["id"]))
    assert not pilots.is_captain(pilots.get(b["id"]))
    pilots.set_role(b["id"], pilots.CAPTAIN)
    assert not pilots.is_captain(pilots.get(b["id"]))
    assert not pilots.is_captain(pilots.get(a["id"]))


def _levels_rule(progress, done_set):
    levels = ["A1", "A2", "B1.1"]
    words = {"A1": ["a", "b", "c", "d", "e"], "A2": ["f", "g"], "B1.1": ["h"]}
    return lambda lv: access.level_open(progress, lv, levels, words.get, lambda s: s in done_set)


def test_student_progressive_levels(root, tmp_path):
    pilots._active = None
    p = Progress(tmp_path / "e.json")
    done = set()
    is_open = _levels_rule(p, done)
    assert is_open("A1") and not is_open("A2") and not is_open("B1.1")
    done.update({"a", "b", "c"})                 # 60 % < 80 %
    assert not is_open("A2")
    done.add("d")                                # 80 %
    assert is_open("A2") and not is_open("B1.1")
    p.settings["cefr_unlock_pct"] = 100          # настройка порога
    assert not is_open("A2")
    prev, need, now = access.level_need(p, "A2", ["A1", "A2", "B1.1"],
                                        {"A1": list("abcde")}.get, lambda s: s in done)
    assert (prev, need, now) == ("A1", 100, 80)


def test_start_level_setting_does_not_bypass(root, tmp_path):
    pilots._active = None
    p = Progress(tmp_path / "e.json")
    p.settings["cefr_start_level"] = "A2"
    is_open = _levels_rule(p, set())
    assert is_open("A1") and not is_open("A2") and not is_open("B1.1")
    assert access.start_level(p, ["A1", "A2", "B1.1"]) == "A2"


def test_captain_gets_everything(root, tmp_path):
    from stamina import roles
    roles._FORCE_FILE_STORE = True
    cap = pilots.create("Captain")
    roles.write_access_cache(cap["id"], ok=True, login="dev")
    _activate(pilots.get(cap["id"]))
    p = Progress(tmp_path / "e.json")
    is_open = _levels_rule(p, set())
    assert is_open("A1") and is_open("A2") and is_open("B1.1")
    for lv in cefr.available():
        assert access.level_open(p, lv, cefr.available(), lambda l: [], lambda s: False)
    pack = verbs.frequent()
    assert verbs.unlocked_count(p, pack) == len(pack)
    assert not verbs.locked_lemmas(p)


def test_student_verbs_still_gated(root, tmp_path):
    pilots._active = pilots.create("Student")
    p = Progress(tmp_path / "e.json")
    pack = verbs.frequent()
    if len(pack) > verbs.UNLOCK_START:
        assert verbs.unlocked_count(p, pack) == verbs.UNLOCK_START
        assert verbs.locked_lemmas(p)
