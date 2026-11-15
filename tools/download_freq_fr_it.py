#!/usr/bin/env python
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FREQ_DIR = ROOT / "data" / "vocab_sources" / "freq"
FREQ_DIR.mkdir(parents=True, exist_ok=True)

urls = {
    "fr_50k.txt": "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/fr/fr_50k.txt",
    "it_50k.txt": "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/it/it_50k.txt",
}

for name, url in urls.items():
    dest = FREQ_DIR / name
    if dest.is_file() and dest.stat().st_size > 0:
        print(f"Already have {name}")
        continue
    print(f"Downloading {name}...")
    req = urllib.request.Request(url, headers={"User-Agent": "StarTyping-vocab/1.0"})
    with urllib.request.urlopen(req, timeout=180) as resp, dest.open("wb") as out:
        out.write(resp.read())
    print(f"  Done: {dest.stat().st_size} bytes")

print("All done")