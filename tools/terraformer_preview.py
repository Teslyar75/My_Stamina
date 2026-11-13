"""Превью роботов-терраформеров в PNG для самопроверки.

    python tools/terraformer_preview.py [--out DIR] [--tk] [--only a1,c2]

По умолчанию — гладкий рендер отсека (``terraformer_render.render``, тот же кадр,
что уходит в ``tk.PhotoImage``), дисплей не нужен. ``--tk`` — снимок экрана с
настоящего ``TerraformerViewer`` на ``tk.Canvas`` (под Xvfb: ``xvfb-run -a …``).
``--flat`` — запасной плоский Canvas-рендер (``frame_polys``) через PIL.
Складывает по роботу 3 ракурса и сводные листы ``sheet_cefr.png`` / ``sheet_freq.png``.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from stamina import terraformer_models as tm  # noqa: E402
from stamina import terraformer_render as tr  # noqa: E402

BG = "#0b1118"
VIEWS = (("front34", tm.DEFAULT_YAW, tm.DEFAULT_PITCH),
         ("side", -1.35, 0.12),
         ("back34", 2.7, 0.38))
CELL = 360


def _font(size: int):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def render_pil(robot_id: str, yaw: float, pitch: float, size: int = CELL, t: float = 0.6,
               fit: bool = True) -> Image.Image:
    ss = 2  # суперсэмплинг — края без «лесенки»
    im = Image.new("RGB", (size * ss, size * ss), BG)
    d = ImageDraw.Draw(im)
    for coords, fill, outline in tm.frame_polys(robot_id, yaw, pitch, 1.0, (0.0, 0.0), t,
                                                width=size * ss, height=size * ss, fit=fit):
        pts = list(zip(coords[0::2], coords[1::2]))
        d.polygon(pts, fill=fill, outline=outline)
    return im.resize((size, size), Image.LANCZOS)


def render_smooth(robot_id: str, yaw: float, pitch: float, size: int = CELL, t: float = 0.6,
                  fit: bool = True) -> Image.Image:
    return tr.render(robot_id, yaw, pitch, 1.0, (0.0, 0.0), t, width=size, height=size,
                     quality="full", fit=fit).composite(BG, tr.core_pulse(t))


def render_tk(robot_id: str, views, size: int = CELL, t: float = 0.6) -> list[Image.Image]:
    import tkinter as tk

    from PIL import ImageGrab
    root = tk.Tk()
    root.overrideredirect(True)
    root.geometry(f"{size}x{size}+0+0")
    cv = tk.Canvas(root, width=size, height=size, bg=BG, highlightthickness=0)
    cv.pack()
    out = []
    viewer = tr.TerraformerViewer(cv, robot_id)
    root.update()
    for _name, yaw, pitch in views:
        viewer.view.yaw, viewer.view.pitch = yaw, pitch
        viewer.redraw("full")
        root.update()
        x, y = cv.winfo_rootx(), cv.winfo_rooty()
        out.append(ImageGrab.grab(bbox=(x, y, x + size, y + size), xdisplay=os.environ.get("DISPLAY")))
    root.destroy()
    return out


def sheet(line: str, imgs: dict[str, list[Image.Image]], path: Path) -> None:
    rows = [r for r in tm.ROBOTS if r.line == line]
    CELL = next(iter(imgs.values()))[0].width
    head = 34
    W = CELL * len(VIEWS) + 260
    H = (CELL + 8) * len(rows) + head
    sh = Image.new("RGB", (W, H), "#070b10")
    d = ImageDraw.Draw(sh)
    f1, f2 = _font(30), _font(15)
    d.text((10, 6), f"{line.upper()} — {', '.join(v[0] for v in VIEWS)}", fill="#9fb4c8", font=f2)
    for i, r in enumerate(rows):
        y = head + i * (CELL + 8)
        d.text((14, y + 20), r.name, fill="#ffffff", font=f1)
        cap = r.caption
        words, line_s, yy = cap.split(), "", y + 64
        for w in words:
            if line_s and d.textlength(line_s + w, font=f2) > 236:
                d.text((14, yy), line_s, fill="#9fb4c8", font=f2)
                yy += 20
                line_s = ""
            line_s += w + " "
        d.text((14, yy), line_s, fill="#9fb4c8", font=f2)
        d.text((14, y + CELL - 40), f"{tm.polygon_count(r.id, 'high')} граней", fill="#5f7184", font=f2)
        for j, im in enumerate(imgs[r.id]):
            sh.paste(im, (260 + j * CELL, y))
    sh.save(path)


def lineup(line: str, path: Path, size: int = 300) -> None:
    rows = [r for r in tm.ROBOTS if r.line == line]
    im = Image.new("RGB", (size * len(rows), size), "#070b10")
    for i, r in enumerate(rows):
        im.paste(render_smooth(r.id, tm.DEFAULT_YAW, 0.12, size, fit=False), (i * size, 0))
    im.save(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="tf_preview")
    ap.add_argument("--tk", action="store_true")
    ap.add_argument("--flat", action="store_true")
    ap.add_argument("--size", type=int, default=CELL)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    ids = [s for s in a.only.split(",") if s] or list(tm.ROBOT_IDS)
    imgs: dict[str, list[Image.Image]] = {}
    for rid in ids:
        if a.tk:
            ims = render_tk(rid, VIEWS, a.size)
        elif a.flat:
            ims = [render_pil(rid, yaw, pitch, a.size) for _n, yaw, pitch in VIEWS]
        else:
            ims = [render_smooth(rid, yaw, pitch, a.size) for _n, yaw, pitch in VIEWS]
        for (name, _y, _p), im in zip(VIEWS, ims):
            im.save(out / f"{rid}_{name}.png")
        imgs[rid] = ims
        print(rid, tm.polygon_count(rid), "faces")
    if not a.only:
        for line in ("cefr", "freq"):
            sheet(line, imgs, out / f"sheet_{line}.png")
            lineup(line, out / f"lineup_{line}.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
