"""SM-2 Spaced Repetition Algorithm."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class SM2Card:
    interval: int = 0
    ease_factor: float = 2.5
    repetitions: int = 0
    due_date: date | None = None
    last_review: date | None = None


class SM2Scheduler:
    @staticmethod
    def initial_card() -> SM2Card:
        return SM2Card(
            interval=0,
            ease_factor=2.5,
            repetitions=0,
            due_date=date.today(),
            last_review=None,
        )

    @staticmethod
    def next_interval(card: SM2Card, quality: int) -> SM2Card:
        if quality < 0 or quality > 5:
            raise ValueError("Quality must be 0-5")

        new_card = SM2Card(
            interval=card.interval,
            ease_factor=card.ease_factor,
            repetitions=card.repetitions,
            due_date=card.due_date,
            last_review=date.today(),
        )

        if quality < 3:
            new_card.repetitions = 0
            new_card.interval = 1
        else:
            if new_card.repetitions == 0:
                new_card.interval = 1
            elif new_card.repetitions == 1:
                new_card.interval = 6
            else:
                new_card.interval = math.ceil(new_card.interval * new_card.ease_factor)
            new_card.repetitions += 1

        new_card.ease_factor = max(1.3, new_card.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
        new_card.due_date = date.today() + timedelta(days=new_card.interval)

        return new_card

    @staticmethod
    def is_due(card: SM2Card) -> bool:
        if card.due_date is None:
            return True
        return card.due_date <= date.today()

    @staticmethod
    def days_until_due(card: SM2Card) -> int:
        if card.due_date is None:
            return 0
        delta = card.due_date - date.today()
        return max(0, delta.days)

    @staticmethod
    def quality_to_label(quality: int) -> str:
        return ["Again", "Hard", "Good", "Easy"][min(max(quality, 0), 3)] if quality < 4 else "Easy"