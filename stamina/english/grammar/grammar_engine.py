"""Gramma r Engine - generates exercises from grammar JSON files."""
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional


GRAAMMAR_DIR = Path(__file__).parent


def load_grammar(level: str) -> Dict[str, Any]:
    """Load grammar file for given CEFR level."""
    path = GRAAMMAR_DIR / f"{level.lower()}.json"
    if not path.exists():
        raise FileNotFoundError(f"Grammar file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_random_topic(grammar: Dict[str, Any]) -> Dict[str, Any]:
    """Select a random topic from grammar data."""
    topics = grammar.get("topics", [])
    if not topics:
        raise ValueError("No topics found in grammar data")
    return random.choice(topics)


def generate_exercise(level: str, topic_name: Optional[str] = None) -> Dict[str, Any]:
    """Generate an exercise for the given level and optional topic."""
    grammar = load_grammar(level)
    
    if topic_name:
        topic = next(
            (t for t in grammar["topics"] if t["name"] == topic_name),
            None,
        )
        if not topic:
            raise ValueError(f"Topic '{topic_name}' not found in {level} grammar")
    else:
        topic = get_random_topic(grammar)
    
    return {
        "level": level,
        "topic": topic["name"],
        "focus": topic["focus"],
        "exercise_count": topic["total_exercises"],
        "type": random.choice(["fill_gap", "transform", "choose_right", "make_question"]),
    }


def list_available_levels() -> List[str]:
    """Return list of available CEFR levels."""
    return sorted(
        p.stem for p in GRAAMMAR_DIR.glob("*.json") if p.stem not in {"tables"}
    )


def detect_level_from_sentence(sentence: str) -> Optional[str]:
    """Simple heuristic to detect CEFR level from sentence."""
    simple_markers = ["is", "are", "am", "have", "has"]
    if any(word in sentence.lower() for word in simple_markers):
        return "A1"
    return None


# Example usage
if __name__ == "__main__":
    print("Available levels:", list_available_levels())
    ex = generate_exercise("A1", "Present Simple")
    print(f"Generated exercise: {ex}")