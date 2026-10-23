"""Аудит контраста скинов по WCAG 2.1 (токены stamina/themes/*.json).

    python tools/contrast_audit.py            таблица провалов, код 1 если есть
    python tools/contrast_audit.py --fix      минимально подтянуть провальные токены (пишет JSON)

Пары «текст — фон» взяты из того, как токены используются в интерфейсе:
текст и подписи лежат на bg/bg2/panel/panel_hi, на кнопках (обычная, hover,
активная = cyan_deep), полях ввода и списках (panel/bg2), в выпадающих меню
(panel); акцентные цвета — заголовки, статусы и крупные надписи (≥3:1).
FAINT — линии и отключённые элементы (WCAG их не нормирует), но и их держим ≥2:1,
чтобы рамки не исчезали. Обычный текст ≥4.5:1, крупный/заголовки ≥3:1.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

THEMES = Path(__file__).resolve().parent.parent / "stamina" / "themes"
SURFACES = ("bg", "bg2", "panel", "panel_hi")
RULES: list[tuple[str, tuple[str, ...], float]] = [
    ("text", SURFACES, 4.5),                      # основной текст, кнопки, поля, списки, меню
    ("muted", SURFACES, 4.5),                     # подписи, подсказки, строка статуса
    ("cyan", SURFACES, 3.0),                      # заголовки, рамки кнопок, активные пункты
    ("accent", SURFACES, 3.0),
    ("ok", SURFACES, 3.0),
    ("error", SURFACES, 3.0),
    ("purple", SURFACES, 3.0),
    ("faint", ("bg", "panel"), 2.0),
]


def lum(h: str) -> float:
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a: str, b: str) -> float:
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def mix(a: str, b: str, t: float) -> str:
    a, b = a.lstrip("#"), b.lstrip("#")
    return "#" + "".join(f"{round(int(a[i:i + 2], 16) * (1 - t) + int(b[i:i + 2], 16) * t):02x}" for i in (0, 2, 4))


def audit(colors: dict) -> list[tuple[str, str, float, float]]:
    out = []
    for fg, bgs, need in RULES:
        if fg not in colors:
            continue
        for bg in bgs:
            if bg in colors:
                r = ratio(colors[fg], colors[bg])
                if r < need:
                    out.append((fg, bg, round(r, 2), need))
    return out


def fix_token(colors: dict, fg: str, bgs: tuple[str, ...], need: float) -> str | None:
    """Самый маленький сдвиг fg к белому или чёрному, при котором все пары проходят."""
    base = colors[fg]
    best = None
    for target in ("#ffffff", "#000000"):
        for step in range(1, 101):
            c = mix(base, target, step / 100)
            if all(ratio(c, colors[b]) >= need for b in bgs if b in colors):
                if best is None or step < best[0]:
                    best = (step, c)
                break
    return best[1] if best else None


def main() -> int:
    do_fix = "--fix" in sys.argv
    bad = 0
    print("| скин | токен | фон | было | стало | нужно |\n|---|---|---|---|---|---|")
    for p in sorted(THEMES.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        cols = data["colors"]
        fails = audit(cols)
        if not fails:
            continue
        changed = False
        for fg, bgs, need in RULES:
            if not any(f[0] == fg for f in fails):
                continue
            new = fix_token(cols, fg, bgs, need) if do_fix else None
            for f in fails:
                if f[0] == fg:
                    after = f"{new} ({ratio(new, cols[f[1]]):.2f})" if new else "—"
                    print(f"| {p.stem} | {fg} {cols[fg]} | {f[1]} {cols[f[1]]} | {f[2]} | {after} | {need} |")
            if new:
                cols[fg] = new
                changed = True
            else:
                bad += 1
        if changed:
            raw = p.read_bytes().decode("utf-8")
            for k, v in cols.items():          # точечная замена: формат и переводы строк файла не трогаем
                raw = re.sub(rf'("{k}"\s*:\s*")#[0-9A-Fa-f]{{6}}(")', rf"\g<1>{v}\g<2>", raw, count=1)
            p.write_bytes(raw.encode("utf-8"))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
