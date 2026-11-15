#!/usr/bin/env python
"""Download Kaikki DE/ES dictionaries and COERLL textbooks onto disk.

Raw files stay in data/vocab_sources/ (gitignored).
Database: data/vocab_sources/kaikki/vocab.sqlite
Log: data/vocab_sources/fetch_open_vocab.log

Stdout gets short progress lines only, never dictionary entries.
A second run resumes a partial download and skips a finished file.
"""

from __future__ import annotations

import gzip
import json
import sqlite3
import ssl
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "vocab_sources"
KA = RAW / "kaikki"
CO = RAW / "coerll"
LOG = RAW / "fetch_open_vocab.log"
STATUS = RAW / "fetch_status.txt"

UA = "StarTyping-vocab/1.0 (local dictionary build)"
MIN_FREE = 3 * 1024 ** 3

FILES = [
    (
        "de-en",
        "https://kaikki.org/dictionary/German/kaikki.org-dictionary-German.jsonl",
        KA / "kaikki.org-dictionary-German.jsonl",
        False,
    ),
    (
        "es-en",
        "https://kaikki.org/dictionary/Spanish/kaikki.org-dictionary-Spanish.jsonl",
        KA / "kaikki.org-dictionary-Spanish.jsonl",
        False,
    ),
    (
        "de-native",
        "https://kaikki.org/dictionary/downloads/de/de-extract.jsonl.gz",
        KA / "de-extract.jsonl.gz",
        True,
    ),
    (
        "es-native",
        "https://kaikki.org/dictionary/downloads/es/es-extract.jsonl.gz",
        KA / "es-extract.jsonl.gz",
        True,
    ),
]

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

COERLL_STARTS = [
    "https://coerll.utexas.edu/coerll/materials/",
    "https://coerll.utexas.edu/dib/",
]
ASSET_EXT = {".pdf", ".zip", ".mp3", ".mp4", ".ogg", ".epub", ".docx", ".odt"}
MAX_HTML_PAGES = 1500
MAX_HTML_BYTES = 400 * 1024 * 1024
MAX_ASSET_BYTES = 2 * 1024 ** 3


def log(msg: str) -> None:
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    RAW.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def status(msg: str) -> None:
    STATUS.write_text(msg + "\n", encoding="utf-8")
    log(msg)


def free_bytes() -> int:
    import shutil

    return shutil.disk_usage(ROOT).free


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
    if expected and free_bytes() < (expected - have) + MIN_FREE:
        raise SystemExit(f"low disk for {dest.name}: free {free_bytes()}")
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
        if code == "ru" or lang in {"russian", "russisch", "ruso"}:
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


def build_db(freq_de: dict[str, int], freq_es: dict[str, int]) -> None:
    db_path = KA / "vocab.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS words (
            slug TEXT NOT NULL,
            lemma TEXT,
            pos TEXT,
            lang TEXT,
            rank INTEGER,
            band TEXT,
            cefr TEXT,
            gender TEXT,
            gloss_en TEXT,
            gloss_ru TEXT,
            gloss_native TEXT,
            example TEXT,
            source TEXT,
            score INTEGER,
            PRIMARY KEY (lang, slug)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lang_band ON words(lang, band)")
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
        lang = "de" if key.startswith("de") else "es"
        native = key.endswith("native")
        freq = freq_de if lang == "de" else freq_es
        bands = DE_BANDS if lang == "de" else ES_BANDS
        if native:
            source = "Wiktionary " + lang + " (Kaikki, CC BY-SA 4.0)"
        else:
            source = "English Wiktionary via Kaikki, CC BY-SA 4.0"
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
                en = "" if native else " | ".join(glosses)
                native_gloss = " | ".join(glosses) if native else ""
                score = (10 if ru else 0) + (3 if en else 0) + (1 if native_gloss else 0) + (1 if rank else 0)
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
                        en,
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


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                self.hrefs.append(value)


def allowed(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host.endswith("coerll.utexas.edu")



def open_url(url: str, timeout: int = 60):
    """Open a URL. If the local trust store rejects the certificate, try once without it."""
    req = request(url)
    try:
        return opener().open(req, timeout=timeout)
    except Exception as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        log("cert fallback " + url)
        ctx = ssl._create_unverified_context()
        lax = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
        return lax.open(request(url), timeout=timeout)


def fetch_coerll() -> None:
    CO.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    queue = list(COERLL_STARTS)
    pages = 0
    html_bytes = 0
    asset_bytes = 0
    while queue and pages < MAX_HTML_PAGES and html_bytes < MAX_HTML_BYTES:
        if free_bytes() < MIN_FREE:
            log("COERLL stopped: low disk")
            return
        url = queue.pop(0).split("#")[0]
        if url in seen or not allowed(url):
            continue
        seen.add(url)
        try:
            with open_url(url) as resp:
                data = resp.read()
                final = resp.geturl()
                ctype = resp.headers.get("Content-Type", "")
        except Exception as exc:
            log(f"COERLL skip {url}: {exc}")
            continue
        path = urlparse(final).path.lower()
        ext = Path(path).suffix
        if ext in ASSET_EXT or "pdf" in ctype or "zip" in ctype or "audio" in ctype:
            if asset_bytes + len(data) > MAX_ASSET_BYTES:
                continue
            name = Path(path).name or "file.bin"
            dest = CO / "files" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                dest.write_bytes(data)
            asset_bytes += len(data)
            log(f"COERLL file {name} ({len(data)} bytes)")
            continue
        if "html" not in ctype and not path.endswith(("/", ".html", ".htm", ".php")):
            continue
        pages += 1
        html_bytes += len(data)
        rel = urlparse(final).path.strip("/") or "index"
        safe = rel.replace("/", "__")[:180]
        out = CO / "pages" / f"{safe}.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        if pages % 25 == 0:
            log(f"COERLL pages {pages}, html {html_bytes // 1024} KB, files {asset_bytes // 1024} KB")
        parser = LinkParser()
        try:
            parser.feed(data.decode("utf-8", errors="replace"))
        except Exception:
            continue
        for href in parser.hrefs:
            nxt = urljoin(final, href).split("#")[0]
            if nxt not in seen and allowed(nxt):
                queue.append(nxt)
    (CO / "crawl.txt").write_text(
        f"pages={pages}\nhtml_bytes={html_bytes}\nasset_bytes={asset_bytes}\n",
        encoding="utf-8",
    )
    log(f"COERLL done: pages {pages}, html {html_bytes}, files {asset_bytes}")


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    status("start")
    for _key, url, dest, _gz in FILES:
        status(f"download {dest.name}")
        download(url, dest)
    freq_de = load_freq(RAW / "freq" / "de_50k.txt")
    freq_es = load_freq(RAW / "freq" / "es_50k.txt")
    build_db(freq_de, freq_es)
    status("COERLL")
    fetch_coerll()
    status("done")


if __name__ == "__main__":
    main()
