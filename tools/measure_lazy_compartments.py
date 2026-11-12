#!/usr/bin/env python3
"""Замер старта Cockpit и открытия English (см. docs/perf/LAZY_COMPARTMENTS.md)."""
from __future__ import annotations

import os
import sys
import time


def rss_mb() -> float:
    try:
        for line in open("/proc/self/status", encoding="utf-8"):
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024.0
    except OSError:
        pass
    return 0.0


def main() -> int:
    os.environ.setdefault("STAR_TYPING_SAFE", "1")
    os.environ.setdefault("DISPLAY", ":99")
    label = os.environ.get("MEASURE_LABEL", "RUN")
    t0 = time.perf_counter()
    from stamina.cockpit import Cockpit

    app = Cockpit()
    app.update_idletasks()
    app.update()
    t_frame = (time.perf_counter() - t0) * 1000
    rss1 = rss_mb()
    lazy_mods = [
        m for m in (
            "stamina.english.screen",
            "stamina.speedread.screen",
            "stamina.lounge.screen",
            "stamina.radio.screen",
            "stamina.comm_screen",
            "stamina.docs_screen",
            "stamina.orion_screen",
        )
        if m in sys.modules
    ]
    t1 = time.perf_counter()
    app.show("english")
    deadline = time.time() + 120
    scr = None
    while time.time() < deadline:
        app.update()
        scr = app.screens.get("english")
        if scr is not None and getattr(getattr(scr, "vocab", None), "ready", False) and getattr(scr, "_built", False):
            break
        time.sleep(0.05)
    t_eng = (time.perf_counter() - t1) * 1000
    rss2 = rss_mb()
    vocab = getattr(scr, "vocab", None) if scr else None
    print(
        f"{label} first_frame_ms={t_frame:.0f} rss_start_mb={rss1:.1f} "
        f"open_english_ms={t_eng:.0f} rss_english_mb={rss2:.1f} delta_mb={rss2 - rss1:.1f} "
        f"lazy_at_start={lazy_mods} vocab_lazy={getattr(vocab, 'lazy', None)} "
        f"n_words={len(getattr(vocab, 'words', []) or [])}"
    )
    app.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
