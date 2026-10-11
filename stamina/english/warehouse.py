"""Склад карточек: выученные слова + все их примеры предложений.

Карточка на складе, если слово «знаю»/выучено и есть хотя бы один пример.
На вкладке: список предложений с чекбоксами (сложность = сколько отмечено),
проверка микрофоном каждого отмеченного (≥ FLIP_OK), кнопка «ПОДСКАЗКА» озвучивает перевод.
"""
from __future__ import annotations

from stamina.i18n import t as _t

SENT_PASS = 60   # пример в СКАНЕРЕ (история; на складе не обязателен)
FLIP_OK = 80     # порог зачёта предложения на складе
MAX_DIFF = 3


def card_sentences(vocab, word: dict) -> list[dict]:
    """Примеры слова для склада (до MAX_DIFF), только с английским текстом."""
    out = []
    for s in vocab.sentences(word)[:MAX_DIFF]:
        en = (s.get("en") or "").strip()
        if not en:
            continue
        out.append({"en": en, "ru": (s.get("ru") or "").strip()})
    return out


def is_away(progress, slug: str) -> bool:
    """Слово снято со склада «вернуть в работу»."""
    return slug in (ensure_stats(progress).get("away") or [])


def is_done(progress, slug: str) -> bool:
    """Карточка в отсеке «отработанный материал»."""
    return card_record(progress, slug) is not None


def is_ready(progress, vocab, slug: str) -> bool:
    """На активном складе: выучено, есть примеры, не «в работе» и не отработано."""
    if is_away(progress, slug) or is_done(progress, slug):
        return False
    if not (progress.is_known(slug) or progress.is_learned(slug)):
        return False
    w = vocab.get(slug)
    return bool(w and card_sentences(vocab, w))


def make_card(progress, vocab, word: dict) -> dict:
    slug = word["slug"]
    sents = card_sentences(vocab, word)
    ru = progress.tr(slug) or word.get("ru") or word.get("definition") or ""
    done = card_record(progress, slug)
    return {
        "slug": slug,
        "word": word["word"],
        "ru": ru,
        "ipa": word.get("ipa") or "",
        "respelling": word.get("respelling") or "",
        "sentences": sents,
        "difficulty": max(1, len(sents)),
        "rank": word.get("rank", 0),
        "pos": word.get("pos") or "",
        "stars": int((done or {}).get("stars", 0) or 0),
        "avg": float((done or {}).get("avg", 0) or 0),
        "passed": bool(done),
    }


def candidate_slugs(progress) -> set[str]:
    slugs = {s for s, w in progress.data.get("words", {}).items() if w.get("known")}
    for s, c in progress.data.get("cards", {}).items():
        if c.get("interval", 0) >= 21:
            slugs.add(s)
    return slugs


def collect_cards(progress, vocab, *, difficulty: int | None = None) -> list[dict]:
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


def collect_away(progress, vocab) -> list[dict]:
    """Карточки, снятые со склада для дальнейшей работы."""
    out: list[dict] = []
    for slug in list(ensure_stats(progress).get("away") or []):
        if is_done(progress, slug):
            continue
        w = vocab.get(slug)
        if not w or not card_sentences(vocab, w):
            continue
        out.append(make_card(progress, vocab, w))
    out.sort(key=lambda c: (c["rank"], c["word"].lower()))
    return out


def collect_done(progress, vocab) -> list[dict]:
    """Отсек «отработанный материал»: пройденные карточки со звёздами."""
    out: list[dict] = []
    for slug in list((ensure_stats(progress).get("cleared") or {}).keys()):
        w = vocab.get(slug)
        if not w or not card_sentences(vocab, w):
            continue
        out.append(make_card(progress, vocab, w))
    out.sort(key=lambda c: (-c.get("stars", 0), -c.get("avg", 0), c["rank"]))
    return out


def count_cards(progress, vocab) -> int:
    return sum(1 for slug in candidate_slugs(progress) if is_ready(progress, vocab, slug))


def count_done(progress, vocab) -> int:
    return len(collect_done(progress, vocab))


def ensure_stats(progress) -> dict:
    wh = progress.data.setdefault("warehouse", {})
    wh.setdefault("flips", 0)
    wh.setdefault("ok", 0)
    wh.setdefault("by_day", {})
    wh.setdefault("best", {})
    wh.setdefault("sel", {})  # slug → [bool, …] отмеченные предложения
    wh.setdefault("away", [])  # сняты со склада → снова в работу
    wh.setdefault("cleared", {})  # slug → {stars, avg, scores, day}
    return wh


