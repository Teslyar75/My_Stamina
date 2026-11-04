"""OpenCode: снимки через -f, поток событий, понятные ошибки; разметка чата."""

import io
import json
import subprocess

from stamina import chat_md, orion


def test_build_command_files_after_prompt(tmp_path):
    a = tmp_path / "a.png"
    a.write_bytes(b"x")
    cmd = orion.build_command("opencode", "orion-chat", "Что на снимке?", files=[str(a), str(tmp_path / "нет.png")])
    i = cmd.index("Что на снимке?")
    assert cmd[i + 1:] == ["-f", str(a)]


def test_agent_timeout_from_profile():
    assert orion.agent_timeout({}) == orion.TIMEOUT
    assert orion.agent_timeout({"timeout": "1800"}) == 1800
    assert orion.agent_timeout({"timeout": "5"}) == orion.MIN_TIMEOUT
    assert orion.agent_timeout({"timeout": "abc"}) == orion.TIMEOUT


def test_event_status_and_errors():
    assert orion.event_status({"type": "text", "part": {"text": "При"}}) == ("text", "При")
    kind, val = orion.event_status({"type": "tool_use", "part": {"tool": "read", "state": {"title": "a.py"}}})
    assert kind == "status" and "read" in val and "a.py" in val
    err = {"type": "error", "error": {"name": "ProviderAuthError",
                                      "data": {"providerID": "opencode", "message": "Model not found"}}}
    assert "ProviderAuthError" in orion.error_text(err) and "Model not found" in orion.error_text(err)
    assert orion.stderr_detail("info start\nERROR rate limit exceeded\nbye") == "ERROR rate limit exceeded"


class _Proc:
    def __init__(self, out: bytes, err: bytes = b"", code: int = 0, hang=False):
        self.stdout, self.stderr = io.BytesIO(out), io.BytesIO(err)
        self.returncode, self.pid, self.hang = code, 4343, hang
        self.args = []

    def wait(self, timeout=None):
        if self.hang:
            raise subprocess.TimeoutExpired("opencode", timeout)
        return self.returncode

    def poll(self):
        return self.returncode

    def kill(self):
        self.hang = False
        self.returncode = -9


def _run(monkeypatch, proc, **kw):
    seen = {}

    def popen(cmd, **_k):
        seen["cmd"] = cmd
        return proc
    monkeypatch.setattr(orion.subprocess, "Popen", popen)
    monkeypatch.setattr(orion, "find_cli", lambda: "/usr/bin/opencode")
    monkeypatch.setattr(orion, "_kill", lambda p: p.kill())
    return orion._run_opencode({"id": "orion"}, "привет", profile="orion-chat", character="", **kw), seen


def test_streaming_events_reach_screen(monkeypatch, tmp_path):
    lines = [{"type": "step_start", "sessionID": "s1"},
             {"type": "tool_use", "part": {"tool": "read"}},
             {"type": "text", "part": {"text": "Кра", "messageID": "m"}},
             {"type": "text", "part": {"text": "сный", "messageID": "m"}}]
    out = "\n".join(json.dumps(x, ensure_ascii=False) for x in lines).encode()
    shot = tmp_path / "s.png"
    shot.write_bytes(b"x")
    got = []
    res, seen = _run(monkeypatch, _Proc(out), files=[str(shot)], on_event=lambda k, v: got.append((k, v)))
    assert res.reply == "Красный" and not res.error and res.session == "s1"
    assert ("text", "Кра") in got and any(k == "status" and "read" in v for k, v in got)
    assert seen["cmd"][-2:] == ["-f", str(shot)]


def test_provider_error_is_readable(monkeypatch):
    out = json.dumps({"type": "error", "error": {"name": "APIError",
                                                 "data": {"message": "Insufficient credits"}}}).encode()
    res, _ = _run(monkeypatch, _Proc(out, b"", 1))
    assert res.error == "provider" and "Insufficient credits" in res.detail
    res, _ = _run(monkeypatch, _Proc(b"", b"log\nError: model xyz not found\n", 1))
    assert res.error == "spawn" and "model xyz not found" in res.detail


def test_timeout_keeps_partial(monkeypatch):
    out = json.dumps({"type": "text", "part": {"text": "половина", "messageID": "m"}}).encode()
    res, _ = _run(monkeypatch, _Proc(out, hang=True), timeout=31)
    assert res.error == "timeout" and res.reply == "половина" and "31" in res.detail


def test_remember_keeps_agent_newlines():
    orion.remember("orion", "orion", "**Итог**\n\n\n\n- раз\n- два\n```\ncode\n```")
    text = orion.history("orion")["messages"][-1]["text"]
    assert text == "**Итог**\n\n- раз\n- два\n```\ncode\n```"


