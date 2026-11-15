#!/usr/bin/env python
"""Собрать словари A1 для немецкого и испанского из открытых источников.

Скрипт сам скачивает:
  частотные ранги — hermitdave/FrequencyWords 2018 (CC BY-SA 4.0);
  примеры — выгрузка Tatoeba (CC BY 2.0 FR), пары deu–rus и spa–rus,
  с именем автора и номером предложения.

Сырьё кладётся в data/vocab_sources/ и в git не входит.
Список слов, часть речи, русский перевод и род — в
tools/lang_vocab/a1_de.tsv и a1_es.tsv: у Goethe, DWDS и Cervantes
нет открытой выгрузки.

Запуск из корня репозитория:
  python tools/build_lang_vocab_a1.py
  python tools/build_lang_vocab_a1.py --lang de
Повторный запуск не качает заново уже лежащие архивы.
"""
from __future__ import annotations

import argparse
import bz2
import json
import re
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "vocab_sources"
UA = "StarTyping-vocab/1.0 (educational; CC BY attribution)"
TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)
DE_ART = {"m": "der", "f": "die", "n": "das", "pl": "die"}

FILES = {
    "freq_de": "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/de/de_50k.txt",
    "freq_es": "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/es/es_50k.txt",
    "deu_detailed": "https://downloads.tatoeba.org/exports/per_language/deu/deu_sentences_detailed.tsv.bz2",
    "spa_detailed": "https://downloads.tatoeba.org/exports/per_language/spa/spa_sentences_detailed.tsv.bz2",
    "rus_detailed": "https://downloads.tatoeba.org/exports/per_language/rus/rus_sentences_detailed.tsv.bz2",
    "deu_rus_links": "https://downloads.tatoeba.org/exports/per_language/deu/deu-rus_links.tsv.bz2",
    "spa_rus_links": "https://downloads.tatoeba.org/exports/per_language/spa/spa-rus_links.tsv.bz2",
}

LANGS = {
    "de": {
        "band": "goethe-a1",
        "freq": "freq_de",
        "detailed": "deu_detailed",
        "links": "deu_rus_links",
        "tsv": ROOT / "tools" / "lang_vocab" / "a1_de.tsv",
        "out": ROOT / "stamina" / "languages" / "plugins" / "de" / "vocab_a1.json",
    },
    "es": {
        "band": "cervantes-a1",
        "freq": "freq_es",
        "detailed": "spa_detailed",
        "links": "spa_rus_links",
        "tsv": ROOT / "tools" / "lang_vocab" / "a1_es.tsv",
        "out": ROOT / "stamina" / "languages" / "plugins" / "es" / "vocab_a1.json",
    },
}


def download(key: str) -> Path:
    url = FILES[key]
    name = url.rsplit("/", 1)[-1]
    dest = RAW / ("freq" if key.startswith("freq_") else "tatoeba_export") / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 0:
        print(f"уже есть {dest.name}", flush=True)
        return dest
    partial = dest.with_name(dest.name + ".part")
    print(f"качаю {name}", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    got = 0
    try:
        with urllib.request.urlopen(req, timeout=180) as resp, partial.open("wb") as out:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                got += len(chunk)
                print(f"  {name} {got / 1e6:.0f} МБ", flush=True)
        partial.replace(dest)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    print(f"  готово {name}", flush=True)
    return dest


def iter_tsv(path: Path):
    opener = bz2.open if path.suffix == ".bz2" else open
    with opener(path, "rt", encoding="utf-8", errors="replace", newline="\n") as src:
        for line in src:
            yield line.rstrip("\n").split("\t")


def slug_for(lemma: str, pos: str) -> str:
    if lemma == "Sie":
        return "sie-formal"
    if lemma == "Ihr":
        return "ihr-formal"
    return lemma.casefold().replace(" ", "-") + "-" + pos


def fold_key(text: str) -> str:
    text = text.casefold().replace("ß", "ss")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def read_words(path: Path) -> list[dict]:
    rows = []
    seen = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) < 4:
            raise SystemExit("короткая строка: " + line)
        lemma, pos, ru, gender = parts[0], parts[1], parts[2], parts[3]
        plural = parts[4] if len(parts) > 4 else ""
        article = parts[5] if len(parts) > 5 else ""
        slug = slug_for(lemma, pos)
        if slug in seen:
            raise SystemExit("повтор slug " + slug)
        seen.add(slug)
        if pos == "noun" and gender not in {"m", "f", "n", "pl"}:
            raise SystemExit("у существительного нет рода: " + lemma)
        glosses = [bit.strip() for bit in ru.split(";") if bit.strip()]
        if not glosses:
            raise SystemExit("нет перевода: " + lemma)
        rows.append({
            "slug": slug, "lemma": lemma, "pos": pos, "ru": glosses,
            "gender": gender, "plural": plural, "article": article,
        })
    if len(rows) < 300:
        raise SystemExit(f"{path.name}: меньше 300 слов ({len(rows)})")
    return rows


