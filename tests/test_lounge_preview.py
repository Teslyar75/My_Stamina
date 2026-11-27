"""Tests for lounge preview thumbnails: no overlapping text, text inside terminal box."""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
import unittest
from typing import Any

from stamina import theme
from stamina.lounge.screen import LoungeScreen, _draw_terminal_preview


class _AppStub:
    """Minimal app stub for LoungeScreen."""
    living = None

    def set_status(self, *args: Any, **kwargs: Any) -> None:
        pass

    def open_help(self) -> None:
        pass


class LoungePreviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.root = tk.Tk()
        except tk.TclError:
            cls.root = None
            return
        theme.init(cls.root)
        cls.root.geometry("1280x720")

    @classmethod
    def tearDownClass(cls) -> None:
        if getattr(cls, "root", None) is not None:
            try:
                cls.root.destroy()
            except tk.TclError:
                pass

    def setUp(self) -> None:
        if getattr(self, "root", None) is None:
            self.skipTest("нет дисплея")
        self.lounge = LoungeScreen(self.root, _AppStub())
        self.lounge.pack(fill=tk.BOTH, expand=True)
        self.root.update_idletasks()
        # Wait for the after(50, draw) callbacks to fire
        self.root.after(100, lambda: None)
        self.root.update()

    def tearDown(self) -> None:
        try:
            self.lounge.destroy()
        except tk.TclError:
            pass
        self.root.update()

    def _get_card_canvas(self, game_id: str) -> tk.Canvas | None:
        for card in self.lounge.cards:
            if card["id"] == game_id:
                return card["prev"]
        return None

    def _collect_text_bboxes(self, canvas: tk.Canvas) -> list[tuple[int, int, int, int]]:
        """Return list of (x1, y1, x2, y2) for all text items on canvas."""
        bboxes = []
        for item_id in canvas.find_all():
            if canvas.type(item_id) == "text":
                try:
                    bbox = canvas.bbox(item_id)
                    if bbox:
                        bboxes.append(bbox)
                except tk.TclError:
                    pass
        return bboxes

    def _find_terminal_rect(self, canvas: tk.Canvas) -> tuple[int, int, int, int] | None:
        """Find the dark terminal rectangle (create_rectangle with dark fill)."""
        for item_id in canvas.find_all():
            if canvas.type(item_id) == "rectangle":
                try:
                    coords = canvas.coords(item_id)
                    fill = canvas.itemcget(item_id, "fill")
                    # Terminal boxes have dark fills like #0D1117, #1a1a2e, #012456
                    if fill and fill.startswith("#") and len(coords) == 4:
                        x1, y1, x2, y2 = coords
                        # Check it's a reasonably sized box (not a tiny decoration)
                        if x2 - x1 > 50 and y2 - y1 > 30:
                            return (int(x1), int(y1), int(x2), int(y2))
                except tk.TclError:
                    pass
        return None

    def _assert_no_vertical_overlap(self, bboxes: list[tuple[int, int, int, int]]) -> None:
        """Assert no two text bboxes overlap vertically (allow 1px rounding)."""
        for i, (x1a, y1a, x2a, y2a) in enumerate(bboxes):
            for j, (x1b, y1b, x2b, y2b) in enumerate(bboxes):
                if i >= j:
                    continue
                # Check vertical overlap: allow 1px tolerance
                if not (y2a <= y1b + 1 or y2b <= y1a + 1):
                    self.fail(
                        f"Text bboxes overlap vertically: "
                        f"bbox {i}=({x1a},{y1a},{x2a},{y2a}) vs bbox {j}=({x1b},{y1b},{x2b},{y2b})"
                    )

    def _assert_inside_terminal(
        self,
        bboxes: list[tuple[int, int, int, int]],
        term_rect: tuple[int, int, int, int],
        canvas_w: int,
        canvas_h: int,
    ) -> None:
        """Assert every text bbox is fully inside terminal rect and canvas."""
        tx1, ty1, tx2, ty2 = term_rect
        for i, (x1, y1, x2, y2) in enumerate(bboxes):
            # Inside terminal rect (with small tolerance for rounding)
            self.assertGreaterEqual(x1, tx1 - 1, f"bbox {i} x1 < term x1")
            self.assertGreaterEqual(y1, ty1 - 1, f"bbox {i} y1 < term y1")
            self.assertLessEqual(x2, tx2 + 1, f"bbox {i} x2 > term x2")
            self.assertLessEqual(y2, ty2 + 1, f"bbox {i} y2 > term y2")
            # Inside canvas
            self.assertGreaterEqual(x1, -1, f"bbox {i} x1 < 0")
            self.assertGreaterEqual(y1, -1, f"bbox {i} y1 < 0")
            self.assertLessEqual(x2, canvas_w + 1, f"bbox {i} x2 > canvas_w")
            self.assertLessEqual(y2, canvas_h + 1, f"bbox {i} y2 > canvas_h")

    def test_docker_trainer_preview(self) -> None:
        canvas = self._get_card_canvas("docker_trainer")
        self.assertIsNotNone(canvas, "docker_trainer card not found")
        assert canvas is not None

        bboxes = self._collect_text_bboxes(canvas)
        term_rect = self._find_terminal_rect(canvas)
        self.assertIsNotNone(term_rect, "Terminal rectangle not found for docker_trainer")
        assert term_rect is not None

        self._assert_no_vertical_overlap(bboxes)
        self._assert_inside_terminal(bboxes, term_rect, canvas.winfo_width(), canvas.winfo_height())
        self.assertGreaterEqual(len(bboxes), 2, "At least 2 text lines should be drawn")

    def test_linux_trainer_preview(self) -> None:
        canvas = self._get_card_canvas("linux_trainer")
        self.assertIsNotNone(canvas, "linux_trainer card not found")
        assert canvas is not None

        bboxes = self._collect_text_bboxes(canvas)
        term_rect = self._find_terminal_rect(canvas)
        self.assertIsNotNone(term_rect, "Terminal rectangle not found for linux_trainer")
        assert term_rect is not None

        self._assert_no_vertical_overlap(bboxes)
        self._assert_inside_terminal(bboxes, term_rect, canvas.winfo_width(), canvas.winfo_height())
        self.assertGreaterEqual(len(bboxes), 2, "At least 2 text lines should be drawn")

    def test_powershell_trainer_preview(self) -> None:
        canvas = self._get_card_canvas("powershell_trainer")
        self.assertIsNotNone(canvas, "powershell_trainer card not found")
        assert canvas is not None

        bboxes = self._collect_text_bboxes(canvas)
        term_rect = self._find_terminal_rect(canvas)
        self.assertIsNotNone(term_rect, "Terminal rectangle not found for powershell_trainer")
        assert term_rect is not None

        self._assert_no_vertical_overlap(bboxes)
        self._assert_inside_terminal(bboxes, term_rect, canvas.winfo_width(), canvas.winfo_height())
        self.assertGreaterEqual(len(bboxes), 2, "At least 2 text lines should be drawn")

    def test_draw_terminal_preview_small_canvas(self) -> None:
        """Test _draw_terminal_preview directly on a small canvas (px(80) height)."""
        c = tk.Canvas(self.root, width=240, height=80, bg=theme.BG)
        c.pack()
        self.root.update_idletasks()

        ww, hh = 240, 80
        mono_font_spec = theme.font(7, mono=True)
        box_w = int(ww * 0.85)
        box_h = int(hh * 0.7)
        ox = (ww - box_w) // 2
        oy = (hh - box_h) // 2
        lines = [
            ("$ docker run -d ship/radio", theme.AMBER),
            ("abc123def456", theme.TEXT),
            ("$ docker ps", theme.AMBER),
            ("CONTAINER ID   IMAGE          STATUS    PORTS     NAMES", theme.TEXT),
            ("abc123def456   ship/radio     Up 5s     8080/tcp  ship_abc", theme.TEXT),
            ("$ docker logs abc123", theme.AMBER),
            ("[radio] Module ready ✓", theme.CYAN),
        ]
        _draw_terminal_preview(c, ww, hh, ox, oy, box_w, box_h, "#0D1117", theme.AMBER, lines, mono_font_spec)
        self.root.update_idletasks()

        bboxes = self._collect_text_bboxes(c)
        term_rect = self._find_terminal_rect(c)
        self.assertIsNotNone(term_rect)
        assert term_rect is not None

        self._assert_no_vertical_overlap(bboxes)
        self._assert_inside_terminal(bboxes, term_rect, ww, hh)
        self.assertGreaterEqual(len(bboxes), 2, "At least 2 text lines should fit on small canvas")
        c.destroy()

    def test_draw_terminal_preview_even_smaller_canvas(self) -> None:
        """Test _draw_terminal_preview on an even smaller canvas."""
        c = tk.Canvas(self.root, width=200, height=60, bg=theme.BG)
        c.pack()
        self.root.update_idletasks()

        ww, hh = 200, 60
        mono_font_spec = theme.font(7, mono=True)
        box_w = int(ww * 0.85)
        box_h = int(hh * 0.7)
        ox = (ww - box_w) // 2
        oy = (hh - box_h) // 2
        lines = [
            ("$ docker run -d ship/radio", theme.AMBER),
            ("abc123def456", theme.TEXT),
            ("$ docker ps", theme.AMBER),
            ("CONTAINER ID   IMAGE          STATUS    PORTS     NAMES", theme.TEXT),
        ]
        _draw_terminal_preview(c, ww, hh, ox, oy, box_w, box_h, "#0D1117", theme.AMBER, lines, mono_font_spec)
        self.root.update_idletasks()

        bboxes = self._collect_text_bboxes(c)
        term_rect = self._find_terminal_rect(c)
        self.assertIsNotNone(term_rect)
        assert term_rect is not None

        self._assert_no_vertical_overlap(bboxes)
        self._assert_inside_terminal(bboxes, term_rect, ww, hh)
        self.assertGreaterEqual(len(bboxes), 2, "At least 2 text lines should fit")
        c.destroy()


if __name__ == "__main__":
    unittest.main()