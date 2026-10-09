"""Одноразовый (и повторяемый) инструмент: обернуть русские строки интерфейса в t("…").

python tools/i18n_extract.py            — переписать исходники и обновить stamina/i18n/ru.json
python tools/i18n_extract.py --dry-run  — только показать, сколько строк найдено

Ключ = исходная русская фраза (как в gettext): нет перевода → показывается она же.
f-строки превращаются в t("Уровень {0}").format(level). Пропускаются: докстроки, регулярные
выражения, пути, наборы букв для уроков, словарь для генерации упражнений, скрипты PowerShell.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "stamina"
CY = re.compile("[А-Яа-яЁёІіЇїЄєҐґ]")
SKIP_FILES = {"layouts.py", "i18n/__init__.py", "text_processing.py", "textmap.py"}
SKIP_VALUES = {"Рабочий стол", "OneDrive/Рабочий стол", "OneDrive/Документы"}


def skip_value(path: Path, s: str) -> bool:
    if s in SKIP_VALUES or not CY.search(s):
        return True
    if s.startswith("^") or "[^" in s or "\\b" in s or "$ErrorActionPreference" in s:
        return True
    if len(s) > 400 and s.count("\n") > 3 and "{" not in s:     # словари слов, скрипты
        return True
    if re.fullmatch(r"[а-яё0-9]+", s) and path.name == "missions.py":   # наборы букв уроков
        return True
    return False


def docstring_ids(tree) -> set:
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body:
            b = n.body[0]
            if isinstance(b, ast.Expr) and isinstance(b.value, (ast.Constant, ast.JoinedStr)):
                out.add(id(b.value))
    return out


def already_wrapped(tree, fn: str) -> set:
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == fn:
            for a in n.args:
                out.add(id(a))
    return out


def skip_parent_ids(tree, path: Path) -> set:
    """Узлы, внутри которых строки не трогаем (списки слов-подсказок в quiz.py и т.п.)."""
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and path.name == "quiz.py":
            names = [t.id for t in n.targets if isinstance(t, ast.Name)]
            if any(x.isupper() for x in names) and isinstance(n.value, (ast.List, ast.Tuple, ast.Set, ast.Call)):
                for m in ast.walk(n.value):
                    out.add(id(m))
        if isinstance(n, ast.JoinedStr):
            for m in ast.walk(n):
                if m is not n:
                    out.add(id(m))
        if isinstance(n, ast.FormattedValue) and n.format_spec is not None:
            for m in ast.walk(n.format_spec):
                out.add(id(m))
    return out


def fstring_template(node: ast.JoinedStr, src_lines):
    tpl, args = [], []
    for v in node.values:
        if isinstance(v, ast.Constant):
            tpl.append(v.value.replace("{", "{{").replace("}", "}}"))
        else:
            spec = ""
            if v.format_spec is not None:
                if not all(isinstance(x, ast.Constant) for x in v.format_spec.values):
                    return None
                spec = ":" + "".join(x.value for x in v.format_spec.values)
            conv = "" if v.conversion == -1 else "!" + chr(v.conversion)
            seg = ast.get_source_segment("".join(src_lines), v.value)
            if seg is None or "\n" in seg:
                return None
            tpl.append("{%d%s%s}" % (len(args), conv, spec))
            args.append(seg)
    return "".join(tpl), args


def offsets(src: str):
    starts, pos = [0], 0
    for line in src.splitlines(keepends=True):
        pos += len(line.encode("utf-8"))
        starts.append(pos)
    return starts


def process(path: Path, keys: dict, dry: bool) -> int:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
           {a.arg for n in ast.walk(tree) if isinstance(n, ast.arguments) for a in n.args + n.kwonlyargs}
    fn = "t" if ("t" not in used or "_t" in used and False) else "_t"
    if "_t" in used and fn == "_t":
        fn = "tr_"
    imported = re.search(r"^from stamina\.i18n import (\w+)(?: as (\w+))?", src, re.M)
    if imported:
        fn = imported.group(2) or imported.group(1)
    docs, wrapped, inner = docstring_ids(tree), already_wrapped(tree, fn), skip_parent_ids(tree, path)
    repl = []
    lines = src.splitlines(keepends=True)
    for n in ast.walk(tree):
        if id(n) in docs or id(n) in wrapped or id(n) in inner:
            continue
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            if skip_value(path, n.value):
                continue
            keys[n.value] = n.value
            repl.append((n, "%s(%s)" % (fn, json.dumps(n.value, ensure_ascii=False))))
        elif isinstance(n, ast.JoinedStr):
            text = "".join(v.value for v in n.values if isinstance(v, ast.Constant))
            if not CY.search(text) or any(skip_value(path, v.value) and CY.search(v.value)
                                          for v in n.values if isinstance(v, ast.Constant)):
                continue
            res = fstring_template(n, lines)
            if res is None:
                print("  ! пропущена f-строка", path.name, n.lineno)
                continue
            tpl, args = res
            keys[tpl] = tpl
            repl.append((n, "%s(%s).format(%s)" % (fn, json.dumps(tpl, ensure_ascii=False), ", ".join(args))))
    if dry or not repl:
        return len(repl)
    b = src.encode("utf-8")
    st = offsets(src)
    spans = []
    for n, new in repl:
        a = st[n.lineno - 1] + n.col_offset
        z = st[n.end_lineno - 1] + n.end_col_offset
        spans.append((a, z, new))
    spans.sort(reverse=True)
    for a, z, new in spans:
        b = b[:a] + new.encode("utf-8") + b[z:]
    out = b.decode("utf-8")
    if not imported:
        imp = "from stamina.i18n import t\n" if fn == "t" else "from stamina.i18n import t as %s\n" % fn
        m = re.search(r"^from __future__ import [^\n]+\n", out, re.M)
        if m:
            out = out[:m.end()] + "\n" + imp + out[m.end():]
        else:
            tr = ast.parse(out)
            line = tr.body[0].end_lineno if tr.body and isinstance(tr.body[0], ast.Expr) else 0
            ls = out.splitlines(keepends=True)
            out = "".join(ls[:line]) + ("\n" if line else "") + imp + "".join(ls[line:])
    ast.parse(out)
    path.write_text(out, encoding="utf-8")
    return len(repl)


def main() -> None:
    dry = "--dry-run" in sys.argv
    ru_path = PKG / "i18n" / "ru.json"
    keys = json.loads(ru_path.read_text(encoding="utf-8")) if ru_path.exists() else {}
    total = 0
    for p in sorted(PKG.rglob("*.py")):
        rel = p.relative_to(PKG).as_posix()
        if rel in SKIP_FILES or p.name in SKIP_FILES:
            continue
        n = process(p, keys, dry)
        if n:
            print(f"{n:4d}  {rel}")
        total += n
    print("всего:", total, "ключей:", len(keys))
    if not dry:
        ru_path.write_text(json.dumps(dict(sorted(keys.items())), ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    main()