def load_freq(path: Path) -> dict[str, int]:
    table = {}
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        bits = line.split()
        if bits and bits[0] not in table:
            table[bits[0]] = i
    return table


def rank_of(lemma: str, table: dict[str, int], index: int) -> int:
    for key in (lemma.casefold(), fold_key(lemma)):
        if key in table:
            return table[key]
    return 50000 + index


def load_links(path: Path) -> dict[str, str]:
    links = {}
    for cols in iter_tsv(path):
        if len(cols) >= 2 and cols[0] not in links:
            links[cols[0]] = cols[1]
    print(f"  связей {len(links)}", flush=True)
    return links


def load_russian(path: Path, needed: set[str]) -> dict[str, tuple[str, str]]:
    found = {}
    seen = 0
    for cols in iter_tsv(path):
        seen += 1
        if seen % 250000 == 0:
            print(f"  русский {seen}, найдено {len(found)}", flush=True)
        if len(cols) < 4 or cols[0] not in needed:
            continue
        found[cols[0]] = (cols[2], cols[3] or "unknown")
        if len(found) == len(needed):
            break
    print(f"  русских предложений {len(found)}", flush=True)
    return found


def sentence_ok(text: str) -> bool:
    if not text or not (12 <= len(text) <= 140):
        return False
    if "http" in text or "@" in text:
        return False
    first = text.lstrip("¿¡\"'«„“")[:1]
    if first.isalpha() and first.islower():
        return False
    return 3 <= len(TOKEN.findall(text)) <= 12


def collect_examples(detailed, links, russian, rows, code):
    nouns = {}
    others = {}
    pos_of = {}
    lemma_of = {}
    phrases = []
    for row in rows:
        key = row["lemma"].casefold()
        pos_of[row["slug"]] = row["pos"]
        lemma_of[row["slug"]] = row["lemma"]
        if " " in key:
            phrases.append((key, row["slug"]))
            continue
        group = nouns if row["pos"] in {"noun", "name"} else others
        group.setdefault(key, []).append(row["slug"])

    def targets(token):
        key = token.casefold()
        noun_slugs = nouns.get(key, [])
        other_slugs = others.get(key, [])
        if code != "de":
            return noun_slugs + other_slugs
        if token[:1].isupper() and noun_slugs:
            return noun_slugs
        if token[:1].islower() and other_slugs:
            verbs = [s for s in other_slugs if pos_of[s] == "verb"]
            if verbs and any(pos_of[s] == "det" for s in other_slugs):
                return [s for s in other_slugs if pos_of[s] != "det"]
            return other_slugs
        if token[:1].isupper() and other_slugs:
            head = [s for s in other_slugs if pos_of[s] in {"det", "pron"}]
            return head or other_slugs
        return noun_slugs or other_slugs
    buckets = {row["slug"]: [] for row in rows}

    def push(slug, item):
        bucket = buckets[slug]
        if any(old["text"] == item["text"] for old in bucket):
            return
        bucket.append(item)
        bucket.sort(key=lambda ex: (ex["lead"], ex["nwords"], len(ex["text"])))
        del bucket[2:]

    seen = 0
    for cols in iter_tsv(detailed):
        seen += 1
        if seen % 250000 == 0:
            print(f"  предложения {seen}", flush=True)
        if len(cols) < 4:
            continue
        rus_id = links.get(cols[0])
        rus = russian.get(rus_id or "")
        if not rus:
            continue
        text = cols[2].strip()
        if not sentence_ok(text):
            continue
        rus_text = rus[0].strip()
        if not rus_text:
            continue
        user = cols[3] or "unknown"
        rus_user = rus[1] or "unknown"
        nwords = len(TOKEN.findall(text))
        item_base = {
            "id": cols[0],
            "text": text,
            "translation": rus_text,
            "source": (
                f"Tatoeba #{cols[0]} @{user} / #{rus_id} @{rus_user} (CC BY 2.0 FR) "
                f"https://tatoeba.org/eng/sentences/show/{cols[0]}"
            ),
            "cefr_level": "A1",
            "nwords": nwords,
        }
        hit = []
        for tok in TOKEN.findall(text):
            hit.extend(targets(tok))
        low = text.casefold()
        for phrase, slug in phrases:
            if phrase in low:
                hit.append(slug)
        for slug in hit:
            sample = dict(item_base)
            sample["word_slugs"] = [slug]
            sample["lead"] = 0
            if code == "de" and pos_of.get(slug) == "noun":
                toks = TOKEN.findall(text)
                if toks and toks[0].casefold() == lemma_of[slug].casefold():
                    sample["lead"] = 1
            push(slug, sample)
    return buckets


