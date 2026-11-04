"""Свой голос агента, кнопка «повторить», подсказка о правах токена моста GitHub."""

import io
import json
import urllib.error

import pytest

from stamina import agent_connect as ac
from stamina import ship_chat as sc
from stamina.voice import agent_voice, tts

WIN_ROWS = ["onecore|Microsoft Pavel|ru-RU|Male", "onecore|Microsoft Irina|ru-RU|Female",
            "onecore|Microsoft David|en-US|Male", "sapi|Microsoft Irina Desktop|ru-RU|Female"]


@pytest.fixture
def rows(monkeypatch):
    box = {"rows": list(WIN_ROWS)}
    monkeypatch.setattr(tts, "voices", lambda refresh=False: list(box["rows"]))
    return box


def test_orion_keeps_ship_voice_and_explicit_wins(rows):
    assert agent_voice.voice_for({"id": "orion"}) == ""
    assert agent_voice.voice_for({"id": "grok", "tts_voice": "Microsoft David"}) == "Microsoft David"


def test_other_agent_gets_first_different_voice_same_language(rows):
    assert agent_voice.orion_voice("ru") == "Microsoft Pavel"
    assert agent_voice.voice_for({"id": "grok"}, "ru") == "Microsoft Irina"
    # детерминированно: тот же ответ при повторе
    assert agent_voice.voice_for({"id": "grok"}, "ru") == "Microsoft Irina"
    # Орион с явным голосом Irina — агенту достаётся другой
    assert agent_voice.voice_for({"id": "grok"}, "ru", {"tts_voice": "Microsoft Irina"}) == "Microsoft Pavel"


def test_other_language_then_single_voice_fallback(rows):
    rows["rows"] = ["onecore|Microsoft Pavel|ru-RU|Male", "onecore|Microsoft David|en-US|Male"]
    assert agent_voice.voice_for({"id": "grok"}, "ru") == "Microsoft David"
    rows["rows"] = ["onecore|Microsoft Pavel|ru-RU|Male"]
    assert agent_voice.voice_for({"id": "grok"}, "ru") == ""        # один голос — как у Ориона
    rows["rows"] = []
    assert agent_voice.voice_for({"id": "grok"}, "ru") == ""


def test_choices_unique(rows):
    assert agent_voice.choices()[0] == "Microsoft Pavel" and len(agent_voice.choices()) == 4


def test_linux_voice_list_and_command(monkeypatch):
    out = (b"Pty Language       Age/Gender VoiceName          File          Other Languages\n"
           b" 5  ru              --/M      Russian            zle/ru\n"
           b" 5  en-us           --/F      English_(America)  gmw/en-US\n")

    class R:
        stdout = out
    monkeypatch.setattr(tts.sys, "platform", "linux")
    monkeypatch.setattr(tts, "linux_tool", lambda: "/usr/bin/espeak-ng")
    monkeypatch.setattr(tts.subprocess, "run", lambda *a, **k: R())
    got = tts.voices(refresh=True)
    assert got == ["espeak|Russian|ru|Male", "espeak|English_(America)|en-us|Female"]
    assert tts.voices_ready()
    cmd = tts._linux_cmd("/usr/bin/espeak-ng", "hi", lang="ru", rate=0, volume=100, voice="Russian")
    assert cmd[1:3] == ["-v", "Russian"]
    cmd = tts._linux_cmd("/usr/bin/spd-say", "hi", lang="ru", rate=0, volume=100, voice="x")
    assert "-y" in cmd and cmd[-1] == "hi"
    monkeypatch.setattr(tts, "linux_tool", lambda: "")
    assert tts.voices(refresh=True) == []          # без движка — пусто, без ошибок
    tts.voices(refresh=True)


# ---------------------------------------------------------------- мост: права токена
class Resp(io.BytesIO):
    def __init__(self, data, headers=None):
        super().__init__(data)
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


