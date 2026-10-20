"""Сэмплер для входа через экран логина (как у пользователя)."""
import sys
import threading
import time
import traceback
from collections import deque

sys.path.insert(0, ".")

LOG = open("_w7.txt", "w", encoding="utf-8", buffering=1)


def log(msg):
    LOG.write(f"{time.strftime('%H:%M:%S')} {msg}\n")


main_id = threading.main_thread().ident
samples = deque(maxlen=400)


def sampler():
    while True:
        frame = sys._current_frames().get(main_id)
        if frame is not None:
            samples.append((time.time(), "".join(traceback.format_stack(frame, limit=14))))
        time.sleep(0.1)


threading.Thread(target=sampler, daemon=True).start()

from stamina import cockpit as ck

orig_mainloop = ck.Cockpit.mainloop


def patched_mainloop(self, *a, **k):
    state = {"last": time.time(), "start": time.time(), "worst": 0.0}

    def pulse():
        now = time.time()
        gap = now - state["last"]
        start = state["last"]
        state["last"] = now
        if gap > 0.35:
            state["worst"] = max(state["worst"], gap)
            log(f"=== ЗАМИРАНИЕ {gap:.2f} с (экран={self.current}) ===")
            seen = set()
            for ts, stack in list(samples):
                if ts < start - 0.05:
                    continue
                tail = stack.strip().splitlines()[-9:]
                key = tail[-1] if tail else ""
                if key in seen:
                    continue
                seen.add(key)
                log("---\n" + "\n".join(tail))
        if now - state["start"] < 60:
            self.after(50, pulse)
        else:
            log(f"ИТОГ: худшее {state['worst']:.2f} с")
    self.after(50, pulse)
    return orig_mainloop(self, *a, **k)


ck.Cockpit.mainloop = patched_mainloop

from stamina import app

app.run_app([])
