"""Склад карточек: выученные слова + все их примеры предложений.

Карточка на складе, если слово «знаю»/выучено и есть хотя бы один пример.
Прогон: слово + отмеченные предложения (≥ FLIP_OK), средняя ≥ PASS_QUALITY.
Нужно N качественных прогонов → автоматически в «Отработано» (без ручной кнопки).
"""
from __future__ import annotations

from stamina.i18n import t as _t

SENT_PASS = 60   # пример в СКАНЕРЕ (история; на складе не обязателен)
FLIP_OK = 80     # порог зачёта слова/предложения в одном прогоне
PASS_QUALITY = 85  # средняя точность прогона, чтобы он засчитался (★★ и выше)
MAX_DIFF = 3
PASS_CHOICES = (1, 2, 3, 5)
DEFAULT_PASSES = 2


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
    wh.setdefault("cleared", {})  # slug → {stars, avg, scores, day, passes}
    wh.setdefault("runs", {})  # slug → {goal, passes[], current{}}
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


def default_passes(progress) -> int:
    n = int(progress.settings.get("warehouse_passes", DEFAULT_PASSES) or DEFAULT_PASSES)
    return max(1, min(5, n))


def run_state(progress, slug: str) -> dict:
    """Прогресс многократных прогонов карточки (до попадания в «Отработано»)."""
    runs = ensure_stats(progress).setdefault("runs", {})
    st = runs.get(slug)
    if not isinstance(st, dict):
        st = {"goal": default_passes(progress), "passes": [], "current": {}}
        runs[slug] = st
    st.setdefault("goal", default_passes(progress))
    if not isinstance(st.get("passes"), list):
        st["passes"] = []
    if not isinstance(st.get("current"), dict):
        st["current"] = {}
    return st


def set_run_goal(progress, slug: str, n: int) -> int:
    st = run_state(progress, slug)
    st["goal"] = max(1, min(5, int(n)))
    progress.save()
    return st["goal"]


def passes_done(progress, slug: str) -> int:
    return len(run_state(progress, slug).get("passes") or [])


def passes_goal(progress, slug: str) -> int:
    return int(run_state(progress, slug).get("goal") or default_passes(progress))


def load_current_scores(progress, slug: str) -> dict[int, int]:
    """Баллы текущего (ещё не засчитанного) прогона."""
    out: dict[int, int] = {}
    for k, v in (run_state(progress, slug).get("current") or {}).items():
        try:
            out[int(k)] = int(v or 0)
        except (TypeError, ValueError):
            continue
    return out


def save_current_scores(progress, slug: str, scores: dict[int, int]) -> None:
    st = run_state(progress, slug)
    st["current"] = {str(k): int(v) for k, v in scores.items() if int(v or 0) > 0}
    progress.save()


def clear_run_progress(progress, slug: str) -> None:
    """Сбросить прогоны и текущие баллы (возврат из «Отработано» или новый цикл)."""
    wh = ensure_stats(progress)
    wh.get("runs", {}).pop(slug, None)
    best = wh.get("best") or {}
    for k in list(best.keys()):
        if k.startswith(f"{slug}:"):
            del best[k]
    progress.save()


def load_scores(progress, slug: str, n_sents: int) -> dict[int, int]:
    """Баллы текущего прогона; для отработанных — лучший сохранённый результат."""
    cur = load_current_scores(progress, slug)
    if cur:
        return cur
    rec = card_record(progress, slug)
    if rec:
        out: dict[int, int] = {}
        for k, v in (rec.get("scores") or {}).items():
            try:
                out[int(k)] = int(v or 0)
            except (TypeError, ValueError):
                continue
        return out
    return {}


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


