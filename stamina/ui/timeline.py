from __future__ import annotations

import inspect
import tkinter as tk
from dataclasses import dataclass, field

from stamina import monitors, theme
from stamina.theme import blend, px


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
        # Плавный рост штриха: 0 — обычный, 1 — рядом с курсором. Один таймер
        # на всю ленту, при достижении цели он сам останавливается.
        self._hover_progress: dict[str, float] = {}
        self._hover_targets: dict[str, float] = {}
        self._anim_job: str | None = None
        self._tick_boxes: dict[str, tuple[float, float, float, float]] = {}
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
        """Экранные границы зоны штриха (старый API, используется тестами)."""
        box = self._item_boxes.get(item.id)
        if not box:
            return 0, 0, 0, 0
        x0, y0, x1, y1 = box
        ox, oy = self._screen_origin()
        return ox + x0, oy + y0, ox + x1, oy + y1

    def _tick_screen_box(self, item: TimelineItem) -> tuple[float, float, float, float]:
        """Экранные границы самого штриха — меню прижимается к нему, а не к зоне."""
        box = self._tick_boxes.get(item.id) or self._item_boxes.get(item.id)
        if not box:
            return 0, 0, 0, 0
        x0, y0, x1, y1 = box
        ox, oy = self._screen_origin()
        return ox + x0, oy + y0, ox + x1, oy + y1

    def _full_tick_screen_box(self, item: TimelineItem) -> tuple[float, float, float, float]:
        """Границы штриха в полностью выросшем состоянии.

        Popup ставится сразу сюда и больше не едет: иначе меню появляется у
        короткого штриха, а затем его «толкает» растущая чёрточка, и кнопка
        дёргается перед глазами.
        """
        box = self._item_boxes.get(item.id)
        if not box:
            return self._tick_screen_box(item)
        x0, y0, x1, y1 = box
        ox, oy = self._screen_origin()
        if self.orientation == "horizontal":
            cx = (x0 + x1) / 2
            top = y0 + px(6)
            return ox + cx, oy + top, ox + cx, oy + top + px(30)
        cy = (y0 + y1) / 2
        right = x1 - px(6)
        return ox + right - px(28), oy + cy, ox + right, oy + cy

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
        ids = {i.id for i in self._items}
        self._hover_progress = {k: v for k, v in self._hover_progress.items() if k in ids}
        self._hover_targets = {k: v for k, v in self._hover_targets.items() if k in ids}
        self._hover_id = self._hover_id if self._hover_id in ids else None
        if self._active_id not in ids:
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
        self._tick_boxes.clear()
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
            self._draw_tick(item, x0, y0, x1, y1, color=color, active=active, hover=hover,
                            glow=self._hover_progress.get(item.id, 0.0))
            pos += gap
        self._total = pos + self._scroll + px(14)
        self._draw_scroll_hint()
        self.lift()
        if self._popup is not None and self._popup_item is not None:
            self._place_popup(self._popup_item)

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

    def _draw_tick(self, item: TimelineItem, x0, y0, x1, y1, *, color: str, active: bool,
                   hover: bool, glow: float = 0.0) -> None:
        tags = self._tags(item)
        glow = max(0.0, min(1.0, glow))
        # Короткая чёрточка — приглушённая; у курсора — в 2–3 раза длиннее и ярче.
        bright = blend(color, theme.TEXT, 0.12 + 0.60 * glow)
        width = 3 if glow > 0.6 else 2 if active or hover or glow > 0.1 else 1
        if self.orientation == "horizontal":
            # Верхняя лента растёт вниз — к меню, а не вверх под край окна.
            cx, base_y = (x0 + x1) // 2, y0 + px(6)
            base_h = px(14) if active else px(8)
            tick_h = base_h + (px(30) - base_h) * glow
            x, ya = self._xy(cx, base_y)
            _, ybb = self._xy(cx, base_y + tick_h)
            self._tick_boxes[item.id] = (cx, base_y, cx, base_y + tick_h)
            self.canvas.create_line(x, ya, x, ybb, fill=bright, width=width, tags=tags)
            if active:
                x3, y3 = self._xy(cx - px(3), base_y + tick_h)
                x4, y4 = self._xy(cx + px(3), base_y + tick_h + px(6))
                self.canvas.create_oval(x3, y3, x4, y4, fill=bright, outline="", tags=tags)
            if item.unread:
                x3, y3 = self._xy(cx + px(4), base_y + tick_h - px(2))
                x4, y4 = self._xy(cx + px(8), base_y + tick_h + px(2))
                self.canvas.create_oval(x3, y3, x4, y4, fill=theme.AMBER, outline="", tags=tags)
        else:
            # Правая лента растёт ВЛЕВО — навстречу меню, а не за край окна.
            cy, base_x = (y0 + y1) // 2, x1 - px(6)
            base_w = px(14) if active else px(8)
            tick_w = base_w + (px(28) - base_w) * glow
            xa, ya = self._xy(base_x - tick_w, cy)
            xb, _ = self._xy(base_x, cy)
            self._tick_boxes[item.id] = (base_x - tick_w, cy, base_x, cy)
            self.canvas.create_line(xa, ya, xb, ya, fill=bright, width=width, tags=tags)
            if active:
                x3, y3 = self._xy(base_x + px(1), cy - px(3))
                x4, y4 = self._xy(base_x + px(7), cy + px(3))
                self.canvas.create_oval(x3, y3, x4, y4, fill=bright, outline="", tags=tags)
            if item.unread:
                x3, y3 = self._xy(base_x - px(6), cy - px(8))
                x4, y4 = self._xy(base_x - px(2), cy - px(4))
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

    def _near_items(self, x: int, y: int) -> dict[str, float]:
        """Цели анимации для штрихов под курсором и рядом с ним.

        Верхняя лента растёт вниз, правая — влево. «Рядом» — полшага до
        соседнего штриха: он тоже начинает светиться, но чуть слабее.
        """
        out: dict[str, float] = {}
        rx, ry, rw, rh = self._region()
        pad = px(14)
        if not (-pad <= x <= rw + pad and -pad <= y <= rh + pad):
            return out
        gap = self._gap()
        for item in self._items:
            box = self._item_boxes.get(item.id)
            if not box:
                continue
            x0, y0, x1, y1 = box
            if self.orientation == "horizontal":
                cx, half = (x0 + x1) / 2, (x1 - x0) / 2
                dist = abs(x - cx)
                span = y0 - pad <= y <= y1 + gap / 2 + pad
            else:
                cy, half = (y0 + y1) / 2, (y1 - y0) / 2
                dist = abs(y - cy)
                span = x0 - pad <= x <= x1 + gap / 2 + pad
            if not span or dist > gap / 2 + px(10):
                continue
            out[item.id] = 1.0 if dist <= half + px(8) else 0.45
        return out

    def _set_hover_targets(self, targets: dict[str, float]) -> None:
        self._hover_targets = dict(targets)
        for iid in list(self._hover_progress):
            if iid not in self._hover_targets:
                self._hover_targets[iid] = 0.0
        if self._anim_job is None and any(
            abs(self._hover_progress.get(iid, 0.0) - target) > 0.001
            for iid, target in self._hover_targets.items()
        ):
            self._anim_job = self.after(16, self._animate_hover)

    def _animate_hover(self) -> None:
        self._anim_job = None
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        changed = False
        for iid, target in list(self._hover_targets.items()):
            cur = self._hover_progress.get(iid, 0.0)
            if abs(cur - target) <= 0.001:
                continue
            step = 0.20 if cur < target else 0.14
            nxt = min(target, cur + step) if cur < target else max(target, cur - step)
            self._hover_progress[iid] = nxt
            changed = True
        if changed:
            self.redraw()
        if any(abs(self._hover_progress.get(iid, 0.0) - target) > 0.001
               for iid, target in self._hover_targets.items()):
            try:
                self._anim_job = self.after(16, self._animate_hover)
            except tk.TclError:
                pass

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
        targets = self._near_items(e.x, e.y)
        item = self._item_at(e.x, e.y)
        if item is None and targets:
            nearest = max(targets, key=lambda iid: targets[iid])
            item = next((i for i in self._items if i.id == nearest), None)
        hid = item.id if item else None
        if hid != self._hover_id:
            self._hover_id = hid
        self._set_hover_targets(targets)
        if item is not None:
            self._show_popup(item)
        elif self._popup is not None and self._popup_item is not None:
            self._place_popup(self._popup_item)

    def _on_leave(self, _e=None) -> None:
        self.after(160, self._maybe_close_popup)
        self._hover_id = None
        self._set_hover_targets({})

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
        return "break"

    # --- popup ------------------------------------------------------------
    def _show_popup(self, item: TimelineItem) -> None:
        if self._popup_for == item.id and self._popup is not None:
            self._place_popup(item)   # чёрточка выросла — меню едет за её концом
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
        x0, y0, x1, y1 = self._full_tick_screen_box(item)
        if x1 <= x0 and y1 <= y0:
            return
        root = popup.winfo_toplevel()
        rx, ry = root.winfo_rootx(), root.winfo_rooty()
        pw = max(px(180), popup.winfo_reqwidth())
        ph = popup.winfo_reqheight()
        gap = px(10)   # чуть шире, чтобы выросший штрих не «толкал» кнопки
        # place() expects coordinates relative to the parent (the toplevel),
        # not screen coordinates.
        if self.orientation == "horizontal":
            sx, sy = (x0 + x1) / 2 - pw / 2, y1 + gap
        else:
            sx, sy = x0 - gap - pw, (y0 + y1) / 2 - ph / 2
        x, y = sx - rx, sy - ry
        max_x = root.winfo_width() - pw - px(4)
        max_y = root.winfo_height() - ph - px(4)
        x = max(px(4), min(x, max(px(4), max_x)))
        y = max(px(4), min(y, max(px(4), max_y)))
        # Окно может стоять на втором мониторе с отрицательными координатами:
        # winfo_screenwidth() знает только основной экран, поэтому границы
        # берём из рабочей области монитора, на котором находится чёрточка.
        anchor_x, anchor_y = int((x0 + x1) / 2), int((y0 + y1) / 2)
        area = monitors.work_area(self, anchor_x, anchor_y)
        sx, sy = monitors.fit(rx + x, ry + y, pw, ph, area)
        popup.place(x=int(sx - rx), y=int(sy - ry), width=pw)
        popup.lift()

    def _in_popup_zone(self, x: int, y: int) -> bool:
        """Меню живёт, пока курсор идёт от чёрточки к кнопкам и по самому меню."""
        popup = self._popup
        item = self._popup_item
        if popup is None or item is None:
            return False
        pad = px(40)
        dx0, dy0, dx1, dy1 = self._full_tick_screen_box(item)
        px0 = popup.winfo_rootx()
        py0 = popup.winfo_rooty()
        px1, py1 = px0 + popup.winfo_width(), py0 + popup.winfo_height()
        if (dx0 - pad <= x <= dx1 + pad and dy0 - pad <= y <= dy1 + pad) or \
           (px0 - pad <= x <= px1 + pad and py0 - pad <= y <= py1 + pad):
            return True
        # Коридор между выросшим штрихом и меню: при диагональном движении
        # курсор не должен покидать зону на полпути к кнопке.
        return min(dx0, px0) - pad <= x <= max(dx1, px1) + pad and \
               min(dy0, py0) - pad <= y <= max(dy1, py1) + pad

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
