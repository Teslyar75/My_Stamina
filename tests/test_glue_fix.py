"""Склейки слов: корень (фильтры не сращивают слова) и кнопка «Проверить ИИ»."""
from pathlib import Path

import pytest

from stamina import glue_fix
from stamina.text_processing import process_text, remove_punctuation
from stamina.zen_engine import prepare_words

DATA = Path(__file__).parent / "data"


def words(t):
    return t.split()


@pytest.mark.parametrize("src,expect", [
    ("of vague distaste--this was", "of vague distaste this was"),
    ("the Ministry of Truth---Ministry, in Newspeak", "the ministry of truth ministry in newspeak"),
    ("live--did live", "live did live"),
    ("nine-\nteenth century", "nineteenth century"),
    ("about forty-\nfive", "about forty-five"),
    ("сло-\nво за словом", "слово за словом"),
    ("он сказал—и ушёл", "он сказал и ушёл"),
    ("конец строки.\nНачало", "конец строки начало"),
    ("end.\r\nStart", "end start"),
    ("end,\tStart", "end start"),
])
def test_filters_never_glue(src, expect):
    assert process_text(src, glue=False) == expect
    assert process_text(src, glue=True) == expect


def test_line_ends_after_punctuation_keep_space():
    src = "It was cold.\nWinston ran;\nhe stopped!\n«Да,» — сказал он.\nПотом"
    out = process_text(src)
    assert out == "it was cold winston ran he stopped да сказал он потом"


@pytest.mark.parametrize("glued,split", [
    ("nineteenthcentury", "nineteenth century"),
    ("distastethis", "distaste this"),
    ("1984was", "1984 was"),
    ("appendixwas", "appendix was"),
    ("presumablysince", "presumably since"),
    ("ивот", "и вот"),
    ("непонял", "не понял"),
])
def test_lexicon_splits(glued, split):
    text = f"the text {glued} goes on" if glued.isascii() else f"тут {glued} дальше"
    assert split in glue_fix.repair(text)[0]


@pytest.mark.parametrize("word", ["telescreen telescreen telescreen", "pillowed", "sleepiest", "nothing", "another",
                                  "meagreness", "1984", "4th", "forty-five", "don't",
                                  "погода", "подруга", "узнал", "человечество"])
def test_real_words_untouched(word):
    text = f"x {word} y" if " " not in word else word
    assert glue_fix.repair(text)[0] == text


def test_book_words_trusted():
    text = "doublethink is doublethink and doublethink again"
    assert glue_fix.repair(text)[1] == []


def test_orwell_pipeline_has_no_glue():
    src = (DATA / "orwell_1984_ch1.txt").read_text(encoding="utf-8")
    out = process_text(src, glue=True)
    assert "distastethis" not in out and "fortyfive" not in out
    old = process_text(src.replace("-", ""), glue=False)  # как резал старый фильтр
    assert "fortyfive" in old
    fixed, fixes = glue_fix.repair(old)
    assert "forty five" in fixed
    assert len(fixes) >= 3


def test_russian_and_other_sample():
    ru = ("Он посмотрел в окно.\nДождь шёл—не переставая.\nИвот наконец-то\nпришло утро; "
          "все спали…\nА потом—тишина.")
    out = process_text(ru, glue=True)
    assert out == "он посмотрел в окно дождь шёл не переставая и вот наконец-то пришло утро все спали а потом тишина"
    en = "Call me Ishmael.\nSome years ago--never mind how long precisely--having little money"
    assert process_text(en, glue=True) == ("call me ishmael some years ago never mind how long precisely "
                                "having little money")


def test_zen_prepare_words_no_glue():
    assert prepare_words("hello—world it's distaste--this") == ["hello", "world", "it's", "distaste", "this"]


def test_remap_index():
    text = "aa distastethis bb"
    new, fixes = glue_fix.repair(text)
    assert new == "aa distaste this bb"
    i = text.index("bb")
    assert new[glue_fix.remap_index(text, fixes, i):].startswith("bb")


def test_fix_stored(tmp_path, monkeypatch):
    from stamina import session_storage
    from stamina.session_storage import SessionState, load_session, save_session
    monkeypatch.setattr(session_storage, "SESSION_PATH", tmp_path / "session.json")

    class S:
        cargo = ("one nineteenthcentury house and distastethis end", "")

        def load_cargo(self):
            return self.cargo

        def save_cargo(self, a, o):
            self.cargo = (a, o)

    st = S()
    base = st.cargo[0]
    save_session(SessionState(text=base, index=base.index("end")))
    rep = glue_fix.fix_stored(st)
    assert rep.count == 2
    assert st.cargo[0] == "one nineteenth century house and distaste this end"
    s = load_session()
    assert s.text == st.cargo[0] and s.text[s.index:] == "end"
    assert glue_fix.fix_stored(st).count == 0


# --- ложные разрезы: настоящие слова и авторские сложные слова не трогаем ---
import pytest as _pt
from stamina import glue_fix as _g


@_pt.mark.parametrize("word", ["dogeared", "execrate", "matchwood", "concertinalike", "goodwise",
                               "speedwise", "overfulfilment", "underheated", "malreported"])
def test_false_split_guard(word):
    assert _g.find(f"he said {word} and left") == []


def test_no_one_letter_fragments():
    sp = _g.find("a selfabasement x")
    assert all(" a " not in f" {f.split} " for f in sp)
    assert _g.segment("dogeared", "en") != ["do", "geared"]


def test_newspeak_family_and_productive_prefix():
    text = ("goodthink goodthinkful goodthinker minitrue minipax miniluv miniplenty "
            "the party said goodthink is good")
    assert not any(f.token.startswith("mini") or f.token.startswith("goodthink") for f in _g.find(text))


def test_repeated_glue_split_when_spaced_form_present():
    text = "the nineteenthcentury " * 4 + "in the nineteenth century"
    assert _g.find(text) and all(f.split == "nineteenth century" for f in _g.find(text))
