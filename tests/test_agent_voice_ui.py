"""Кнопка 🔊 у реплики, голос моста, сообщения без запроса и поле голоса в диалоге — на настоящем Tk."""
import unittest
from unittest import mock

from stamina import orion, ship_chat
from stamina.voice import tts
from tests import test_orion as _base


ROWS = ["onecore|Microsoft Pavel|ru-RU|Male", "onecore|Microsoft Irina|ru-RU|Female"]


class AgentVoiceUiTest(unittest.TestCase):
    setUp = _base.OrionScreenTest.setUp
    tearDown = _base.OrionScreenTest.tearDown
    _screen = _base.OrionScreenTest._screen

    def _bridge(self):
        orion.upsert({"id": "grok", "name": "Star Typing", "kind": "github_bridge", "discussion_id": "D"})
        orion.set_active("grok") if hasattr(orion, "set_active") else None

    def test_replay_and_unsolicited_use_agent_voice(self):
        self._bridge()
        scr = self._screen()
        scr._rec = lambda: orion.get("grok")
        scr._answer_voice = True
        spoken = []
        with mock.patch.object(tts, "voices", lambda refresh=False: list(ROWS)), \
                mock.patch.object(tts, "available", lambda: True), \
                mock.patch.object(tts, "speak", lambda text, **kw: spoken.append((text, kw)) or True):
            scr._on_bridge("reply", "grok", {"id": "w1", "body": "**Совет** недели", "unsolicited": True})
            self.assertEqual(spoken[-1][1]["voice"], "Microsoft Irina")
            self.assertIn("Совет", spoken[-1][0])
            scr.show_tab("chat")
            scr._render_feed()
            self.assertTrue(scr.text.tag_ranges("replay"))
            n = len(spoken)
            scr.replay(len(scr._msg_texts) - 1)
            self.assertEqual(len(spoken), n + 1)
            self.assertEqual(spoken[-1][1]["voice"], "Microsoft Irina")
            scr.replay(999)                       # вне диапазона — молча
        self.assertIn("Совет", orion.history("grok")["messages"][-1]["text"])

    def test_bridge_permission_error_is_bridge_specific(self):
        self._bridge()
        scr = self._screen()
        rec = orion.get("grok")
        scr._on_bridge_sent(rec, {"ok": False, "error": "bridge_perm", "need": "comment", "repo": "o/r",
                                  "detail": "Resource not accessible by personal access token"})
        note = orion.history("grok")["messages"][-1]["text"]
        self.assertIn(ship_chat.TOKEN_SETTINGS, note)
        self.assertNotIn("адрес и модель", note)

    def test_dialog_voice_menu_and_preview(self):
        from stamina.agent_dialog import ConnectAgentDialog
        spoken = []
        with mock.patch.object(tts, "voices", lambda refresh=False: list(ROWS)), \
                mock.patch.object(tts, "voices_ready", lambda: True), \
                mock.patch.object(tts, "available", lambda: True), \
                mock.patch.object(tts, "speak", lambda text, **kw: spoken.append(kw) or True):
            dlg = ConnectAgentDialog(self.app, record={"id": "grok", "name": "Star", "kind": "github_bridge"})
            dlg.update()
            dlg.preview_voice()
            self.assertEqual(spoken[-1]["voice"], "Microsoft Irina")
            dlg.vars["tts_voice"].set("Microsoft Pavel")
            dlg.preview_voice()
            self.assertEqual(spoken[-1]["voice"], "Microsoft Pavel")
            with mock.patch("tkinter.Menu.tk_popup"):
                dlg.voice_menu()
            dlg.destroy()
