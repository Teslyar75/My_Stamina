"""Бортовой чат через GitHub: загрузка снимков, вебхук, разбор ответов, ожидание в фоне."""

import base64
import io
import json
import urllib.error

import pytest

from stamina import agent_connect as ac
from stamina import orion, ship_chat as sc


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


class FakeGitHub:
    """Маршрутизатор запросов: (method, url-фрагмент или graphql-ключ) → ответ."""

    def __init__(self, routes):
        self.routes = routes
        self.seen = []

    def __call__(self, req, timeout=0):
        body = json.loads(req.data) if req.data else None
        self.seen.append((req.get_method(), req.full_url, body, dict(req.header_items())))
        for (method, frag), answer in self.routes.items():
            hit = frag in (body or {}).get("query", "") if req.full_url.endswith("/graphql") \
                else frag in req.full_url
            if req.get_method() == method and hit:
                if callable(answer):
                    answer = answer(req, body)
                if isinstance(answer, Exception):
                    raise answer
                return Resp(json.dumps(answer).encode())
        raise AssertionError(f"unexpected {req.get_method()} {req.full_url}")


def http404():
    return urllib.error.HTTPError("u", 404, "nf", {}, io.BytesIO(b"{}"))


REC = {"id": "grok", "kind": "github_bridge", "bridge_repo": "o/r", "discussion_number": "5",
       "bridge_login": "pilot", "cred_ref": "StarTyping/agent/grok"}
DISC = {"data": {"viewer": {"login": "pilot"}, "repository": {
    "hasDiscussionsEnabled": True, "discussion": {"id": "D_5", "number": 5, "title": "Чат"}}}}
POSTED = {"data": {"addDiscussionComment": {"comment": {"id": "c", "createdAt": "2026-11-04T10:00:00Z"}}}}


def test_send_uploads_shots_posts_comment_and_webhook(monkeypatch, store, tmp_path):
    store.d["StarTyping/agent/grok"] = "ghp_x"
    store.d["StarTyping/agent/grok/webhook"] = "whk"
    shot = tmp_path / "a.png"
    shot.write_bytes(b"\x89PNGdata")
    gh = FakeGitHub({
        ("POST", "hasDiscussionsEnabled"): DISC,
        ("GET", "/git/ref/heads/ship-chat-media"): http404(),
        ("GET", "/git/ref/heads/main"): {"object": {"sha": "abc"}},
        ("GET", "/repos/o/r"): {"default_branch": "main"},
        ("POST", "/git/refs"): {},
        ("PUT", "/contents/shots/"): lambda req, body: {"content": {
            "download_url": "https://raw/" + req.full_url.split("/contents/")[1]}},
        ("POST", "addDiscussionComment"): POSTED,
        ("POST", "hook.example"): {},
    })
    monkeypatch.setattr(ac, "_opener", lambda: gh)
    rec = dict(REC, webhook="https://hook.example/in", webhook_header="X-Key", webhook_scheme="Token")
    out = sc.send(rec, "Привет", context={"compartment": "Пульт", "tab": "Уроки", "raw": "ctx"},
                  geo="(10, 20) кнопка", shots=[shot], pilot="Сергей", app_version="1.2")
    assert out["ok"] and out["webhook"] == "" and out["after"] == "2026-11-04T10:00:00Z"
    put = [s for s in gh.seen if s[0] == "PUT"][0]
    assert put[2]["branch"] == "ship-chat-media" and base64.b64decode(put[2]["content"]) == b"\x89PNGdata"
    assert f"/shots/" in put[1] and out["message_id"] + "-1.png" in put[1]
    refs = [s for s in gh.seen if s[1].endswith("/git/refs")][0]
    assert refs[2] == {"ref": "refs/heads/ship-chat-media", "sha": "abc"}
    comment = [s for s in gh.seen if "addDiscussionComment" in (s[2] or {}).get("query", "")][0][2]
    body = comment["variables"]["body"]
    assert "Привет" in body and "![a.png](https://raw/shots/" in body and "📍 (10, 20)" in body
    assert f"<!-- star-typing-msg: {out['message_id']} -->" in body
    hook = [s for s in gh.seen if "hook.example" in s[1]][0]
    assert hook[3]["X-key"] == "Token whk"
    p = hook[2]
    assert p["message_id"] == out["message_id"] and p["geo"] == "(10, 20) кнопка"
    assert p["context"]["compartment"] == "Пульт" and p["context"]["tab"] == "Уроки"
    assert p["screenshots"][0]["url"].startswith("https://raw/shots/")
    assert p["discussion"] == {"repo": "o/r", "number": 5, "node_id": "D_5"}
    assert p["pilot"] == "Сергей" and p["app_version"] == "1.2"
    assert "ghp_x" not in json.dumps(p) and "whk" not in json.dumps(p)


def test_webhook_default_header_and_failure_is_not_fatal(monkeypatch, store):
    seen = []

    def opener(req, timeout=0):
        seen.append(req)
        raise urllib.error.HTTPError("u", 500, "x", {}, io.BytesIO(b""))
    monkeypatch.setattr(ac, "_opener", lambda: opener)
    assert sc.send_webhook({"id": "g"}, {}) == "off"
    assert sc.send_webhook({"id": "g", "webhook": "https://h"}, {"message_id": "m"}, key="k") == "HTTP 500"
    assert seen[0].get_header("Authorization") == "Bearer k"


