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


def test_wheel_over_scrollbar_scrolls_attached_text(root):
    """Колесо над ползунком должно крутить поле, к которому он прицеплен."""
    wheel_router.install(root)
    text = tk.Text(root, height=5)
    bar = tk.Scrollbar(root, command=text.yview)
    text.configure(yscrollcommand=bar.set)
    bar.pack(side=tk.RIGHT, fill=tk.Y)
    text.pack(fill=tk.BOTH, expand=True)
    for i in range(40):
        text.insert("end", f"row {i}\n")
    root.update()

    target = wheel_router.target(bar, 1)
    assert target is not None
    before = text.yview()[0]
    e = type("E", (), {"widget": bar, "delta": -120, "num": 0})()
    wheel_router.route(e)
    root.update()
    assert text.yview()[0] > before


def test_wheel_over_slim_bar_uses_owner_canvas(root):
    wheel_router.install(root)
    cv, inner = _scroller(root)
    root.update()
    bar = tk.Canvas(root, width=10)
    bar.view = type("View", (), {"canvas": cv})()
    bar.pack(side=tk.RIGHT, fill=tk.Y)

    assert wheel_router.target(bar, 1) is cv
    before = cv.yview()[0]
    e = type("E", (), {"widget": bar, "delta": -120, "num": 0})()
    wheel_router.route(e)
    root.update()
    assert cv.yview()[0] > before


def test_install_survives_new_tk_after_destroy():
    """После destroy() новый Tk() снова "." — роутер должен повеситься заново."""
    try:
        first = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    first.geometry("300x200")
    wheel_router.install(first)
    assert wheel_router.installed(first)
    first.destroy()
    nxt = tk.Tk()
    nxt.geometry("300x200")
    try:
        assert not wheel_router.installed(nxt)
        wheel_router.install(nxt)
        assert wheel_router.installed(nxt)
        cv, inner = _scroller(nxt)
        nxt.update()
        inner.winfo_children()[3].event_generate("<MouseWheel>", delta=-120)
        nxt.update()
        assert cv.yview()[0] > 0
        inner.winfo_children()[3].event_generate("<Button-5>")
        nxt.update()
        assert cv.yview()[0] > 0
    finally:
        nxt.destroy()
