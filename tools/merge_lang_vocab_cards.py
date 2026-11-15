#!/usr/bin/env python
"""Слияние карточек языков: одна лемма — одна карточка, примеры не теряются.

Обрабатывает:
  stamina/languages/plugins/{de,es,fr,it}/vocab_*.json
  data/vocab_sources/kaikki/vocab.sqlite (опционально, --sqlite)

Запуск из корня:
  python tools/merge_lang_vocab_cards.py --dry-run
  python tools/merge_lang_vocab_cards.py --write
  python tools/merge_lang_vocab_cards.py --write --sqlite
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "stamina" / "languages" / "plugins"
SQLITE = ROOT / "data" / "vocab_sources" / "kaikki" / "vocab.sqlite"
LEVELS = ("a1", "a2", "b1", "b2", "c1", "c2")

BAND_BY_LANG_LEVEL = {
    "de": {"a1": "goethe-a1", "a2": "goethe-a2", "b1": "goethe-b1", "b2": "goethe-b2", "c1": "goethe-c1", "c2": "goethe-c2"},
    "es": {"a1": "cervantes-a1", "a2": "cervantes-a2", "b1": "cervantes-b1", "b2": "cervantes-b2", "c1": "cervantes-c1", "c2": "cervantes-c2"},
    "fr": {"a1": "delf-a1", "a2": "delf-a2", "b1": "delf-b1", "b2": "delf-b2", "c1": "delf-c1", "c2": "delf-c2"},
    "it": {"a1": "celi-a1", "a2": "celi-a2", "b1": "celi-b1", "b2": "celi-b2", "c1": "celi-c1", "c2": "celi-c2"},
}

POS_RANK = {
    "noun": 0, "verb": 1, "adj": 2, "adv": 3, "pron": 4, "det": 5, "prep": 6, "conj": 7,
    "intj": 8, "name": 9, "phrase": 10, "symbol": 11, "character": 12, "article": 13, "num": 14, "unknown": 99,
}


def _lemma_key(lemma: str) -> str:
    return (lemma or "").strip().casefold()


def _pos_rank(pos: str) -> int:
    return POS_RANK.get((pos or "unknown").lower(), 50)


def _merge_translations(into: dict, other: dict) -> None:
    for lang, vals in (other or {}).items():
        bucket = into.setdefault(lang, [])
        seen = {x.casefold() for x in bucket}
        for v in vals or []:
            t = (v or "").strip()
            if not t:
                continue
            k = t.casefold()
            if k not in seen:
                bucket.append(t)
                seen.add(k)


def _dedupe_examples(examples: list[dict]) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for ex in examples or []:
        if not isinstance(ex, dict):
            continue
        text = (ex.get("text") or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append({k: v for k, v in ex.items() if k not in {"nwords", "lead"}})
    out.sort(key=lambda e: (len(e.get("text") or ""), e.get("id") or ""))
    return out


def _pick_primary(cards: list[dict]) -> dict:
    def sort_key(c: dict) -> tuple:
        rank = int(c.get("frequency_rank") or 10**9)
        return (_pos_rank(c.get("pos")), rank, -len(c.get("examples") or []), c.get("slug") or "")

    return min(cards, key=sort_key)


def merge_word_group(cards: list[dict]) -> dict:
    primary = _pick_primary(cards)
    merged = dict(primary)
    all_pos = sorted({(c.get("pos") or "?") for c in cards})
    merged["pos"] = primary.get("pos") or all_pos[0]
    merged["pos_all"] = all_pos
    merged_aliases = sorted({c.get("slug") for c in cards if c.get("slug")})
    if len(merged_aliases) > 1:
        merged["merged_slugs"] = merged_aliases

    translations: dict = {}
    tags: set[str] = set()
    examples: list[dict] = []
    for c in cards:
        _merge_translations(translations, c.get("translations") or {})
        tags.update(c.get("tags") or [])
        for ex in c.get("examples") or []:
            row = dict(ex)
            slugs = set(row.get("word_slugs") or [])
            slugs.update(s for s in merged_aliases if s)
            row["word_slugs"] = sorted(slugs)
            examples.append(row)
    merged["translations"] = translations
    merged["tags"] = sorted(tags)
    merged["examples"] = _dedupe_examples(examples)
    best_rank = min(int(c.get("frequency_rank") or 10**9) for c in cards)
    if best_rank < 10**9:
        merged["frequency_rank"] = best_rank
    return merged


def merge_vocab_payload(data: dict) -> tuple[dict, dict]:
    words = list(data.get("words") or [])
    groups: dict[str, list[dict]] = defaultdict(list)
    for w in words:
        groups[_lemma_key(w.get("lemma") or "")].append(w)
    merged_words: list[dict] = []
    stats = {
        "in": len(words),
        "out": 0,
        "groups_merged": 0,
        "examples_before": sum(len(w.get("examples") or []) for w in words),
        "examples_after": 0,
    }
    for key in sorted(groups, key=lambda k: (groups[k][0].get("frequency_rank") or 10**9, k)):
        if not key:
            continue
        bucket = groups[key]
        if len(bucket) == 1:
            one = dict(bucket[0])
            one["examples"] = _dedupe_examples(one.get("examples") or [])
            merged_words.append(one)
        else:
            stats["groups_merged"] += 1
            merged_words.append(merge_word_group(bucket))
    stats["out"] = len(merged_words)
    stats["examples_after"] = sum(len(w.get("examples") or []) for w in merged_words)
    out = dict(data)
    out["words"] = merged_words
    out["card_merge"] = {
        "rule": "one_lemma_one_card",
        "merged_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
    }
    return out, stats


def process_json_lang(lang: str, write: bool, backup: bool) -> list[dict]:
    rows: list[dict] = []
    lang_dir = PLUGINS / lang
    if not lang_dir.is_dir():
        return rows
    for level in LEVELS:
        path = lang_dir / f"vocab_{level}.json"
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        merged, stats = merge_vocab_payload(data)
        stats["lang"] = lang
        stats["level"] = level.upper()
        rows.append(stats)
        if write:
            if backup:
                bak = path.with_suffix(path.suffix + ".pre-merge.bak")
                if not bak.is_file():
                    shutil.copy2(path, bak)
            path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    return rows


def merge_sqlite_lang(lang: str, write: bool) -> dict:
    if not SQLITE.is_file():
        return {"lang": lang, "sqlite": "missing"}
    conn = sqlite3.connect(SQLITE)
    conn.row_factory = sqlite3.Row
    total_removed = 0
    total_kept = 0
    for _level, band in BAND_BY_LANG_LEVEL.get(lang, {}).items():
        rows = conn.execute(
            "SELECT * FROM words WHERE lang=? AND band=? ORDER BY rank, lemma",
            (lang, band),
        ).fetchall()
        by_lemma: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for row in rows:
            by_lemma[_lemma_key(row["lemma"])].append(row)
        for lemma_key, group in by_lemma.items():
            if not lemma_key:
                continue
            if len(group) == 1:
                total_kept += 1
                continue

            def row_key(r):
                return (_pos_rank(r["pos"]), int(r["rank"] or 10**9), r["slug"])

            keep = min(group, key=row_key)
            drop = [r for r in group if r["slug"] != keep["slug"]]
            examples: list[str] = []
            gloss_ru = (keep["gloss_ru"] or "").strip()
            gloss_en = (keep["gloss_en"] or "").strip()
            ex0 = (keep["example"] or "").strip()
            if ex0:
                examples.append(ex0)
            for r in group:
                val = (r["gloss_ru"] or "").strip()
                if val and not gloss_ru:
                    gloss_ru = val
                val = (r["gloss_en"] or "").strip()
                if val and not gloss_en:
                    gloss_en = val
                ex = (r["example"] or "").strip()
                if ex and ex.casefold() not in {e.casefold() for e in examples}:
                    examples.append(ex)
            if write:
                conn.execute(
                    "UPDATE words SET gloss_ru=?, gloss_en=?, example=? WHERE lang=? AND slug=?",
                    (gloss_ru, gloss_en, examples[0] if examples else "", lang, keep["slug"]),
                )
                for r in drop:
                    conn.execute("DELETE FROM words WHERE lang=? AND slug=?", (lang, r["slug"]))
            total_kept += 1
            total_removed += len(drop)
    if write:
        conn.commit()
    conn.close()
    return {"lang": lang, "sqlite_kept": total_kept, "sqlite_removed": total_removed}


def main() -> int:
    ap = argparse.ArgumentParser(description="Одна лемма — одна карточка, примеры сохраняются.")
    ap.add_argument("--langs", default="de,es,fr,it")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--sqlite", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()
    if not args.write and not args.dry_run:
        args.dry_run = True
    langs = [x.strip() for x in args.langs.split(",") if x.strip()]
    print("merge_lang_vocab_cards", "write" if args.write else "dry-run", "langs:", ", ".join(langs))
    for lang in langs:
        for s in process_json_lang(lang, write=args.write, backup=not args.no_backup):
            print(
                f"  {s['lang'].upper()} {s['level']}: {s['in']} -> {s['out']} cards "
                f"(merged groups {s['groups_merged']}); examples {s['examples_before']} -> {s['examples_after']}"
            )
        if args.sqlite:
            sq = merge_sqlite_lang(lang, write=args.write)
            print(f"  sqlite {lang}: kept {sq.get('sqlite_kept')}, removed {sq.get('sqlite_removed')}")
    if args.dry_run and not args.write:
        print("Hint: rerun with --write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
