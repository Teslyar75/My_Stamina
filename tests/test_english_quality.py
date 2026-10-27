"""Качественные повторения: 20 слотов, настраиваемая цель, авто-зачёт по баллу."""
from stamina.english import quality
from stamina.english.progress import Progress


def _progress(tmp_path) -> Progress:
    return Progress(tmp_path / "english.json")


def test_slot_profile_word():
    sm = quality.slots("word", 5)
    assert len(sm) == quality.MAX_SLOTS
    groups = {}
    for s in sm:
        groups[s["group"]] = groups.get(s["group"], 0) + 1
    assert groups == {"A": 4, "B": 10, "C": 3, "D": 2, "E": 1}
    # пары чтения: два порога на каждое из пяти предложений
    assert [s["key"] for s in sm if s["group"] == "B"][:4] == ["b00", "b01", "b10", "b11"]


def test_slot_profile_verb_and_sentence():
    assert len(quality.slots("verb", 3)) == 20
    assert len(quality.slots("sentence", 5)) == 20


def test_goal_can_be_lowered(tmp_path):
    p = _progress(tmp_path)
    assert quality.set_goal(p, "apple", 5) == 5
    assert quality.counts(p, "apple")["goal"] == 5
    assert quality.set_goal(p, "apple", 50) == 20      # больше слотов не бывает
    assert quality.set_goal(p, "apple", 1) == 1


def test_auto_fills_slots_by_score(tmp_path):
    p = _progress(tmp_path)
    # 80% хватает на первый слот слова
    res, key = quality.auto(p, "apple", "A", 80)
    assert (res, key) == ("ok", "a0")
    # тот же слот повторно не засчитывается, берётся следующий
    res, key = quality.auto(p, "apple", "A", 91)
    assert (res, key) == ("ok", "a1")
    # низкий балл не закрывает слот с высоким порогом
    assert quality.auto(p, "apple", "A", 95)[0] == "ok"
    res, key = quality.auto(p, "apple", "A", 82)
    assert key == "a3" and res == "low"
    assert quality.counts(p, "apple")["filled"] == 3
    # следующий заход с высоким баллом закрывает и четвёртый слот
    assert quality.auto(p, "apple", "A", 99) == ("ok", "a3")
    # закрытая группа
    assert quality.auto(p, "apple", "A", 99) == ("full", None)


def test_self_rated_slot_has_no_score(tmp_path):
    p = _progress(tmp_path)
    quality.set_goal(p, "apple", 5)
    res, key = quality.auto(p, "apple", "A", 0, self_rated=True)
    assert (res, key) == ("self", "a0")
    rec = quality.get(p, "apple")
    assert rec["slots"]["a0"][0] is None
    assert rec["self"] == 1
    assert quality.average_score(p, "apple") == 0.0


def test_complete_at_goal(tmp_path):
    p = _progress(tmp_path)
    quality.set_goal(p, "apple", 5)
    for _ in range(4):
        assert quality.auto(p, "apple", "A", 95)[0] == "ok"
    assert not quality.is_complete(p, "apple")
    assert quality.auto(p, "apple", "B", 95, si=0)[0] == "ok"
    assert quality.is_complete(p, "apple")
    assert quality.remaining(p, "apple") == 0
    assert quality.hint(p, "apple") == "готово"


def test_counts_do_not_write(tmp_path):
    p = _progress(tmp_path)
    before = len(p.data.get("quality") or {})
    c = quality.counts(p, "apple", n_sents=5)
    assert c["total"] == 20 and c["goal"] == 20 and c["filled"] == 0
    assert len(p.data.get("quality") or {}) == before


def test_average_and_reset(tmp_path):
    p = _progress(tmp_path)
    quality.auto(p, "apple", "A", 80)
    quality.auto(p, "apple", "A", 90)
    assert quality.average_score(p, "apple") == 85.0
    quality.reset(p, "apple")
    assert quality.filled(p, "apple") == 0


def test_b_slots_follow_sentence(tmp_path):
    p = _progress(tmp_path)
    assert quality.auto(p, "apple", "B", 90, si=2) == ("ok", "b20")
    assert quality.auto(p, "apple", "B", 90, si=2) == ("ok", "b21")
    # пара этого предложения закрыта, следующая — другое предложение
    assert quality.auto(p, "apple", "B", 86, si=2) == ("ok", "b00")


def test_migrate_v1(tmp_path):
    p = _progress(tmp_path)
    p.data["version"] = 1
    p.data.pop("quality", None)
    p.save()
    quality.migrate(p)
    assert p.data["version"] == 2
    assert p.data["quality"] == {}
    assert p.data["settings"]["quality_goal"] == 20
