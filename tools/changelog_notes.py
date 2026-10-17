#!/usr/bin/env python3
"""Вырезать секцию CHANGELOG.md для тега vX.Y.Z → stdout (body для GitHub Release)."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def normalize_version(tag: str) -> str:
    t = tag.strip()
    if t.lower().startswith("v"):
        t = t[1:]
    return t


def extract_notes(changelog: str, version: str) -> str:
    ver = normalize_version(version)
    # ## 3.6.0 — …  или ## v3.6.0 …
    pat = re.compile(
        rf"^##\s+v?{re.escape(ver)}\b[^\n]*\n(.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pat.search(changelog)
    if not m:
        return f"Release {ver}\n"
    body = m.group(1).strip()
    return body + "\n" if body else f"Release {ver}\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--changelog", type=Path, default=Path("CHANGELOG.md"))
    p.add_argument("--tag", required=True, help="vX.Y.Z or X.Y.Z")
    args = p.parse_args()
    if not args.changelog.is_file():
        print(f"missing {args.changelog}", file=sys.stderr)
        return 1
    text = args.changelog.read_text(encoding="utf-8")
    sys.stdout.write(extract_notes(text, args.tag))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
