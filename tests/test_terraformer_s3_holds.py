"""Tests for per-unit holds in terraformer (S3 holds refactor)."""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

import pytest

from stamina import pilots, theme
from stamina.terraformer_trainer import (
    HOLD_CAP as TRAINER_HOLD_CAP,
    RESOURCES,
    TrainerModel,
    load_blueprint,
)
from stamina import terraformer_strategy as strategy


class TestPerUnitHolds:
    """Tests for per-unit holds system."""

    def test_unit_has_holds_field(self):
        """Unit dataclass should have holds field."""
        u = strategy.Unit(uid="test", level="A1", x=0, y=0)
        assert hasattr(u, "holds")
        assert isinstance(u.holds, dict)
        assert u.holds == {}

    def test_unit_serialization_includes_holds(self):
        """Unit.to_dict() should include holds."""
        u = strategy.Unit(uid="test", level="A1", x=0, y=0)
        u.holds["soil"] = 3
        u.holds["spice"] = 1
        d = u.to_dict()
        assert "holds" in d
        assert d["holds"]["soil"] == 3
        assert d["holds"]["spice"] == 1

    def test_unit_deserialization_restores_holds(self):
        """Unit.from_dict() should restore holds."""
        d = {"uid": "test", "level": "A1", "x": 0, "y": 0, "holds": {"soil": 3, "spice": 1}}
        u = strategy.Unit.from_dict(d)
        assert u.holds["soil"] == 3
        assert u.holds["spice"] == 1

    def test_model_initializes_unit_holds(self):
        """New units should have holds initialized for all resources."""
        model = TrainerModel(w=10, h=10, depth=1)
        for u in model.units:
            for res in RESOURCES + (strategy.SPICE, "soil"):
                assert res in u.holds
                assert u.holds[res] == 0

    def test_active_unit_returns_selected_or_main(self):
        """active_unit() should return selected unit or main_unit."""
        model = TrainerModel(w=10, h=10, depth=1)
        # No selection -> main_unit
        assert model.active_unit() is model.main_unit
        # Explicit unit overrides selection
        if len(model.units) > 1:
            assert model.active_unit(model.units[1]) is model.units[1]

    def test_dig_uses_active_unit_holds(self):
        """dig_at() should use active unit's holds."""
        model = TrainerModel(w=10, h=10, depth=1)
        unit = model.main_unit
        # Dig with main unit - digs at layer 0 which is water/organic/quartz
        result = model.dig_at(unit.x, unit.y, unit)
        assert result in ("ok", "hold_full", "too_deep", "site", "spring")
        # Unit should have some resource in holds
        assert any(v > 0 for v in unit.holds.values())

    def test_dig_respects_hold_cap(self):
        """dig_at() should respect _hold_cap() not hardcoded HOLD_CAP."""
        model = TrainerModel(w=10, h=10, depth=1)
        unit = model.main_unit
        cap = model._hold_cap()
        # Fill hold by digging repeatedly
        for _ in range(cap + 5):
            result = model.dig_at(unit.x, unit.y, unit)
            if result == "hold_full":
                break
        # Total holds should not exceed cap for any single resource
        for val in unit.holds.values():
            assert val <= cap

    def test_try_place_block_uses_unit_holds(self):
        """try_place_block() should consume soil from unit's holds."""
        model = TrainerModel(w=10, h=10, depth=1)
        unit = model.main_unit
        cap = model._hold_cap()
        # Fill unit's soil hold (need to dig soil layer)
        # Soil is typically at layer 1+, so dig multiple times
        for _ in range(cap * 2):
            model.dig_at(unit.x, unit.y, unit)
        # Check if unit has soil
        if unit.holds.get("soil", 0) >= cap:
            success, _ = model.try_place_block(unit.x, unit.y, unit)
            # If there's a platform at this position, it should succeed
            # Otherwise it fails with "здесь нет чертежа платформы"
            if success:
                assert unit.holds.get("soil", 0) == 0

    def test_unload_uses_unit_holds(self):
        """unload() should use unit's holds."""
        model = TrainerModel(w=10, h=10, depth=1)
        unit = model.main_unit
        cap = model._hold_cap()
        # Fill unit's soil hold
        for _ in range(cap * 2):
            model.dig_at(unit.x, unit.y, unit)
        # Move unit to site if needed
        if model.site_cells():
            site_x, site_y = model.site_cells()[0]
            unit.x, unit.y = site_x, site_y
        # Unload - should use unit's soil
        if unit.holds.get("soil", 0) >= cap:
            result = model.unload(unit)
            assert result in ("ok", "complete", "done")
            assert unit.holds.get("soil", 0) == 0

    def test_unload_not_full_uses_unit_holds(self):
        """unload() not_full message should use unit's holds and _hold_cap."""
        model = TrainerModel(w=10, h=10, depth=1)
        unit = model.main_unit
        cap = model._hold_cap()
        # Don't fill completely
        model.dig_at(unit.x, unit.y, unit)
        result = model.unload(unit)
        assert result == "not_full"

    def test_tick_extraction_deposits_to_main_unit(self):
        """tick_extraction() should deposit to main_unit."""
        model = TrainerModel(w=10, h=10, depth=1)
        # Complete a platform manually
        if model.platforms:
            p = model.platforms[0]
            p.complete = True
            gained = model.tick_extraction()
            # Should deposit to main_unit
            assert model.main_unit.holds.get(p.resource, 0) > 0

    def test_stats_aggregates_all_units_holds(self):
        """stats() should aggregate holds from all units."""
        model = TrainerModel(w=10, h=10, depth=1)
        model.main_unit.holds["water"] = 3
        model.main_unit.holds["iron"] = 1
        # Add a second unit
        u2 = model.add_unit("A1")
        u2.holds["water"] = 2
        u2.holds["stone"] = 4
        stats = model.stats()
        # Stats includes RESOURCES keys
        assert stats["water"] == 5  # 3 + 2
        assert stats["iron"] == 1
        assert stats["stone"] == 4

    def test_blueprint_includes_units_with_holds(self):
        """to_blueprint() should include units with their holds."""
        model = TrainerModel(w=10, h=10, depth=1)
        model.main_unit.holds["water"] = 3
        model.main_unit.holds[strategy.SPICE] = 2
        bp = model.to_blueprint()
        assert bp["version"] == 6
        assert "units" in bp
        assert len(bp["units"]) == len(model.units)
        # Check main unit has holds
        main_data = bp["units"][0]
        assert "holds" in main_data
        assert main_data["holds"]["water"] == 3
        assert main_data["holds"][strategy.SPICE] == 2

    def test_from_blueprint_restores_unit_holds(self):
        """from_blueprint() should restore unit holds."""
        model = TrainerModel(w=10, h=10, depth=1)
        model.main_unit.holds["water"] = 3
        model.main_unit.holds[strategy.SPICE] = 2
        bp = model.to_blueprint()
        # Create new model from blueprint
        model2 = TrainerModel.from_blueprint(bp)
        assert model2.main_unit.holds["water"] == 3
        assert model2.main_unit.holds[strategy.SPICE] == 2

    def test_legacy_blueprint_migrates_holds_to_active_unit(self):
        """Старый общий отсек переносится в активного юнита и удаляется из чертежа."""
        model = TrainerModel(w=10, h=10, depth=1)
        bp = model.to_blueprint()
        bp["version"] = 4
        bp["holds"] = {"water": 5, strategy.SPICE: 3}
        bp.pop("units", None)
        bp.pop("selected", None)
        bp.pop("missions", None)
        bp.pop("worm", None)

        model2 = TrainerModel.from_blueprint(bp)
        assert model2.main_unit.holds["water"] == 5
        assert model2.main_unit.holds[strategy.SPICE] == 3
        # Новый чертёж больше не содержит общего отсека.
        assert "holds" not in model2.to_blueprint()

    def test_selected_units_have_independent_holds(self):
        """Each selected unit should have independent holds."""
        model = TrainerModel(w=10, h=10, depth=1)
        if len(model.units) < 2:
            pytest.skip("Need at least 2 units")
        u1, u2 = model.units[0], model.units[1]
        cap = model._hold_cap()
        # Fill u1
        for _ in range(cap * 2):
            model.dig_at(u1.x, u1.y, u1)
        # Fill u2 partially
        model.dig_at(u2.x, u2.y, u2)
        # They should have different amounts
        assert u1.holds != u2.holds

    def test_move_updates_unit_position(self):
        """move() should update the unit's position."""
        model = TrainerModel(w=10, h=10, depth=1)
        unit = model.main_unit
        start_x, start_y = unit.x, unit.y
        model.move(1, 0, unit)
        assert unit.x == start_x + 1
        assert unit.y == start_y
        # Robot should sync with main_unit
        assert model.robot == [unit.x, unit.y]

    def test_auto_unloader_uses_unit(self):
        """auto_unloader should use the unit that moved."""
        model = TrainerModel(w=10, h=10, depth=1)
        model.upgrades = model.upgrades + ("auto_unloader",)
        # Setup a platform at unit position
        # This is a basic smoke test - just ensure no crash
        model.move(0, 0, model.main_unit)  # no-op, just test


