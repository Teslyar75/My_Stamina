"""Машинный черновик языков интерфейса (es/fr/it) из ru.json.

Ключ в словарях — русская фраза, поэтому переводим сами ключи. Плейсхолдеры
{0}, {1}, {name} на время перевода заменяются токенами, иначе Google их ломает.

Скрипт возобновляемый: кэш `_orion/mt_cache.json` хранит уже переведённое,
`--limit N` ограничивает число новых запросов за прогон (сеть капризна,
а 3000 фраз за один заход — это полчаса ожидания).

    python tools/i18n_mt.py --lang es --limit 600
    python tools/i18n_mt.py --lang fr --limit 600
    python tools/i18n_mt.py --lang it --limit 600
    python tools/i18n_mt.py --lang es --report   # только цифры

Черновик кладётся в stamina/i18n/<lang>.json и правится руками: файл читается
как обычный словарь, порядок ключей — как в ru.json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "stamina" / "i18n"
CACHE = ROOT / "_orion" / "mt_cache.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) StarTyping/3.8"
TIMEOUT = 10
PAUSE = 0.25
BATCH = 12

PLACEHOLDER = re.compile(r"\{[^{}]*\}")
TOKEN_OPEN, TOKEN_CLOSE = "\ue000", "\ue001"


def protect(text: str) -> tuple[str, list[str]]:
    found: list[str] = []

    def keep(m: re.Match) -> str:
        found.append(m.group(0))
        return f"{TOKEN_OPEN}{len(found) - 1}{TOKEN_CLOSE}"

    return PLACEHOLDER.sub(keep, text), found


def restore(text: str, found: list[str]) -> str:
    for i, value in enumerate(found):
        pattern = re.compile(re.escape(TOKEN_OPEN) + r"\s*" + str(i) + r"\s*" + re.escape(TOKEN_CLOSE))
        text = pattern.sub(lambda _m, v=value: v, text)
    return text


def translate(text: str, lang: str) -> str:
    return translate_many([text], lang)[0]


def translate_many(items: list[str], lang: str) -> list[str]:
    """Пакет фраз одним запросом: /translate_a/t отдаёт массив в том же порядке."""
    guarded: list[str] = []
    founds: list[list[str]] = []
    for text in items:
        part, found = protect(text)
        guarded.append(part)
        founds.append(found)
    qs = "".join("&q=" + urllib.parse.quote(text) for text in guarded)
    url = f"https://translate.googleapis.com/translate_a/t?client=gtx&sl=ru&tl={lang}{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT * 2) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if isinstance(data, dict):
        data = [data.get("trans") or ""]
    values = [str(part or "").strip() for part in data]
    if len(values) != len(items):
        raise ValueError(f"пакет {len(items)} → {len(values)}")
    out: list[str] = []
    for value, found in zip(values, founds):
        if not value:
            raise ValueError("пустой ответ")
        out.append(restore(value, found))
    return out


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, ValueError):
        return {}


def dump(path: Path, table: dict, order: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = {key: table[key] for key in order if key in table}
    text = json.dumps(ordered, ensure_ascii=False, indent=1)
    path.write_bytes((text + "\n").encode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True, choices=("es", "fr", "it"))
    ap.add_argument("--limit", type=int, default=600)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    source = load(I18N / "ru.json")
    if not source:
        print("нет ru.json", file=sys.stderr)
        return 1
    order = list(source)
    target_path = I18N / f"{args.lang}.json"
    target = load(target_path)
    cache = load(CACHE)
    cache_lang = cache.setdefault(args.lang, {})

    todo = [key for key in order if key not in target]
    if args.report:
        print(f"{args.lang}: готово {len(target)} / {len(order)}, в кэше {len(cache_lang)}, "
              f"осталось {len(todo)}")
        return 0

    done = 0
    failed = 0
    for key in todo:
        if key in cache_lang:
            target[key] = cache_lang[key]
            done += 1
    batch = BATCH
    while done < len(todo) and done < args.limit:
        chunk = [key for key in todo if key not in target][:batch]
        if not chunk:
            break
        try:
            values = translate_many(chunk, args.lang)
        except (OSError, ValueError, KeyError, IndexError):
            failed += 1
            if batch > 1:
                batch = max(1, batch // 2)      # большой пакет не прошёл — дробим
                continue
            time.sleep(1.5 * failed)
            if failed >= 6:
                print("сеть не отвечает, прогон остановлен", file=sys.stderr)
                break
            continue
        failed = 0
        if batch < BATCH:
            batch = min(BATCH, batch * 2)
        failed = 0
        for key, value in zip(chunk, values):
            cache_lang[key] = value
            target[key] = value
            done += 1
        dump(target_path, target, order)
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        time.sleep(PAUSE)

    dump(target_path, target, order)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    print(f"{args.lang}: прогон {done}, сбоев {failed}, готово {len(target)} / {len(order)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
