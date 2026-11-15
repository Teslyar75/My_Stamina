#!/usr/bin/env python
"""Собрать словари A1–C2 для немецкого и испанского из Kaikki + Tatoeba.

Запуск из корня репозитория:
  python tools/build_lang_vocab_all.py
  python tools/build_lang_vocab_all.py --lang de
  python tools/build_lang_vocab_all.py --levels A2 B1 B2
"""
from __future__ import annotations

import argparse
import bz2
import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RAW = ROOT / "data" / "vocab_sources"
UA = "StarTyping-vocab/1.0 (educational; CC BY attribution)"
TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)
DE_ART = {"m": "der", "f": "die", "n": "das", "pl": "die"}

FILES = {
    "freq_de": "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/de/de_50k.txt",
    "freq_es": "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/es/es_50k.txt",
    "freq_fr": "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/fr/fr_50k.txt",
    "freq_it": "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/it/it_50k.txt",
    "deu_detailed": "https://downloads.tatoeba.org/exports/per_language/deu/deu_sentences_detailed.tsv.bz2",
    "spa_detailed": "https://downloads.tatoeba.org/exports/per_language/spa/spa_sentences_detailed.tsv.bz2",
    "fra_detailed": "https://downloads.tatoeba.org/exports/per_language/fra/fra_sentences_detailed.tsv.bz2",
    "ita_detailed": "https://downloads.tatoeba.org/exports/per_language/ita/ita_sentences_detailed.tsv.bz2",
    "rus_detailed": "https://downloads.tatoeba.org/exports/per_language/rus/rus_sentences_detailed.tsv.bz2",
    "deu_rus_links": "https://downloads.tatoeba.org/exports/per_language/deu/deu-rus_links.tsv.bz2",
    "spa_rus_links": "https://downloads.tatoeba.org/exports/per_language/spa/spa-rus_links.tsv.bz2",
    "fra_rus_links": "https://downloads.tatoeba.org/exports/per_language/fra/fra-rus_links.tsv.bz2",
    "ita_rus_links": "https://downloads.tatoeba.org/exports/per_language/ita/ita-rus_links.tsv.bz2",
}

DE_BANDS = [
    (600, "goethe-a1", "A1"),
    (1200, "goethe-a2", "A2"),
    (2500, "goethe-b1", "B1"),
    (5000, "goethe-b2", "B2"),
    (10000, "goethe-c1", "C1"),
    (20000, "goethe-c2", "C2"),
]
ES_BANDS = [
    (600, "cervantes-a1", "A1"),
    (1200, "cervantes-a2", "A2"),
    (2500, "cervantes-b1", "B1"),
    (5000, "cervantes-b2", "B2"),
    (10000, "cervantes-c1", "C1"),
    (20000, "cervantes-c2", "C2"),
]
FR_BANDS = [
    (600, "delf-a1", "A1"),
    (1200, "delf-a2", "A2"),
    (2500, "delf-b1", "B1"),
    (5000, "delf-b2", "B2"),
    (10000, "delf-c1", "C1"),
    (20000, "delf-c2", "C2"),
]
IT_BANDS = [
    (600, "celi-a1", "A1"),
    (1200, "celi-a2", "A2"),
    (2500, "celi-b1", "B1"),
    (5000, "celi-b2", "B2"),
    (10000, "celi-c1", "C1"),
    (20000, "celi-c2", "C2"),
]

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]


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


def load_freq(path: Path) -> dict[str, int]:
    table = {}
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        bits = line.split()
        if bits and bits[0] not in table:
            table[bits[0]] = i
    return table


def band_for(rank: int, bands: list[tuple[int, str, str]]) -> tuple[str, str]:
    if rank <= 0:
        return "rest", ""
    for limit, band, cefr in bands:
        if rank <= limit:
            return band, cefr
    return "rest", ""


def slug_for(lemma: str, pos: str) -> str:
    if lemma == "Sie":
        return "sie-formal"
    if lemma == "Ihr":
        return "ihr-formal"
    return lemma.casefold().replace(" ", "-") + "-" + pos


