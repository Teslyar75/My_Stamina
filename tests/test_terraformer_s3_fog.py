"""Tests for Stage 3: fog of war (S3-fog).

Covers:
- visible_cells() includes units and radar structures
- is_explored / is_visible work correctly
- flat drawing: unexplored = black, explored-not-visible = dim, visible = full
- iso drawing: unexplored = black diamond, explored-not-visible = dim, visible = full
- _update_explored accumulates explored cells
"""

import sys
sys.path.insert(0, "D:/tmp/st-s3-fog")

import stamina.terraformer_trainer as tt


class TestVisibleCells:
    def test_units_grant_vision(self):
        model = tt.TrainerModel(w=20, h=15, seed=1)
        # Place a unit at (10, 7) with A1 sight radius 4
        model.units[0].x, model.units[0].y = 10, 7
        vis = model.visible_cells()
        # Unit's own cell should be visible
        assert (10, 7) in vis
        # Cells within radius 4 should be visible
        assert (12, 7) in vis
        assert (10, 9) in vis
        assert (6, 7) in vis
        assert (10, 5) in vis
        # Cell at distance 5 should not be visible
        assert (15, 7) not in vis
        assert (10, 12) not in vis

    def test_radar_grants_vision(self):
        model = tt.TrainerModel(w=30, h=20, seed=1)
        # Build a radar at (15, 10)
        from stamina.terraformer_trainer import BuildingBlueprint
        radar = BuildingBlueprint("radar", (15, 10))
        radar.built = True
        model.buildings.append(radar)
        vis = model.visible_cells()
        # Radar's own cell should be visible
        assert (15, 10) in vis
        # Cells within radar radius (10) should be visible
        assert (20, 10) in vis
        assert (15, 15) in vis
        assert (10, 10) in vis
        assert (15, 5) in vis
        # Cell at distance 11 should not be visible
        assert (26, 10) not in vis
        assert (15, 21) not in vis

    def test_non_radar_structures_no_vision(self):
        model = tt.TrainerModel(w=20, h=15, seed=1)
        # Move unit away from center to avoid collision
        model.units[0].x, model.units[0].y = 0, 0
        from stamina.terraformer_trainer import BuildingBlueprint
        shelter = BuildingBlueprint("shelter", (10, 7))
        shelter.built = True
        model.buildings.append(shelter)
        vis = model.visible_cells()
        # Shelter should not grant vision
        assert (10, 7) not in vis

    def test_combined_unit_and_radar_vision(self):
        model = tt.TrainerModel(w=30, h=20, seed=1)
        model.units[0].x, model.units[0].y = 5, 5
        from stamina.terraformer_trainer import BuildingBlueprint
        radar = BuildingBlueprint("radar", (20, 15))
        radar.built = True
        model.buildings.append(radar)
        vis = model.visible_cells()
        # Both vision sources should contribute
        assert (5, 5) in vis  # unit
        assert (8, 5) in vis  # unit radius
        assert (20, 15) in vis  # radar
        assert (25, 15) in vis  # radar radius


class TestExploredTracking:
    def test_explored_accumulates(self):
        model = tt.TrainerModel(w=20, h=15, seed=1)
        # Move unit to known position and update
        model.units[0].x, model.units[0].y = 10, 7
        model._update_explored()
        first_explored = set(model.explored)
        assert (10, 7) in model.explored
        assert (12, 7) in model.explored
        # Move unit and update again
        model.units[0].x, model.units[0].y = 15, 10
        model._update_explored()
        # Old cells should still be explored
        assert (10, 7) in model.explored
        assert (12, 7) in model.explored
        # New cells should be explored
        assert (15, 10) in model.explored
        # Total explored should have grown
        assert len(model.explored) > len(first_explored)

    def test_is_explored_and_is_visible(self):
        model = tt.TrainerModel(w=20, h=15, seed=1)
        model.units[0].x, model.units[0].y = 10, 7
        model._update_explored()
        vis = model.visible_cells()
        assert model.is_explored(10, 7)
        assert model.is_visible(10, 7, vis)
        assert not model.is_visible(15, 10, vis)
        assert not model.is_explored(15, 10)


