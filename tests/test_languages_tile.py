"""Плитка слова в «Иностранных языках»: данные карточки и смоук отрисовки.

Чистые функции проверяем без Tk, саму плитку — через настоящий Canvas и пропуск,
если дисплея нет (как в остальных GUI-тестах корабля).
"""
from __future__ import annotations

import pytest

from stamina.languages.core.base import WordEntry
from stamina.languages.ui import WordTile, gloss_text, head_text, level_text, pos_short


def word(**kw) -> WordEntry:
    base = dict(slug="der-baum", lemma="Baum", pos="noun", language="de",
                cefr_level="A1", frequency_rank=712)
    base.update(kw)
    return WordEntry(**base)


def test_head_without_morphology_is_lemma() -> None:
    assert head_text(word()) == "Baum"


def test_head_keeps_german_article() -> None:
    from stamina.languages.core.base import GermanMorphology, MorphologyBundle
    entry = word(morphology=MorphologyBundle(german=GermanMorphology(article_sg="der")))
    assert head_text(entry) == "der Baum"


def test_gloss_takes_first_three_translations() -> None:
    entry = word(translations={"ru": ["дерево", "древо", "лес", "лишнее"]})
    assert gloss_text(entry) == "дерево, древо, лес"


def test_gloss_empty_when_no_translation() -> None:
    assert gloss_text(word()) == ""


def test_pos_short_known_and_unknown() -> None:
    assert pos_short(word(pos="verb")) == "VERB"
    assert pos_short(word(pos="adjective")) == "ADJ"
    assert pos_short(word(pos="weird")) == "WEIRD"


def test_level_is_upper_case() -> None:
    assert level_text(word(cefr_level="b2")) == "B2"


def test_rank_zero_when_missing() -> None:
    entry = word(frequency_rank=0)
    assert int(getattr(entry, "frequency_rank", 0) or 0) == 0


def test_tile_draws_and_takes_focus() -> None:
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    try:
        root.withdraw()
        tile = WordTile(root, word(translations={"ru": ["дерево"]}),
                        is_known=lambda _slug: True, in_lists=lambda _slug: True)
        tile.pack()
        root.update_idletasks()
        tile.redraw()
        tile.set_focus(True)
        assert tile.focused is True
        assert tile.flipped is False
        tile.set_focus(False)
        assert tile.focused is False
        tile.destroy()
    finally:
        root.destroy()
