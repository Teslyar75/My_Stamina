"""Tests for Stage 3: resource deposit rendering and visibility (S3-res).

Covers:
- Big-map level has deposits of each resource type, spread across the map, count > 0
- A deposit in an unexplored cell is not visible/found
- After vision reveals the cell, the deposit is visible/found
- Once found, it stays visible after the unit moves away (explored but not currently in vision)
- A deposit on a built/revealed foundation or platform is treated as visible and would be drawn
"""

import sys
sys.path.insert(0, "D:/tmp/st-s3-res")

from stamina import terraformer_strategy as strategy
from stamina.terraformer_trainer import (
    TrainerModel,
    RESOURCES,
)
from stamina.terraformer_strategy import find_for_cell


class TestBigMapDepositsExist:
    """Deposits exist across the full big map for each level."""

    def test_each_level_has_all_resource_types(self):
        """Each level's map size should have deposits of all 5 resource types."""
        for level in strategy.LEVELS:
            w, h = strategy.map_size(level)
            model = TrainerModel.for_level(level, seed=1)
            # Count finds per resource
            counts = {r: 0 for r in RESOURCES}
            for (x, y), (res, layer) in model.finds.items():
                if res in counts:
                    counts[res] += 1
            # Each resource should have at least some deposits
            for res in RESOURCES:
                assert counts[res] > 0, f"Level {level} ({w}x{h}): no {res} deposits found"

    def test_deposits_spread_across_map(self):
        """Deposits should not be clustered only near origin; check spread."""
        model = TrainerModel.for_level("C2", seed=1)  # 100x60
        # Check that deposits exist in all quadrants
        quadrants = {
            "tl": 0, "tr": 0, "bl": 0, "br": 0
        }
        mid_x, mid_y = model.w // 2, model.h // 2
        for (x, y) in model.finds:
            if x < mid_x and y < mid_y:
                quadrants["tl"] += 1
            elif x >= mid_x and y < mid_y:
                quadrants["tr"] += 1
            elif x < mid_x and y >= mid_y:
                quadrants["bl"] += 1
            else:
                quadrants["br"] += 1
        # Each quadrant should have some deposits
        for q, count in quadrants.items():
            assert count > 0, f"Quadrant {q} has no deposits: {quadrants}"

    def test_reasonable_density_not_empty(self):
        """Total deposits should be reasonable for map size (not empty, not overwhelming)."""
        model = TrainerModel.for_level("C2", seed=1)  # 100x60 = 6000 cells
        total_cells = model.w * model.h
        total_finds = len(model.finds)
        # Density should be around 4-8% (FIND_PLAN targets ~6%)
        density = total_finds / total_cells
        assert 0.03 < density < 0.10, f"Density {density:.2%} out of range (3-10%)"

    def test_find_for_cell_works_for_all_coordinates(self):
        """find_for_cell should return deposits for any coordinate on big map."""
        model = TrainerModel.for_level("B2.1", seed=42)  # 88x52
        # Test several coordinates across the map
        test_coords = [
            (0, 0), (10, 5), (44, 26), (87, 51), (50, 30)
        ]
        found_any = False
        for x, y in test_coords:
            result = find_for_cell(model.seed, x, y)
            if result is not None:
                found_any = True
                res, layer = result
                assert res in RESOURCES
                assert layer in (0, 1, 2)
        assert found_any, "find_for_cell returned None for all test coordinates"