WORD_KEY = -1  # ключ проверки основного слова в scores / best


def card_record(progress, slug: str) -> dict | None:
    rec = ensure_stats(progress).get("cleared", {}).get(slug)
    return rec if isinstance(rec, dict) else None


def stars_for_avg(avg: float) -> int:
    """Как в миссиях: ★ ≥60%, ★★ ≥80%, ★★★ ≥95%."""
    if avg >= 95:
        return 3
    if avg >= 80:
        return 2
    if avg >= 60:
        return 1
    return 0


def stars_glyph(n: int) -> str:
    n = max(0, min(3, int(n)))
    return "★" * n + "☆" * (3 - n)


def load_scores(progress, slug: str, n_sents: int) -> dict[int, int]:
    """Лучшие баллы слова и предложений (из best + cleared)."""
    wh = ensure_stats(progress)
    best = wh.get("best") or {}
    out: dict[int, int] = {}
    for i in [WORD_KEY, *range(n_sents)]:
        v = int(best.get(f"{slug}:{i}", 0) or 0)
        if v:
            out[i] = v
    rec = card_record(progress, slug)
    if rec:
        for k, v in (rec.get("scores") or {}).items():
            try:
                ki = int(k)
            except (TypeError, ValueError):
                continue
            out[ki] = max(out.get(ki, 0), int(v or 0))
    return out


def is_run_complete(scores: dict[int, int], sel: list[bool]) -> bool:
    """Слово + все отмеченные предложения ≥ FLIP_OK."""
    if int(scores.get(WORD_KEY, 0) or 0) < FLIP_OK:
        return False
    if not any(sel):
        return False
    return all(int(scores.get(i, 0) or 0) >= FLIP_OK for i, on in enumerate(sel) if on)


def run_average(scores: dict[int, int], sel: list[bool]) -> float:
    parts = [int(scores.get(WORD_KEY, 0) or 0)]
    parts += [int(scores.get(i, 0) or 0) for i, on in enumerate(sel) if on]
    return round(sum(parts) / len(parts), 1) if parts else 0.0


def complete_card(progress, slug: str, scores: dict[int, int], sel: list[bool]) -> tuple[int, float, int, bool]:
    """Засчитать прохождение. Возвращает (stars, avg, xp, improved)."""
    import datetime as dt

    if not is_run_complete(scores, sel):
        return 0, 0.0, 0, False
    avg = run_average(scores, sel)
    stars = stars_for_avg(avg)
    wh = ensure_stats(progress)
    cleared = wh.setdefault("cleared", {})
    prev = cleared.get(slug) if isinstance(cleared.get(slug), dict) else None
    prev_stars = int((prev or {}).get("stars", 0) or 0)
    score_map = {str(WORD_KEY): int(scores.get(WORD_KEY, 0) or 0)}
    for i, on in enumerate(sel):
        if on:
            score_map[str(i)] = int(scores.get(i, 0) or 0)
    first = prev is None
    cleared[slug] = {
        "stars": max(prev_stars, stars),
        "avg": max(float((prev or {}).get("avg", 0) or 0), avg),
        "scores": score_map,
        "day": dt.date.today().isoformat(),
    }
    # с активного склада / «в работе» → отсек «отработанный материал»
    away = wh.setdefault("away", [])
    if slug in away:
        away.remove(slug)
    xp = 0
    improved = stars > prev_stars
    if improved:
        gain = 5 * (stars - prev_stars)
        if progress.award_once(f"warehouse:clear:{slug}:{stars}", gain):
            xp = gain
        elif first and progress.award_once(f"warehouse:clear:{slug}", 5 * stars):
            xp = 5 * stars
    progress.save()
    return cleared[slug]["stars"], cleared[slug]["avg"], xp, improved or first


def reopen_on_shelf(progress, slug: str) -> None:
    """Вернуть из «отработанного» снова на активный склад (сброс прохождения)."""
    wh = ensure_stats(progress)
    wh.get("cleared", {}).pop(slug, None)
    away = wh.setdefault("away", [])
    if slug in away:
        away.remove(slug)
    if not progress.is_known(slug) and not progress.is_learned(slug):
        progress.set_known(slug, True)
    else:
        progress.save()


