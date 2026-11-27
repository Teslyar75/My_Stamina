#!/usr/bin/env python3
"""Детерминированное деление файлов tests/ на шарды для CI без pytest-xdist.

    python tools/pytest_shard.py --shards 4 --shard 1

Печатает один путь к файлу тестов на строку — список можно сразу передать pytest.
Вес файла — число функций test_* из AST, разложение жадное по убыванию веса
(largest processing time first), поэтому результат не зависит от порядка файлов
и не использует случайность.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def count_tests(path: Path) -> int:
    """Посчитать тестовые функции в файле, не импортируя тесты."""
    source = path.read_text(encoding="utf-8-sig", errors="replace")
    tree = ast.parse(source, filename=str(path))
    count = 0
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            count += node.name.startswith("test_")
        elif isinstance(node, ast.ClassDef):
            count += sum(
                child.name.startswith("test_")
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
    return count


def make_shards(total: int, tests_dir: Path) -> list[list[Path]]:
    """Разложить файлы тестов по шардам, балансируя число тест-функций."""
    files = sorted(tests_dir.glob("test_*.py"))
    if not files:
        raise SystemExit(f"в {tests_dir} нет файлов test_*.py")

    items = [(path, max(1, count_tests(path))) for path in files]
    items.sort(key=lambda item: (-item[1], item[0].as_posix()))

    buckets: list[list[Path]] = [[] for _ in range(total)]
    loads = [0] * total
    for path, weight in items:
        index = min(range(total), key=lambda idx: (loads[idx], idx))
        buckets[index].append(path)
        loads[index] += weight

    for bucket in buckets:
        bucket.sort(key=lambda path: path.as_posix())
    return buckets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shards", type=int, required=True, help="сколько шардов сделать")
    parser.add_argument("--shard", type=int, required=True, help="номер шарда, от 1")
    parser.add_argument("--tests-dir", type=Path, default=ROOT / "tests")
    parser.add_argument("--summary", action="store_true", help="вес каждого шарда в stderr")
    args = parser.parse_args(argv)

    if args.shards < 1:
        parser.error("--shards должен быть >= 1")
    if not 1 <= args.shard <= args.shards:
        parser.error("--shard должен быть от 1 до --shards")

    buckets = make_shards(args.shards, args.tests_dir)
    if args.summary:
        weights = [sum(max(1, count_tests(path)) for path in bucket) for bucket in buckets]
        print("шарды:", ", ".join(f"{i + 1}: {w}" for i, w in enumerate(weights)),
              file=sys.stderr)
    for path in buckets[args.shard - 1]:
        print(path.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
