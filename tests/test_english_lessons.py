"""Уроки и справочник: правила привязаны к урокам, порядок не перескакивает."""
from stamina.english import cefr, grammar, lessons
from stamina.english.progress import Progress


def _p(tmp_path) -> Progress:
    return Progress(tmp_path / "english.json")


def test_grammar_a1_rules():
    rules = grammar.rules("A1")
    assert len(rules) >= 10
    ids = [r["id"] for r in rules]
    assert len(ids) == len(set(ids))
    for r in rules:
        assert r["title"] and r["short"]
        assert r["sections"], r["id"]
        for sec in r["sections"]:
            assert sec["text"]
            for ex in sec.get("examples") or []:
                assert ex["en"].strip() and ex["ru"].strip()


def test_grammar_find_across_levels():
    lv, rule = grammar.find("a1-to-be")
    assert lv == "A1" and rule["id"] == "a1-to-be"
    assert grammar.find("nope") is None


def test_plan_is_sequential_and_linked():
    plan = lessons.plan("A1")
    assert len(plan) == 10
    assert [x["n"] for x in plan] == list(range(1, len(plan) + 1))
    slugs = {w["slug"] for w in cefr.prepared("A1")}
    for lesson in plan:
        assert lesson["rules"] and lesson["words"] and lesson["steps"]
        for rid in lesson["rules"]:
            assert grammar.find(rid), (lesson["id"], rid)
        for slug in lesson["words"]:
            assert slug in slugs, (lesson["id"], slug)


def test_unlock_order(tmp_path):
    p = _p(tmp_path)
    first, second, third = (lessons.plan("A1")[i] for i in range(3))
    assert lessons.unlocked(p, first)
    assert not lessons.unlocked(p, second)
    assert lessons.next_lesson(p)["id"] == first["id"]

    lessons.complete(p, first["id"])
    assert lessons.done(p, first["id"])
    assert lessons.unlocked(p, second)
    assert not lessons.unlocked(p, third)
    assert lessons.next_lesson(p)["id"] == second["id"]
    assert p.data["lessons"]["current"] == second["id"]
    assert lessons.summary(p)["done"] == 1


def test_complete_all(tmp_path):
    p = _p(tmp_path)
    for lesson in lessons.plan("A1"):
        lessons.complete(p, lesson["id"])
    assert lessons.summary(p)["done"] == 10
    assert lessons.next_lesson(p) is None
    assert p.data["lessons"]["current"] is None


def test_uncomplete_restores(tmp_path):
    p = _p(tmp_path)
    lessons.complete(p, "a1-01")
    lessons.uncomplete(p, "a1-01")
    assert not lessons.done(p, "a1-01")
    assert lessons.next_lesson(p)["id"] == "a1-01"
