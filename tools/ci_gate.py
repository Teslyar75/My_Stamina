#!/usr/bin/env python3
"""Единая точка проверки корабля: тесты + готовые аудиты одним запуском.

    python tools/ci_gate.py                 блокирующие шаги, сводка в stdout
    python tools/ci_gate.py --list          показать шаги без запуска
    python tools/ci_gate.py --full          добавить требовательные к экрану аудиты
    python tools/ci_gate.py --only dep      запустить только совпадающие по имени шаги
    python tools/ci_gate.py --md gate_report.md --json gate_report.json
    python tools/ci_gate.py --strict        провальный advisory-шаг тоже делает ошибкой

Зачем: в репозитории уже есть contrast_audit.py, i18n_check.py, alt_ui_audit.py и
более тысячи тестов — но в CI не запускается ни один из них (в workflows только
changelog_notes.py и «процесс жив 20 секунд»). Скрипт ничего не проверяет сам; он
собирает существующие проверки в один отчёт с кодом возврата, удобным для CI.

Шаги, которым нужен дисплей (Tk, снимки экранов), помечены needs_display и по
умолчанию не блокируют: на headless-машине они падают по внешней причине, а не
из-за правки.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def build_steps() -> list[dict]:
    """Шаги по порядку. tier: 'block' обязателен, 'advisory' только докладывает в отчёт."""
    return [
        {
            "name": "pytest (все тесты)",
            "cmd": [sys.executable, "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider"],
            "tier": "block",
            "needs_display": True,
            "full_only": False,
            "why": "регрессия проходит молча, если тесты не запускает вообще никто",
        },
        {
            "name": "contrast_audit (WCAG по скинам)",
            "cmd": [sys.executable, "tools/contrast_audit.py"],
            "tier": "block",
            "needs_display": False,
            "full_only": False,
            "why": "держит контраст текста не ниже 4.5:1 по всем семи скинам",
        },
        {
            "name": "i18n_check (переводы интерфейса)",
            "cmd": [sys.executable, "tools/i18n_check.py"],
            "tier": "block",
            "needs_display": False,
            "full_only": False,
            "why": "каждый вызов t(...) должен иметь перевод на все четыре языка",
        },
        {
            "name": "dep_audit (заявленные зависимости)",
            "cmd": [sys.executable, "tools/dep_audit.py"],
            "tier": "block",
            "needs_display": False,
            "full_only": False,
            "why": "жёсткий импорт без requirements = ImportError на чистой машине",
        },
        {
            "name": "alt_ui_audit (паритет классика/альт-вид)",
            "cmd": [sys.executable, "tools/alt_ui_audit.py"],
            "tier": "advisory",
            "needs_display": True,
            "full_only": True,
            "why": "нужен Tk и реальный экран; дорого по времени",
        },
    ]


def run_step(step: dict, repo: Path, timeout: int) -> dict:
    started = time.time()
    try:
        proc = subprocess.run(
            step["cmd"], cwd=str(repo), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        code, tail = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError:
        code, tail = 127, "команда не найдена"
    except subprocess.TimeoutExpired:
        code, tail = 124, f"таймаут {timeout} c"
    return {
        **step,
        "exit": code,
        "seconds": round(time.time() - started, 1),
        "output_tail": tail.strip().splitlines()[-8:],
    }


def render_markdown(results: list[dict], ok: bool) -> str:
    lines = ["# Отчёт проверки корабля", "", "| Шаг | Уровень | Код | Время | Итог |",
             "|---|---|---|---|---|"]
    for r in results:
        verdict = "прошёл" if r["exit"] == 0 else (
            "провал (блокирующий)" if r["tier"] == "block" else "замечание")
        lines.append(f"| {r['name']} | {r['tier']} | {r['exit']} | {r['seconds']} c | {verdict} |")
    lines.append("")
    lines.append("**Итог: " + ("зелёный" if ok else "красный") + "**")
    fails = [r for r in results if r["exit"] != 0]
    if fails:
        lines += ["", "## Хвосты вывода", ""]
        for r in fails:
            lines.append(f"### {r['name']}")
            lines.append("```")
            lines.extend(r["output_tail"])
            lines.append("```")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent),
                        help="корень репозитория (по умолчанию — родитель tools/)")
    parser.add_argument("--full", action="store_true", help="включить шаги, требующие экрана")
    parser.add_argument("--strict", action="store_true", help="advisory-провал тоже красит запуск")
    parser.add_argument("--timeout", type=int, default=1800, help="лимит на один шаг, секунд")
    parser.add_argument("--md", metavar="PATH", help="записать markdown-отчёт")
    parser.add_argument("--json", metavar="PATH", help="записать JSON-отчёт")
    parser.add_argument("--list", action="store_true", help="показать шаги и выйти")
    parser.add_argument("--only", metavar="ПОДСТРОКА", action="append", default=[],
                        help="запустить только шаги, имя которых содержит подстроку")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    steps = build_steps()
    if args.only:
        steps = [s for s in steps if any(needle.lower() in s["name"].lower() for needle in args.only)]
    if args.list:
        for s in steps:
            flags = []
            if s["tier"] == "advisory":
                flags.append("advisory")
            if s["needs_display"]:
                flags.append("нужен дисплей")
            if s["full_only"]:
                flags.append("только --full")
            print(f"- {s['name']}: {' '.join(s['cmd'])}"
                  + (f"  [{', '.join(flags)}]" if flags else "") + f"\n    {s['why']}")
        return 0

    results = []
    for step in steps:
        if step["full_only"] and not args.full:
            continue
        print(f">> {step['name']} ...", flush=True)
        res = run_step(step, repo, args.timeout)
        results.append(res)
        print(f"   exit={res['exit']} за {res['seconds']} c", flush=True)
        if res["exit"] != 0:
            for line in res["output_tail"]:
                print(f"   | {line}")

    blocking_fail = any(r["exit"] and r["tier"] == "block" for r in results)
    advisory_fail = any(r["exit"] and r["tier"] == "advisory" for r in results)
    ok = not blocking_fail and not (args.strict and advisory_fail)

    if args.md:
        Path(args.md).write_text(render_markdown(results, ok), encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nГАТ: " + ("зелёный" if ok else "красный"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