REC = {"id": "grok", "kind": "github_bridge", "bridge_repo": "o/r", "discussion_number": "5"}
DISC = {"data": {"viewer": {"login": "pilot"}, "repository": {
    "hasDiscussionsEnabled": True, "discussion": {"id": "D_5", "number": 5, "title": "Чат"}}}}


def opener(repo_info, headers=None, gql=DISC):
    seen = []

    def call(req, timeout=0):
        seen.append((req.get_method(), req.full_url))
        if req.full_url.endswith("/graphql"):
            q = json.loads(req.data)["query"]
            assert "mutation" not in q                 # проверка ничего не пишет
            if isinstance(gql, Exception):
                raise gql
            return Resp(json.dumps(gql).encode())
        assert req.get_method() == "GET"
        if isinstance(repo_info, Exception):
            raise repo_info
        return Resp(json.dumps(repo_info).encode(), headers)
    call.seen = seen
    return call


def test_check_classic_token_scopes(monkeypatch):
    monkeypatch.setattr(ac, "_opener", lambda: opener({"private": True, "permissions": {"push": True}},
                                                      {"X-OAuth-Scopes": "repo, read:org"}))
    ok, msg = ac.check(REC, key="t")
    assert ok is True and "#5" in msg
    monkeypatch.setattr(ac, "_opener", lambda: opener({"private": True, "permissions": {"push": True}},
                                                      {"X-OAuth-Scopes": "read:org"}))
    ok, msg = ac.check(REC, key="t")
    assert ok is False and sc.TOKEN_SETTINGS in msg and "Discussions" in msg


def test_check_fine_grained_is_never_green(monkeypatch):
    monkeypatch.setattr(ac, "_opener", lambda: opener({"private": True, "permissions": {"push": True}}))
    ok, msg = ac.check(REC, key="t")
    assert ok is None and sc.TOKEN_SETTINGS in msg
    monkeypatch.setattr(ac, "_opener", lambda: opener({"private": True, "permissions": {"push": False}}))
    ok, msg = ac.check(REC, key="t")
    assert ok is None and "Contents" in msg


def test_check_graphql_not_accessible(monkeypatch):
    bad = {"errors": [{"message": "Resource not accessible by personal access token"}]}
    monkeypatch.setattr(ac, "_opener", lambda: opener({}, gql=bad))
    ok, msg = ac.check(REC, key="t")
    assert ok is False and "Repository access" in msg and sc.TOKEN_SETTINGS in msg


def test_send_maps_permission_errors_to_bridge_hint(monkeypatch):
    def call(req, timeout=0):
        q = json.loads(req.data)["query"]
        if "mutation" in q:
            return Resp(json.dumps({"errors": [{"message": "Resource not accessible by personal "
                                                           "access token"}]}).encode())
        return Resp(json.dumps(DISC).encode())
    monkeypatch.setattr(ac, "_opener", lambda: call)
    out = sc.send(REC, "hi", token="t")
    assert out["error"] == "bridge_perm" and out["need"] == "comment" and out["repo"] == "o/r"
    err = urllib.error.HTTPError("u", 403, "Forbidden", {}, io.BytesIO(b'{"message":"x"}'))
    monkeypatch.setattr(ac, "_opener", lambda: opener(err, gql=err))
    out = sc.send(REC, "hi", token="t")
    assert out["error"] == "bridge_perm" and out["need"] == "read"
    hint = sc.permission_hint("o/r", "media")
    assert "Contents" in hint and "o/r" in hint and "personal-access-tokens" in hint
    assert sc.is_permission_error(404) and not sc.is_permission_error(500, "boom")


# ---------------------------------------------------------------- сообщения без запроса
from pathlib import Path  # noqa: E402
import tempfile  # noqa: E402

from stamina import orion, pilots  # noqa: E402

MARK = "<!-- star-typing-reply -->"


