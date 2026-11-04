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


def test_busy_or_disabled_does_not_send():
    s, clock, sent, box = _make("x", busy=True)
    s.arm()
    clock.run()
    assert sent == []
    box["busy"], box["on"] = False, False
    assert not s.arm() and sent == []


def test_should_send_rules():
    assert autosend.should_send(text=" a  b ", baseline="a b")
    assert not autosend.should_send(text="", baseline="")
