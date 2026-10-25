"""Наборы CEFR: загрузка data/sets/cefr_*.json и слияние со словарём.

Одно слово — одна карточка. Если слово уже есть в частотном словаре, мы не
создаём дубль: добавляем метку набора, уровень и добираем примеры до пяти.
"""
from __future__ import annotations

import json

from . import paths

LEVELS = [
    ("A1", "A1 · ВЫЖИВАНИЕ", "easy"),
    ("A2", "A2 · БЫТ", "easy"),
    ("B1.1", "B1.1 · ПОРОГ", "medium"),
    ("B1.2", "B1.2 · ПОРОГ+", "medium"),
    ("B2.1", "B2.1 · СВОБОДНО", "medium"),
    ("B2.2", "B2.2 · СВОБОДНО+", "tricky"),
    ("C1", "C1 · ПРОДВИНУТЫЙ", "tricky"),
    ("C2", "C2 · МАСТЕРСТВО", "tricky"),
]
LEVEL_TITLE = {lv: title for lv, title, _d in LEVELS}
LEVEL_DIFF = {lv: diff for lv, _t, diff in LEVELS}
SET_ID = {lv: f"cefr-{lv.lower().replace('.', '-')}" for lv in LEVEL_TITLE}

MAX_SENTENCES = 5
MIN_SENTENCES = 5


def path(level: str):
    return paths.DATA_DIR / "sets" / f"cefr_{level.lower().replace('.', '_')}.json"


def available() -> list[str]:
    return [lv for lv in LEVEL_TITLE if path(lv).exists()]


def load(level: str) -> dict | None:
    try:
        return json.loads(path(level).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def entries(level: str) -> list[dict]:
    data = load(level) or {}
    return [w for w in (data.get("words") or []) if w.get("word")]


def _clean_sentences(raw: list) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for s in raw or []:
        en = (s.get("en") or "").strip() if isinstance(s, dict) else ""
        if not en or en.lower() in seen:
            continue
        seen.add(en.lower())
        out.append({"en": en, "ru": (s.get("ru") or "").strip(),
                    "source": (s.get("source") or "original"),
                    "license": (s.get("license") or "CC BY-SA 4.0")})
    return out


def prepared(level: str) -> list[dict]:
    """Записи словаря в формате Vocab, ещё до слияния."""
    data = load(level) or {}
    lv = data.get("level") or level
    sid = data.get("id") or SET_ID.get(level, "cefr-a1")
    src = data.get("source") or {"name": "original", "license": "CC BY-SA 4.0"}
    out: list[dict] = []
    for idx, raw in enumerate(entries(level)):
        sents = _clean_sentences(raw.get("sentences"))
        if len(sents) < MIN_SENTENCES:
            continue                      # без пяти примеров слово в набор не берём
        senses = raw.get("senses") or []
        definition = (senses[0].get("definition") if senses else "") or raw.get("definition", "")
        out.append({
            "word": raw["word"].strip(),
            "slug": (raw.get("slug") or raw["word"].strip().lower()),
            "pos": raw.get("pos") or "noun",
            "pos_all": raw.get("pos_all") or [raw.get("pos") or "noun"],
            "ru": raw.get("ru", ""),
            "ipa": raw.get("ipa", ""),
            "respelling": raw.get("respelling", ""),
            "definition": definition,
            "senses": senses,
            "sentences": sents,
            "sets": [sid],
            "level": lv,
            "cefr_level": lv,
            "cefr_order": idx,
            "difficulty": raw.get("difficulty") or LEVEL_DIFF.get(lv, "easy"),
            "source": src,
            "license": src.get("license", "CC BY-SA 4.0"),
            "rank": int(raw.get("rank") or 0),
        })
    return out


def merge_into(vocab, level: str) -> int:
    """Влить набор в словарь. Возвращает число слов, у которых стало больше примеров."""
    added_or_filled = 0
    for rec in prepared(level):
        cur = vocab.get(rec["slug"])
        if cur is None:
            rec["rank"] = rec["rank"] or vocab.next_rank()
            vocab.add_record(rec)
            added_or_filled += 1
            continue
        # слово уже есть: метка набора, уровень, примеры до пяти
        sets = cur.setdefault("sets", [])
        if rec["sets"][0] not in sets:
            sets.append(rec["sets"][0])
        cur.setdefault("cefr_order", rec.get("cefr_order", 9999))
        cur.setdefault("cefr_level", rec["cefr_level"])
        cur.setdefault("level", rec["level"])
        cur.setdefault("definition", rec["definition"])
        cur.setdefault("ipa", rec.get("ipa", ""))
        have = {s.get("en", "").lower() for s in (cur.get("sentences") or [])}
        sents = list(cur.get("sentences") or [])
        for s in rec["sentences"]:
            if len(sents) >= MAX_SENTENCES:
                break
            if s["en"].lower() not in have:
                sents.append(s)
                have.add(s["en"].lower())
        if sents != (cur.get("sentences") or []):
            cur["sentences"] = sents
            added_or_filled += 1
    return added_or_filled


def merge_available(vocab) -> list[str]:
    done = []
    for lv in available():
        merge_into(vocab, lv)
        done.append(lv)
    return done


def stats(level: str) -> tuple[int, int]:
    """(слов, предложений) в файле — без обращения к прогрессу."""
    words = entries(level)
    return len(words), sum(len(w.get("sentences") or []) for w in words)