def fold_key(text: str) -> str:
    text = text.casefold().replace("ß", "ss")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


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


def build_for_lang(code: str, levels: list[str]) -> None:
    from stamina.languages.core.sqlite_vocab import sqlite_path, entry_from_row
    import sqlite3

    print(f"=== {code.upper()} ===", flush=True)

    db_path = sqlite_path()
    if not db_path.is_file():
        raise SystemExit(f"Kaikki DB не найдена: {db_path}. Сначала запусти tools/fetch_open_vocab.py")

    freq_key = {"de": "freq_de", "es": "freq_es", "fr": "freq_fr", "it": "freq_it"}[code]
    links_key = {"de": "deu_rus_links", "es": "spa_rus_links", "fr": "fra_rus_links", "it": "ita_rus_links"}[code]
    detailed_key = {"de": "deu_detailed", "es": "spa_detailed", "fr": "fra_detailed", "it": "ita_detailed"}[code]
    bands = {"de": DE_BANDS, "es": ES_BANDS, "fr": FR_BANDS, "it": IT_BANDS}[code]

    freq = load_freq(download(freq_key))
    links = load_links(download(links_key))
    russian = load_russian(download("rus_detailed"), set(links.values()))

    conn = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    words_by_level: dict[str, list[dict]] = {level: [] for level in LEVELS}

    for level in levels:
        band_name, _ = next((b, c) for limit, b, c in bands if c == level)
        print(f"  загружаю слова для {level} ({band_name})", flush=True)
        rows = conn.execute(
            "SELECT * FROM words WHERE lang=? AND band=? ORDER BY rank",
            (code, band_name)
        ).fetchall()

        for row in rows:
            entry = entry_from_row(row)
            words_by_level[level].append({
                "slug": entry.slug,
                "lemma": entry.lemma,
                "pos": entry.pos,
                "language": code,
                "cefr_level": level,
                "frequency_rank": entry.frequency_rank,
                "frequency_band": entry.frequency_band,
                "translations": entry.translations,
                "gender": entry.morphology.gender,
                "examples": [],
                "tags": [level],
                "source": f"Kaikki {code} (CC BY-SA 4.0); examples: Tatoeba (CC BY 2.0 FR)",
                "verified": True,
            })
        print(f"    слов: {len(words_by_level[level])}")

    conn.close()

    if not any(words_by_level.values()):
        print("  нет слов для выбранных уровней", flush=True)
        return

    detailed_path = download(detailed_key)
    code_param = code

    nouns = {}
    others = {}
    pos_of = {}
    lemma_of = {}
    phrases = []
    for level in levels:
        for word in words_by_level[level]:
            key = word["lemma"].casefold()
            pos_of[word["slug"]] = word["pos"]
            lemma_of[word["slug"]] = word["lemma"]
            if " " in key:
                phrases.append((key, word["slug"]))
                continue
            group = nouns if word["pos"] in {"noun", "name"} else others
            group.setdefault(key, []).append(word["slug"])

    def targets(token):
        key = token.casefold()
        noun_slugs = nouns.get(key, [])
        other_slugs = others.get(key, [])
        if code_param != "de":
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

    buckets = {}
    for level in levels:
        for word in words_by_level[level]:
            buckets[word["slug"]] = []

    def push(slug, item):
        bucket = buckets[slug]
        if any(old["text"] == item["text"] for old in bucket):
            return
        bucket.append(item)
        bucket.sort(key=lambda ex: (ex["lead"], ex["nwords"], len(ex["text"])))
        del bucket[5:]

    seen = 0
    for cols in iter_tsv(detailed_path):
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
            if code_param == "de" and pos_of.get(slug) == "noun":
                toks = TOKEN.findall(text)
                if toks and toks[0].casefold() == lemma_of[slug].casefold():
                    sample["lead"] = 1
            push(slug, sample)

    out_dir = ROOT / "stamina" / "languages" / "plugins" / code
    out_dir.mkdir(parents=True, exist_ok=True)

    for level in levels:
        band_name, _ = next((b, c) for limit, b, c in bands if c == level)
        words = []
        with_ex = 0
        for word in words_by_level[level]:
            examples = []
            for ex in buckets[word["slug"]]:
                examples.append({k: v for k, v in ex.items() if k not in {"nwords", "lead"}})
            if examples:
                with_ex += 1
            morph = {}
            if code == "de":
                gender = word["gender"]
                article = DE_ART.get(gender, "")
                if gender == "pl":
                    german = {"article": article, "nominative_sg": "", "nominative_pl": (article + " " + word["lemma"]).strip()}
                else:
                    german = {
                        "article": article,
                        "nominative_sg": (article + " " + word["lemma"]).strip() if article else "",
                        "nominative_pl": ("die " + word.get("plural", "")) if word.get("plural") else "",
                    }
                morph["german"] = german
            elif code == "es":
                gender = word["gender"]
                article = word.get("article") or ("el" if gender == "m" else "la" if gender == "f" else "")
                plural_art = "los" if gender == "m" else "las" if gender == "f" else ""
                plural = word.get("plural", "")
                spanish = {
                    "gender": gender,
                    "singular": (article + " " + word["lemma"]).strip() if article else word["lemma"],
                    "plural": (plural_art + " " + plural).strip() if plural else "",
                    "infinitive": word["lemma"] if word["pos"] == "verb" else "",
                }
                morph["spanish"] = spanish
            elif code == "fr":
                gender = word["gender"]
                article = word.get("article") or ("le" if gender == "m" else "la" if gender == "f" else "")
                plural_art = "les" if gender in ("m", "f") else ""
                plural = word.get("plural", "")
                french = {
                    "gender": gender,
                    "singular": (article + " " + word["lemma"]).strip() if article else word["lemma"],
                    "plural": (plural_art + " " + plural).strip() if plural else "",
                    "infinitive": word["lemma"] if word["pos"] == "verb" else "",
                }
                morph["french"] = french
            elif code == "it":
                gender = word["gender"]
                article = word.get("article") or ("il" if gender == "m" else "la" if gender == "f" else "")
                plural_art = "i" if gender == "m" else "le" if gender == "f" else ""
                plural = word.get("plural", "")
                italian = {
                    "gender": gender,
                    "singular": (article + " " + word["lemma"]).strip() if article else word["lemma"],
                    "plural": (plural_art + " " + plural).strip() if plural else "",
                    "infinitive": word["lemma"] if word["pos"] == "verb" else "",
                }
                morph["italian"] = italian
            item = {
                "slug": word["slug"],
                "lemma": word["lemma"],
                "pos": word["pos"],
                "language": code,
                "cefr_level": level,
                "frequency_rank": word["frequency_rank"],
                "frequency_band": band_name,
                "translations": word["translations"],
                "gender": word["gender"] or None,
                "examples": examples,
                "tags": [level],
                "source": word["source"],
                "verified": True,
            }
            item.update(morph)
            words.append(item)
        payload = {
            "language": code,
            "level": level,
            "attribution": {
                "lemmas": f"Kaikki {code} (CC BY-SA 4.0), frequency bands by Goethe/Cervantes",
                "frequency": "hermitdave/FrequencyWords 2018, CC BY-SA 4.0, OpenSubtitles",
                "examples": "Tatoeba export, CC BY 2.0 FR; each example names both authors and sentence ids",
            },
            "words": words,
        }
        out_path = out_dir / f"vocab_{level.lower()}.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        print(f"записал {out_path.name}: слов {len(words)}, с примерами {with_ex}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Собрать vocab_XX.json для DE/ES/FR/IT из Kaikki + Tatoeba")
    parser.add_argument("--lang", choices=["de", "es", "fr", "it", "all"], default="all")
    parser.add_argument("--levels", nargs="+", choices=LEVELS, default=LEVELS)
    args = parser.parse_args()
    codes = ["de", "es", "fr", "it"] if args.lang == "all" else [args.lang]
    for code in codes:
        build_for_lang(code, args.levels)


if __name__ == "__main__":
    main()