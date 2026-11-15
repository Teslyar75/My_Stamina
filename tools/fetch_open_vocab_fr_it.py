#!/usr/bin/env python
"""Download Kaikki FR/IT dictionaries and add to existing vocab.sqlite."""

from __future__ import annotations

import gzip
import json
import sqlite3
import ssl
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "vocab_sources"
KA = RAW / "kaikki"
LOG = RAW / "fetch_open_vocab.log"
STATUS = RAW / "fetch_status.txt"

UA = "StarTyping-vocab/1.0 (local dictionary build)"

FILES = [
    (
        "fr-native",
        "https://kaikki.org/dictionary/downloads/fr/fr-extract.jsonl.gz",
        KA / "fr-extract.jsonl.gz",
        True,
    ),
    (
        "it-native",
        "https://kaikki.org/dictionary/downloads/it/it-extract.jsonl.gz",
        KA / "it-extract.jsonl.gz",
        True,
    ),
]

# CEFR bands based on frequency ranks (similar to DE/ES)
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


def log(msg: str) -> None:
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    RAW.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def status(msg: str) -> None:
    STATUS.write_text(msg + "\n", encoding="utf-8")
    log(msg)


def opener() -> urllib.request.OpenerDirector:
    ctx = ssl.create_default_context()
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))


def request(url: str, extra: dict | None = None) -> urllib.request.Request:
    headers = {"User-Agent": UA}
    if extra:
        headers.update(extra)
    return urllib.request.Request(url, headers=headers)


def content_length(url: str) -> int | None:
    req = request(url)
    req.method = "HEAD"
    try:
        with opener().open(req, timeout=60) as resp:
            n = resp.headers.get("Content-Length")
            return int(n) if n else None
    except Exception as exc:
        log(f"HEAD failed {url}: {exc}")
        return None


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    expected = content_length(url)
    if dest.is_file() and expected and dest.stat().st_size == expected:
        log(f"already complete {dest.name} ({expected} bytes)")
        return
    if dest.is_file() and not expected and dest.stat().st_size > 0:
        log(f"already present {dest.name}, server size unknown, skip")
        return
    part = dest.with_suffix(dest.suffix + ".part")
    have = part.stat().st_size if part.is_file() else 0
    headers = {}
    if have:
        headers["Range"] = f"bytes={have}-"
        log(f"resume {dest.name} from byte {have}")
    else:
        log(f"download {dest.name}")
    req = request(url, headers)
    with opener().open(req, timeout=120) as resp:
        code = getattr(resp, "status", 200)
        mode = "ab" if code == 206 and have else "wb"
        if code != 206:
            have = 0
        got = have
        with part.open(mode) as out:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                got += len(chunk)
                if got // (50 * 1024 * 1024) != (got - len(chunk)) // (50 * 1024 * 1024):
                    log(f"  {dest.name}: {got // (1024 * 1024)} MB")
    part.replace(dest)
    log(f"saved {dest.name}: {dest.stat().st_size} bytes")


def load_freq(path: Path) -> dict[str, int]:
    ranks: dict[str, int] = {}
    if not path.is_file():
        log(f"missing frequency list {path}")
        return ranks
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        word = line.split(" ", 1)[0].strip().casefold()
        if word and word not in ranks:
            ranks[word] = i
    return ranks


def band_for(rank: int, bands: list[tuple[int, str, str]]) -> tuple[str, str]:
    if rank <= 0:
        return "rest", ""
    for limit, band, cefr in bands:
        if rank <= limit:
            return band, cefr
    return "rest", ""


def slug_of(word: str, pos: str) -> str:
    raw = word.casefold().replace(" ", "-")
    chars = []
    for ch in raw:
        if ch.isalnum() or ch in "-'":
            chars.append(ch)
    return ("".join(chars).strip("-") + "-" + (pos or "x"))[:140]


def collect_text(node, want_ru, glosses, examples, depth: int = 0) -> None:
    if depth > 5:
        return
    if isinstance(node, dict):
        code = str(node.get("lang_code") or node.get("code") or "")
        lang = str(node.get("lang") or "").casefold()
        if code == "ru" or lang in {"russian", "russisch", "ruso", "russe", "russo"}:
            word = node.get("word") or node.get("translation")
            if isinstance(word, str) and word and word not in want_ru and len(want_ru) < 6:
                want_ru.append(word[:120])
        if isinstance(node.get("glosses"), list):
            for g in node["glosses"]:
                if isinstance(g, str) and g and len(glosses) < 4:
                    glosses.append(g[:180])
        ex = node.get("example") or node.get("text")
        if isinstance(ex, str) and " " in ex and len(examples) < 1 and 8 < len(ex) < 200:
            examples.append(ex)
        if len(glosses) < 4 or len(want_ru) < 6:
            for value in node.values():
                if isinstance(value, (dict, list)):
                    collect_text(value, want_ru, glosses, examples, depth + 1)
    elif isinstance(node, list):
        for item in node[:30]:
            collect_text(item, want_ru, glosses, examples, depth + 1)


