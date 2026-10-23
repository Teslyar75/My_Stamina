"""Сквозная проверка ВСЕХ режимов проверки английского:
python tools/english_cards_check.py LAYOUT SKIN OUTDIR [WxH]

Открывает отсек «Английский», ждёт словарь и проходит каждый режим настоящим вводом:
ПРОВЕРКА СИСТЕМ (карточки SM-2: Space → оценки 1-4), миссии СЛУЧАЙНАЯ / ГОВОРЕНИЕ /
ЧТЕНИЕ / ВОПРОСЫ (все типы задач S1-S3, R1-R3, Q1-Q4: выбор цифрой, ввод слова,
самооценка речи) до ОТЧЁТА О ПОЛЁТЕ, Esc-выход, карточки ИЗ КНИГИ (Space → оценка),
журнал прогресса и остальные страницы отсека.
После каждого шага — скриншот и проверка: страница видна, на экране, не перекрыта,
текст карточки отрисован; прогресс записан на диск. Временный APPDATA.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class _Key:
    """Минимальное событие клавиши для on_key страниц."""

    def __init__(self, keysym: str) -> None:
        self.keysym = keysym
        self.char = keysym if len(keysym) == 1 else ""


PRACTICE_MODES = ("random", "speaking", "reading", "questions")


def _answer_task(pr) -> str:
    """Ответить на текущую задачу миссии так, как это сделал бы пилот; вернуть тип задачи."""
    t = pr.tasks[pr.i]
    kind = t["type"]
    if "options" in t:
        good = t.get("answers") or [t["answer"]]
        pr.on_key(_Key(str(good[0] + 1)))                    # цифра 1-4 — как с клавиатуры
    elif kind == "Q4":
        pr.q4.delete(0, "end")
        pr.q4.insert(0, t["word"]["word"])
        pr.check_q4()
    elif kind.startswith("S"):
        pr.on_speech([], 80)                                  # самооценка «сказал хорошо»
    return kind


def run_modes(en, shot, pump, rep: dict) -> None:
    """Пройти все режимы проверки; в rep["modes"] — что проверено и с каким итогом."""
    modes: dict = {}
    rep["modes"] = modes
    # 1. ПРОВЕРКА СИСТЕМ — флеш-карточки SM-2
    en.start_review()
    rv = en.pages["review"]
    shot("review_front", rv)
    rv.on_key(_Key("space"))
    shot("review_back", rv)
    n0 = len(rv.queue)
    for key in ("4", "2", "1"):
        if rv.queue:
            rv.on_key(_Key("space"))
            rv.on_key(_Key(key))
            pump(0.1)
    rep["review_graded"] = n0 - len(rv.queue)
    shot("review_after", rv)
    modes["review"] = {"graded": rep["review_graded"]}
    # 2. Миссии всех видов — до отчёта, с обратной связью после каждого ответа
    pr = en.pages["practice"]
    for mode in PRACTICE_MODES:
        en.start_session(mode, source="set")
        pump(0.3)
        info: dict = {"active": bool(pr.active), "types": [], "feedback": 0, "answered": 0}
        modes["mission_" + mode] = info
        if not pr.active:
            continue
        shot(f"mission_{mode}_task", pr)
        guard = 0
        while pr.active and pr.i < len(pr.tasks) and guard < 40:
            guard += 1
            info["types"].append(_answer_task(pr))
            pump(0.05)
            if pr.answered_cur:
                info["answered"] += 1
                if pr.fb is not None and str(pr.fb.cget("text")).strip():
                    info["feedback"] += 1                     # немедленный видимый отклик
            if guard == 1:
                shot(f"mission_{mode}_answered", pr)
            pr.on_key(_Key("Return"))                          # ДАЛЕЕ — Enter
            pump(0.05)
        info["types"] = sorted(set(info["types"]))
        info["report"] = bool(getattr(pr, "finished", False))
        shot(f"mission_{mode}_report", pr)
        pr.on_key(_Key("Escape"))                              # Esc — к миссиям
        pump(0.2)
    # Esc посреди миссии (выход без отчёта, с подтверждением/без)
    en.start_session("random", source="set")
    pump(0.2)
    shot("mission_task", pr)
    pr.skip()
    shot("mission_skip", pr)
    pr.on_key(_Key("Escape"))
    pump(0.2)
    shot("mission_quit", pr)
    modes["mission_esc"] = {"active_after_esc": bool(pr.active)}
    # 3. Карточки ИЗ КНИГИ
    bk = en.pages["book"]
    en.show("book")
    shot("book", bk)
    from stamina.english import book_sentences as bs
    store = bs.ensure_store(en.progress)
    if not store["books"]:                                   # чистый профиль: одна учебная «книга»
        store["books"]["qa"] = {"id": "qa", "title": "QA", "sentences": [
            {"id": f"qa:{i}", "i": i, "w0": i * 10, "en": en_s, "ru": ru_s}
            for i, (en_s, ru_s) in enumerate([("The ship is ready.", "Корабль готов."),
                                              ("We fly at dawn.", "Мы летим на рассвете."),
                                              ("Read the book.", "Прочитай книгу.")])]}
    try:
        bk.start_drill(due_only=False)
    except Exception:  # noqa: BLE001 — нет книжных карточек в чистом профиле
        rep["errors"].append(traceback.format_exc())
    pump(0.3)
    drill = getattr(bk, "mode", "") == "drill"
    modes["book_drill"] = {"started": drill}
    if drill:
        shot("book_drill_front", bk)
        bk.on_key(_Key("space"))
        shot("book_drill_back", bk)
        n0 = len(bk.queue) - bk.i
        bk.on_key(_Key("3"))
        pump(0.2)
        shot("book_drill_graded", bk)
        modes["book_drill"]["graded"] = n0 - (len(bk.queue) - bk.i)
        bk.on_key(_Key("Escape"))
        pump(0.2)
    # 4. Прочие страницы: журнал прогресса, наборы, списки, склад, сканер, настройки
    for name in en.pages:
        if name in ("review", "practice", "book", "overview"):
            continue
        en.show(name)
        shot("page_" + name, en.pages[name])
    en.show("overview")


def main() -> int:
    layout, skin, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    size = sys.argv[4] if len(sys.argv) > 4 else "1280x720"
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        pass
    tmp = tempfile.mkdtemp(prefix="stamina_en_")
    os.environ["APPDATA"] = tmp
    from stamina import pilots, storage
    pilots.reset_root(Path(tmp) / "Stamina")
    storage.DEFAULT_SETTINGS.update(ui_layout=layout, skin=skin, living_space="off", idle_minutes=0)
    from PIL import ImageGrab
    from stamina.cockpit import Cockpit
    app = Cockpit()
    errors: list[str] = []
    app.report_callback_exception = lambda *a: errors.append("".join(traceback.format_exception(*a)))
    app.geometry(f"{size}+0+0")
    app.attributes("-topmost", True)
    out.mkdir(parents=True, exist_ok=True)
    rep: dict = {"layout": layout, "skin": skin, "size": size, "steps": [], "errors": errors}

    def pump(sec=0.4):
        t = time.time() + sec
        while time.time() < t:
            app.update()
            time.sleep(0.02)

    def shot(name, page):
        pump()
        x, y = app.winfo_rootx(), app.winfo_rooty()
        im = ImageGrab.grab((x, y, x + app.winfo_width(), y + app.winfo_height()))
        im.save(out / f"en_{layout}_{skin}_{size}_{name}.png")
        # проверка видимости: страница отображена и её центр на экране принадлежит ей самой
        cx = page.winfo_rootx() + page.winfo_width() // 2
        # центр видимой части страницы (страница может быть прокручена к карточке)
        y0 = max(page.winfo_rooty(), app.winfo_rooty())
        y1 = min(page.winfo_rooty() + page.winfo_height(), app.winfo_rooty() + app.winfo_height())
        cy = (y0 + y1) // 2
        top = app.winfo_containing(cx, cy)
        owner = top
        while owner is not None and owner is not page:
            owner = owner.master
        g = im.convert("L").resize((64, 36))
        lum = sum(g.getdata()) / (64 * 36)
        rep["steps"].append({"step": name, "mapped": bool(page.winfo_ismapped()), "w": page.winfo_width(),
                             "h": page.winfo_height(), "on_top": owner is page, "top": str(top),
                             "mean_luma": round(lum, 1), "errors_so_far": len(errors)})

    try:
        pump(3.0)                     # стартовые таймеры кабины (приветствие, возврат на мостик)
        app.show("english")
        t0 = time.time()
        en = None
        while time.time() - t0 < 60:
            pump(0.2)
            en = app.screens.get("english")
            if app.current != "english":
                app.show("english")
            if getattr(en, "_built", False) and app.current == "english":
                break
        rep["current"] = app.current
        rep["en_class"] = type(en).__name__
        rep["vocab_s"] = round(time.time() - t0, 1)
        shot("overview", en.pages["overview"])
        run_modes(en, shot, pump, rep)
        en.progress.save() if hasattr(en.progress, "save") else None
        files = [str(p.relative_to(tmp)) for p in Path(tmp).rglob("*.json") if "english" in str(p).lower()]
        rep["progress_files"] = files
        rep["cards_in_progress"] = len(en.progress.data.get("cards", {}))
    except Exception:  # noqa: BLE001
        errors.append(traceback.format_exc())
    log = Path(tmp) / "Stamina" / "debug.log"
    rep["debug_tracebacks"] = log.read_text(encoding="utf-8", errors="replace").count("Traceback") if log.exists() else 0
    (out / f"en_{layout}_{skin}_{size}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = [s for s in rep["steps"] if not (s["mapped"] and s["on_top"]) or s["mean_luma"] < 12]
    print(layout, skin, size, "шагов", len(rep["steps"]), "проблем", len(bad), "ошибок", len(errors),
          "карт", rep.get("cards_in_progress"), "оценено", rep.get("review_graded"))
    for m, v in rep.get("modes", {}).items():
        print("  режим", m, json.dumps(v, ensure_ascii=False))
    for s in bad:
        print("  ", s)
    for e in errors[:3]:
        print("  ERR", e[-700:])
    app.destroy()
    os._exit(1 if bad or errors else 0)


if __name__ == "__main__":
    main()
