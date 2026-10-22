"""Аудит паритета «классический ↔ альтернативный вид» (ALT UI, «Пульт-кабина»).

Перечисляет программно все элементы управления каждого экрана и каждой вкладки
(HudButton, Button, Checkbutton, Radiobutton, Menubutton/OptionMenu, Scale, Entry,
Spinbox, Combobox) в классическом виде и проверяет, что в alt каждый из них
доступен: виджет на месте и целиком лежит в окне (по ширине) и в прокручиваемой
области (по высоте) — или убран в список «⋯ ЕЩЁ» своей строки.

    python tools/alt_ui_audit.py                 → таблица markdown в stdout
    python tools/alt_ui_audit.py --md FILE       → таблица в файл
    python tools/alt_ui_audit.py --one LAYOUT SKIN WxH JSON   (внутренний режим)

Каждый вид собирается в отдельном процессе с временным APPDATA и временной
папкой пилотов — данные пилота не трогаются.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIZES = ("1440x800", "1280x720", "1024x768")
CTRL = ("Button", "Checkbutton", "Radiobutton", "Menubutton", "Scale", "Entry", "Spinbox",
        "TButton", "TCheckbutton", "TRadiobutton", "TMenubutton", "TCombobox", "TScale", "TEntry", "TSpinbox")


def _label(w) -> str:
    t = getattr(w, "_text", None)
    if t is None:
        try:
            t = w.cget("text")
        except Exception:  # noqa: BLE001
            t = ""
    t = " ".join(str(t).split())
    return t or w.winfo_class()


def _kind(w):
    from stamina.hud import HudButton
    if isinstance(w, HudButton):
        return "HudButton"
    c = w.winfo_class()
    return c if c in CTRL else None


def _scroll_owner(w, stop):
    """Есть ли у виджета предок-Canvas со своей прокруткой (списки внутри экрана)."""
    x = w.master
    while x is not None and x is not stop:
        try:
            if x.winfo_class() == "Canvas" and (str(x.cget("yscrollcommand")) or str(x.cget("xscrollcommand"))):
                return True
        except Exception:  # noqa: BLE001
            pass
        x = x.master
    return False


def _managed(w, stop) -> bool:
    x = w
    while x is not None and x is not stop:
        try:
            if not x.winfo_manager():
                return False
        except Exception:  # noqa: BLE001
            return False
        x = x.master
    return True


def collect_one(layout: str, skin: str, size: str) -> dict:
    tmp = tempfile.mkdtemp(prefix="stamina_audit_")
    os.environ["APPDATA"] = tmp
    sys.path.insert(0, ROOT)
    from pathlib import Path
    from stamina import pilots, storage
    pilots.reset_root(Path(tmp))
    storage.DEFAULT_SETTINGS.update(ui_layout=layout, skin=skin, living_space="off", idle_minutes=0)
    from stamina.cockpit import Cockpit
    from stamina import alt_ui
    app = Cockpit()
    w, h = map(int, size.split("x"))
    app.geometry(f"{w}x{h}+0+0")
    app.update()
    names = list(app.screens) + [n for n in getattr(app, "_factories", {}) if n not in app.screens]
    out = {"layout": layout, "skin": skin, "size": size, "controls": [], "chrome": [],
           "window": f"{app.winfo_width()}x{app.winfo_height()}"}
    view = getattr(app, "_alt_view", None)
    for name in names:
        try:
            app.show(name)
        except Exception as e:  # noqa: BLE001
            out["controls"].append({"screen": name, "tab": "", "kind": "ERROR", "text": repr(e), "ok": False, "why": "show"})
            continue
        app.update()
        scr = app.screens.get(name)
        if scr is None:
            continue
        tabs = list(scr.tab_keys()) if hasattr(scr, "tab_keys") and hasattr(scr, "show_tab") else [""]
        seen, unseen = set(), {}
        for tab in tabs or [""]:
            if tab:
                scr.show_tab(tab)
            app.update()
            if layout == "alt":
                alt_ui.refresh_screen(app)
                app.update()
            hidden = {id(b) for _t, b in alt_ui.hidden_commands(scr)} if layout == "alt" else set()
            cont = view.canvas if view is not None else app.content
            inner = view.inner if view is not None else app.content
            cw = cont.winfo_width()
            ch = max(inner.winfo_height(), cont.winfo_height()) if view is not None else cont.winfo_height()
            td = getattr(scr, "tabs", None)
            if tab and isinstance(td, dict) and tab in td:
                ent = td[tab]
                panel, only_managed = (ent[0] if isinstance(ent, (tuple, list)) else ent), False
            else:
                panel, only_managed = scr, True
            stack = [panel]
            while stack:
                x = stack.pop()
                stack.extend(x.winfo_children())
                k = _kind(x)
                if k is None or getattr(x, "_alt_more", False):
                    continue
                if id(x) in seen:
                    continue
                rec = {"screen": name, "tab": tab, "kind": k, "text": _label(x)}
                if only_managed and id(x) not in hidden and not _managed(x, scr):
                    unseen.setdefault(id(x), dict(rec, tab="", ok=False, why="скрыт"))
                    continue
                seen.add(id(x))
                if id(x) in hidden:
                    rec.update(ok=True, why="ещё")
                elif not _managed(x, scr):
                    rec.update(ok=False, why="скрыт")
                elif _scroll_owner(x, scr):
                    rec.update(ok=True, why="своя прокрутка")
                else:
                    rx = x.winfo_rootx() - inner.winfo_rootx()
                    ry = x.winfo_rooty() - inner.winfo_rooty()
                    inside = rx >= -1 and rx + x.winfo_width() <= cw + 1 and ry >= -1 and ry + x.winfo_height() <= ch + 1
                    vis = x.winfo_width() > 2 and x.winfo_height() > 2
                    rec.update(ok=inside and vis, why="виден" if inside and vis else f"обрезан ({rx},{ry} {x.winfo_width()}x{x.winfo_height()} в {cw}x{ch})")
                out["controls"].append(rec)
        out["controls"].extend(r for i, r in unseen.items() if i not in seen)
    # хром: шапка, док, полка (всё вне области экранов)
    app.show("bridge"); app.update()
    stack = [c for c in app.winfo_children()]
    content_root = str(view if view is not None else app.content)
    while stack:
        x = stack.pop()
        if str(x).startswith(content_root):
            continue
        stack.extend(x.winfo_children())
        k = _kind(x)
        if k:
            out["chrome"].append({"kind": k, "text": _label(x)})
    try:
        app.destroy()
    except Exception:  # noqa: BLE001
        pass
    pilots.reset_root()
    return out


def run(layout, skin, size, timeout=300) -> dict:
    fd, path = tempfile.mkstemp(suffix=".json"); os.close(fd)
    env = dict(os.environ)
    subprocess.run([sys.executable, os.path.abspath(__file__), "--one", layout, skin, size, path],
                   cwd=ROOT, env=env, timeout=timeout, check=True)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    os.remove(path)
    return data


def _key(r):
    return (r["screen"], r["tab"], r["kind"], r["text"])


def parity(classic: dict, alt: dict) -> dict:
    from collections import Counter
    c = Counter(_key(r) for r in classic["controls"])
    a = Counter(_key(r) for r in alt["controls"] if r["ok"])
    missing = [k for k in c if a[k] < c[k]]
    cut = [r for r in alt["controls"] if not r["ok"]]
    return {"classic": sum(c.values()), "alt_ok": sum(min(c[k], a[k]) for k in c), "missing": missing, "cut": cut,
            "more": sum(1 for r in alt["controls"] if r.get("why") == "ещё"),
            "classic_cut": sum(1 for r in classic["controls"] if not r["ok"])}


def markdown(skin="starship") -> str:
    classic = run("classic", skin, "1440x800")
    rows, by = [], {}
    for r in classic["controls"]:
        by.setdefault((r["screen"], r["tab"]), []).append(r)
    res = {s: parity(classic, run("alt", skin, s)) for s in SIZES}
    alt = run("alt", skin, "1280x720")
    altmap = {}
    for r in alt["controls"]:
        altmap.setdefault(_key(r), []).append(r["why"])
    lines = ["| Экран | Вкладка | Контролов (классика) | В alt на виду | В «⋯ ещё» | Своя прокрутка | Нет / обрезано |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for (scr, tab), rs in by.items():
        whys = [altmap.get(_key(r), ["нет"]).pop(0) if altmap.get(_key(r)) else "нет" for r in rs]
        lines.append(f"| {scr} | {tab or '—'} | {len(rs)} | {whys.count('виден')} | {whys.count('ещё')} | "
                     f"{whys.count('своя прокрутка')} | {sum(1 for w in whys if w not in ('виден', 'ещё', 'своя прокрутка'))} |")
    head = [f"Скин для аудита: `{skin}`. Классический вид снят при 1440×800.", "",
            "| Размер окна (alt) | Контролов в классике | Доступно в alt | В «⋯ ещё» | Пробелы | Обрезано в alt |",
            "|---|---:|---:|---:|---:|---:|"]
    for s, p in res.items():
        head.append(f"| {s} | {p['classic']} | {p['alt_ok']} | {p['more']} | {len(p['missing'])} | {len(p['cut'])} |")
    gaps = []
    for s, p in res.items():
        for k in p["missing"]:
            gaps.append(f"- {s}: нет `{' / '.join(k)}`")
        for r in p["cut"]:
            gaps.append(f"- {s}: {r['screen']}/{r['tab']} `{r['text']}` — {r['why']}")
    chrome_c = sorted({r["text"] for r in classic["chrome"]})
    chrome_a = sorted({r["text"] for r in alt["chrome"]})
    tail = ["", "### Шапка и навигация (вне экранов)", "",
            f"Классика: {len(chrome_c)} кнопок — " + ", ".join(f"`{t}`" for t in chrome_c), "",
            f"Alt: {len(chrome_a)} кнопок — " + ", ".join(f"`{t}`" for t in chrome_a)]
    return "\n".join(head + ["", "### По экранам (alt 1280×720)", ""] + lines + ["", "### Пробелы", ""]
                     + (gaps or ["- нет"]) + tail) + "\n"


if __name__ == "__main__":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        pass
    a = sys.argv[1:]
    if a[:1] == ["--one"]:
        data = collect_one(a[1], a[2], a[3])
        with open(a[4], "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os._exit(0)
    md = markdown(a[a.index("--skin") + 1] if "--skin" in a else "starship")
    if a[:1] == ["--md"]:
        with open(a[1], "w", encoding="utf-8", newline="\n") as f:
            f.write(md)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(md)