def _move_to_cleared(progress, slug: str, stars: int, avg: float, score_map: dict,
                     passes: list) -> tuple[int, float, int, bool]:
    """Финальный перенос в «Отработано» после нужного числа качественных прогонов."""
    import datetime as dt

    wh = ensure_stats(progress)
    cleared = wh.setdefault("cleared", {})
    prev = cleared.get(slug) if isinstance(cleared.get(slug), dict) else None
    prev_stars = int((prev or {}).get("stars", 0) or 0)
    first = prev is None
    cleared[slug] = {
        "stars": max(prev_stars, stars),
        "avg": max(float((prev or {}).get("avg", 0) or 0), avg),
        "scores": score_map,
        "day": dt.date.today().isoformat(),
        "passes": len(passes),
    }
    away = wh.setdefault("away", [])
    if slug in away:
        away.remove(slug)
    wh.get("runs", {}).pop(slug, None)
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


def finish_pass(progress, slug: str, scores: dict[int, int], sel: list[bool]
                ) -> dict:
    """Завершить текущий прогон карточки.

    Возвращает dict:
      status: "incomplete" | "weak" | "pass" | "cleared"
      + avg, stars, done, goal, xp (по ситуации)
    """
    import datetime as dt

    if not is_run_complete(scores, sel):
        save_current_scores(progress, slug, scores)
        return {"status": "incomplete"}

    avg = run_average(scores, sel)
    stars = stars_for_avg(avg)
    score_map = {str(WORD_KEY): int(scores.get(WORD_KEY, 0) or 0)}
    for i, on in enumerate(sel):
        if on:
            score_map[str(i)] = int(scores.get(i, 0) or 0)

    st = run_state(progress, slug)
    # слабый прогон — не засчитываем, сбрасываем текущие баллы
    if avg < PASS_QUALITY:
        st["current"] = {}
        progress.save()
        return {"status": "weak", "avg": avg, "stars": stars,
                "done": len(st["passes"]), "goal": int(st["goal"])}

    st["passes"].append({
        "avg": avg, "stars": stars, "scores": score_map,
        "day": dt.date.today().isoformat(),
    })
    st["current"] = {}
    done = len(st["passes"])
    goal = int(st["goal"])
    xp = 0
    if progress.award_once(f"warehouse:pass:{slug}:{done}:{dt.date.today().isoformat()}", 2):
        xp = 2

    if done < goal:
        progress.save()
        return {"status": "pass", "avg": avg, "stars": stars,
                "done": done, "goal": goal, "xp": xp}

    # все прогоны набраны на хорошем уровне → автоматически в «Отработано»
    avgs = [float(p.get("avg") or 0) for p in st["passes"]]
    final_avg = round(sum(avgs) / len(avgs), 1) if avgs else avg
    final_stars = max(int(p.get("stars") or 0) for p in st["passes"])
    # берём scores последнего прогона
    last_scores = st["passes"][-1].get("scores") or score_map
    c_stars, c_avg, c_xp, improved = _move_to_cleared(
        progress, slug, final_stars, final_avg, last_scores, st["passes"])
    return {"status": "cleared", "avg": c_avg, "stars": c_stars,
            "done": done, "goal": goal, "xp": xp + c_xp, "improved": improved}


def complete_card(progress, slug: str, scores: dict[int, int], sel: list[bool]) -> tuple[int, float, int, bool]:
    """Совместимость: один прогон с goal=1, затем в «Отработано»."""
    st = run_state(progress, slug)
    st["goal"] = 1
    res = finish_pass(progress, slug, scores, sel)
    if res["status"] == "cleared":
        return int(res["stars"]), float(res["avg"]), int(res.get("xp") or 0), bool(res.get("improved"))
    return 0, 0.0, 0, False


def reopen_on_shelf(progress, slug: str) -> None:
    """Вернуть из «отработанного» снова на активный склад (сброс прохождения)."""
    wh = ensure_stats(progress)
    wh.get("cleared", {}).pop(slug, None)
    away = wh.setdefault("away", [])
    if slug in away:
        away.remove(slug)
    clear_run_progress(progress, slug)
    if not progress.is_known(slug) and not progress.is_learned(slug):
        progress.set_known(slug, True)
    else:
        progress.save()


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
