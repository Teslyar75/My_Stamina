import tkinter as tk

import pytest

from stamina import wheel_router


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    r.geometry("300x200")
    yield r
    r.destroy()


def _scroller(parent):
    cv = tk.Canvas(parent, height=100, yscrollincrement=10)
    sb = tk.Scrollbar(parent, command=cv.yview)
    cv.configure(yscrollcommand=sb.set)
    inner = tk.Frame(cv)
    cv.create_window(0, 0, window=inner, anchor="nw")
    for i in range(40):
        tk.Label(inner, text=f"row {i}").pack()
    inner.update_idletasks()
    cv.configure(scrollregion=cv.bbox("all"))
    cv.pack(fill=tk.BOTH, expand=True)
    return cv, inner


def test_routes_to_nearest_scrollable_ancestor(root):
    wheel_router.install(root)
    cv, inner = _scroller(root)
    root.update()
    lbl = inner.winfo_children()[3]
    assert wheel_router.target(lbl, 1) is cv
    lbl.event_generate("<MouseWheel>", delta=-120)
    root.update()
    assert cv.yview()[0] > 0


def test_at_edge_and_own_binding(root):
    cv, inner = _scroller(root)
    root.update()
    lbl = inner.winfo_children()[0]
    assert wheel_router.target(lbl, -1) is None          # вверх некуда
    lbl.bind("<MouseWheel>", lambda e: "break")
    assert wheel_router._own_wheel(lbl)
    assert wheel_router.direction(type("E", (), {"num": 5, "delta": 0})()) == 1
