from __future__ import annotations

import inspect
import tkinter as tk
from dataclasses import dataclass, field

from stamina import theme
from stamina.theme import px


@dataclass
class TimelineItem:
    id: str
    label: str
    status: str | None = None
    unread: int = 0
    children: list["TimelineItem"] = field(default_factory=list)


class Timeline(tk.Canvas):
    """Interactive ribbon of ticks.

    orientation: horizontal|vertical. Items: list[dict|TimelineItem].

    With ``surface=`` the ticks are drawn as tagged items on a foreign canvas
    (the full-window slideshow), while this widget only owns the logic/events.
    ``region`` returns ``(x, y, w, h)`` in that canvas' coordinates.
    """

    def __init__(self, master, *, orientation: str = "horizontal", command=None,
                 bg: str | None = None, scrim: str = "#0B0E14", surface: tk.Canvas | None = None,
                 region=None, tag: str | None = None, dash_width=None, **kw):
        self.orientation = orientation
        self.command = command
        self.surface = surface
        self.dash_width = int(dash_width) if dash_width is not None else px(30)
        self._region_fn = region
        self._tag = tag or f"timeline_{id(self):x}"
        self._items: list[TimelineItem] = []
        self._active_id: str | None = None
        self._hover_id: str | None = None
        self._popup: tk.Frame | None = None
        self._popup_for: str | None = None
        self._popup_buttons: list[tk.Widget] = []
        self._popup_item: TimelineItem | None = None
        self._focus_idx: int = -1
        self._item_boxes: dict[str, tuple[int, int, int, int]] = {}
        self._scroll = 0
        self._total = 0
        self._scrim = scrim
        bg = bg or theme.BG

        if surface is not None:
            # Never mapped: the visible drawing belongs to ``surface``.
            super().__init__(master, width=1, height=1, highlightthickness=0, bd=0)
            try:
                self.place_forget()
            except tk.TclError:
                pass
            self.canvas = surface
            self._bind_surface(surface)
        else:
            strip = px(40) if orientation == "horizontal" else px(52)
            w = kw.pop("width", strip if orientation == "vertical" else 200)
            h = kw.pop("height", strip if orientation == "horizontal" else 200)
            super().__init__(master, bg=bg, highlightthickness=0, width=w, height=h, **kw)
            self.canvas = self
            self.bind("<Configure>", lambda _e: self.redraw())
            self.bind("<Motion>", self._on_motion)
            self.bind("<Leave>", self._on_leave)
            self.bind("<Button-1>", self._on_click)
            self.bind("<MouseWheel>", self._on_wheel)
            self.bind("<Button-4>", lambda e: self._on_wheel(e, delta=120))
            self.bind("<Button-5>", lambda e: self._on_wheel(e, delta=-120))
        if surface is None:
            self.bind("<Left>", self._on_key_left)
            self.bind("<Right>", self._on_key_right)
            self.bind("<Up>", self._on_key_up)
            self.bind("<Down>", self._on_key_down)
            self.bind("<Return>", self._on_key_activate)
            self.bind("<KP_Enter>", self._on_key_activate)
            self.bind("<Escape>", lambda _e: self.close_popup())
            self.bind("<Tab>", self._on_tab)
            self.bind("<FocusOut>", lambda _e: self.after_idle(self._maybe_close_popup))

    def _bind_surface(self, surface: tk.Canvas) -> None:
        """Events follow the visible canvas when ribbons move over a work window."""
        surface.bind("<Motion>", self._on_surface_motion, add="+")
        surface.bind("<Button-1>", self._on_surface_click, add="+")
        surface.bind("<Leave>", lambda _e: self._on_leave(), add="+")
        surface.bind("<MouseWheel>", self._on_wheel, add="+")
        surface.bind("<Button-4>", lambda e: self._on_wheel(e, delta=120), add="+")
        surface.bind("<Button-5>", lambda e: self._on_wheel(e, delta=-120), add="+")

    def set_surface(self, surface: tk.Canvas) -> None:
        """Draw the same ribbon on another canvas (home photo ↔ work overlay)."""
        if surface is self.canvas:
            self.lift()
            return
        self.close_popup()
        old = self.canvas
        self.canvas = surface
        self.surface = surface
        if old is not None and old is not surface:
            try:
                old.delete(self._tag)
            except tk.TclError:
                pass
        self._bind_surface(surface)
        self.redraw()

    # --- geometry helpers -------------------------------------------------
    def _region(self) -> tuple[int, int, int, int]:
        if self._region_fn is not None:
            try:
                x, y, w, h = self._region_fn()
                return int(x), int(y), max(1, int(w)), max(1, int(h))
            except Exception:  # noqa: BLE001
                pass
        if self.surface is None:
            return 0, 0, max(1, self.winfo_width()), max(1, self.winfo_height())
        w = max(1, self.surface.winfo_width())
        h = max(1, self.surface.winfo_height())
        strip = px(40) if self.orientation == "horizontal" else px(52)
        if self.orientation == "horizontal":
            return 0, 0, w, strip
        return w - strip, 0, strip, h

    def _view_size(self) -> tuple[int, int]:
        _x, _y, w, h = self._region()
        return w, h

    def _screen_origin(self) -> tuple[int, int]:
        """Top-left of the ribbon's local coordinate system in screen pixels."""
        if self.surface is None:
            return self.winfo_rootx(), self.winfo_rooty()
        rx, ry, _w, _h = self._region()
        return self.surface.winfo_rootx() + rx, self.surface.winfo_rooty() + ry

    def _xy(self, x: float, y: float) -> tuple[float, float]:
        rx, ry, _w, _h = self._region()
        return x + rx, y + ry

    def _dash_screen_box(self, item: TimelineItem) -> tuple[int, int, int, int]:
        box = self._item_boxes.get(item.id)
        if not box:
            return 0, 0, 0, 0
        x0, y0, x1, y1 = box
        ox, oy = self._screen_origin()
        return ox + x0, oy + y0, ox + x1, oy + y1

    def lift(self) -> None:
        """Keep dashes above a freshly drawn slideshow frame."""
        if self.surface is not None:
            self.surface.tag_raise(self._tag)

    def _emit(self, item: TimelineItem, from_popup: bool) -> None:
        if self.command is None:
            return
        try:
            arity = len(inspect.signature(self.command).parameters)
        except (TypeError, ValueError):
            arity = 2
        if arity >= 3:
            self.command(item.id, item, from_popup)
        else:
            self.command(item.id, item)

    # --- items/drawing ----------------------------------------------------
    @staticmethod
    def _coerce(item) -> TimelineItem:
        if isinstance(item, TimelineItem):
            return item
        children = [Timeline._coerce(c) for c in (item.get("children") or [])]
        return TimelineItem(id=str(item.get("id", "")), label=str(item.get("label", "")),
                            status=item.get("status"), unread=int(item.get("unread") or 0),
                            children=children)

    def set_items(self, items) -> None:
        self._items = [self._coerce(i) for i in (items or [])]
        if self._active_id not in {i.id for i in self._items}:
            self._active_id = self._items[0].id if self._items else None
        self._clamp_scroll()
        self.redraw()

    def set_active(self, item_id: str | None) -> None:
        self._active_id = item_id
        self.redraw()

    def items(self) -> list[TimelineItem]:
        return list(self._items)

    def active_id(self) -> str | None:
        return self._active_id

    def _gap(self) -> int:
        return px(44) if self.orientation == "horizontal" else px(34)

    def _group_gap(self) -> int:
        return px(18)

    def _clamp_scroll(self) -> None:
        view = max(1, self._view_size()[0 if self.orientation == "horizontal" else 1])
        self._scroll = max(0, min(self._scroll, max(0, self._total - view + px(20))))

    def redraw(self) -> None:
        if self.surface is not None:
            self.canvas.delete(self._tag)
        else:
            self.delete("all")
        self._item_boxes.clear()
        if not self._items:
            return
        gap = self._gap()
        group_gap = self._group_gap()
        pos = px(14) - self._scroll
        active_color = theme.CYAN
        idle_color = theme.MUTED
        hover_color = theme.TEXT
        for idx, item in enumerate(self._items):
            if idx and self._is_group_break(idx):
                pos += group_gap
            x0, y0, x1, y1 = self._tick_bbox(pos)
            self._item_boxes[item.id] = (x0, y0, x1, y1)
            active = item.id == self._active_id
            hover = item.id == self._hover_id
            color = active_color if active else hover_color if hover else idle_color
            self._draw_tick(item, x0, y0, x1, y1, color=color, active=active, hover=hover)
            pos += gap
        self._total = pos + self._scroll + px(14)
        self._draw_scroll_hint()
        self.lift()

    def _is_group_break(self, idx: int) -> bool:
        it = self._items[idx]
        return bool(getattr(it, "group_break", False) or it.status == "group")

    def _tick_bbox(self, pos: int) -> tuple[int, int, int, int]:
        w, h = self._view_size()
        if self.orientation == "horizontal":
            return pos - px(10), px(6), pos + px(10), h - px(6)
        return px(6), pos - px(10), w - px(6), pos + px(10)

    def _tags(self, item: TimelineItem) -> tuple[str, ...]:
        return (self._tag, "timeline", "dash", item.id, self.orientation)

    def _draw_tick(self, item: TimelineItem, x0, y0, x1, y1, *, color: str, active: bool, hover: bool) -> None:
        tags = self._tags(item)
        if self.orientation == "horizontal":
            cx, base_y = (x0 + x1) // 2, y1 - px(10)
            tick_h = px(14) if active else px(10) if hover else px(8)
            x, ya = self._xy(cx, base_y - tick_h)
            _, ybb = self._xy(cx, base_y)
            self.canvas.create_line(x, ya, x, ybb, fill=color, width=2 if active else 1, tags=tags)
            if active:
                x3, y3 = self._xy(cx - px(3), base_y - tick_h - px(6))
                x4, y4 = self._xy(cx + px(3), base_y - tick_h)
                self.canvas.create_oval(x3, y3, x4, y4, fill=color, outline="", tags=tags)
            if item.unread:
                x3, y3 = self._xy(cx + px(4), base_y - tick_h - px(2))
                x4, y4 = self._xy(cx + px(8), base_y - tick_h + px(2))
                self.canvas.create_oval(x3, y3, x4, y4, fill=theme.AMBER, outline="", tags=tags)
        else:
            cy, base_x = (y0 + y1) // 2, x0 + px(10)
            tick_w = px(14) if active else px(10) if hover else px(8)
            xa, ya = self._xy(base_x, cy)
            xb, _ = self._xy(base_x + tick_w, cy)
            self.canvas.create_line(xa, ya, xb, ya, fill=color, width=2 if active else 1, tags=tags)
            if active:
                x3, y3 = self._xy(base_x + tick_w, cy - px(3))
                x4, y4 = self._xy(base_x + tick_w + px(6), cy + px(3))
                self.canvas.create_oval(x3, y3, x4, y4, fill=color, outline="", tags=tags)
            if item.unread:
                x3, y3 = self._xy(base_x + tick_w + px(1), cy - px(8))
                x4, y4 = self._xy(base_x + tick_w + px(5), cy - px(4))
                self.canvas.create_oval(x3, y3, x4, y4, fill=theme.AMBER, outline="", tags=tags)

    def _draw_scroll_hint(self) -> None:
        w, h = self._view_size()
        if self._total <= w + px(20) if self.orientation == "horizontal" else self._total <= h + px(20):
            return
        if self.orientation == "horizontal":
            x, y = self._xy(w - px(8), px(8))
        else:
            x, y = self._xy(px(8), h - px(8))
        self.canvas.create_text(x, y, text="?", fill=theme.MUTED, font=theme.font(8, True),
                                anchor="ne" if self.orientation == "horizontal" else "sw",
                                tags=(self._tag, "timeline", "dash"))

    def _item_at(self, x: int, y: int) -> TimelineItem | None:
        for item in self._items:
            box = self._item_boxes.get(item.id)
            if not box:
                continue
            x0, y0, x1, y1 = box
            pad = px(8)
            if x0 - pad <= x <= x1 + pad and y0 - pad <= y <= y1 + pad:
                return item
        return None

    # --- events -----------------------------------------------------------
    def _local(self, e) -> tuple[int, int] | None:
        if self.surface is None:
            return e.x, e.y
        rx, ry, w, h = self._region()
        x, y = e.x - rx, e.y - ry
        if 0 <= x <= w and 0 <= y <= h:
            return x, y
        return None

    def _on_surface_motion(self, e) -> None:
        pt = self._local(e)
        if pt is None:
            self._on_leave()
            return
        self._on_motion(_Point(pt[0], pt[1]))

    def _on_surface_click(self, e) -> None:
        pt = self._local(e)
        if pt is not None:
            self._on_click(_Point(pt[0], pt[1]))

    def _on_motion(self, e) -> None:
        item = self._item_at(e.x, e.y)
        hid = item.id if item else None
        if hid != self._hover_id:
            self._hover_id = hid
            self.redraw()
        if item is not None:
            self._show_popup(item)

    def _on_leave(self, _e=None) -> None:
        self.after(120, self._maybe_close_popup)
        if self._hover_id is not None:
            self._hover_id = None
            self.redraw()

    def _on_click(self, e) -> None:
        item = self._item_at(e.x, e.y)
        if item is None:
            return
        self.focus_set()
        self.activate(item)

    def activate(self, item: TimelineItem, *, from_popup: bool = False) -> None:
        self.set_active(item.id)
        self._emit(item, from_popup)

    def _on_wheel(self, e, delta=None) -> None:
        d = delta if delta is not None else getattr(e, "delta", 0)
        if d == 0:
            return
        step = px(40)
        self._scroll = max(0, self._scroll - (step if d > 0 else -step))
        self._clamp_scroll()
        self.redraw()

    # --- popup ------------------------------------------------------------
    def _show_popup(self, item: TimelineItem) -> None:
        if self._popup_for == item.id and self._popup is not None:
            return
        self.close_popup()
        root = self.winfo_toplevel()
        popup = tk.Frame(root, bg=theme.PANEL, bd=0, highlightthickness=1, highlightbackground=theme.LINE)
        scrim = tk.Frame(popup, bg=self._scrim)
        scrim.pack(fill=tk.BOTH, expand=True)
        inner = tk.Frame(scrim, bg=theme.PANEL)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        title = tk.Label(inner, text=item.label, bg=theme.PANEL, fg=theme.CYAN,
                         font=theme.font(9, True), anchor="w")
        title.pack(fill=tk.X, padx=px(10), pady=(px(8), px(4)))
        btns: list[tk.Widget] = []
        targets = item.children if item.children else [item]
        for child in targets:
            b = tk.Button(inner, text=child.label, anchor="w", relief="flat", bd=0,
                          bg=theme.PANEL, fg=theme.TEXT, activebackground=theme.PANEL_HI,
                          activeforeground=theme.CYAN, font=theme.font(9), cursor="hand2",
                          command=lambda c=child, p=item: self._popup_activate(p, c))
            b.pack(fill=tk.X, padx=px(6), pady=px(1))
            b.bind("<Enter>", lambda _e, w=b: w.configure(bg=theme.PANEL_HI, fg=theme.CYAN))
            b.bind("<Leave>", lambda _e, w=b: w.configure(bg=theme.PANEL, fg=theme.TEXT))
            btns.append(b)
        self._popup = popup
        self._popup_for = item.id
        self._popup_item = item
        self._popup_buttons = btns
        self._place_popup(item)
        popup.bind("<Leave>", lambda _e: self.after(120, self._maybe_close_popup))
        popup.bind("<Enter>", lambda _e: None)
        for b in btns:
            b.bind("<Escape>", lambda _e: self.close_popup())
            b.bind("<Tab>", self._on_tab)

    def _place_popup(self, item: TimelineItem) -> None:
        popup = self._popup
        if popup is None:
            return
        self.update_idletasks()
        popup.update_idletasks()
        box = self._item_boxes.get(item.id)
        if not box:
            return
        root = popup.winfo_toplevel()
        x0, y0, x1, y1 = self._dash_screen_box(item)
        pw = max(px(180), popup.winfo_reqwidth())
        ph = popup.winfo_reqheight()
        gap = px(4)
        # place() expects coordinates relative to the parent (the toplevel),
        # not screen coordinates.
        if self.orientation == "horizontal":
            x = (x0 + x1) // 2 - root.winfo_rootx() - pw // 2
            y = y1 - root.winfo_rooty() + gap
        else:
            x = x0 - root.winfo_rootx() - gap - pw   # left of the vertical dash
            y = (y0 + y1) // 2 - root.winfo_rooty() - ph // 2

        max_x = root.winfo_width() - pw - px(4)
        max_y = root.winfo_height() - ph - px(4)
        x = max(px(4), min(x, max(px(4), max_x)))
        y = max(px(4), min(y, max(px(4), max_y)))
        # Also stay inside the physical screen (Windows DPI scaling).
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        rx, ry = root.winfo_rootx(), root.winfo_rooty()
        x = max(px(4) - rx, min(x, sw - pw - px(4) - rx))
        y = max(px(4) - ry, min(y, sh - ph - px(4) - ry))
        popup.place(x=x, y=y, width=pw)
        popup.lift()

    def _in_popup_zone(self, x: int, y: int) -> bool:
        """Keep the popup alive over the dash, the popup and the narrow gap."""
        popup = self._popup
        item = self._popup_item
        if popup is None or item is None:
            return False
        pad = px(14)
        dx0, dy0, dx1, dy1 = self._dash_screen_box(item)
        px0 = popup.winfo_rootx()
        py0 = popup.winfo_rooty()
        px1, py1 = px0 + popup.winfo_width(), py0 + popup.winfo_height()
        return (dx0 - pad <= x <= dx1 + pad and dy0 - pad <= y <= dy1 + pad) or \
               (px0 - pad <= x <= px1 + pad and py0 - pad <= y <= py1 + pad)

    def close_popup(self) -> None:
        if self._popup is not None:
            try:
                self._popup.destroy()
            except tk.TclError:
                pass
        self._popup = None
        self._popup_for = None
        self._popup_item = None
        self._popup_buttons = []
        self._focus_idx = -1

    def _maybe_close_popup(self) -> None:
        try:
            x, y = self.winfo_pointerxy()
            w = self.winfo_containing(x, y)
        except tk.TclError:
            self.close_popup()
            return
        if self._in_popup_zone(x, y):
            return
        cur = w
        while cur is not None:
            if cur is self or cur is self._popup:
                return
            cur = getattr(cur, "master", None)
        self.close_popup()

    def _popup_activate(self, parent: TimelineItem, child: TimelineItem) -> None:
        self.close_popup()
        target = child if child is not parent else parent
        self.activate(target, from_popup=True)

    def focused(self) -> bool:
        try:
            f = self.focus_get()
        except Exception:
            return False
        cur = f
        while cur is not None:
            if cur is self or cur is self._popup:
                return True
            cur = getattr(cur, "master", None)
        return False

    def _move_focus(self, delta: int) -> str | None:
        if not self._items:
            return None
        if self._focus_idx < 0:
            try:
                cur = self._active_id or self._items[0].id
                self._focus_idx = [i.id for i in self._items].index(cur)
            except ValueError:
                self._focus_idx = 0
        self._focus_idx = max(0, min(len(self._items) - 1, self._focus_idx + delta))
        item = self._items[self._focus_idx]
        self._hover_id = item.id
        self.redraw()
        self._show_popup(item)
        return "break"

    def _on_key_left(self, _e):
        if self.orientation == "horizontal":
            return self._move_focus(-1)
        return None

    def _on_key_right(self, _e):
        if self.orientation == "horizontal":
            return self._move_focus(1)
        return None

    def _on_key_up(self, _e):
        if self.orientation == "vertical":
            return self._move_focus(-1)
        if self.orientation == "horizontal":
            item = self._current_focus_item()
            if item:
                self._show_popup(item)
                if self._popup_buttons:
                    self._popup_buttons[0].focus_set()
                return "break"
        return None

    def _on_key_down(self, _e):
        if self.orientation == "vertical":
            return self._move_focus(1)
        if self.orientation == "horizontal":
            item = self._current_focus_item()
            if item:
                self._show_popup(item)
                if self._popup_buttons:
                    self._popup_buttons[0].focus_set()
                return "break"
        return None

    def _current_focus_item(self) -> TimelineItem | None:
        if not self._items:
            return None
        if 0 <= self._focus_idx < len(self._items):
            return self._items[self._focus_idx]
        for i in self._items:
            if i.id == self._active_id:
                return i
        return self._items[0]

    def _on_key_activate(self, _e):
        item = self._current_focus_item()
        if item is None:
            return None
        if self._popup_buttons and self.focus_get() in self._popup_buttons:
            self.focus_get().invoke()
            return "break"
        self.activate(item)
        return "break"

    def _on_tab(self, _e):
        self.close_popup()
        return None


class _Point:
    __slots__ = ("x", "y")

    def __init__(self, x: int, y: int) -> None:
        self.x, self.y = x, y
