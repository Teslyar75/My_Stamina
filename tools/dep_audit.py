#!/usr/bin/env python3
"""Показывает, какие сторонние модули код импортирует, но где они не заявлены.

    python tools/dep_audit.py                   текст-сводка, код 1 если приложение зависит от незаявленного
    python tools/dep_audit.py --md              markdown-таблица
    python tools/dep_audit.py --json out.json   машиночитаемый отчёт
    python tools/dep_audit.py --allow vosk      счесть модуль необязательным вручную

Зачем: requirements.txt объявляет Pillow/pypdf/fpdf2, а vosk и sounddevice живут
в комментариях. Проверка статическая — ничего не импортирует и не запускает,
поэтому работает и на машине без установленных пакетов.

Импорт внутри `try: ... except ImportError:` считается необязательным: программа
умеет работать без него (фон, распознавание речи). Всё остальное — жёсткая
зависимость, и если её нет в requirements.txt, на чистой машине будет ImportError.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Файлы, чьи строки считаются «заявлено». Приложение и окружение разработки —
# разные списки: ImportError в тесте досадно, ImportError в main.py лишает
# пользователя программы.
REQUIREMENTS_FILES = ("requirements.txt", "requirements-dev.txt")

# Папки, которые не принадлежат приложению (свои окружения, данные, клоны).
SKIP_DIR_NAMES = {
    ".venv", "venv", "env", "__pycache__", ".git", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", "models", "web_star_typing", "node_modules", "build", "dist",
    "_local_shots", "_orion", "graphify-out", ".cursor", ".claude", ".opencode",
}

# Имя модуля при импорте -> имя пакета в requirements.
IMPORT_TO_DIST = {
    "PIL": "Pillow",
    "win32com": "pywin32",
    "win32api": "pywin32",
    "win32con": "pywin32",
    "win32gui": "pywin32",
    "pkg_resources": "setuptools",
    "yaml": "PyYAML",
    "fpdf": "fpdf2",
    "bs4": "beautifulsoup4",
    "sklearn": "scikit-learn",
}

FIRST_PARTY = {"stamina", "main", "tools", "scripts", "tests", "conftest"}


def set_root(path: str) -> Path:
    """Корень репозитория: по умолчанию родитель tools/, можно передать через --repo."""
    global ROOT
    ROOT = Path(path).resolve()
    return ROOT


def repo_module_names() -> set[str]:
    """Имена локальных модулей/пакетов: `import alt_ui_audit` вне пакета — тоже своё."""
    names = {p.stem for p in ROOT.glob("*.py")}
    for path in python_files("stamina", "tools", "scripts"):
        names.add(path.stem)
        if path.name == "__init__.py" and path.parent.name not in SKIP_DIR_NAMES:
            names.add(path.parent.name)
    return names


def declared_requirements() -> set[str]:
    """Имена дистрибутивов из requirements* (без версий, без комментариев)."""
    names: set[str] = set()
    for filename in REQUIREMENTS_FILES:
        req = ROOT / filename
        if not req.exists():
            continue
        for raw in req.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line or line.startswith("-"):
                continue
            for sep in ("===", "==", ">=", "<=", "~=", "!=", ">", "<", "["):
                line = line.split(sep, 1)[0]
            if line.strip():
                names.add(line.strip().lower())
    return names


def python_files(*dirs: str) -> list[Path]:
    out: list[Path] = []
    for name in dirs:
        target = ROOT / name
        if target.is_file():
            out.append(target)
            continue
        if not target.is_dir():
            continue
        for path in target.rglob("*.py"):
            if SKIP_DIR_NAMES.isdisjoint(path.relative_to(ROOT).parts):
                out.append(path)
    return sorted(set(out))


class Visitor(ast.NodeVisitor):
    """Собирает корневые имена импортов и помечает защищённые try/except ImportError."""

    def __init__(self) -> None:
        self.hard: set[str] = set()
        self.optional: set[str] = set()
        self._guarded_depth = 0

    def _add(self, root_name: str | None) -> None:
        if not root_name or root_name in FIRST_PARTY:
            return
        bucket = self.optional if self._guarded_depth else self.hard
        bucket.add(root_name)

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            self._add(alias.name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.level:  # from . import x — локальный пакет
            return
        self._add((node.module or "").split(".")[0])

    def visit_Try(self, node: ast.Try) -> None:  # noqa: N802
        def guards(handler: ast.excepthandler) -> bool:
            if handler.type is None:  # голый except — тоже спасает от ImportError
                return True
            names = {"ImportError", "ModuleNotFoundError"}
            if isinstance(handler.type, ast.Name):
                return handler.type.id in names or handler.type.id in {"Exception", "BaseException"}
            if isinstance(handler.type, ast.Tuple):
                return any(
                    isinstance(elt, ast.Name)
                    and (elt.id in names or elt.id in {"Exception", "BaseException"})
                    for elt in handler.type.elts
                )
            return False

        protects = any(guards(h) for h in node.handlers)
        if protects:
            self._guarded_depth += 1
        self.generic_visit(node)
        if protects:
            self._guarded_depth -= 1


def is_app_file(rel: str) -> bool:
    """Файл входит в то, что запускает пользователь (не tests/ и не tools/)."""
    top = rel.replace("\\", "/").split("/")[0]
    return top == "stamina" or top == "main.py"


def audit(allow: set[str]) -> dict:
    stdlib = set(getattr(sys, "stdlib_module_names", set()))
    declared = declared_requirements()
    local = FIRST_PARTY | repo_module_names()
    hard: dict[str, list[str]] = {}
    optional: dict[str, list[str]] = {}

    for path in python_files("main.py", "stamina", "tools", "scripts", "tests"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        vis = Visitor()
        vis.visit(tree)
        rel = str(path.relative_to(ROOT))
        for name in vis.hard | vis.optional:
            if name in local:
                continue
            target = optional if name in vis.optional else hard
            target.setdefault(name, [])
            if rel not in target[name]:
                target[name].append(rel)

    undeclared = {}
    for name, files in hard.items():
        if name in stdlib or name in local or name.lower() in allow:
            continue
        dist = IMPORT_TO_DIST.get(name, name)
        if dist.lower() in declared or name.lower() in declared:
            continue
        undeclared[name] = {
            "dist": dist,
            "files": files,
            "app_critical": any(is_app_file(f) for f in files),
        }

    return {
        "declared": sorted(declared),
        "third_party_hard": sorted(set(hard) - stdlib - local),
        "optional": sorted(set(optional) - stdlib - local),
        "undeclared": undeclared,
    }


def as_markdown(report: dict) -> str:
    lines = [
        "# Аудит зависимостей",
        "",
        f"Заявлено: {', '.join(report['declared']) or '—'}",
        "",
        f"Жёсткие сторонние импорты: {', '.join(report['third_party_hard']) or '—'}",
        f"Необязательные (в try/except): {', '.join(report['optional']) or '—'}",
        "",
    ]
    if not report["undeclared"]:
        lines.append("**Пропусков нет: каждый жёсткий импорт объявлен или входит в стандартную библиотеку.**")
        return "\n".join(lines)
    lines += ["## Не заявлено", "", "| Модуль | Пакет | Область | Файлы |", "|---|---|---|---|"]
    for name in sorted(report["undeclared"]):
        info = report["undeclared"][name]
        files = ", ".join(info["files"][:6])
        if len(info["files"]) > 6:
            files += f" (+{len(info['files']) - 6})"
        scope = "приложение" if info["app_critical"] else "разработка/инструменты"
        lines.append(f"| `{name}` | {info['dist']} | {scope} | {files} |")
    return "\n".join(lines)


def main() -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", metavar="PATH", help="записать отчёт JSON")
    parser.add_argument("--allow", action="append", default=[], help="считать модуль необязательным")
    parser.add_argument("--md", action="store_true", help="печатать markdown вместо текста")
    parser.add_argument("--repo", default=None, help="корень репозитория (по умолчанию родитель tools/)")
    args = parser.parse_args()

    if args.repo:
        set_root(args.repo)

    report = audit({name.lower() for name in args.allow})

    if args.json:
        Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if args.md:
        print(as_markdown(report))

    missing = report["undeclared"]
    app_missing = [n for n, info in missing.items() if info["app_critical"]]
    dev_missing = [n for n in missing if n not in app_missing]
    print(
        f"dep_audit: заявлено {len(report['declared'])}, "
        f"жёстких сторонних {len(report['third_party_hard'])}, "
        f"необязательных {len(report['optional'])}, "
        f"не заявлено в приложении {len(app_missing)}, в инструментах {len(dev_missing)}"
    )
    for name in sorted(app_missing):
        files = missing[name]["files"]
        print(f"  ! {name} ({missing[name]['dist']}) -> {', '.join(files[:4])}"
              + (f" и ещё {len(files) - 4}" if len(files) > 4 else ""))
    for name in sorted(dev_missing):
        files = missing[name]["files"]
        print(f"  ~ {name} ({missing[name]['dist']}) -> {', '.join(files[:3])}"
              + (f" и ещё {len(files) - 3}" if len(files) > 3 else ""))
    return 1 if app_missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