def gender_of(obj: dict) -> str:
    tags = [str(t) for t in obj.get("tags") or []]
    for form in obj.get("forms") or []:
        if isinstance(form, dict):
            tags.extend(str(t) for t in form.get("tags") or [])
    if "masculine" in tags:
        return "m"
    if "feminine" in tags:
        return "f"
    if "neuter" in tags:
        return "n"
    return ""


def open_lines(path: Path, gz: bool):
    if gz:
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def build_db_fr_it(freq_fr: dict[str, int], freq_it: dict[str, int]) -> None:
    db_path = KA / "vocab.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    insert = """
        INSERT INTO words VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(lang, slug) DO UPDATE SET
            rank=excluded.rank,
            band=excluded.band,
            cefr=excluded.cefr,
            gender=CASE WHEN words.gender='' THEN excluded.gender ELSE words.gender END,
            gloss_en=CASE WHEN length(excluded.gloss_en)>length(words.gloss_en) THEN excluded.gloss_en ELSE words.gloss_en END,
            gloss_ru=CASE WHEN length(excluded.gloss_ru)>length(words.gloss_ru) THEN excluded.gloss_ru ELSE words.gloss_ru END,
            gloss_native=CASE WHEN length(excluded.gloss_native)>length(words.gloss_native) THEN excluded.gloss_native ELSE words.gloss_native END,
            example=CASE WHEN words.example='' THEN excluded.example ELSE words.example END,
            source=words.source,
            score=MAX(words.score, excluded.score)
        WHERE excluded.score >= words.score
           OR (words.gloss_ru='' AND excluded.gloss_ru!='')
    """

    for key, _url, path, gz in FILES:
        if not path.is_file():
            log(f"skip parse, missing {path.name}")
            continue
        lang = "fr" if key.startswith("fr") else "it"
        freq = freq_fr if lang == "fr" else freq_it
        bands = FR_BANDS if lang == "fr" else IT_BANDS
        source = f"Wiktionary {lang} (Kaikki, CC BY-SA 4.0)"
        status(f"parse {path.name}")
        n = kept = 0
        batch = []
        with open_lines(path, gz) as fh:
            for line in fh:
                n += 1
                if n % 50000 == 0:
                    log(f"  {path.name}: lines {n}, kept {kept}")
                line = line.strip()
                if not line or line[0] != "{":
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                word = obj.get("word")
                pos = obj.get("pos") or ""
                if not isinstance(word, str) or not word or not pos:
                    continue
                if len(word) > 80 or "\n" in word:
                    continue
                ru = []
                glosses = []
                examples = []
                collect_text(obj, ru, glosses, examples)
                rank = freq.get(word.casefold(), 0)
                band, cefr = band_for(rank, bands)
                native_gloss = " | ".join(glosses)
                score = (10 if ru else 0) + (3 if native_gloss else 0) + (1 if rank else 0)
                batch.append(
                    (
                        slug_of(word, pos),
                        word,
                        pos,
                        lang,
                        rank,
                        band,
                        cefr,
                        gender_of(obj),
                        "",  # gloss_en (empty for native)
                        " | ".join(ru),
                        native_gloss,
                        examples[0] if examples else "",
                        source,
                        score,
                    )
                )
                kept += 1
                if len(batch) >= 2000:
                    conn.executemany(insert, batch)
                    conn.commit()
                    batch.clear()
        if batch:
            conn.executemany(insert, batch)
            conn.commit()
        log(f"parsed {path.name}: lines {n}, kept {kept}")

    row = conn.execute("SELECT lang, COUNT(*) FROM words GROUP BY lang").fetchall()
    bands_rows = conn.execute(
        "SELECT lang, band, COUNT(*) FROM words GROUP BY lang, band ORDER BY lang, band"
    ).fetchall()
    summary = KA / "summary.txt"
    lines = [f"{lang}\t{count}" for lang, count in row]
    lines += [f"{lang}\t{band}\t{count}" for lang, band, count in bands_rows]
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log("summary " + str(summary.relative_to(ROOT)))
    conn.close()


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    status("start fr/it")
    for _key, url, dest, _gz in FILES:
        status(f"download {dest.name}")
        download(url, dest)
    freq_fr = load_freq(RAW / "freq" / "fr_50k.txt")
    freq_it = load_freq(RAW / "freq" / "it_50k.txt")
    build_db_fr_it(freq_fr, freq_it)
    status("done fr/it")


if __name__ == "__main__":
    main()