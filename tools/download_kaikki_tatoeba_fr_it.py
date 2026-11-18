#!/usr/bin/env python
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "vocab_sources"
KAIKKI_DIR = RAW / "kaikki"
TATOEBA_DIR = RAW / "tatoeba_export"
KAIKKI_DIR.mkdir(parents=True, exist_ok=True)
TATOEBA_DIR.mkdir(parents=True, exist_ok=True)

UA = "StarTyping-vocab/1.0 (educational; CC BY attribution)"

# Kaikki dictionary extracts (JSONL.gz)
kaikki_urls = {
    "fr-extract.jsonl.gz": "https://kaikki.org/dictionary/French/kaikki.org-dictionary-French.jsonl.gz",
    "it-extract.jsonl.gz": "https://kaikki.org/dictionary/Italian/kaikki.org-dictionary-Italian.jsonl.gz",
}

# Tatoeba exports
tatoeba_urls = {
    "fra_sentences_detailed.tsv.bz2": "https://downloads.tatoeba.org/exports/per_language/fra/fra_sentences_detailed.tsv.bz2",
    "ita_sentences_detailed.tsv.bz2": "https://downloads.tatoeba.org/exports/per_language/ita/ita_sentences_detailed.tsv.bz2",
    "fra-rus_links.tsv.bz2": "https://downloads.tatoeba.org/exports/per_language/fra/fra-rus_links.tsv.bz2",
    "ita-rus_links.tsv.bz2": "https://downloads.tatoeba.org/exports/per_language/ita/ita-rus_links.tsv.bz2",
}

def download(url: str, dest: Path):
    if dest.is_file() and dest.stat().st_size > 0:
        print(f"Already have {dest.name}")
        return
    print(f"Downloading {dest.name}...")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=300) as resp, dest.open("wb") as out:
        chunk_size = 1 << 20
        got = 0
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            out.write(chunk)
            got += len(chunk)
            if got % (10 << 20) == 0:
                print(f"  {got / 1e6:.0f} MB")
    print(f"  Done: {dest.stat().st_size / 1e6:.1f} MB")

for name, url in kaikki_urls.items():
    download(url, KAIKKI_DIR / name)

for name, url in tatoeba_urls.items():
    download(url, TATOEBA_DIR / name)

print("All downloads complete")