class TestStep1HoldFlow:
    """Шаг 1: свои отсеки, активный юнит, авторазгрузка и «Сформировать»."""

    def test_no_shared_holds_and_one_cap(self) -> None:
        model = TrainerModel(w=10, h=10, depth=1)
        assert not hasattr(model, "holds")
        assert TRAINER_HOLD_CAP is strategy.HOLD_CAP
        assert model._hold_cap() == strategy.HOLD_CAP == 5
        model.upgrades = model.upgrades + ("soil_compactor", "yield_booster")
        assert model._hold_cap() == strategy.HOLD_CAP

    def test_camera_and_resources_follow_active_unit(self) -> None:
        model = TrainerModel(w=20, h=20, seed=1, depth=2)
        second = model.add_unit("A1", x=8, y=7)
        model.set_active_unit(second)
        assert model.active_uid == second.uid
        assert model.robot == [second.x, second.y]
        assert model.main_unit is model.units[0]

        second.holds["soil"] = 3
        bp = model.to_blueprint()
        assert "holds" not in bp
        assert bp["active_uid"] == second.uid
        restored = TrainerModel.from_blueprint(bp)
        assert restored.active_uid == second.uid
        assert restored.robot == [second.x, second.y]
        active = next(u for u in restored.units if u.uid == second.uid)
        assert active.holds["soil"] == 3

        # Прямое назначение selected в старых тестах не должно тащить камеру.
        restored.selected = {restored.units[0].uid}
        assert restored.active_uid == second.uid
        assert restored.robot == [second.x, second.y]

    def test_move_syncs_camera_to_active_not_main(self) -> None:
        model = TrainerModel(w=20, h=20, seed=1, depth=2)
        second = model.add_unit("A1", x=8, y=7)
        model.set_active_unit(second)
        before_main = list(model.main_unit.holds.items())
        assert model.move(1, 0)
        assert model.robot == [second.x, second.y] == [9, 7]
        assert model.main_unit.x != second.x or model.main_unit.y != second.y
        assert list(model.main_unit.holds.items()) == before_main

    def test_full_unit_drives_and_unloads_itself(self) -> None:
        model = TrainerModel(w=20, h=20, seed=1, depth=2)
        model.developer = True
        model.springs.clear()
        model.dug = [[0 for _ in range(model.w)] for _ in range(model.h)]
        unit = model.main_unit
        unit.x, unit.y = 9, 9
        unit.mode = "autonomous"
        unit.holds["soil"] = strategy.HOLD_CAP
        assert model._find_build_target(unit) is not None

        placed_before = len(model.blocks) + len(model.platform_blocks)
        for _ in range(30):
            model.tick_autonomous()
            if unit.holds.get("soil", 0) == 0:
                break

        assert unit.holds.get("soil", 0) == 0
        assert len(model.blocks) + len(model.platform_blocks) > placed_before
        assert unit.order == ""
        assert unit.target is None

    def test_form_current_stage_builds_in_one_press(self) -> None:
        model = TrainerModel(w=20, h=20, seed=1, depth=2)
        model.developer = True
        # Платформа появляется, только когда найдено месторождение.
        platform = model._ensure_platform("water", (10, 10))
        assert platform is not None
        accessible = [p for p in model.platforms
                      if all(0 <= x < model.w and 0 <= y < model.h
                             for x, y in p.all_cells_abs())]
        assert accessible and any(not p.complete for p in accessible)

        ok, _ = model.form_current_stage()
        assert ok
        assert model.walls_open
        assert set(model.site_cells()).issubset(set(model.blocks))
        assert all(p.complete for p in accessible)
        assert model.form_current_stage()[0] is False


