"""Language plugin registry with auto-discovery."""
from __future__ import annotations

import importlib
import importlib.util
import logging
from pathlib import Path
from typing import Any

from .base import LanguagePlugin

logger = logging.getLogger(__name__)


class LanguageRegistry:
    def __init__(self, plugins_dir: Path | None = None):
        self._plugins: dict[str, LanguagePlugin] = {}
        self._plugins_dir = plugins_dir or Path(__file__).parent.parent / "plugins"
        self._discovered = False

    def discover(self) -> None:
        if self._discovered:
            return
        self._discovered = True

        if not self._plugins_dir.exists():
            logger.warning("Plugins directory not found: %s", self._plugins_dir)
            return

        for lang_dir in self._plugins_dir.iterdir():
            if not lang_dir.is_dir() or lang_dir.name.startswith("_"):
                continue
            try:
                self._load_plugin(lang_dir)
            except Exception as e:
                logger.error("Failed to load plugin %s: %s", lang_dir.name, e)

    def _load_plugin(self, lang_dir: Path) -> None:
        init_file = lang_dir / "__init__.py"
        if not init_file.exists():
            return

        spec = importlib.util.spec_from_file_location(f"stamina.languages.plugins.{lang_dir.name}", init_file)
        if spec is None or spec.loader is None:
            return

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, LanguagePlugin) and attr is not LanguagePlugin:
                plugin = attr()
                self._plugins[plugin.code] = plugin
                logger.info("Loaded language plugin: %s (%s)", plugin.code, plugin.name_target)
                break

    def get(self, code: str) -> LanguagePlugin | None:
        if not self._discovered:
            self.discover()
        return self._plugins.get(code)

    def all(self) -> list[LanguagePlugin]:
        if not self._discovered:
            self.discover()
        return list(self._plugins.values())

    def get_codes(self) -> list[str]:
        if not self._discovered:
            self.discover()
        return list(self._plugins.keys())

    def get_cross_pair(self, l1: str, l2: str) -> Any | None:
        cross_dir = Path(__file__).parent.parent / "cross_pairs"
        pair_file = cross_dir / f"{l1}to{l2}.json"
        if pair_file.exists():
            import json
            return json.loads(pair_file.read_text(encoding="utf-8"))
        return None


REGISTRY = LanguageRegistry()


def get_registry() -> LanguageRegistry:
    return REGISTRY