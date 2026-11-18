"""Quality review system (4-grade self-assessment)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QualityReview:
    slug: str
    grade: int
    timestamp: float
    mode: str


class QualityReviewEngine:
    GRADES = {
        0: ("Again", "Повторить"),
        1: ("Hard", "Сложно"),
        2: ("Good", "Хорошо"),
        3: ("Easy", "Легко"),
    }

    def __init__(self, progress, vocab):
        self.progress = progress
        self.vocab = vocab

    def get_due_quality(self, slugs: list[str], limit: int = 20) -> list[str]:
        due = []
        quality_data = self.progress.data.get("quality", {})
        for slug in slugs:
            q = quality_data.get(slug)
            if q is None or q.get("due", 0) <= 0:
                due.append(slug)
        return due[:limit]

    def record_quality(self, slug: str, grade: int, mode: str = "quality") -> None:
        if grade not in self.GRADES:
            raise ValueError("Grade must be 0-3")
        import time
        quality_data = self.progress.data.setdefault("quality", {})
        quality_data[slug] = {
            "grade": grade,
            "last_review": time.time(),
            "due": self._next_interval(grade),
            "streak": quality_data.get(slug, {}).get("streak", 0) + (1 if grade >= 2 else 0),
        }
        self.progress.save()

    def _next_interval(self, grade: int) -> int:
        intervals = [0, 1, 3, 7]
        return intervals[grade]

    def get_quality_stats(self) -> dict[str, int]:
        quality_data = self.progress.data.get("quality", {})
        counts = {0: 0, 1: 0, 2: 0, 3: 0}
        for q in quality_data.values():
            g = q.get("grade", 0)
            if g in counts:
                counts[g] += 1
        return counts