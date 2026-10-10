"""Склад карточек: слова, которые уже выучены и у которых пройдены предложения в СКАНЕРЕ.

Карточка попадает на склад, если:
  • слово «знаю» или выучено (SM-2 interval ≥ 21);
  • у каждого примера в speech_best есть балл ≥ SENT_PASS (если примеров нет — условие пустое).

Сложность карточки = число примеров (1…3). Перебор на вкладке: RU → микрофон ≥ FLIP_OK → EN + TTS.
"""
from __future__ import annotations

from stamina.i18n import t as _t

SENT_PASS = 60   # предложение в КАНАЛЕ СВЯЗИ засчитано
FLIP_OK = 80     # порог переворота карточки на складе
MAX_DIFF = 3


def _n_sents(vocab, word: dict) -> int:
    return min(MAX_DIFF, len(vocab.sentences(word)))


def sentences_passed(progress, slug: str, n: int) -> bool:
    """Все примеры слова закрыты в СКАНЕРЕ (или примеров нет)."""
    if n <= 0:
        return True
    best = progress.data.get("speech_best") or {}
    return all(int(best.get(f"{slug}:{i}", 0) or 0) >= SENT_PASS for i in range(n))


def is_ready(progress, vocab, slug: str) -> bool:
    """Слово готово к складу: выучено/знаю + предложения пройдены."""
    if not (progress.is_known(slug) or progress.is_learned(slug)):
        return False
    w = vocab.get(slug)
    if not w:
        return False
    return sentences_passed(progress, slug, _n_sents(vocab, w))


def make_card(progress, vocab, word: dict) -> dict:
    slug = word["slug"]
    n = _n_sents(vocab, word)
    ru = progress.tr(slug) or word.get("ru") or word.get("definition") or ""
    return {
        "slug": slug,
        "word": word["word"],
        "ru": ru,
        "ipa": word.get("ipa") or "",
        "respelling": word.get("respelling") or "",
        "difficulty": max(1, n) if n else 1,
        "sentences_n": n,
        "rank": word.get("rank", 0),
        "pos": word.get("pos") or "",
    }


def candidate_slugs(progress) -> set[str]:
    """Слова-кандидаты: отмечены «знаю» или выучены по SM-2."""
    slugs = {s for s, w in progress.data.get("words", {}).items() if w.get("known")}
    for s, c in progress.data.get("cards", {}).items():
        if c.get("interval", 0) >= 21:
            slugs.add(s)
    return slugs


def collect_cards(progress, vocab, *, difficulty: int | None = None) -> list[dict]:
    """Собрать все карточки склада; опционально отфильтровать по сложности 1…3."""
    out: list[dict] = []
    for slug in candidate_slugs(progress):
        w = vocab.get(slug)
        if not w or not is_ready(progress, vocab, slug):
            continue
        card = make_card(progress, vocab, w)
        if difficulty is not None and card["difficulty"] != difficulty:
            continue
        out.append(card)
    out.sort(key=lambda c: (c["difficulty"], c["rank"], c["word"].lower()))
    return out


def count_cards(progress, vocab) -> int:
    return sum(1 for slug in candidate_slugs(progress)
               if (w := vocab.get(slug)) and sentences_passed(progress, slug, _n_sents(vocab, w)))


def ensure_stats(progress) -> dict:
    wh = progress.data.setdefault("warehouse", {})
    wh.setdefault("flips", 0)
    wh.setdefault("ok", 0)
    wh.setdefault("by_day", {})
    wh.setdefault("best", {})
    return wh


def record_flip(progress, slug: str, score: int, *, ok: bool) -> int:
    """Записать попытку на складе. Возвращает начисленные XP (0 если повтор в тот же день при ok)."""
    import datetime as dt

    wh = ensure_stats(progress)
    wh["flips"] += 1
    prev = int(wh["best"].get(slug, 0) or 0)
    wh["best"][slug] = max(prev, score)
    xp = 0
    if ok:
        wh["ok"] += 1
        day = dt.date.today().isoformat()
        wh["by_day"][day] = wh["by_day"].get(day, 0) + 1
        # XP: сложность учтёт вызывающий; базово 3, award_once на день+slug
        if progress.award_once(f"warehouse:{slug}:{day}", 3):
            xp = 3
    progress.record_attempt(slug, "warehouse", "flip", ok, 5 if score >= 85 else 4 if ok else 2, score)
    progress.save()
    return xp


DIFF_LABEL = {
    1: _t("★ · 1 пример"),
    2: _t("★★ · 2 примера"),
    3: _t("★★★ · 3 примера"),
}


def difficulty_text(n: int) -> str:
    return DIFF_LABEL.get(max(1, min(MAX_DIFF, n)), DIFF_LABEL[1])
