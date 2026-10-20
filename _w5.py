"""Сэмплер: где стоит главный поток во время замираний (с включённым радио)."""
import sys
import threading
import time
import traceback
from collections import deque

sys.path.insert(0, ".")

LOG = open("_w5.txt", "w", encoding="utf-8", buffering=1)


def log(msg):
    LOG.write(f"{time.strftime('%H:%M:%S')} {msg}\n")


main_id = threading.main_thread().ident
samples = deque(maxlen=300)


def sampler():
    while True:
        frame = sys._current_frames().get(main_id)
        if frame is not None:
            samples.append((time.time(), "".join(traceback.format_stack(frame, limit=10))))
        time.sleep(0.1)


threading.Thread(target=sampler, daemon=True).start()

from stamina import pilot_screens

pilot_screens.ask_pin = lambda *a, **k: True

from stamina import cockpit as ck

orig_mainloop = ck.Cockpit.mainloop


def patched_mainloop(self, *a, **k):
    state = {"last": time.time(), "start": time.time()}

    def pulse():
        now = time.time()
        gap = now - state["last"]
        start = state["last"]
        state["last"] = now
        if gap > 0.35:
            log(f"=== ЗАМИРАНИЕ {gap:.2f} с (экран={self.current}) ===")
            seen = set()
            for ts, stack in list(samples):
                if ts < start - 0.05:
                    continue
                tail = stack.strip().splitlines()[-8:]
                key = tail[-1] if tail else ""
                if key in seen:
                    continue
                seen.add(key)
                log("---\n" + "\n".join(tail))
        if now - state["start"] < 26:
            self.after(50, pulse)
        else:
            log("конец")
    self.after(50, pulse)
    return orig_mainloop(self, *a, **k)


ck.Cockpit.mainloop = patched_mainloop

from stamina import app

app.run_app(["--pilot", "p-20261009-4fa9"])
