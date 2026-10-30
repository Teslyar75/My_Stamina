"""Перевод документа на EN/DE: офлайн через Argos (пакет языка качается по требованию),
иначе — сетевой запасной путь из `translator.py`.

Markdown не ломаем: каждая строка переводится без своего маркера («# », «- », «> »),
маркер возвращается на место. Пустые строки и строки-код остаются как есть.
Без tkinter — логика проверяется тестами с подменённым движком.
"""
from __future__ import annotations

import threading

from stamina import langdetect, mdlite

TARGETS = ("en", "de")
CHUNK = 800                       # символов на один сетевой запрос


# -- Argos ----------------------------------------------------------------------
def argos_available() -> bool:
    try:
        import argostranslate.translate  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _argos_pairs() -> set[tuple[str, str]]:
    from argostranslate import package
    return {(p.from_code, p.to_code) for p in package.get_installed_packages()}


def argos_route(sl: str, tl: str) -> list[tuple[str, str]]:
    """Какие пакеты нужны: прямой sl→tl, иначе через английский (ru→en→de)."""
    if sl == tl:
        return []
    if "en" in (sl, tl):
        return [(sl, tl)]
    return [(sl, "en"), ("en", tl)]


def argos_ensure(sl: str, tl: str, progress=None) -> None:
    """Докачать недостающие пакеты Argos (один раз, дальше всё офлайн)."""
    from argostranslate import package
    have = _argos_pairs()
    need = [p for p in argos_route(sl, tl) if p not in have]
    if not need:
        return
    package.update_package_index()
    index = package.get_available_packages()
    for a, b in need:
        pkg = next((p for p in index if p.from_code == a and p.to_code == b), None)
        if pkg is None:
            raise LookupError(f"argos: no package {a}->{b}")
        if progress:
            progress(f"{a}→{b}")
        package.install_from_path(pkg.download())


def _argos_line(text: str, sl: str, tl: str) -> str:
    from argostranslate import translate
    out = text
    for a, b in argos_route(sl, tl):
        out = translate.translate(out, a, b)
    return out


# -- сеть (запасной путь) ---------------------------------------------------------
def _net_batch(lines: list[str], sl: str, tl: str) -> list[str]:
    from stamina import translator
    joined = "\n".join(lines)
    for fn in (translator._google, translator._mymemory):
        try:
            res = fn(joined, sl, tl).split("\n")
            if len(res) == len(lines):
                return res
            if len(lines) == 1:
                return [" ".join(res)]
        except Exception:  # noqa: BLE001
            continue
    if len(lines) > 1:                       # разошлось число строк — по одной
        return [_net_batch([x], sl, tl)[0] for x in lines]
    raise OSError("translation failed")


# -- общий проход по Markdown ------------------------------------------------------
def split_line(line: str) -> tuple[str, str]:
    """(маркер, текст): «- пункт» → («- », «пункт»)."""
    _kind, n = mdlite.block_of(line)
    return line[:n], line[n:]


def translate_md(text: str, tl: str, *, sl: str = "", engine=None, progress=None) -> str:
    """Перевести Markdown-текст построчно. engine(lines, sl, tl) -> lines."""
    sl = sl or langdetect.detect(text) or "ru"
    if sl in ("und", ""):
        sl = "ru"
    lines = text.split("\n")
    jobs = []                                   # (индекс, маркер, текст)
    in_code = False
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        mark, body = split_line(line)
        if in_code or not body.strip():
            continue
        jobs.append((i, mark, body))
    engine = engine or pick_engine(sl, tl)
    batch: list = []
    size = 0
    done = 0

    def flush():
        nonlocal batch, size, done
        if not batch:
            return
        res = engine([b for _i, _m, b in batch], sl, tl)
        for (i, mark, _b), r in zip(batch, res):
            lines[i] = mark + r.strip()
        done += len(batch)
        if progress:
            progress(done, len(jobs))
        batch, size = [], 0

    for job in jobs:
        if size + len(job[2]) > CHUNK:
            flush()
        batch.append(job)
        size += len(job[2])
    flush()
    return "\n".join(lines)


def pick_engine(sl: str, tl: str):
    """Argos, если библиотека стоит (пакеты докачает), иначе сеть."""
    if argos_available():
        try:
            argos_ensure(sl, tl)
            return lambda ls, a, b: [_argos_line(x, a, b) for x in ls]
        except Exception:  # noqa: BLE001
            pass
    return _net_batch


def engine_name() -> str:
    return "argos" if argos_available() else "online"


def translate_in_background(text: str, tl: str, *, on_done, on_progress=None) -> threading.Thread:
    """Фон: on_done(result | None, error) и on_progress(done, total) — из потока."""
    def work():
        try:
            out = translate_md(text, tl, progress=on_progress)
        except Exception as exc:  # noqa: BLE001
            on_done(None, str(exc) or exc.__class__.__name__)
            return
        on_done(out, "")

    th = threading.Thread(target=work, daemon=True, name="doc-translate")
    th.start()
    return th