def archive_to_done(progress, vocab, slug: str, scores: dict[int, int] | None = None
                    ) -> tuple[int, float, int]:
    """Вручную отправить карточку в «Отработано».

    Звёзды — по лучшим баллам слова и всех примеров (если баллов нет — ★★ по умолчанию).
    Возвращает (stars, avg, xp).
    """
    import datetime as dt

    w = vocab.get(slug)
    if not w:
        return 0, 0.0, 0
    n = len(card_sentences(vocab, w))
    scores = dict(scores or load_scores(progress, slug, n))
    sel = [True] * n if n else []
    # если прогон полностью закрыт по правилам — обычное complete
    if n and is_run_complete(scores, sel):
        return complete_card(progress, slug, scores, sel)[:3]

    parts = [int(scores.get(i, 0) or 0) for i in [WORD_KEY, *range(n)] if int(scores.get(i, 0) or 0) > 0]
    if parts:
        avg = round(sum(parts) / len(parts), 1)
        stars = max(1, stars_for_avg(avg))
    else:
        avg = 80.0
        stars = 2  # ручной перенос «хорошо проработанной» без замеров
    wh = ensure_stats(progress)
    cleared = wh.setdefault("cleared", {})
    prev = cleared.get(slug) if isinstance(cleared.get(slug), dict) else None
    prev_stars = int((prev or {}).get("stars", 0) or 0)
    score_map = {str(i): int(scores.get(i, 0) or 0) for i in [WORD_KEY, *range(n)]
                 if int(scores.get(i, 0) or 0) > 0}
    cleared[slug] = {
        "stars": max(prev_stars, stars),
        "avg": max(float((prev or {}).get("avg", 0) or 0), avg),
        "scores": score_map,
        "day": dt.date.today().isoformat(),
        "manual": True,
    }
    away = wh.setdefault("away", [])
    if slug in away:
        away.remove(slug)
    xp = 0
    final_stars = cleared[slug]["stars"]
    if final_stars > prev_stars:
        gain = 5 * (final_stars - prev_stars)
        if progress.award_once(f"warehouse:archive:{slug}:{final_stars}", gain):
            xp = gain
    progress.save()
    return final_stars, cleared[slug]["avg"], xp


def return_to_work(progress, slug: str) -> None:
    """Убрать со склада: снова «не знаю», карточка к проверке сегодня."""
    import datetime as dt

    wh = ensure_stats(progress)
    away = wh.setdefault("away", [])
    if slug not in away:
        away.append(slug)
    if progress.is_known(slug):
        progress.set_known(slug, False)
    c = progress.add_card(slug)
    c["due"] = dt.date.today().isoformat()
    # чтобы слово точно попало в очередь проверки
    if c.get("reps", 0) == 0:
        c["reps"] = 1
    progress.save()


def back_to_warehouse(progress, slug: str) -> None:
    """Вернуть слово на склад (из списка «в работе»)."""
    wh = ensure_stats(progress)
    away = wh.setdefault("away", [])
    if slug in away:
        away.remove(slug)
    progress.set_known(slug, True)
    progress.save()


def selection(progress, slug: str, n: int) -> list[bool]:
    """Какие предложения отмечены для прохождения (по умолчанию все)."""
    wh = ensure_stats(progress)
    raw = wh["sel"].get(slug)
    if not isinstance(raw, list) or len(raw) != n:
        sel = [True] * n
        wh["sel"][slug] = sel
        progress.save()
        return list(sel)
    return [bool(x) for x in raw]


def set_selection(progress, slug: str, sel: list[bool]) -> None:
    wh = ensure_stats(progress)
    if not sel or not any(sel):
        sel = [True] + [False] * (len(sel) - 1)  # хотя бы одно
    wh["sel"][slug] = list(sel)
    progress.save()


def record_sentence(progress, slug: str, si: int, score: int, *, ok: bool) -> int:
    """Попытка по предложению. XP раз в день на slug+индекс при успехе."""
    import datetime as dt

    wh = ensure_stats(progress)
    wh["flips"] += 1
    key = f"{slug}:{si}"
    prev = int(wh["best"].get(key, 0) or 0)
    wh["best"][key] = max(prev, score)
    xp = 0
    if ok:
        wh["ok"] += 1
        day = dt.date.today().isoformat()
        wh["by_day"][day] = wh["by_day"].get(day, 0) + 1
        if progress.award_once(f"warehouse:{key}:{day}", 3):
            xp = 3
    progress.record_attempt(slug, "warehouse", f"sent:{si}", ok,
                            5 if score >= 85 else 4 if ok else 2, score)
    progress.save()
    return xp


DIFF_LABEL = {
    1: _t("★ · 1 предложение"),
    2: _t("★★ · 2 предложения"),
    3: _t("★★★ · 3 предложения"),
}


def difficulty_text(n: int) -> str:
    return DIFF_LABEL.get(max(1, min(MAX_DIFF, n)), DIFF_LABEL[1])
