"""Качественное чтение вслух для языкового отсека.

Английский склад считает «качественные повторения» слотами (stamina.english.quality).
Здесь тот же механизм для карточки языка: слово и его фразы Tatoeba. Фраза
читается целиком, слот группы B загорается по баллу не ниже порога. Ничего
своего не изобретаем — пороги и дневной предел общие с английским.
"""
from __future__ import annotations

from datetime import date

from stamina.english import quality
from stamina.english.textutil import score_sentence
from stamina.languages.core.sqlite_vocab import PORTION, portion_slugs

PASS = 80          # тот же порог, что FLIP_OK на английском складе
PAUSE_MS = 900     # пауза после зачёта, чтобы пилот услышал себя и выдохнул


def sentences(word) -> list:
    """Фразы карточки: только непустые, в порядке словаря."""
    return [ex for ex in (getattr(word, "examples", None) or []) if (ex.text or "").strip()]


def has_sentences(vocab, slug: str) -> bool:
    word = vocab.get_word(slug)
    return bool(word and sentences(word))


def known_slugs(progress) -> list[str]:
    """Слова «знаю» и выученные — с них начинается отработка чтения."""
    out = {slug for slug, item in progress.data.get("words", {}).items() if item.get("known")}
    for slug, card in progress.data.get("cards", {}).items():
        if int(card.get("interval", 0) or 0) >= 21:
            out.add(slug)
    return sorted(out)


def _level_set(plugin, level: str):
    tail = level.casefold()
    return next((freq for freq in plugin.freq_sets if freq.id.endswith(tail)), None)


def card_slugs(progress, vocab, plugin, *, limit: int = 60) -> list[str]:
    """Очередь карточек: знакомые слова с фразами, затем первая порция A1.

    Слова без фраз в чтение не попадают: читать нечего.
    """
    known = [slug for slug in known_slugs(progress) if has_sentences(vocab, slug)]
    rank = lambda slug: (vocab.get_word(slug).frequency_rank or 10 ** 9)  # noqa: E731
    known.sort(key=rank)
    fresh: list[str] = []
    freq = _level_set(plugin, "A1")
    if freq is not None:
        for slug in portion_slugs(vocab, freq.id, 0, min(freq.size, PORTION)):
            if slug not in known and has_sentences(vocab, slug):
                fresh.append(slug)
    return (known + fresh)[:limit]


def queue(progress, slugs: list[str]) -> list[str]:
    """Сначала незакрытые карточки, с которыми уже работали, потом остальные."""
    started = quality.due_today(progress, slugs)
    seen = set(started)
    return started + [slug for slug in slugs if slug not in seen]


def counts(progress, slug: str, n_sents: int) -> dict:
    return quality.counts(progress, slug, n_sents=n_sents)


def hint(progress, slug: str, n_sents: int) -> str:
    return quality.hint(progress, slug, n_sents=n_sents)


def is_complete(progress, slug: str, n_sents: int) -> bool:
    return quality.is_complete(progress, slug, n_sents=n_sents)


def score_passage(word, passage, alts, strictness: str = "normal"):
    """Балл чтения фразы. Возвращает (score, marks, heard)."""
    target = (passage.text or "").strip()
    ranked = [
        (score_sentence(target, alt, word.lemma, strictness=strictness), alt)
        for alt in (alts or [])
    ]
    if not ranked:
        return 0, None, ""
    (score, marks), heard = max(ranked, key=lambda item: item[0][0])
    return int(score), marks, heard


def record(progress, slug: str, score: int, si: int, n_sents: int, *, self_rated: bool = False) -> tuple[str, str | None]:
    """Засчитать слот чтения. Возвращает (результат quality.auto, ключ слота)."""
    res, key = quality.auto(progress, slug, "B", score, si=si, self_rated=self_rated, n_sents=n_sents)
    if res == "ok":
        xp = 5 if score >= 85 else 3
        progress.award_once(f"reading:{slug}:{key}:{date.today().isoformat()}", xp)
        progress.record_attempt(slug, True, "reading", 0, 5 if score >= 85 else 4)
    elif res == "low":
        progress.record_attempt(slug, False, "reading", 0, 3)
    return res, key