def morphology(code, row):
    gender = row["gender"]
    lemma = row["lemma"]
    plural = row["plural"]
    if code == "de":
        article = row["article"] or DE_ART.get(gender, "")
        if gender == "pl":
            german = {"article": article, "nominative_sg": "", "nominative_pl": (article + " " + lemma).strip()}
        else:
            german = {
                "article": article,
                "nominative_sg": (article + " " + lemma).strip() if article else "",
                "nominative_pl": ("die " + plural) if plural else "",
            }
        return {"gender": gender or None, "german": german}
    article = row["article"] or ("el" if gender == "m" else "la" if gender == "f" else "")
    plural_art = "los" if gender == "m" else "las" if gender == "f" else ""
    plural_only = bool(plural) and plural.casefold() == lemma.casefold()
    spanish = {
        "gender": gender,
        "singular": "" if plural_only else ((article + " " + lemma).strip() if article else lemma),
        "plural": (plural_art + " " + plural).strip() if plural else "",
        "infinitive": lemma if row["pos"] == "verb" else "",
    }
    return {"gender": gender or None, "spanish": spanish}


def build(code: str) -> None:
    spec = LANGS[code]
    print(f"=== {code} ===", flush=True)
    rows = read_words(spec["tsv"])
    freq = load_freq(download(spec["freq"]))
    links = load_links(download(spec["links"]))
    russian = load_russian(download("rus_detailed"), set(links.values()))
    buckets = collect_examples(download(spec["detailed"]), links, russian, rows, code)
    words = []
    with_ex = 0
    for i, row in enumerate(rows, start=1):
        examples = []
        for ex in buckets[row["slug"]]:
            examples.append({k: v for k, v in ex.items() if k not in {"nwords", "lead"}})
        if examples:
            with_ex += 1
        morph = morphology(code, row)
        item = {
            "slug": row["slug"],
            "lemma": row["lemma"],
            "pos": row["pos"],
            "language": code,
            "cefr_level": "A1",
            "frequency_rank": rank_of(row["lemma"], freq, i),
            "frequency_band": spec["band"],
            "translations": {"ru": row["ru"]},
            "gender": morph.get("gender"),
            "examples": examples,
            "tags": ["A1"],
            "source": "Star Typing A1 list; rank: FrequencyWords 2018 (CC BY-SA 4.0); examples: Tatoeba (CC BY 2.0 FR)",
            "verified": bool(examples),
        }
        if "german" in morph:
            item["german"] = morph["german"]
        if "spanish" in morph:
            item["spanish"] = morph["spanish"]
        words.append(item)
    payload = {
        "language": code,
        "level": "A1",
        "attribution": {
            "lemmas": "Star Typing pedagogical A1 list (tools/lang_vocab)",
            "frequency": "hermitdave/FrequencyWords 2018, CC BY-SA 4.0, OpenSubtitles",
            "examples": "Tatoeba export, CC BY 2.0 FR; each example names both authors and sentence ids",
        },
        "words": words,
    }
    spec["out"].write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(f"записал {spec['out'].name}: слов {len(words)}, с примерами {with_ex}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Скачать источники и собрать vocab_a1.json")
    parser.add_argument("--lang", choices=["de", "es", "all"], default="all")
    args = parser.parse_args()
    codes = ["de", "es"] if args.lang == "all" else [args.lang]
    for code in codes:
        build(code)


if __name__ == "__main__":
    main()