def test_discussions_disabled_and_check(monkeypatch, store):
    off = {"data": {"viewer": {"login": "p"}, "repository": {"hasDiscussionsEnabled": False, "discussion": None}}}
    monkeypatch.setattr(ac, "_opener", lambda: FakeGitHub({("POST", "hasDiscussionsEnabled"): off}))
    ok, msg = ac.check(REC, key="t")
    assert not ok and "disabled" in msg
    monkeypatch.setattr(ac, "_opener", lambda: FakeGitHub({("POST", "hasDiscussionsEnabled"): DISC,
                                                            ("GET", "/repos/o/r"): {"permissions": {"push": True}}}))
    ok, msg = ac.check(REC, key="t")
    # права детального токена на запись заранее не узнать — не «зелёный», но и не ошибка
    assert ok is None and "#5" in msg and "pilot" in msg
    assert ac.check({"kind": "github_bridge"}, key="t") == (False, "config discussion")
    assert ac.check(REC)[1] == "no_key"
    err = urllib.error.HTTPError("u", 401, "x", {}, io.BytesIO(b'{"message":"Bad credentials"}'))
    monkeypatch.setattr(ac, "_opener", lambda: FakeGitHub({("POST", "hasDiscussionsEnabled"): err}))
    ok, msg = ac.check(REC, key="t")
    assert not ok and "auth" in msg


def test_pick_replies_markers_reply_to_and_login_fallback():
    after = "2026-11-04T10:00:00Z"
    nodes = [
        {"id": "own", "body": "q\n<!-- star-typing-msg: M1 -->", "createdAt": "2026-11-04T10:00:00Z",
         "author": {"login": "pilot"}},
        {"id": "a", "body": "Взялся <!-- star-typing-reply --><!-- star-typing-interim --><!-- reply-to: M1 -->",
         "createdAt": "2026-11-04T10:00:05Z", "author": {"login": "pilot"}},
        {"id": "b", "body": "чужое <!-- star-typing-reply --><!-- reply-to: M2 -->",
         "createdAt": "2026-11-04T10:00:06Z", "author": {"login": "bot"}},
        {"id": "c", "body": "заметка пилота", "createdAt": "2026-11-04T10:00:07Z", "author": {"login": "pilot"},
         "replies": {"nodes": [{"id": "d", "body": "**Готово** <!-- star-typing-reply -->",
                                "createdAt": "2026-11-04T10:01:00Z", "author": {"login": "pilot"}}]}},
        {"id": "old", "body": "x <!-- star-typing-reply -->", "createdAt": "2026-11-04T09:00:00Z"},
    ]
    got = sc.pick_replies(nodes, message_id="M1", after=after, me="pilot")
    assert [g["id"] for g in got] == ["a", "d"]
    assert got[0]["interim"] and got[0]["body"] == "Взялся" and not got[1]["interim"]
    assert got[1]["body"] == "**Готово**"
    assert [g["id"] for g in sc.pick_replies(nodes, message_id="M1", after=after, me="pilot",
                                             seen={"a"})] == ["d"]
    # без меток — новый комментарий не от пилота
    plain = [{"id": "e", "body": "ок", "createdAt": "2026-11-04T10:02:00Z", "author": {"login": "grok"}}]
    assert sc.pick_replies(plain, message_id="M1", after=after, me="pilot")[0]["body"] == "ок"
    assert sc.pick_replies(plain, message_id="M1", after=after, me="") == []


def test_backoff():
    assert sc.next_delay(10) == 5 and sc.next_delay(300) == 15 and sc.next_delay(1200) == 45


def test_watcher_interim_then_final_and_restart(monkeypatch):
    orion.upsert(dict(REC))
    sent = {"message_id": "M1", "node_id": "D_5", "after": "2026-11-04T10:00:00Z", "login": "pilot"}
    sc.add_pending("grok", sent)
    assert [e["message_id"] for e in sc.waiting("grok")] == ["M1"]
    replies = iter([
        [{"id": "a", "body": "Взялся <!-- star-typing-reply --><!-- star-typing-interim -->",
          "createdAt": "2026-11-04T10:00:05Z", "author": {"login": "pilot"}}],
        [{"id": "a", "body": "Взялся <!-- star-typing-reply --><!-- star-typing-interim -->",
          "createdAt": "2026-11-04T10:00:05Z", "author": {"login": "pilot"}},
         {"id": "b", "body": "Готово <!-- star-typing-reply --><!-- reply-to: M1 -->",
          "createdAt": "2026-11-04T10:00:09Z", "author": {"login": "pilot"}}],
    ])
    monkeypatch.setattr(sc, "token_for", lambda rec: "t")
    monkeypatch.setattr(sc, "gql", lambda tok, q, v: {"node": {"comments": {"nodes": next(replies)}}})
    monkeypatch.setattr(sc, "check_inbox", lambda rec, now=None: [])   # здесь — только ожидание ответа
    events = []
    clock = [1000.0]
    w = sc.Watcher(lambda kind, aid, data: events.append((kind, data.get("body"))), now=lambda: clock[0])
    monkeypatch.setattr(sc.time, "time", lambda: clock[0])
    w.tick()
    assert events == [("reply", "Взялся")] and sc.waiting()
    # «перезапуск»: новый сторож, ожидание читается с диска, «взялся» не повторяется
    w2 = sc.Watcher(lambda kind, aid, data: events.append((kind, data.get("body"))), now=lambda: clock[0])
    w2.tick()
    assert events[1:] == [("reply", "Готово"), ("done", None)] and sc.waiting() == []


def test_watcher_expires_and_cancel():
    sc.add_pending("grok", {"message_id": "M9", "node_id": "D", "after": "z"})
    sc.add_pending("grok", {"message_id": "M8", "node_id": "D", "after": "z"})
    assert sc.drop_pending(agent_id="grok") == 2
    sc.add_pending("grok", {"message_id": "M7", "node_id": "D", "after": "z"})
    events = []
    w = sc.Watcher(lambda k, a, d: events.append(k), now=lambda: 10 ** 10)
    w.tick()
    assert events == ["expired"] and sc.waiting() == []
