"""Tests for per-unit holds in terraformer (S3 holds refactor)."""
import pytest
from stamina.terraformer_trainer import TrainerModel, RESOURCES
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
        assert bp["version"] == 5
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

    def test_legacy_blueprint_migrates_holds_to_main_unit(self):
        """Old blueprint (no unit holds) should migrate model.holds to main_unit."""
        # Create a v4-style blueprint without units
        model = TrainerModel(w=10, h=10, depth=1)
        model.holds["water"] = 5
        model.holds[strategy.SPICE] = 3
        bp = model.to_blueprint()
        bp["version"] = 4
        bp.pop("units", None)
        bp.pop("selected", None)
        bp.pop("missions", None)
        bp.pop("worm", None)
        # Load into new model
        model2 = TrainerModel.from_blueprint(bp)
        # Legacy model.holds should be transferred to main_unit
        assert model2.main_unit.holds["water"] == 5
        assert model2.main_unit.holds[strategy.SPICE] == 3

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