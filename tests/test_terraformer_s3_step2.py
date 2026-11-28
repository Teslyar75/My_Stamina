"""Шаг 2: галерея A1–C2, напоминания и постоянная разведка."""
from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from pathlib import Path

import pytest

from stamina import pilots, terraformer_strategy as strategy, theme
from stamina.terraformer_trainer import BuildingBlueprint, TrainerModel, generate_finds


class TestPermanentIntel:
    """Фундамент, постройки и побыванная земля не закрываются туманом."""

    def test_permanent_cells_and_explored(self) -> None:
        model = TrainerModel(w=30, h=20, seed=1)
        victim = model.add_unit("A1", x=12, y=9)
        model.blocks.append((11, 9))
        model.platform_blocks.add((12, 10))
        model.visited.add((20, 10))
        building = BuildingBlueprint("shelter", (13, 9))
        building.built = True
        model.buildings.append(building)

        permanent = model._permanent_cells()
        assert set(model.site_cells()).issubset(permanent)
        assert {(11, 9), (12, 10), (13, 9), (20, 10)}.issubset(permanent)
        assert (victim.x, victim.y) in model.visited

        model.explored.clear()
        model._update_explored()
        assert permanent.issubset(model.explored)

    def test_building_marks_cell_explored(self) -> None:
        model = TrainerModel(w=30, h=20, seed=1)
        model.credits = 1000
        ok, _ = model.build_structure("shelter", 20, 10)
        assert ok
        assert (20, 10) in model.visited
        assert model.is_explored(20, 10)

    def test_worm_loss_keeps_permanent_cells(self, monkeypatch: pytest.MonkeyPatch) -> None:
        model = TrainerModel(w=30, h=20, seed=1)
        victim = model.add_unit("A1", x=15, y=7)
        victim.hp = 1
        far = {(25, 15), (26, 15), (27, 15), (28, 15)}
        model.explored.update(far)
        monkeypatch.setattr(strategy, "worm_step",
                            lambda *args, **kwargs: ((victim.x, victim.y), False))
        model._tick_count = strategy.WORM_MOVE_EVERY - 1

        event = model.tick_worm()
        assert event is not None and event.get("lost_intel")
        assert victim not in model.units
        assert 0 < len(far & model.explored) < len(far)
        assert set(model.site_cells()).issubset(model.explored)
        assert model.visited.issubset(model.explored)

    def test_main_unit_death_does_not_erase_intel(self, monkeypatch: pytest.MonkeyPatch) -> None:
        model = TrainerModel(w=30, h=20, seed=1)
        main = model.main_unit
        main.hp = 1
        model.explored.add((25, 15))
        monkeypatch.setattr(strategy, "worm_step",
                            lambda *args, **kwargs: ((main.x, main.y), False))
        model._tick_count = strategy.WORM_MOVE_EVERY - 1
        event = model.tick_worm()
        assert event is not None and not event.get("lost_intel")
        assert (25, 15) in model.explored

    def test_visited_survives_blueprint(self) -> None:
        model = TrainerModel(w=30, h=20, seed=42)
        model.visited.add((19, 11))
        model.explored.add((19, 11))
        blueprint = model.to_blueprint()
        assert blueprint["version"] == 6
        assert [19, 11] in blueprint["visited"]
        restored = TrainerModel.from_blueprint(blueprint)
        assert (19, 11) in restored.visited
        assert restored._permanent_cells().issubset(restored.explored)


class _Event:
    def __init__(self, x: float = 0, y: float = 0) -> None:
        self.x = x
        self.y = y


class TestStep2Ui(unittest.TestCase):
    """Галерея и напоминания в обоих видах карты."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.root = tk.Tk()
        except tk.TclError:
            cls.root = None
            return
        theme.init(cls.root)
        cls.root.geometry("1100x700")

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
        self.tmp = tempfile.TemporaryDirectory()
        data = Path(self.tmp.name) / "Stamina"
        data.mkdir()
        pilots.reset_root(data)
        pilots.activate(pilots.create("Tester")["id"])
        from stamina.lounge.trainer import TrainerGame
        try:
            self.game = TrainerGame(self.root, on_back=lambda: None, app=None)
            self.game.pack(fill=tk.BOTH, expand=True)
            self.root.update()
            self.game.redraw()
        except tk.TclError as exc:
            if "image" in str(exc).lower():
                self.tmp.cleanup()
                self.skipTest(f"Tk image: {exc}")
            raise

    def tearDown(self) -> None:
        try:
            self.game.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.game.destroy()
        except tk.TclError:
            pass
        pilots.reset_root()
        self.tmp.cleanup()

    def _texts(self) -> list[str]:
        c = self.game.canvas
        return [c.itemcget(i, "text") for i in c.find_all() if c.type(i) == "text"]

    def test_gallery_has_all_levels_and_click_selects_one(self) -> None:
        game = self.game
        game.toggle_gallery()
        self.root.update()
        tags = [set(game.canvas.gettags(i)) for i in game.canvas.find_all()]
        level_tags = set()
        for item_tags in tags:
            for tag in item_tags:
                if tag.startswith("gallery_level:"):
                    level_tags.add(tag.split(":", 1)[1])
        assert level_tags == set(strategy.LEVELS)
        assert any("РАСКЛАДКА" in text for text in self._texts())

        items = game.canvas.find_withtag("gallery_level:C2")
        assert items
        box = game.canvas.bbox(items[0])
        assert box is not None
        e = _Event((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        game._on_lmb_down(e)
        assert game._gallery_level == "C2"
        game.redraw()
        assert any("КАРТА 100×60" in text for text in self._texts())

    def test_gallery_layout_is_seeded(self) -> None:
        game = self.game
        seed = game.model.seed
        first = game._gallery_finds("C2")
        assert first == generate_finds(seed, 100, 60)
        game.model.seed = seed + 1
        game._gallery_finds_cache.clear()
        assert game._gallery_finds("C2") != first

    def test_reminders_visible_in_flat_and_iso(self) -> None:
        game = self.game
        texts = self._texts()
        assert any(text.startswith("НУЖНО:") for text in texts)
        assert any(text.startswith("МОЖНО:") for text in texts)
        game.on_key(type("E", (), {"keysym": "i", "keycode": 73, "state": 0})())
        self.root.update()
        texts = self._texts()
        assert game.iso_view
        assert any(text.startswith("НУЖНО:") for text in texts)
        assert any(text.startswith("МОЖНО:") for text in texts)

    def test_intel_loss_shows_toast(self) -> None:
        game = self.game
        game.model.tick_worm = lambda: {"cell": None, "spice": False,
                                        "attacked": None, "lost_intel": True}
        game.tick()
        self.root.update()
        assert game.toast is not None
        assert "разведданных" in game.toast[0]
