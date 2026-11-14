"""Terraformer integration: rewards from language learning progress."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .registry import get_registry


TERRAFORMER_REWARDS = {
    "daily_goal_met": {"energy": 50, "xp": 10},
    "streak_3": {"energy": 100, "blueprint": "pipe_t1"},
    "streak_7": {"energy": 200, "blueprint": "pump_t1"},
    "streak_30": {"energy": 500, "robot_skin": "linguist_bot"},
    "level_up_A2": {"energy": 300, "unlock": "robot_A2"},
    "level_up_B1": {"energy": 500, "unlock": "robot_B1", "blueprint": "smart_network"},
    "level_up_B2": {"energy": 800, "unlock": "robot_B2"},
    "level_up_C1": {"energy": 1200, "unlock": "robot_C1", "blueprint": "quantum_link"},
    "level_up_C2": {"energy": 2000, "unlock": "robot_C2", "skin": "polyglot_commander"},
    "achievement_first_100": {"energy": 150},
    "achievement_1000_words": {"energy": 500, "blueprint": "maglev_t1"},
    "cross_pair_session": {"energy": 75, "bonus": "double_xp"},
}


class TerraformerRewards:
    def __init__(self, pilot_dir: Path):
        self.pilot_dir = pilot_dir
        self.terraformer_file = pilot_dir / "terraformer_rewards.json"
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            if self.terraformer_file.exists():
                import json
                return json.loads(self.terraformer_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"energy": 0, "blueprints": [], "skins": [], "unlocks": [], "history": []}

    def save(self) -> None:
        try:
            self.terraformer_file.write_text(
                __import__("json").dumps(self.data, ensure_ascii=False, indent=1),
                encoding="utf-8"
            )
        except OSError:
            pass

    def grant(self, event: str, lang: str, metadata: dict | None = None) -> dict[str, Any]:
        reward = TERRAFORMER_REWARDS.get(event, {})
        if not reward:
            return {}

        granted = {"event": event, "lang": lang, "timestamp": __import__("time").time(), **reward}
        if metadata:
            granted["metadata"] = metadata

        self.data["energy"] = self.data.get("energy", 0) + reward.get("energy", 0)
        if "blueprint" in reward:
            self.data.setdefault("blueprints", []).append(reward["blueprint"])
        if "skin" in reward:
            self.data.setdefault("skins", []).append(reward["skin"])
        if "unlock" in reward:
            self.data.setdefault("unlocks", []).append(reward["unlock"])
        self.data.setdefault("history", []).append(granted)

        self.save()
        return granted

    def get_energy(self) -> int:
        return self.data.get("energy", 0)

    def spend_energy(self, amount: int) -> bool:
        if self.data.get("energy", 0) >= amount:
            self.data["energy"] -= amount
            self.save()
            return True
        return False


def calculate_terraformer_energy(pilot_dir: Path) -> int:
    total = 0
    registry = get_registry()
    for plugin in registry.all():
        prog_file = pilot_dir / f"lang_{plugin.code}.json"
        if not prog_file.exists():
            continue
        try:
            import json
            data = json.loads(prog_file.read_text(encoding="utf-8"))
            prog_xp = data.get("xp", {}).get("total", 0)
            streak = 0
            by_day = data.get("xp", {}).get("by_day", {})
            from datetime import date, timedelta
            d = date.today()
            while by_day.get(d.isoformat(), 0) > 0:
                streak += 1
                d -= timedelta(days=1)
            total += prog_xp // 100
            total += min(streak * 5, 200)
        except Exception:
            pass
    return total


def on_language_event(event: str, lang: str, pilot_dir: Path, metadata: dict | None = None) -> dict[str, Any]:
    rewards = TerraformerRewards(pilot_dir)
    return rewards.grant(event, lang, metadata)