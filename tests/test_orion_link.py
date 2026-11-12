"""Индикатор связи Ориона: тона, подписи, кэш health, цвет имени, UI."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from stamina import orion, orion_link, pilots, theme
from tests.test_orion import OrionScreenTest


class OrionLinkLogicTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        pilots.reset_root(Path(self._tmp))
        orion_link.clear_cache()

    def tearDown(self):
        pilots.reset_root()
        orion_link.clear_cache()

    def test_labels_four_states(self):
        self.assertEqual(orion_link.label_for("off"), "Нет связи")
        self.assertEqual(orion_link.label_for("busy"), "Подключение")
        self.assertEqual(orion_link.label_for("ok"), "На связи")
        self.assertEqual(orion_link.label_for("down"), "Ошибка")

    def test_name_fg_green_amber_red(self):
        self.assertEqual(orion_link.name_fg_for("ok"), "green")
        self.assertEqual(orion_link.name_fg_for("busy"), "amber")
        self.assertEqual(orion_link.name_fg_for("off"), "red")
        self.assertEqual(orion_link.name_fg_for("down"), "red")

    def test_offline_when_disabled(self):
        agent = {"id": "orion", "name": "Орион", "kind": "opencode", "enabled": False}
        view = orion_link.derive_view(agent, None)
        self.assertEqual(view.tone, "off")
        self.assertEqual(view.reason, "agent_off")
        self.assertEqual(view.name_fg, "red")
        self.assertEqual(view.label, "Нет связи")

    def test_busy_while_checking(self):
        agent = orion.active()
        view = orion_link.derive_view(agent, None, checking=True)
        self.assertEqual(view.tone, "busy")
        self.assertEqual(view.name_fg, "amber")
        self.assertEqual(view.label, "Подключение")

    def test_ok_when_available(self):
        agent = orion.active()
        health = orion_link.Health(True, "", "ok", kind="opencode", agent_id="orion",
                                   name="Орион")
        view = orion_link.derive_view(agent, health)
        self.assertEqual(view.tone, "ok")
        self.assertEqual(view.name_fg, "green")
        self.assertEqual(view.label, "На связи")

    def test_error_when_no_cli(self):
        agent = orion.active()
        health = orion_link.Health(False, "no_cli", "down", kind="opencode",
                                   agent_id="orion", name="Орион")
        view = orion_link.derive_view(agent, health)
        self.assertEqual(view.tone, "down")
        self.assertEqual(view.name_fg, "red")
        self.assertEqual(view.label, "Ошибка")
        self.assertIn("OpenCode", view.tip)

    def test_probe_opencode_uses_available(self):
        agent = orion.active()
        with mock.patch("stamina.orion.available", return_value=(True, "/bin/opencode")):
            orion_link.clear_cache()
            h = orion_link.probe(agent, refresh=True)
        self.assertTrue(h.available)
        self.assertEqual(h.state, "ok")
        with mock.patch("stamina.orion.available", return_value=(False, "")):
            h2 = orion_link.probe(agent, refresh=False)
        self.assertTrue(h2.cached)
        self.assertTrue(h2.available)

    def test_list_view_openai_no_key(self):
        rec = orion.upsert({"name": "Deep", "kind": "openai_compat",
                            "model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1"})
        view = orion_link.list_view(rec)
        self.assertEqual(view.tone, "down")
        self.assertEqual(view.reason, "no_key")
        self.assertEqual(view.name_fg, "red")

    def test_tooltip_has_name_and_model(self):
        agent = {"id": "orion", "name": "Орион", "kind": "opencode", "model": "flash",
                 "enabled": True}
        health = orion_link.Health(True, "", "ok", kind="opencode", agent_id="orion",
                                   model="flash", name="Орион")
        view = orion_link.derive_view(agent, health)
        tip = orion_link.tooltip_for(view, agent, health)
        self.assertIn("Орион", tip)
        self.assertIn("flash", tip)

    def test_link_indicator_dot_size(self):
        """Точка ≥10 px — не «полукруг» в 3–4 пикселя."""
        import tkinter as tk
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            self.skipTest("нет дисплея")
        try:
            ind = orion_link.LinkIndicator(root, compact=True)
            self.assertGreaterEqual(ind.DOT, 10)
            self.assertGreaterEqual(ind._dot_size, 10)
            view = orion_link.derive_view(
                {"id": "orion", "name": "Орион", "enabled": True, "kind": "opencode"},
                orion_link.Health(True, "", "ok"))
            ind.apply(view)
            self.assertEqual(ind.view.tone, "ok")
            ind.destroy()
        finally:
            root.destroy()


class OrionLinkUiTest(unittest.TestCase):
    """Список пассажиров + HUD: индикатор и цвет имени по реальной связи."""

    setUp = OrionScreenTest.setUp
    tearDown = OrionScreenTest.tearDown
    _screen = OrionScreenTest._screen

    def test_crew_row_and_hud_mirror(self):
        scr = self._screen()
        self.app.geometry("1280x720")
        self.app.show("orion")
        scr.show_tab("agents")
        with mock.patch("stamina.orion.available", return_value=(True, "/bin/opencode")):
            orion_link.clear_cache()
            if getattr(self.app, "orion_link_watcher", None):
                self.app.orion_link_watcher.refresh(True)
            scr.refresh()
            self.app.update()
            self.app.update_idletasks()
        rows = getattr(scr, "_crew_link_rows", {})
        self.assertIn("orion", rows)
        ind, name_lbl, _agent = rows["orion"]
        self.assertEqual(ind.view.tone, "ok")
        self.assertGreaterEqual(ind._dot_size, 10)
        self.assertEqual(str(name_lbl.cget("fg")).lower(), theme.GREEN.lower())
        self.assertIsNotNone(getattr(scr, "_card_link", None))
        self.assertIsNotNone(getattr(self.app, "_orion_link_ind", None))
        # Клик по HUD ведёт в АГЕНТЫ
        self.app._orion_link_ind._click()
        self.app.update()
        self.assertEqual(scr.current_tab, "agents")


if __name__ == "__main__":
    unittest.main()
