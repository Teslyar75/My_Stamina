# -*- coding: utf-8 -*-
"""Данные вкладки ГЛАГОЛЫ: 12 времён и корректные формы."""
from stamina.english import verbs


def test_tab_verbs_come_from_real_pack():
    pack = {v["lemma"] for v in verbs.irregular()}
    ents = verbs.entries()
    assert 10 <= len(ents) <= verbs.TAB_LIMIT
    for verb in ents:
        assert verb["slug"] in pack           # никаких выдуманных глаголов
        assert verb["ru"]                     # перевод из Wiktionary


def test_every_verb_has_twelve_unique_tenses():
    keys = [t[0] for t in verbs.tenses()]
    assert len(keys) == 12
    for verb in verbs.entries():
        sents = verbs.sentences(verb)
        assert [s["key"] for s in sents] == keys
        assert all(s["en"] for s in sents)  # let/put/cut: Present и Past Simple совпадают — это норма


def test_examples_are_real_tatoeba():
    for verb in verbs.entries():
        for sent in verbs.sentences(verb):
            ex = sent["example"]
            if ex:
                assert ex["source"] == "tatoeba" and ex["source_id"]
                assert str(ex["source_id"]) in sent["ru"]
            else:
                assert sent["ru"] == ""


def test_irregular_forms_are_used():
    sents = {s["key"]: s["en"] for s in verbs.sentences(verbs.find("write"))}
    assert "written" in sents["present_perfect"]
    assert "wrote" in sents["past_simple"]
    assert "writing" in sents["present_continuous"]
    sents = {s["key"]: s["en"] for s in verbs.sentences(verbs.find("speak"))}
    assert "spoke" in sents["past_simple"] and "spoken" in sents["present_perfect"]


# --- паки из настоящих данных (data/verbs/*.json) ---------------------------
import pytest

from stamina.english.progress import Progress


def test_irregular_pack_meets_acceptance():
    pack = verbs.irregular()
    assert len(pack) >= 190
    full = 0
    for v in pack:
        assert v["lemma"] and v["v2"] and v["v3"], v["lemma"]
        assert v["source"] and v["license"], v["lemma"]
        for ex in v["examples"]:
            assert ex["source"] == "tatoeba" and isinstance(ex["source_id"], int) and ex["license"]
            assert ex["en"] and ex["ru"]
        if len(v["examples"]) >= 5:
            full += 1
        else:
            assert v["status"] == "incomplete", v["lemma"]
    assert full / len(pack) >= 0.9


def test_classic_forms_are_right():
    want = {"be": ("was/were", "been"), "go": ("went", "gone"), "do": ("did", "done"),
            "have": ("had", "had"), "lead": ("led", "led"), "stick": ("stuck", "stuck"),
            "write": ("wrote", "written"), "put": ("put", "put")}
    for lemma, (v2, v3) in want.items():
        v = verbs.pack_verb(lemma)
        assert v is not None, lemma
        assert (v["v2"], v["v3"]) == (v2, v3), lemma


def test_frequent_pack_has_1000_with_sources():
    pack = verbs.frequent()
    assert len(pack) == 1000
    assert len({v["lemma"] for v in pack}) == 1000
    assert all(v["source"] and v["license"] for v in pack)
    meta = verbs.load_pack("frequent_1000")
    assert meta["sources"] and meta["tatoeba_api_requests"] == 0


def test_search_from_first_letter():
    res = verbs.search("w")
    assert res and all(v["lemma"].startswith("w") or any(f.startswith("w") for f in
                                                          (v["v2"] + "/" + v["v3"]).split("/"))
                       for v in res[:10])
    assert verbs.search("went")[0]["lemma"] == "go"


def test_unlock_on_fake_progress(tmp_path):
    prog = Progress(tmp_path / "english.json")
    pack = verbs.frequent()
    assert verbs.unlocked_count(prog) == verbs.UNLOCK_START
    first = pack[verbs.UNLOCK_START]["lemma"]
    if first not in {v["lemma"] for v in verbs.irregular()}:
        assert verbs.is_locked(prog, first)
    left, step = verbs.unlock_hint(prog)
    assert left == verbs.UNLOCK_NEED and step == verbs.UNLOCK_STEP
    # освоили почти достаточно — ещё закрыто
    for v in pack[:verbs.UNLOCK_NEED - 1]:
        prog.data["words"].setdefault(v["lemma"], {})["known"] = True
    assert verbs.unlocked_count(prog) == verbs.UNLOCK_START
    # ровно порог — открылся следующий шаг
    prog.data["words"].setdefault(pack[verbs.UNLOCK_NEED - 1]["lemma"], {})["known"] = True
    assert verbs.unlocked_count(prog) == verbs.UNLOCK_START + verbs.UNLOCK_STEP
    # карточка SM-2 с интервалом ≥ 21 тоже считается освоенной
    for v in pack[verbs.UNLOCK_NEED:2 * verbs.UNLOCK_NEED]:
        prog.data["cards"][v["lemma"]] = {"interval": 30, "due": "2099-01-01", "reps": 3}
    assert verbs.unlocked_count(prog) == verbs.UNLOCK_START + 2 * verbs.UNLOCK_STEP
    # порог из настроек
    prog.settings["verbs_unlock_need"] = 1000
    assert verbs.unlocked_count(prog) == verbs.UNLOCK_START


def test_add_to_card_reaches_warehouse(tmp_path):
    from stamina.english import warehouse
    class FakeVocab:  # словарь с одним словом, без загрузки с диска
        def get(self, slug):
            return {"slug": slug, "word": slug} if slug == "go" else None

        def sentences(self, *a, **k):
            return []

    prog = Progress(tmp_path / "english.json")
    vocab = FakeVocab()
    go = verbs.pack_verb("go")
    ok = verbs.add_to_card(prog, vocab, go, "past_simple", "he", "question", "Did he go?")
    saved = prog.data["verb_forms"]["go"]
    assert saved[0]["text"] == "Did he go?" and saved[0]["tense"] == "past_simple"
    assert prog.is_known("go")
    assert isinstance(ok, bool)
    # слова нет в словаре — сохраняем форму, но не трогаем «знаю»
    verbs.add_to_card(prog, vocab, verbs.pack_verb("write"), "past_simple", "I", "affirmative", "I wrote")
    assert not prog.is_known("write") and prog.data["verb_forms"]["write"]


def test_example_for_tense_uses_matching_form():
    go = verbs.pack_verb("go")
    assert verbs.example_for(go, "past_simple")["form"] == "went"
    assert verbs.example_for(go, "present_perfect")["form"] == "gone"
