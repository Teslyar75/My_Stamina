"""Mission generation for language practice."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from .base import VocabSource, WordEntry
from .scheduler import SM2Scheduler


@dataclass
class Mission:
    slug: str
    mode: str
    word: WordEntry
    prompt: str
    expected: str | list[str]
    options: list[str] = None
    metadata: dict[str, Any] = None


class MissionGenerator:
    def __init__(self, vocab: VocabSource, progress, settings: dict):
        self.vocab = vocab
        self.progress = progress
        self.settings = settings
        self._pool: list[str] = []

    def generate_session(self, slugs: list[str], new_limit: int = None, review_limit: int = None) -> list[Mission]:
        self._pool = list(slugs)
        new_limit = new_limit or self.settings.get("new_per_day", 20)
        review_limit = review_limit or self.settings.get("reviews_per_day", 200)

        due_slugs = self.progress.get_due_cards(slugs, review_limit)
        new_slugs = self.progress.get_new_cards(slugs, new_limit)

        missions = []
        for slug in due_slugs:
            word = self.vocab.get_word(slug)
            if word:
                missions.append(self._make_review_mission(word))

        for slug in new_slugs:
            word = self.vocab.get_word(slug)
            if word:
                missions.append(self._make_new_mission(word))

        random.shuffle(missions)
        return missions

    def cards_session(self, slugs: list[str], limit: int = 10) -> list[Mission]:
        """Свободная практика по набору: без учёта расписания, только слова."""
        self._pool = list(slugs)
        missions: list[Mission] = []
        for slug in self._pool[:limit]:
            word = self.vocab.get_word(slug)
            if word:
                missions.append(self._make_new_mission(word))
        random.shuffle(missions)
        return missions

    def _make_review_mission(self, word: WordEntry) -> Mission:
        modes = ["choice", "type", "speak", "listen"]
        mode = random.choice(modes)
        return self._make_mission(word, mode, review=True)

    def _make_new_mission(self, word: WordEntry) -> Mission:
        return self._make_mission(word, "choice", review=False)

    def _make_mission(self, word: WordEntry, mode: str, review: bool) -> Mission:
        translations = word.translations.get("ru") or [word.lemma]
        expected = translations[0]

        if mode == "choice":
            options = [expected]
            pool = list(self._pool)
            random.shuffle(pool)
            for sw in pool:
                if len(options) >= 4:
                    break
                if sw == word.slug:
                    continue
                w = self.vocab.get_word(sw)
                if w and w.translations.get("ru", [""])[0] != expected:
                    options.append(w.translations.get("ru", [""])[0])
            random.shuffle(options)
            prompt = f"Переведите: {word.lemma}"
            return Mission(
                slug=word.slug,
                mode=mode,
                word=word,
                prompt=prompt,
                expected=expected,
                options=options,
                metadata={"review": review},
            )
        elif mode == "type":
            prompt = f"Напишите перевод: {word.lemma}"
            return Mission(
                slug=word.slug,
                mode=mode,
                word=word,
                prompt=prompt,
                expected=expected,
                metadata={"review": review},
            )
        elif mode == "speak":
            prompt = f"Произнесите: {word.lemma}"
            return Mission(
                slug=word.slug,
                mode=mode,
                word=word,
                prompt=prompt,
                expected=word.lemma,
                metadata={"review": review},
            )
        elif mode == "listen":
            prompt = "Прослушайте и напишите"
            return Mission(
                slug=word.slug,
                mode=mode,
                word=word,
                prompt=prompt,
                expected=expected,
                metadata={"review": review, "audio": True},
            )
        else:
            return self._make_mission(word, "choice", review)