def test_chat_markdown_blocks():
    blocks = chat_md.parse("**Ж** *к* `c` [GH](https://github.com)\n- a\n1. b\n"
                           "![s](https://x/p.png)\n```py\nx = 1\n```\nсм. https://a.io/x.")
    kinds = [b[0] if b[0] != "line" else b[1] for b in blocks]
    assert kinds == ["p", "li", "ol", "image", "code", "p"]
    runs = blocks[0][3]
    assert ("Ж", frozenset({"b"}), "") in runs and ("к", frozenset({"i"}), "") in runs
    assert ("c", frozenset({"code"}), "") in runs and ("GH", frozenset({"link"}), "https://github.com") in runs
    assert blocks[3] == ("image", "s", "https://x/p.png") and blocks[4] == ("code", "py", "x = 1")
    assert blocks[5][3][-2] == ("https://a.io/x", frozenset({"link"}), "https://a.io/x")
    assert chat_md.plain("**a** [b](u)\n![i](u)") == "a b"
    assert chat_md.parse("```\nнезакрыт")[-1] == ("code", "", "незакрыт")


# ---------------------------------------------------------------- экран на настоящем Tk
import os
import tempfile
import unittest
from pathlib import Path

from stamina import pilots, ship_chat


class ShipChatScreenTest(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self._tmp = tempfile.mkdtemp()
        pilots.reset_root(Path(self._tmp))
        os.environ.setdefault("APPDATA", self._tmp)
        self._real_run = orion.run_profile
        orion.run_profile = lambda *a, **kw: orion.Result(reply="ok")
        try:
            from stamina.cockpit import Cockpit
            self.app = Cockpit()
        except tk.TclError:
            orion.run_profile = self._real_run
            pilots.reset_root()
            self.skipTest("нет дисплея")
        self.app.update()

    def tearDown(self):
        orion.run_profile = self._real_run
        self.app.destroy()
        pilots.reset_root()

    def _screen(self):
        self.app.show("orion")
        scr = self.app.screens.get("orion")
        if scr is None:
            self.skipTest("раздел ОРИОН не загрузился")
        scr._answer_voice = False
        scr.mic.start = lambda: False
        return scr

    def test_markdown_rendered_with_tags_and_links(self):
        scr = self._screen()
        rec = scr._rec()
        orion.remember(rec["id"], "orion", "**Жир** и `код`\n- пункт\n[сайт](https://example.com)\n"
                                           "![картинка](https://example.invalid/x.png)")
        scr._web_images["https://example.invalid/x.png"] = ""     # не качать в тесте
        scr._render_feed()
        t = scr.text
        body = t.get("1.0", "end")
        self.assertIn("Жир и код", body)
        self.assertNotIn("**", body)
        self.assertIn("• пункт", body)
        self.assertTrue(t.tag_ranges("md_b") and t.tag_ranges("md_code") and t.tag_ranges("md_link"))
        self.assertIn("https://example.com", scr._links)
        self.assertIn("🖼 картинка", body)

    def test_bridge_send_shows_typing_then_reply(self):
        scr = self._screen()
        rec = orion.upsert({"id": "grok", "name": "Star Typing", "kind": "github_bridge",
                            "bridge_repo": "o/r", "discussion_number": "1"})
        orion.set_active("grok")
        sent = {"ok": True, "message_id": "M1", "node_id": "D", "after": "2026-01-01T00:00:00Z",
                "webhook": "off"}
        calls = []
        real_send, real_start = ship_chat.send, scr._bridge_watch.start
        ship_chat.send = lambda *a, **kw: calls.append(kw) or sent
        scr._bridge_watch.start = lambda: None
        try:
            scr._run(rec, "привет", second=False)
            for _ in range(50):
                self.app.update()
                if not scr._busy:
                    break
                import time
                time.sleep(0.05)
            scr._pump()
            self.app.update()
        finally:
            ship_chat.send = real_send
            scr._bridge_watch.start = real_start
        self.assertEqual(calls[0]["context"]["compartment"] != None, True)
        self.assertEqual([e["message_id"] for e in ship_chat.waiting("grok")], ["M1"])
        self.assertIn("печатает", scr.text.get("1.0", "end"))
        scr._on_bridge("reply", "grok", {"body": "**Готово**", "message_id": "M1", "interim": False})
        ship_chat.drop_pending("M1")
        scr._on_bridge("done", "grok", {"message_id": "M1"})
        body = scr.text.get("1.0", "end")
        self.assertIn("Готово", body)
        self.assertNotIn("печатает", body)
