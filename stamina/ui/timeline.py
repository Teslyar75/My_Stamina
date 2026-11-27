from __future__ import annotations

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
    """Interactive timeline ribbon.

    orientation: horizontal|vertical. Items: list[dict|TimelineItem].
    """

    def __init__(self, master, *, orientation: str = "horizontal", command=None,
                 bg: str | None = None, scrim: str = "#0B0E14", **kw):
        self.orientation = orientation
        self.command = command
        self._items: list[TimelineItem] = []
        self._active_id: str | None = None
        self._hover_id: str | None = None
        self._popup: tk.Frame | None = None
        self._popup_for: str | None = None
        self._popup_buttons: list[tk.Widget] = []
        self._focus_idx: int = -1
        self._item_boxes: dict[str, tuple[int, int, int, int]] = {}
        self._scroll = 0
        self._total = 0
        self._scrim = scrim
        bg = bg or theme.BG
        strip = px(40) if orientation == "horizontal" else px(52)
        w = kw.pop("width", strip if orientation == "vertical" else 200)
        h = kw.pop("height", strip if orientation == "horizontal" else 200)
        super().__init__(master, bg=bg, highlightthickness=0, width=w, height=h, **kw)
        self.bind("<Configure>", lambda _e: self.redraw())
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.bind("<MouseWheel>", self._on_wheel)
        self.bind("<Button-4>", lambda e: self._on_wheel(e, delta=120))
        self.bind("<Button-5>", lambda e: self._on_wheel(e, delta=-120))
        self.bind("<Left>", self._on_key_left)
        self.bind("<Right>", self._on_key_right)
        self.bind("<Up>", self._on_key_up)
        self.bind("<Down>", self._on_key_down)
        self.bind("<Return>", self._on_key_activate)
        self.bind("<KP_Enter>", self._on_key_activate)
        self.bind("<Escape>", lambda _e: self.close_popup())
        self.bind("<Tab>", self._on_tab)
        self.bind("<FocusOut>", lambda _e: self.after_idle(self._maybe_close_popup))

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
        view = max(1, (self.winfo_width() if self.orientation == "horizontal" else self.winfo_height()))
        self._scroll = max(0, min(self._scroll, max(0, self._total - view + px(20))))

    def redraw(self) -> None:
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

    def _is_group_break(self, idx: int) -> bool:
        # Larger gap before items that start a semantic group; callers can encode
        # by adding item.status=="group" or by label convention. Default: none.
        it = self._items[idx]
        return bool(getattr(it, "group_break", False) or it.status == "group")

    def _tick_bbox(self, pos: int) -> tuple[int, int, int, int]:
        w = max(1, self.winfo_width())
        h = max(1, self.winfo_height())
        if self.orientation == "horizontal":
            cx = pos
            return cx - px(10), px(6), cx + px(10), h - px(6)
        cy = pos
        return px(6), cy - px(10), w - px(6), cy + px(10)

    def _draw_tick(self, item: TimelineItem, x0, y0, x1, y1, *, color: str, active: bool, hover: bool) -> None:
        if self.orientation == "horizontal":
            cx = (x0 + x1) // 2
            base_y = y1 - px(10)
            tick_h = px(14) if active else px(10) if hover else px(8)
            self.create_line(cx, base_y - tick_h, cx, base_y, fill=color, width=2 if active else 1, tags=("tick", item.id))
            if active:
                self.create_oval(cx - px(3), base_y - tick_h - px(6), cx + px(3), base_y - tick_h, fill=color, outline="")
            if item.unread:
                self.create_oval(cx + px(4), base_y - tick_h - px(2), cx + px(8), base_y - tick_h + px(2), fill=theme.AMBER, outline="")
        else:
            cy = (y0 + y1) // 2
            base_x = x0 + px(10)
            tick_w = px(14) if active else px(10) if hover else px(8)
            self.create_line(base_x, cy, base_x + tick_w, cy, fill=color, width=2 if active else 1, tags=("tick", item.id))
            if active:
                self.create_oval(base_x + tick_w, cy - px(3), base_x + tick_w + px(6), cy + px(3), fill=color, outline="")
            if item.unread:
                self.create_oval(base_x + tick_w + px(1), cy - px(8), base_x + tick_w + px(5), cy - px(4), fill=theme.AMBER, outline="")

    def _draw_scroll_hint(self) -> None:
        view = max(1, (self.winfo_width() if self.orientation == "horizontal" else self.winfo_height()))
        if self._total <= view + px(20):
            return
        if self.orientation == "horizontal":
            self.create_text(self.winfo_width() - px(8), px(8), text="?", fill=theme.MUTED, font=theme.font(8, True), anchor="ne")
        else:
            self.create_text(px(8), self.winfo_height() - px(8), text="?", fill=theme.MUTED, font=theme.font(8, True), anchor="sw")

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

    def activate(self, item: TimelineItem) -> None:
        self.set_active(item.id)
        if self.command:
            self.command(item.id, item)

    def _on_wheel(self, e, delta=None) -> None:
        d = delta if delta is not None else getattr(e, "delta", 0)
        if d == 0:
            return
        step = px(40)
        self._scroll = max(0, self._scroll - (step if d > 0 else -step))
        self._clamp_scroll()
        self.redraw()

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
        x0, y0, x1, y1 = box
        rx = self.winfo_rootx()
        ry = self.winfo_rooty()
        pw = max(px(180), popup.winfo_reqwidth())
        ph = popup.winfo_reqheight()
        if self.orientation == "horizontal":
            x = rx + (x0 + x1) // 2 - pw // 2
            y = ry + y1 + px(2)
        else:
            x = rx + x1 + px(2)
            y = ry + (y0 + y1) // 2 - ph // 2
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(8, min(x, sw - pw - 8))
        y = max(8, min(y, sh - ph - 8))
        popup.place(x=x, y=y, width=pw)
        popup.lift()

    def close_popup(self) -> None:
        if self._popup is not None:
            try:
                self._popup.destroy()
            except tk.TclError:
                pass
        self._popup = None
        self._popup_for = None
        self._popup_buttons = []
        self._focus_idx = -1

    def _maybe_close_popup(self) -> None:
        try:
            x, y = self.winfo_pointerxy()
            w = self.winfo_containing(x, y)
        except tk.TclError:
            self.close_popup()
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
        self.activate(target)

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
            # open popup / focus first child
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
        # Let app-level focus traversal move between ribbons.
        self.close_popup()
        return None
