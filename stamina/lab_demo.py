"""Демо-граф Лаборатории — ТОЛЬКО для скриншотов, тестов и замеров.

Не читает и не пишет файлы пилота; экран показывает плашку «ДЕМО-ДАННЫЕ».
Включается кодом (``LabScreen.set_demo``) или переменной окружения
STAMINA_LAB_DEMO=1 — в обычном интерфейсе кнопки нет.
"""
from __future__ import annotations

import datetime as dt
import random
import time

from stamina.lab_data import CPM_STEPS, DAY, WPM_STEPS, Graph

_TOPICS = ("Food", "Home", "City", "Travel", "Work", "Body", "Nature", "Feelings", "Time", "School")
_LEVELS = ("A1", "A2", "B1", "B2", "C1")
_SYL = ("ka", "lo", "ri", "men", "sta", "vor", "ten", "bel", "dra", "qui", "son", "fe")


def demo_graph(n: int = 1000, seed: int = 7, now: float | None = None) -> Graph:
    now = time.time() if now is None else now
    rnd = random.Random(seed)
    g = Graph()
    g.demo = True
    n_words = max(0, int(n * 0.82))
    for i in range(n_words):
        lvl = _LEVELS[min(len(_LEVELS) - 1, int(rnd.random() ** 1.6 * len(_LEVELS)))]
        topic = _TOPICS[i % len(_TOPICS)]
        word = "".join(rnd.choice(_SYL) for _ in range(rnd.randint(1, 3))) + str(i)
        g.add(f"w:{word}", "word", "en", word, f"cefr:{lvl}:{topic}",
              last=now - rnd.expovariate(1 / 9) * DAY, strength=rnd.randint(0, 8), detail=f"{lvl} · {topic}")
    for i in range(min(40, n // 25)):
        v = f"verb{i}"
        last = now - rnd.random() * 20 * DAY
        g.add("v:" + v, "verb", "en", v, "verbs", last=last, strength=3, detail="v2 · v3")
        for f in ("v2", "v3"):
            g.add(f"vf:{v}:{f}", "form", "en", f"{v}-{f}", "verbs", last=last, strength=3, detail=v)
            g.link("v:" + v, f"vf:{v}:{f}")
    words = [x["id"] for x in g.nodes if x["kind"] == "word"]
    for b in range(min(6, max(1, n // 150))):
        bid = f"b:demo{b}"
        g.add(bid, "book", "read", f"Book {b + 1}", f"book:demo{b}", last=now - b * 4 * DAY, strength=4)
        for w in rnd.sample(words, min(25, len(words))):
            g.link(w, bid)
    prev = None
    for thr in WPM_STEPS[:5]:
        nid = f"sr:wpm:{thr}"
        g.add(nid, "milestone", "read", str(thr), "sr:speed", last=now - rnd.random() * 30 * DAY, strength=2)
        if prev:
            g.link(prev, nid)
        prev = nid
    prev = None
    for thr in CPM_STEPS[:6]:
        nid = f"ty:cpm:{thr}"
        g.add(nid, "milestone", "type", str(thr), "type:cpm", last=now - rnd.random() * 15 * DAY, strength=2)
        if prev:
            g.link(prev, nid)
        prev = nid
    i = 0
    while len(g.nodes) < n:
        i += 1
        nid = f"ty:m:demo-{i:02d}"
        g.add(nid, "mission", "type", f"demo-{i:02d}", "type:missions:demo", last=now - i * DAY, strength=4)
        if i > 1:
            g.link(f"ty:m:demo-{i - 1:02d}", nid)
    today = dt.date.fromtimestamp(now)
    g.active_days = {(today - dt.timedelta(days=d)).isoformat() for d in range(20) if d % 3 != 2}
    return g
