"""Список АГЕНТЫ в Орионе: прокрутка, «тип · модель», ✎ и ✕ (с подтверждением и ключом)."""
import unittest
from tkinter import messagebox

from stamina import agent_connect, orion
from tests.test_orion import OrionScreenTest


class AgentsListTest(unittest.TestCase):
    setUp = OrionScreenTest.setUp
    tearDown = OrionScreenTest.tearDown
    _screen = OrionScreenTest._screen

    def _many(self, n=12):
        for i in range(n):
            orion.upsert({"name": f"Агент {i}", "kind": "openai_compat", "model": f"m-{i}"})
        orion.upsert({"id": "deep", "name": "Deep", "kind": "openai_compat",
                      "model": "deepseek-chat"})

    def _open(self):
        scr = self._screen()
        self.app.geometry("1280x720")
        self.app.show("orion")
        scr.show_tab("agents")
        scr.refresh()
        self.app.update()
        return scr

    def test_subtitle_kind_and_model(self):
        from stamina.orion_screen import OrionScreen
        self.assertEqual(OrionScreen.agent_subtitle({"kind": "openai_compat", "model": "deepseek-chat"}),
                         "OpenAI-совместимый · deepseek-chat")
        self.assertIn("OpenCode", OrionScreen.agent_subtitle({}))

    def test_scroll_reaches_last_card(self):
        self._many()
        scr = self._open()
        c = scr.crew_canvas
        total = scr.crew_box.winfo_reqheight()
        self.assertGreater(total, c.winfo_height())         # список длиннее окна
        self.assertEqual(float(c.cget("scrollregion").split()[3]), total)
        for _ in range(200):
            scr._crew_scroll(1, "units")
        self.app.update()
        self.assertAlmostEqual(c.yview()[1], 1.0)
        last = scr.crew_box.winfo_children()[-1]
        top = c.canvasy(0)
        self.assertGreaterEqual(last.winfo_y(), top)
        self.assertLessEqual(last.winfo_y() + last.winfo_height(), top + c.winfo_height() + 1)
        scr._crew_wheel(type("E", (), {"delta": 120, "num": 0})())
        self.app.update()
        self.assertLess(c.yview()[1], 1.0)                  # колесо вверх листает назад
        self.assertTrue(c.bind("<Down>") and c.bind("<Next>"))

    def test_orion_has_no_delete(self):
        scr = self._open()
        scr._delete_agent("orion")
        self.assertIsNotNone(orion.get("orion"))

    def test_delete_asks_and_removes_key(self):
        rec = orion.upsert({"name": "Тест", "kind": "openai_compat", "model": "x"})
        ref = agent_connect.store_key(rec["id"], "sk-test")
        rec["cred_ref"] = ref
        orion.upsert(rec)
        scr = self._open()
        real = messagebox.askyesno
        try:
            messagebox.askyesno = lambda *a, **k: False
            scr._delete_agent(rec["id"])
            self.assertIsNotNone(orion.get(rec["id"]))
            self.assertEqual(agent_connect.read_key(ref), "sk-test")
            messagebox.askyesno = lambda *a, **k: True
            scr._delete_agent(rec["id"])
        finally:
            messagebox.askyesno = real
        self.assertIsNone(orion.get(rec["id"]))
        self.assertFalse(agent_connect.read_key(ref))

    def test_edit_api_agent_opens_connect_dialog(self):
        import stamina.agent_dialog as ad
        rec = orion.upsert({"name": "Deep", "kind": "openai_compat", "model": "deepseek-chat"})
        seen = {}

        class Fake:
            def __init__(self, master, pilot="", record=None):
                seen["record"] = record

            def run(self):
                return None

        real = ad.ConnectAgentDialog
        ad.ConnectAgentDialog = Fake
        try:
            self._open()._edit_agent_full(rec["id"])
        finally:
            ad.ConnectAgentDialog = real
        self.assertEqual(seen["record"]["id"], rec["id"])


if __name__ == "__main__":
    unittest.main()