class TestDepositVisibility:
    """Deposit visibility follows fog-of-war rules."""

    def test_unexplored_deposit_not_visible(self):
        """Deposit in unexplored cell should not be in revealed/found."""
        model = TrainerModel(w=30, h=20, seed=1)
        model.units[0].x, model.units[0].y = 5, 5
        model._update_explored()
        # Pick a deposit far from unit
        deposit_cells = [c for c, (r, l) in model.finds.items() if r == "iron"]
        assert deposit_cells, "No iron deposits in test map"
        far_deposit = max(deposit_cells, key=lambda c: abs(c[0]-5) + abs(c[1]-5))
        # This deposit should not be explored or revealed
        assert not model.is_explored(*far_deposit), f"Deposit {far_deposit} should be unexplored"
        assert far_deposit not in model.revealed, f"Deposit {far_deposit} should not be revealed"
        assert model.finds_count.get("iron", 0) == 0, "Iron count should be 0 before reveal"

    def test_vision_reveals_deposit(self):
        """Moving unit to see deposit should reveal it."""
        model = TrainerModel(w=30, h=20, seed=1)
        model.units[0].x, model.units[0].y = 5, 5
        model._update_explored()
        # Find an iron deposit (layer 2)
        deposit_cells = [c for c, (r, l) in model.finds.items() if r == "iron"]
        assert deposit_cells
        target = deposit_cells[0]
        # Move unit to see it (A1 sight radius 4)
        model.units[0].x, model.units[0].y = target
        model._update_explored()
        # Now it should be explored and visible
        assert model.is_explored(*target)
        assert model.is_visible(*target, model.visible_cells())
        # Digging at the deposit layer should reveal it
        # (layer 2 for iron, so dig twice to reach layer 2)
        model.dug[target[1]][target[0]] = 2
        result = model._reveal(target[0], target[1], 2)
        assert result is not None, "Reveal should succeed"
        assert target in model.revealed
        assert model.finds_count.get("iron", 0) > 0

    def test_revealed_deposit_stays_visible_after_unit_moves(self):
        """Once revealed, deposit stays in revealed set even when unit moves away."""
        model = TrainerModel(w=30, h=20, seed=1)
        model.units[0].x, model.units[0].y = 5, 5
        model._update_explored()
        deposit_cells = [c for c, (r, l) in model.finds.items() if r == "organic"]
        assert deposit_cells
        target = deposit_cells[0]
        model.units[0].x, model.units[0].y = target
        model._update_explored()
        model.dug[target[1]][target[0]] = 0  # organic is layer 0
        model._reveal(target[0], target[1], 0)
        assert target in model.revealed
        # Move unit far away
        model.units[0].x, model.units[0].y = 25, 15
        model._update_explored()
        # Deposit should still be revealed (and explored)
        assert target in model.revealed, "Revealed deposit should stay revealed"
        assert model.is_explored(*target), "Revealed deposit cell should stay explored"
        # It should NOT be currently visible
        assert not model.is_visible(*target, model.visible_cells())
        # But finds_count should still show it
        assert model.finds_count.get("organic", 0) > 0

    def test_deposit_on_built_platform_is_visible(self):
        """Deposit at center of a built platform should be treated as visible for rendering."""
        model = TrainerModel(w=30, h=20, seed=1)
        # Find a water deposit
        deposit_cells = [c for c, (r, l) in model.finds.items() if r == "water"]
        assert deposit_cells
        center = deposit_cells[0]
        # Reveal it and create platform
        model.units[0].x, model.units[0].y = center
        model._update_explored()
        model.dug[center[1]][center[0]] = 0  # water can be layer 0 or 1
        model._reveal(center[0], center[1], 0)
        assert center in model.revealed
        # Find the platform
        platform = None
        for p in model.platforms:
            if p.center == center:
                platform = p
                break
        assert platform is not None, "Platform should be created for revealed deposit"
        # Mark platform as built (complete)
        platform.complete = True
        # Build all its blocks
        for rel in platform.pattern:
            abs_cell = platform.cell_abs(rel)
            platform.built.add(abs_cell)
            model.platform_blocks.add(abs_cell)
        # Now the deposit center should be considered visible for rendering
        # even if we check via a helper that considers platform centers
        from stamina.terraformer_trainer import deposit_is_visible
        assert deposit_is_visible(model, center[0], center[1]), \
            "Deposit on built platform should be visible"

    def test_deposit_on_unbuilt_platform_is_visible_if_revealed(self):
        """Deposit on platform that exists but not complete should be visible if revealed."""
        model = TrainerModel(w=30, h=20, seed=1)
        deposit_cells = [c for c, (r, l) in model.finds.items() if r == "stone"]
        assert deposit_cells
        center = deposit_cells[0]
        model.units[0].x, model.units[0].y = center
        model._update_explored()
        model.dug[center[1]][center[0]] = 1  # stone is layer 1
        model._reveal(center[0], center[1], 1)
        assert center in model.revealed
        from stamina.terraformer_trainer import deposit_is_visible
        assert deposit_is_visible(model, center[0], center[1]), \
            "Revealed deposit should be visible even if platform not complete"


class TestDepositRenderingLogic:
    """Test the logic that determines if a deposit should be drawn."""

    def test_deposit_is_visible_helper_exists(self):
        """deposit_is_visible(model, x, y) helper should exist and work."""
        from stamina.terraformer_trainer import deposit_is_visible
        model = TrainerModel(w=20, h=15, seed=1)
        # Test with a revealed deposit
        model.revealed.add((5, 5))
        model.finds[(5, 5)] = ("water", 0)
        assert deposit_is_visible(model, 5, 5) is True
        # Test with unexplored deposit
        model.finds[(10, 10)] = ("iron", 2)
        assert deposit_is_visible(model, 10, 10) is False
        # Test with deposit on built platform but not in revealed
        model.platforms.append(type('Platform', (), {
            'center': (15, 10), 'complete': True, 'pattern': ((1,0),)
        })())
        model.platform_blocks.add((16, 10))
        model.finds[(15, 10)] = ("quartz", 2)
        assert deposit_is_visible(model, 15, 10) is True


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])