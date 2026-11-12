"""Вкладка ОРИОН → АГЕНТЫ: две колонки (карточка | привязка) и деградация на узком окне."""
import unittest

from stamina import theme
from stamina.orion_screen import OrionScreen
from stamina.theme import px
from tests.test_orion import OrionScreenTest


class AgentsLayoutTest(unittest.TestCase):
    setUp = OrionScreenTest.setUp
    tearDown = OrionScreenTest.tearDown
    _screen = OrionScreenTest._screen

    def _open(self, size="1366x768"):
        scr = self._screen()
        self.app.geometry(size)
        self.app.show("orion")
        scr.show_tab("agents")
        scr.refresh()
        self.app.update()
        self.app.update_idletasks()
        scr._agents_relayout()
        self.app.update_idletasks()
        return scr

    def test_wide_puts_card_and_bind_side_by_side(self):
        theme.set_ui_scale("M")
        scr = self._open("1366x768")
        self.assertEqual(scr._agents_mode, "wide")
        self.assertEqual(int(scr._agents_card.grid_info()["column"]), 0)
        self.assertEqual(int(scr._agents_bind.grid_info()["column"]), 1)
        self.assertEqual(int(scr._agents_card.grid_info()["row"]), 0)
        self.assertEqual(int(scr._agents_bind.grid_info()["row"]), 0)
        self.assertEqual(int(scr._agents_evo.grid_info()["row"]), 2)
        self.assertEqual(int(scr._agents_manners.grid_info()["row"]), 3)
        self.assertTrue(scr.crew_canvas.winfo_ismapped())
        self.assertTrue(scr._agents_list.winfo_ismapped())
        # эволюция и манеры не вытеснены карточкой
        self.assertTrue(scr._agents_evo.winfo_ismapped())
        self.assertTrue(scr._agents_manners.winfo_ismapped())
        self.assertGreater(scr._agents_evo.winfo_height(), 20)
        self.assertGreater(scr._agents_manners.winfo_height(), 40)

    def test_fields_and_actions_still_present(self):
        scr = self._open("1920x1080")
        for name in ("name_var", "model_var", "note_var", "token_entry", "gh_entry",
                     "code_label", "bind_status", "evo_label", "evo_hint", "char_text",
                     "access_btns", "voice_mode_btn", "enabled_btn"):
            self.assertTrue(hasattr(scr, name), name)
        self.assertEqual(set(scr.access_btns), {"crew", "observer", "commander"})
        self.assertIs(scr._agents_card.master, scr._agents_top)
        self.assertIs(scr._agents_bind.master, scr._agents_top)

    def test_stack_when_right_pane_narrow(self):
        theme.set_ui_scale("M")
        scr = self._open("1100x700")
        scr._layout_agents("stack")
        self.app.update_idletasks()
        self.assertEqual(scr._agents_mode, "stack")
        self.assertEqual(int(scr._agents_card.grid_info()["row"]), 0)
        self.assertEqual(int(scr._agents_bind.grid_info()["row"]), 1)

    def test_tabs_when_very_narrow(self):
        theme.set_ui_scale("S")
        scr = self._open("900x700")
        scr._layout_agents("tabs")
        self.app.update_idletasks()
        self.assertEqual(scr._agents_mode, "tabs")
        self.assertTrue(scr._agents_tab_bar.winfo_ismapped())
        self.assertTrue(scr._agents_card.winfo_ismapped())
        self.assertFalse(scr._agents_bind.winfo_ismapped())
        scr._agents_pick_tab("bind")
        self.app.update_idletasks()
        self.assertTrue(scr._agents_bind.winfo_ismapped())
        self.assertFalse(scr._agents_card.winfo_ismapped())

    def test_mode_thresholds_respect_ui_scale(self):
        for key in ("S", "M", "L", "XL"):
            theme.set_ui_scale(key)
            self.assertEqual(OrionScreen._agents_mode_for(OrionScreen, px(OrionScreen.AGENTS_WIDE_MIN)),
                             "wide")
            self.assertEqual(
                OrionScreen._agents_mode_for(OrionScreen, px(OrionScreen.AGENTS_WIDE_MIN) - 1),
                "stack")
            self.assertEqual(
                OrionScreen._agents_mode_for(OrionScreen, px(OrionScreen.AGENTS_TABS_MAX) - 1),
                "tabs")

    def test_common_sizes_stay_wide_for_s_to_xl(self):
        """1366 и 1920 при S–XL: правая зона достаточно широка для двух колонок."""
        for key in ("S", "M", "L", "XL"):
            theme.set_ui_scale(key)
            for win_w in (1366, 1920):
                right_w = win_w - px(260) - px(40)
                mode = OrionScreen._agents_mode_for(OrionScreen, right_w)
                self.assertEqual(mode, "wide", f"scale={key} win={win_w} right={right_w}")
            # узкое окно — стек или вкладки, не wide
            narrow = OrionScreen._agents_mode_for(OrionScreen, 800 - px(260) - px(40))
            self.assertIn(narrow, ("stack", "tabs"))


if __name__ == "__main__":
    unittest.main()