@pytest.fixture
def root(monkeypatch):
    tmp = tempfile.mkdtemp()
    pilots.reset_root(Path(tmp))
    monkeypatch.delenv("STAMINA_PILOT_DIR", raising=False)
    yield Path(tmp)
    pilots.reset_root()


def comments(*nodes):
    return {"data": {"node": {"comments": {"nodes": list(nodes)}}}}


def test_pick_unsolicited_filters():
    nodes = [{"id": "a", "body": "Рекомендация " + MARK, "createdAt": "2026-11-04T10:00:00Z"},
             {"id": "b", "body": "ответ " + MARK + "<!-- reply-to: M1 -->", "createdAt": "2026-11-04T10:01:00Z"},
             {"id": "c", "body": "просто коммент", "createdAt": "2026-11-04T10:02:00Z"},
             {"id": "d", "body": "старое " + MARK, "createdAt": "2026-10-01T10:00:00Z"}]
    got = sc.pick_unsolicited(nodes, after="2026-11-01T00:00:00Z")
    assert [g["id"] for g in got] == ["a"] and got[0]["body"] == "Рекомендация" and got[0]["unsolicited"]
    assert sc.pick_unsolicited(nodes, after="2026-11-01T00:00:00Z", seen={"a"}) == []


def test_inbox_persisted_no_duplicates_and_offline(root, monkeypatch):
    rec = {"id": "grok", "kind": "github_bridge", "discussion_id": "D_29"}
    box = {"nodes": [{"id": "w1", "body": "Неделя 1 " + MARK, "createdAt": "2026-11-04T09:00:00Z"}]}

    def call(req, timeout=0):
        assert "mutation" not in json.loads(req.data)["query"]
        return Resp(json.dumps(comments(*box["nodes"])).encode())
    monkeypatch.setattr(ac, "_opener", lambda: call)
    now = 1793000000.0          # 2026-10-27…: неделя назад попадает в окно
    assert sc.check_inbox(rec, now=now + 7 * 86400, token="") == []          # без токена — без сети
    got = sc.check_inbox(rec, now=now + 7 * 86400, token="t")
    assert [g["id"] for g in got] == ["w1"]
    assert sc.check_inbox(rec, now=now + 7 * 86400, token="t") == []          # без дублей
    box["nodes"].append({"id": "w2", "body": "Неделя 2 " + MARK, "createdAt": "2026-11-11T09:00:00Z"})
    assert [g["id"] for g in sc.check_inbox(rec, token="t")] == ["w2"]
    assert sc.inbox_path().exists()

    def offline(req, timeout=0):
        raise urllib.error.URLError("offline")
    monkeypatch.setattr(ac, "_opener", lambda: offline)
    with pytest.raises(urllib.error.URLError):
        sc.check_inbox(rec, token="t")


def test_watcher_emits_unsolicited_and_survives_offline(root, monkeypatch):
    orion.upsert({"id": "grok", "name": "Star Typing", "kind": "github_bridge", "discussion_id": "D_29"})
    monkeypatch.setattr(sc, "token_for", lambda rec: "t")
    node = {"id": "w1", "body": "Совет " + MARK, "createdAt": sc._iso(1793000000.0)}
    monkeypatch.setattr(ac, "_opener", lambda: lambda req, timeout=0: Resp(json.dumps(comments(node)).encode()))
    events = []
    w = sc.Watcher(lambda *e: events.append(e), now=lambda: 1793000000.0 + 60)
    assert w.tick() >= 1.0
    assert events and events[0][0] == "reply" and events[0][1] == "grok" and events[0][2]["unsolicited"]
    events.clear()
    w.check_inbox_soon()
    w.tick()
    assert events == []                                   # уже показано

    def offline(req, timeout=0):
        raise urllib.error.URLError("offline")
    monkeypatch.setattr(ac, "_opener", lambda: offline)
    w.check_inbox_soon()
    w.tick()
    assert events == []