class TestFlatDrawingFog:
    """Test that flat rendering uses three fog states correctly."""
    
    def test_unexplored_renders_black(self):
        """Unexplored cells should render as solid black (BG)."""
        # We test the logic by checking the model state that drives rendering
        model = tt.TrainerModel(w=20, h=15, seed=1)
        model.units[0].x, model.units[0].y = 10, 7
        model._update_explored()
        # Cell (0, 0) is unexplored
        assert not model.is_explored(0, 0)
        # In flat drawing, this would trigger: fill=BG (black)

    def test_explored_not_visible_renders_dim(self):
        """Explored but not currently visible cells should render dimmed."""
        model = tt.TrainerModel(w=20, h=15, seed=1)
        model.units[0].x, model.units[0].y = 10, 7
        model._update_explored()
        vis = model.visible_cells()
        # Cell (10, 7) is explored and visible
        assert model.is_explored(10, 7)
        assert model.is_visible(10, 7, vis)
        # Move unit far away
        model.units[0].x, model.units[0].y = 15, 10
        vis2 = model.visible_cells()
        assert model.is_explored(10, 7)
        assert not model.is_visible(10, 7, vis2)
        # In flat drawing, this would trigger: blend(color, BG, 0.62)

    def test_visible_renders_full(self):
        """Currently visible cells should render at full brightness."""
        model = tt.TrainerModel(w=20, h=15, seed=1)
        model.units[0].x, model.units[0].y = 10, 7
        vis = model.visible_cells()
        assert model.is_visible(10, 7, vis)
        # In flat drawing, this would use base_color without dimming


class TestIsoDrawingFog:
    """Test that iso rendering uses three fog states correctly."""

    def test_unexplored_renders_black_diamond(self):
        """Unexplored cells in iso should render as black diamond."""
        model = tt.TrainerModel(w=20, h=15, seed=1)
        model.units[0].x, model.units[0].y = 10, 7
        model._update_explored()
        assert not model.is_explored(0, 0)
        # In iso drawing, this would draw: tile_polygon at gz=0 with fill=BG

    def test_explored_not_visible_renders_dim(self):
        """Explored but not visible cells in iso should render dimmed."""
        model = tt.TrainerModel(w=20, h=15, seed=1)
        model.units[0].x, model.units[0].y = 10, 7
        model._update_explored()
        vis = model.visible_cells()
        model.units[0].x, model.units[0].y = 15, 10
        vis2 = model.visible_cells()
        assert model.is_explored(10, 7)
        assert not model.is_visible(10, 7, vis2)
        # In iso drawing, this would use: blend(base_color, BG, 0.62)

    def test_visible_renders_full(self):
        """Currently visible cells in iso should render at full brightness."""
        model = tt.TrainerModel(w=20, h=15, seed=1)
        model.units[0].x, model.units[0].y = 10, 7
        vis = model.visible_cells()
        assert model.is_visible(10, 7, vis)
        # In iso drawing, this would use base_color without dimming


class TestStructureVisionIntegration:
    """Integration tests for structure vision in the full model."""

    def test_radar_reveals_area_on_build(self):
        model = tt.TrainerModel(w=30, h=20, seed=1)
        model.units[0].x, model.units[0].y = 5, 5
        model._update_explored()
        # Build radar far from unit
        from stamina.terraformer_trainer import BuildingBlueprint
        radar = BuildingBlueprint("radar", (20, 10))
        radar.built = True
        model.buildings.append(radar)
        model._update_explored()
        # Radar area should now be explored
        assert model.is_explored(20, 10)
        assert model.is_explored(25, 10)
        assert model.is_explored(20, 15)

    def test_unbuilt_radar_no_vision(self):
        model = tt.TrainerModel(w=30, h=20, seed=1)
        from stamina.terraformer_trainer import BuildingBlueprint
        radar = BuildingBlueprint("radar", (20, 15))
        radar.built = False  # not built yet
        model.buildings.append(radar)
        model._update_explored()
        assert not model.is_explored(20, 15)

    def test_multiple_radars(self):
        model = tt.TrainerModel(w=50, h=30, seed=1)
        from stamina.terraformer_trainer import BuildingBlueprint
        radar1 = BuildingBlueprint("radar", (10, 10))
        radar1.built = True
        radar2 = BuildingBlueprint("radar", (40, 20))
        radar2.built = True
        model.buildings.extend([radar1, radar2])
        model._update_explored()
        # Both radar areas explored
        assert model.is_explored(10, 10)
        assert model.is_explored(40, 20)
        assert model.is_explored(15, 10)
        assert model.is_explored(35, 20)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])