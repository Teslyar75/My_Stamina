"""Ленивая загрузка открытых источников Grimm Grammar и ZUM Grammatik-Kiste.

При выборе вкладки читаются только source.json и index.json. Файл темы —
при первом открытии, дальше небольшой LRU. Тексты отдаются как есть,
без перевода.
"""
from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path

from stamina.grammar_ui.model import SourceTab

SOURCES_DIR = Path(__file__).resolve().parent / "grammar" / "sources"

SOURCE_TABS = (
    SourceTab(
        id="grimm_grammar",
        title="По методике Grimm Grammar — Техасский университет (COERLL), CC BY 4.0",
    ),
    SourceTab(
        id="zum_grammatik_kiste",
        title="По методике ZUM Deutsch Lernen, CC BY 4.0",
    ),
)

_RESERVED = {"source.json", "index.json", "skipped.json"}


def available_source_ids() -> list[str]:
    found = []
    for tab in SOURCE_TABS:
        if (SOURCES_DIR / tab.id / "source.json").is_file():
            found.append(tab.id)
    return found


def source_tabs() -> list[SourceTab]:
    have = set(available_source_ids())
    return [tab for tab in SOURCE_TABS if tab.id in have]


class OpenSourceBank:
    """Кэш индексов и тем открытых источников. Не читает файлы в конструкторе."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or SOURCES_DIR
        self._meta: dict[str, dict] = {}
        self._index: dict[str, dict] = {}
        self._topics: dict[str, OrderedDict[str, dict]] = {}
        self._lru_size = 8

    def meta(self, source_id: str) -> dict:
        if source_id not in self._meta:
            path = self.root / source_id / "source.json"
            self._meta[source_id] = json.loads(path.read_text(encoding="utf-8"))
        return self._meta[source_id]

    def index(self, source_id: str) -> dict:
        if source_id not in self._index:
            path = self.root / source_id / "index.json"
            self._index[source_id] = json.loads(path.read_text(encoding="utf-8"))
        return self._index[source_id]

    def topics(self, source_id: str) -> list[dict]:
        return list(self.index(source_id).get("topics") or [])

    def load_topic(self, source_id: str, topic_id: str) -> dict:
        cache = self._topics.setdefault(source_id, OrderedDict())
        if topic_id in cache:
            cache.move_to_end(topic_id)
            return cache[topic_id]
        path = self.root / source_id / f"{topic_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        cache[topic_id] = data
        cache.move_to_end(topic_id)
        while len(cache) > self._lru_size:
            cache.popitem(last=False)
        return data

    def loaded_topic_ids(self, source_id: str) -> list[str]:
        return list(self._topics.get(source_id, ()))

    def attribution_line(self, source_id: str, lang: str = "ru") -> str:
        meta = self.meta(source_id)
        block = meta.get("attribution") or {}
        if isinstance(block, dict):
            return str(block.get(lang) or block.get("en") or block.get("de") or "")
        return str(block)