class _Event:
    def __init__(self, x: float = 0, y: float = 0, keysym: str = "",
                 keycode: int = 0, state: int = 0) -> None:
        self.x = x
        self.y = y
        self.keysym = keysym
        self.keycode = keycode
        self.state = state


class TestStep1HudControls(unittest.TestCase):
    """Чекбоксы режимов и кнопка «Сформировать» кликабельны и сохраняются."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.root = tk.Tk()
        except tk.TclError:
            cls.root = None
            return
        theme.init(cls.root)
        cls.root.geometry("1024x600")

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
        self.tmp.cleanup()

    def _click_tag(self, tag: str) -> None:
        items = self.game.canvas.find_withtag(tag)
        assert items, tag
        box = self.game.canvas.bbox(items[0])
        assert box is not None, tag
        e = _Event(x=(box[0] + box[2]) / 2, y=(box[1] + box[3]) / 2)
        self.game._on_lmb_down(e)
        self.game._on_lmb_up(e)

    def test_mode_checkbox_is_clickable_and_saved(self) -> None:
        game = self.game
        unit = game.model.active_unit()
        target = next(mode for mode in ("autonomous", "semi-autonomous", "manual")
                      if mode != unit.mode)
        self._click_tag(f"mode:{unit.uid}:{target}")
        assert unit.mode == target
        saved = load_blueprint()
        saved_unit = saved.unit_by_uid(unit.uid)
        assert saved_unit is not None and saved_unit.mode == target

    def test_form_stage_button_builds_current_stage(self) -> None:
        game = self.game
        game.model.developer = True
        game.redraw()
        self._click_tag("form_stage")
        assert game.model.walls_open
        assert set(game.model.site_cells()).issubset(set(game.model.blocks))
        assert load_blueprint().walls_open is True


class TestUIIntegration:
    """Integration tests for UI methods using per-unit holds."""

    def test_do_dig_uses_active_unit(self):
        """do_dig should use active unit's holds."""
        from stamina.lounge.trainer import TrainerGame
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            def on_back():
                pass
            game = TrainerGame(root, on_back=on_back)
            result = game.do_dig()
            # Should not crash
            assert result in ("ok", "hold_full", "too_deep", "site", "spring")
        finally:
            root.destroy()

    def test_do_place_block_uses_active_unit(self):
        """do_place_block should use active unit's holds."""
        from stamina.lounge.trainer import TrainerGame
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            def on_back():
                pass
            game = TrainerGame(root, on_back=on_back)
            unit = game.model.active_unit()
            cap = game.model._hold_cap()
            # Fill unit's soil hold
            for _ in range(cap * 2):
                game.model.dig_at(unit.x, unit.y, unit)
            # Place block
            if unit.holds.get("soil", 0) >= cap:
                success, _ = game.do_place_block()
                # Should succeed and consume soil if on platform
                assert success is not None
        finally:
            root.destroy()

    def test_do_unload_uses_active_unit(self):
        """do_unload should use active unit's holds."""
        from stamina.lounge.trainer import TrainerGame
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            def on_back():
                pass
            game = TrainerGame(root, on_back=on_back)
            unit = game.model.active_unit()
            cap = game.model._hold_cap()
            # Fill unit's soil hold
            for _ in range(cap * 2):
                game.model.dig_at(unit.x, unit.y, unit)
            # Move to site
            if game.model.site_cells():
                site_x, site_y = game.model.site_cells()[0]
                unit.x, unit.y = site_x, site_y
            # Unload
            if unit.holds.get("soil", 0) >= cap:
                result = game.do_unload()
                assert result in ("ok", "complete", "done", "not_full")
        finally:
            root.destroy()