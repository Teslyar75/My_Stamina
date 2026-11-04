"""Автоотправка голоса: правило и таймер без tkinter."""

from stamina.voice import autosend


class _Clock:
    def __init__(self):
        self.jobs = {}
        self.n = 0

    def after(self, ms, fn):
        self.n += 1
        self.jobs[self.n] = fn
        return self.n

    def cancel(self, job):
        self.jobs.pop(job, None)

    def run(self):
        jobs, self.jobs = self.jobs, {}
        for fn in jobs.values():
            fn()


def _make(text, busy=False, enabled=True):
    clock, sent, box = _Clock(), [], {"t": text, "busy": busy, "on": enabled}
    s = autosend.AutoSender(after=clock.after, after_cancel=clock.cancel, text=lambda: box["t"],
                            sender=lambda: sent.append(box["t"]), enabled=lambda: box["on"],
                            busy=lambda: box["busy"])
    return s, clock, sent, box


def test_sends_after_silence():
    s, clock, sent, _ = _make("привет")
    assert s.arm() and s.armed
    clock.run()
    assert sent == ["привет"] and not s.armed


def test_new_phrase_restarts_and_edit_cancels():
    s, clock, sent, box = _make("раз")
    s.arm()
    box["t"] = "раз два"
    s.arm()
    assert len(clock.jobs) == 1
    box["t"] = "раз два — правлю"
    clock.run()
    assert sent == []


def test_busy_defers_until_free_and_disabled_never_sends():
    s, clock, sent, box = _make("x", busy=True)
    s.arm()
    clock.run()
    assert sent == [] and s.armed          # Орион отвечает — фраза ждёт
    box["busy"] = False
    clock.run()
    assert sent == ["x"]
    box["on"] = False
    assert not s.arm()


def test_edit_while_busy_drops_autosend():
    s, clock, sent, box = _make("x", busy=True)
    s.arm()
    clock.run()
    box["t"], box["busy"] = "x и ещё", False
    clock.run()
    assert sent == [] and not s.armed


def test_should_send_rules():
    assert autosend.should_send(text=" a  b ", baseline="a b")
    assert not autosend.should_send(text="", baseline="")
