"""Подключение агента: провайдеры, хранилище ключей (заглушка), ошибки, разбор openai_compat."""

import io
import json
import urllib.error

import pytest

from stamina import agent_connect as ac
from stamina import orion


class FakeStore:
    def __init__(self):
        self.d = {}

    def set_password(self, svc, user, pw):
        self.d[svc] = pw

    def get_password(self, svc, user):
        return self.d.get(svc)

    def delete_password(self, svc, user):
        self.d.pop(svc, None)


@pytest.fixture
def store(monkeypatch):
    fs = FakeStore()
    monkeypatch.setattr(ac, "_backend", lambda: ("keyring", fs))
    return fs


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_http(monkeypatch, payload=None, exc=None, seen=None):
    def opener(req, timeout=0):
        if seen is not None:
            seen.append(req)
        if exc is not None:
            raise exc
        return Resp(json.dumps(payload).encode())
    monkeypatch.setattr(ac, "_opener", lambda: opener)


def test_store_key_keeps_only_reference(store):
    ref = ac.store_key("bob", "sk-secret")
    assert ref == "StarTyping/agent/bob" and store.d[ref] == "sk-secret"
    assert ac.read_key(ref) == "sk-secret"
    rec = orion.upsert({"name": "Bob", "kind": "openai_compat", "base_url": "https://x/v1",
                        "model": "m", "cred_ref": ref, "api_key": "sk-secret"})
    raw = orion.agents_path().read_text("utf-8")
    assert "sk-secret" not in raw and rec["cred_ref"] == ref and rec["kind"] == "openai_compat"
    ac.delete_key(ref)
    assert ac.read_key(ref) == ""


def test_request_and_response_parsing():
    req = ac.build_chat_request({"base_url": "https://api.deepseek.com/v1/", "model": "deepseek-chat"},
                                "привет", key="k1")
    assert req.full_url == "https://api.deepseek.com/v1/chat/completions"
    assert req.get_header("Authorization") == "Bearer k1"
    body = json.loads(req.data)
    assert body["model"] == "deepseek-chat" and body["messages"][-1]["content"] == "привет"
    assert ac.parse_chat_response(b'{"choices":[{"message":{"content":" OK "}}]}') == "OK"
    with pytest.raises(ValueError):
        ac.parse_chat_response('{"error":{"message":"bad"}}')


def test_ollama_needs_no_key(monkeypatch, store):
    seen = []
    fake_http(monkeypatch, {"choices": [{"message": {"content": "hi"}}]}, seen=seen)
    res = ac.run_openai_compat({"base_url": "http://localhost:11434/v1", "model": "llama3.1"}, "q")
    assert res.reply == "hi" and not res.error
    assert seen[0].get_header("Authorization") is None


def test_missing_key_is_reported(store):
    res = ac.run_openai_compat({"base_url": "https://api.openai.com/v1", "model": "m"}, "q")
    assert res.error == "no_key"


def test_http_401_surfaces_as_auth(monkeypatch, store):
    store.d["StarTyping/agent/a"] = "k"
    err = urllib.error.HTTPError("u", 401, "Unauthorized", {}, io.BytesIO(b'{"error":{"message":"bad key"}}'))
    fake_http(monkeypatch, exc=err)
    res = ac.run_openai_compat({"base_url": "https://api.openai.com/v1", "model": "m",
                                "cred_ref": "StarTyping/agent/a"}, "q")
    assert res.error == "auth" and "bad key" in res.detail


def test_network_error(monkeypatch, store):
    fake_http(monkeypatch, exc=urllib.error.URLError("refused"))
    res = ac.run_openai_compat({"base_url": "http://localhost:1/v1", "model": "m"}, "q")
    assert res.error == "network"


def test_dispatch_by_kind(monkeypatch):
    calls = []
    monkeypatch.setattr(orion, "_run_opencode", lambda rec, text, **kw: calls.append("oc") or orion.Result(reply="a"))
    monkeypatch.setattr(ac, "run_openai_compat", lambda rec, p, **kw: calls.append("oa") or orion.Result(reply="b"))
    monkeypatch.setattr(ac, "run_github_bridge", lambda rec, p, **kw: calls.append("gh") or orion.Result(reply="c"))
    for kind in ("opencode", "openai_compat", "github_bridge"):
        orion.run_profile({"id": "x", "kind": kind}, "hi", profile="p", character="")
    assert calls == ["oc", "oa", "gh"]
    assert orion.run_profile({"id": "x", "kind": "weird"}, "hi", profile="p", character="").error == "kind"


def test_fallback_to_other_profile(monkeypatch):
    orion.upsert({"id": "backup", "name": "Backup", "kind": "openai_compat", "base_url": "http://localhost/v1"})
    monkeypatch.setattr(ac, "run_openai_compat",
                        lambda rec, p, **kw: orion.Result(error="network") if rec["id"] == "main"
                        else orion.Result(reply="ok"))
    res = orion.run_profile({"id": "main", "kind": "openai_compat", "fallback": "backup"}, "hi",
                            profile="p", character="")
    assert res.reply == "ok" and res.fallback_from == "network"


def test_ready_needs_opencode_only_for_opencode(monkeypatch):
    monkeypatch.setattr(orion, "available", lambda: (False, ""))
    assert orion.ready({"kind": "openai_compat"})[0]
    assert not orion.ready({"kind": "opencode"})[0]


def test_github_bridge_posts_and_polls(monkeypatch):
    answers = iter([
        {"data": {"addDiscussionComment": {"comment": {"id": "c1", "createdAt": "2026-10-30T10:00:00Z"}}}},
        {"data": {"node": {"comments": {"nodes": []}}}},
        {"data": {"node": {"comments": {"nodes": [
            {"body": "мой", "createdAt": "2026-10-30T10:00:00Z", "author": {"login": "me"}},
            {"body": "Ответ агента", "createdAt": "2026-10-30T10:01:00Z", "author": {"login": "grok"}}]}}}},
    ])
    fake_http(monkeypatch, None)
    monkeypatch.setattr(ac, "_opener", lambda: (lambda req, timeout=0: Resp(json.dumps(next(answers)).encode())))
    res = ac.run_github_bridge({"id": "g", "discussion_id": "D_1", "bridge_login": "me"}, "hi",
                               token="t", sleep=lambda s: None)
    assert res.reply == "Ответ агента"
    assert ac.run_github_bridge({"id": "g"}, "hi", token="t").error == "config"


def test_dialog_save_keeps_only_reference(store):
    import tkinter as tk
    from stamina.agent_dialog import ConnectAgentDialog, agent_for_pilot
    root = tk.Tk()
    root.withdraw()
    try:
        dlg = ConnectAgentDialog(root, pilot="p1")
        dlg.use_preset("deepseek")
        dlg.vars["name"].set("Deep")
        dlg.key_var.set("sk-dialog")
        dlg.save()
        rec = dlg.result
        assert rec and rec["pilot"] == "p1" and rec["kind"] == "openai_compat"
        assert store.d[rec["cred_ref"]] == "sk-dialog"
        assert "sk-dialog" not in orion.agents_path().read_text("utf-8")
        assert orion.active()["id"] == rec["id"] and agent_for_pilot("p1")["id"] == rec["id"]
        # повторное редактирование без ключа — ссылка сохраняется
        dlg2 = ConnectAgentDialog(root, pilot="p1")
        dlg2.vars["model"].set("deepseek-reasoner")
        dlg2.save()
        assert dlg2.result["cred_ref"] == rec["cred_ref"] and dlg2.result["id"] == rec["id"]
    finally:
        root.destroy()
