"""Проверка уроков грамматики: схема, соответствие индексу, корректность упражнений.

python tools/grammar_lessons_check.py            — проверить все написанные уроки
python tools/grammar_lessons_check.py 1-23       — только диапазон юнитов
Код возврата 1, если есть ошибки. Урок без файла — не ошибка (курс пишется порциями),
но печатается списком «ещё не написан».
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from stamina.english.grammar import lessons as L  # noqa: E402

ALLOWED_TYPES = {"choice", "gap", "translate"}
MIN_BLOCKS, MAX_BLOCKS = 3, 7
MIN_EXAMPLES, MAX_EXAMPLES = 3, 8
MIN_EX, MAX_EX = 6, 12
CYRILLIC = re.compile(r"[А-Яа-яЁё]")
LATIN = re.compile(r"[A-Za-z]")
BANNED = ("**", "##", "__", "```")


def check_lesson(n: int, info: dict) -> list[str]:
    errs: list[str] = []
    p = L.lesson_path(n)
    if not p.exists():
        return []
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [f"не читается JSON ({exc})"]

    for key in ("n", "level", "module", "title", "en", "summary", "can_do", "theory",
                "examples", "traps", "exercises"):
        if key not in d:
            errs.append(f"нет поля {key!r}")
    if errs:
        return errs

    if int(d["n"]) != n:
        errs.append(f"n={d['n']}, ожидалось {n}")
    if d["level"] != info["level"]:
        errs.append(f"level={d['level']!r}, в индексе {info['level']!r}")
    if d["module"] != info["module"]:
        errs.append(f"module={d['module']!r}, в индексе {info['module']!r}")
    if d["title"] != info["title"]:
        errs.append(f"title={d['title']!r}, в индексе {info['title']!r}")
    if d["en"] != info["en"]:
        errs.append(f"en={d['en']!r}, в индексе {info['en']!r}")
    if not (10 <= len(d["summary"]) <= 220):
        errs.append("summary: нужно 10–220 символов")
    if not (2 <= len(d["can_do"]) <= 5):
        errs.append("can_do: 2–5 пунктов")

    theory = d["theory"]
    if not (MIN_BLOCKS <= len(theory) <= MAX_BLOCKS):
        errs.append(f"theory: {len(theory)} блоков, нужно {MIN_BLOCKS}–{MAX_BLOCKS}")
    for i, b in enumerate(theory):
        if not isinstance(b, dict):
            errs.append(f"theory[{i}] не объект")
            continue
        if not str(b.get("h") or "").strip():
            errs.append(f"theory[{i}]: пустой h")
        if len(str(b.get("p") or "")) < 40:
            errs.append(f"theory[{i}]: слишком короткое p")
        for extra in ("formula", "table"):
            if extra not in b:
                continue
            if extra == "formula" and not str(b["formula"]).strip():
                errs.append(f"theory[{i}]: пустой formula")
            if extra == "table":
                t = b["table"]
                if not isinstance(t, dict) or len(t.get("head") or []) < 2 or not t.get("rows"):
                    errs.append(f"theory[{i}]: table нуждается в head (2+) и rows")
                else:
                    w = len(t["head"])
                    for r in t["rows"]:
                        if not isinstance(r, list) or len(r) != w:
                            errs.append(f"theory[{i}]: строка таблицы не по {w} колонкам: {r!r}")
                            break
    if not any(b.get("table") or b.get("formula") for b in theory if isinstance(b, dict)):
        errs.append("theory: нужен хотя бы один formula или table")

    if not (MIN_EXAMPLES <= len(d["examples"]) <= MAX_EXAMPLES):
        errs.append(f"examples: {len(d['examples'])}, нужно {MIN_EXAMPLES}–{MAX_EXAMPLES}")
    for i, e in enumerate(d["examples"]):
        en, ru = str(e.get("en") or ""), str(e.get("ru") or "")
        if not LATIN.search(en):
            errs.append(f"examples[{i}]: нет английского текста")
        if not CYRILLIC.search(ru):
            errs.append(f"examples[{i}]: нет русского перевода")
        if len(en) > 90:
            errs.append(f"examples[{i}]: слишком длинное предложение ({len(en)} символов)")

    if not (2 <= len(d["traps"]) <= 4):
        errs.append("traps: 2–4 штуки")
    for i, t in enumerate(d["traps"]):
        for key in ("bad", "good", "why"):
            if not str(t.get(key) or "").strip():
                errs.append(f"traps[{i}]: пустое поле {key}")
        if L.normalize(str(t.get("bad"))) == L.normalize(str(t.get("good"))):
            errs.append(f"traps[{i}]: bad совпадает с good")

    exs = d["exercises"]
    if not (MIN_EX <= len(exs) <= MAX_EX):
        errs.append(f"exercises: {len(exs)}, нужно {MIN_EX}–{MAX_EX}")
    kinds = {e.get("type") for e in exs if isinstance(e, dict)}
    if "choice" not in kinds:
        errs.append("exercises: нужен хотя бы один choice")
    if not ({"gap", "translate"} & kinds):
        errs.append("exercises: нужен хотя бы один gap или translate")
    choice_n = 0
    for i, e in enumerate(exs):
        if not isinstance(e, dict):
            errs.append(f"exercises[{i}] не объект")
            continue
        kind = e.get("type")
        if kind not in ALLOWED_TYPES:
            errs.append(f"exercises[{i}]: неизвестный тип {kind!r}")
            continue
        q = str(e.get("q") or "")
        if len(q) < 8:
            errs.append(f"exercises[{i}]: пустой или слишком короткий q")
        if not str(e.get("why") or "").strip():
            errs.append(f"exercises[{i}]: нет объяснения why")
        if CYRILLIC.search(q) and kind != "translate":
            errs.append(f"exercises[{i}]: в задании кириллица без translate")
        if kind == "choice":
            choice_n += 1
            opts = e.get("options")
            a = e.get("a")
            if not isinstance(opts, list) or len(opts) < 2:
                errs.append(f"exercises[{i}]: options — список из 2+")
                continue
            if not isinstance(a, int) or not 0 <= a < len(opts):
                errs.append(f"exercises[{i}]: a вне диапазона options")
            if len(set(map(str, opts))) != len(opts):
                errs.append(f"exercises[{i}]: повторяющиеся options")
            if any(CYRILLIC.search(str(o)) for o in opts):
                errs.append(f"exercises[{i}]: кириллица в options")
            if "___" not in q:
                errs.append(f"exercises[{i}]: в q нет пропуска ___")
        else:
            ans = e.get("a")
            if not isinstance(ans, list) or not ans:
                errs.append(f"exercises[{i}]: a — непустой список вариантов")
            else:
                if any(not str(x).strip() for x in ans):
                    errs.append(f"exercises[{i}]: пустой вариант ответа")
                if any(CYRILLIC.search(str(x)) for x in ans):
                    errs.append(f"exercises[{i}]: ответ должен быть по-английски")
            if kind == "gap" and "___" not in q:
                errs.append(f"exercises[{i}]: в gap-задании нет ___")
            if kind == "translate" and not CYRILLIC.search(q):
                errs.append(f"exercises[{i}]: translate без русского задания")
    if exs and choice_n == 0:
        errs.append("exercises: ни одного choice")

    for field in ("summary", "title", "en"):
        if any(b in str(d[field]) for b in BANNED):
            errs.append(f"{field}: markdown-разметка не нужна")
    for b in theory:
        if isinstance(b, dict) and any(x in str(b.get("p") or "") for x in BANNED):
            errs.append("theory: markdown-разметка не нужна")
    return errs


def parse_range(argv: list[str]) -> tuple[int, int]:
    for a in argv:
        m = re.fullmatch(r"(\d{1,3})(?:-(\d{1,3}))?", a)
        if m:
            lo = int(m.group(1))
            return lo, int(m.group(2) or lo)
    return 1, L.TOTAL_UNITS


def main() -> int:
    lo, hi = parse_range(sys.argv[1:])
    units = [u for u in L.units() if lo <= int(u["n"]) <= hi]
    missing, bad, ok = [], [], 0
    for u in units:
        n = int(u["n"])
        errs = check_lesson(n, u)
        if not L.lesson_exists(n):
            missing.append(n)
        elif errs:
            bad.append((n, errs))
        else:
            ok += 1
    print(f"проверено юнитов: {len(units)}; готово: {ok}; не написано: {len(missing)}; с ошибками: {len(bad)}")
    if missing:
        print("  ещё не написаны:", ", ".join(map(str, missing)))
    for n, errs in bad:
        print(f"  u{n:03d}:")
        for e in errs:
            print(f"    - {e}")
    return 1 if bad else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
