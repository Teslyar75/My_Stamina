"""Проверка переводов интерфейса.

python tools/i18n_check.py           — отчёт: ключи из кода, которых нет в ru.json; лишние ключи;
                                        для uk/en/de — нет перевода, лишние, расхождение {0}-подстановок
python tools/i18n_check.py --fix-ru  — пересобрать ru.json по коду (все вызовы t("…"))
python tools/i18n_check.py --missing de > de_missing.json — непереведённые ключи языка (для перевода)
Код возврата 1, если чего-то не хватает (удобно для CI).
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "stamina"
I18N = PKG / "i18n"
PH = re.compile(r"\{[^{}]*\}")


def code_keys() -> dict:
    """{ключ: 'файл:строка'} для всех t("…") (и псевдонимов из `import t as …`)."""
    out = {}
    for p in sorted(PKG.rglob("*.py")):
        src = p.read_text(encoding="utf-8")
        names = {"t"} if "from stamina.i18n import t\n" in src else set()
        names |= set(re.findall(r"from stamina\.i18n import t as (\w+)", src))
        if p.parent.name == "i18n":
            continue
        for n in ast.walk(ast.parse(src)):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in names
                    and n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)):
                out.setdefault(n.args[0].value, f"{p.relative_to(ROOT).as_posix()}:{n.lineno}")
    return out


def load(lang: str) -> dict:
    p = I18N / f"{lang}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def placeholders(s: str) -> list:
    return sorted(PH.findall(s.replace("{{", "").replace("}}", "")))


def main() -> int:
    keys = code_keys()
    if "--fix-ru" in sys.argv:
        (I18N / "ru.json").write_text(json.dumps({k: k for k in sorted(keys)}, ensure_ascii=False, indent=1)
                                      + "\n", encoding="utf-8")
        print("ru.json:", len(keys), "ключей")
        return 0
    if "--missing" in sys.argv:
        lang = sys.argv[sys.argv.index("--missing") + 1]
        tr = load(lang)
        print(json.dumps({k: "" for k in sorted(keys) if not tr.get(k)}, ensure_ascii=False, indent=1))
        return 0
    bad = 0
    ru = load("ru")
    miss = [k for k in keys if k not in ru]
    print(f"код: {len(keys)} ключей; ru.json: {len(ru)}")
    for k in miss:
        print(f"  нет в ru.json: {keys[k]}  {k[:60]!r}")
    for k in sorted(set(ru) - set(keys)):
        print(f"  лишний в ru.json: {k[:60]!r}")
    bad += len(miss)
    langs = sorted(p.stem for p in I18N.glob("*.json") if p.stem != "ru")
    for lang in langs:
        tr = load(lang)
        no = [k for k in keys if not tr.get(k)]
        extra = [k for k in tr if k not in keys]
        ph = [k for k in keys if tr.get(k) and placeholders(tr[k]) != placeholders(k)]
        print(f"{lang}: переведено {len(keys) - len(no)}/{len(keys)}, лишних {len(extra)}, "
              f"ошибок подстановок {len(ph)}")
        for k in no[:15]:
            print(f"  нет перевода: {keys[k]}  {k[:60]!r}")
        if len(no) > 15:
            print(f"  … и ещё {len(no) - 15}")
        for k in ph:
            print(f"  подстановки {placeholders(k)} ≠ {placeholders(tr[k])}: {k[:60]!r}")
        bad += len(no) + len(ph)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
