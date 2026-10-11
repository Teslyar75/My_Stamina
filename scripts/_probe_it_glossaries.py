"""Probe IT glossary sources for download URLs."""
from __future__ import annotations

import json
import re
import urllib.request

UA = {"User-Agent": "StarTyping/My_Stamina glossary import"}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main() -> None:
    html = get("https://coderslingo.com/resources/open-dataset/").decode("utf-8", "replace")
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html)
    print("=== CodersLingo hrefs of interest ===")
    for m in hrefs:
        low = m.lower()
        if any(x in low for x in (".json", ".csv", ".zip", "download", "dataset", "anki", "cdn")):
            print(m)
    for m in re.findall(r"https?://[^\s\"']+(?:json|csv|zip)", html):
        print("abs", m)

    print("\n=== Codekilla repo tree ===")
    tree = json.loads(get("https://api.github.com/repos/codekillaofficial/programming-terminology-for-beginners/contents/"))
    for item in tree:
        print(item["type"], item["name"], item.get("size"))

    g = json.loads(get(
        "https://raw.githubusercontent.com/codekillaofficial/programming-terminology-for-beginners/main/glossary.json"
    ))
    print("glossary keys", g.keys())
    terms = g.get("terms") or g.get("entries") or []
    print("terms count", len(terms))
    if terms:
        print("sample", json.dumps(terms[0], ensure_ascii=False)[:300])


if __name__ == "__main__":
    main()
