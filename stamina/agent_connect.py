"""Подключение агента — общий стандарт для Орион-чата.

Провайдеры выбираются по ``record["kind"]``:

- ``opencode``      — OpenCode CLI (прежнее поведение, ``orion._run_opencode``);
- ``openai_compat`` — любой OpenAI-совместимый API: OpenAI, DeepSeek, OpenRouter,
  Groq, локальная Ollama (без ключа). Чистый HTTP через urllib;
- ``github_bridge`` — мост через GitHub Discussions: сообщение + геолокация +
  скриншоты уходят в обсуждение (или webhook), ответы забираются опросом GraphQL.

Ключи хранятся только в диспетчере учётных данных Windows (keyring, если есть,
иначе ctypes CredWriteW/CredReadW). В json профиля — лишь ссылка ``cred_ref``.
Подписка ChatGPT Plus ключа API не даёт: нужен ключ OpenAI API.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

KINDS = ("opencode", "openai_compat", "github_bridge")
CRED_PREFIX = "StarTyping/agent/"

#: Готовые адреса — пилот выбирает и правит модель.
PRESETS = {
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat"),
    "openrouter": ("https://openrouter.ai/api/v1", "openrouter/auto"),
    "groq": ("https://api.groq.com/openai/v1", "llama-3.1-8b-instant"),
    "ollama": ("http://localhost:11434/v1", "llama3.1"),
}


# ----------------------------------------------------------------- учётные данные
def cred_ref(agent_id: str) -> str:
    return CRED_PREFIX + str(agent_id)


class _WinCred:
    """Минимальная обёртка над CredWriteW/CredReadW/CredDeleteW."""

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes
        self.ct = ctypes

        class CREDENTIAL(ctypes.Structure):
            _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
                        ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
                        ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
                        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                        ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
                        ("Attributes", ctypes.c_void_p), ("TargetAlias", wintypes.LPWSTR),
                        ("UserName", wintypes.LPWSTR)]
        self.CREDENTIAL = CREDENTIAL
        self.adv = ctypes.WinDLL("advapi32", use_last_error=True)

    def set(self, target: str, secret: str) -> None:
        ct = self.ct
        blob = secret.encode("utf-16-le")
        buf = (ct.c_ubyte * len(blob)).from_buffer_copy(blob)
        cred = self.CREDENTIAL(Type=1, TargetName=target, CredentialBlobSize=len(blob),
                               CredentialBlob=ct.cast(buf, ct.POINTER(ct.c_ubyte)),
                               Persist=2, UserName="StarTyping")
        if not self.adv.CredWriteW(ct.byref(cred), 0):
            raise OSError(ct.get_last_error(), "CredWriteW")

    def get(self, target: str) -> str:
        ct = self.ct
        ptr = ct.POINTER(self.CREDENTIAL)()
        if not self.adv.CredReadW(target, 1, 0, ct.byref(ptr)):
            return ""
        try:
            c = ptr.contents
            return ct.string_at(c.CredentialBlob, c.CredentialBlobSize).decode("utf-16-le")
        finally:
            self.adv.CredFree(ptr)

    def delete(self, target: str) -> None:
        self.adv.CredDeleteW(target, 1, 0)


def _backend():
    """keyring, если установлен; иначе Windows ctypes; иначе None (ключ не сохраняем)."""
    try:
        import keyring  # type: ignore
        return ("keyring", keyring)
    except Exception:  # noqa: BLE001
        pass
    if sys.platform == "win32":
        try:
            return ("wincred", _WinCred())
        except Exception:  # noqa: BLE001
            return None
    return None


def store_key(agent_id: str, secret: str) -> str:
    """Положить ключ в хранилище ОС. Возвращает ссылку для профиля ("" — пусто)."""
    ref = cred_ref(agent_id)
    be = _backend()
    if be is None:
        raise RuntimeError("no_store")
    name, obj = be
    if not secret:
        delete_key(ref)
        return ""
    if name == "keyring":
        obj.set_password(ref, "StarTyping", secret)
    else:
        obj.set(ref, secret)
    return ref


def read_key(ref: str) -> str:
    if not ref:
        return ""
    be = _backend()
    if be is None:
        return ""
    name, obj = be
    try:
        if name == "keyring":
            return obj.get_password(ref, "StarTyping") or ""
        return obj.get(ref)
    except Exception:  # noqa: BLE001
        return ""


def delete_key(ref: str) -> None:
    be = _backend()
    if be is None or not ref:
        return
    name, obj = be
    try:
        if name == "keyring":
            obj.delete_password(ref, "StarTyping")
        else:
            obj.delete(ref)
    except Exception:  # noqa: BLE001
        pass


# ----------------------------------------------------------------- openai_compat
def build_chat_request(record: dict, prompt: str, *, key: str = "",
                       history: list[dict] | None = None) -> urllib.request.Request:
    base = str(record.get("base_url") or "").rstrip("/")
    url = base + "/chat/completions"
    msgs = [{"role": "system", "content": str(record.get("system") or "")}] if record.get("system") else []
    msgs += list(history or [])
    msgs.append({"role": "user", "content": prompt})
    body = json.dumps({"model": str(record.get("model") or ""), "messages": msgs,
                       "stream": False}).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "StarTyping"}
    if key:
        headers["Authorization"] = "Bearer " + key
    return urllib.request.Request(url, data=body, headers=headers, method="POST")


def parse_chat_response(raw: bytes | str) -> str:
    data = json.loads(raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw)
    if isinstance(data, dict) and data.get("error"):
        err = data["error"]
        raise ValueError(err.get("message") if isinstance(err, dict) else str(err))
    choices = data.get("choices") or []
    if not choices:
        raise ValueError("no choices")
    msg = choices[0].get("message") or {}
    return str(msg.get("content") or choices[0].get("text") or "").strip()


def _http_error_code(exc: urllib.error.HTTPError) -> tuple[str, str]:
    detail = str(exc.reason or "")
    try:
        parse_chat_response(exc.read())
    except ValueError as err:          # {"error": {"message": ...}} — понятная причина
        detail = str(err) or detail
    except Exception:  # noqa: BLE001
        pass
    detail = f"HTTP {exc.code}: {detail}".strip()
    if exc.code in (401, 403):
        return "auth", detail
    if exc.code == 429:
        return "rate", detail
    return "http", detail


def _opener():
    return urllib.request.urlopen


def run_openai_compat(record: dict, prompt: str, *, timeout: float = 120.0):
    """Один запрос chat/completions. Возвращает orion.Result."""
    from stamina.orion import Result
    started = time.time()
    if not record.get("base_url"):
        return Result(error="config", detail="base_url", seconds=0.0)
    key = read_key(str(record.get("cred_ref") or ""))
    if not key and not _is_local(record.get("base_url", "")):
        return Result(error="no_key", seconds=0.0)
    req = build_chat_request(record, prompt, key=key)
    try:
        with _opener()(req, timeout=timeout) as resp:
            reply = parse_chat_response(resp.read())
    except urllib.error.HTTPError as exc:
        code, detail = _http_error_code(exc)
        return Result(error=code, detail=detail, seconds=time.time() - started)
    except (urllib.error.URLError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        kind = "timeout" if "timed out" in str(reason) else "network"
        return Result(error=kind, detail=str(reason), seconds=time.time() - started)
    except ValueError as exc:
        return Result(error="bad_reply", detail=str(exc), seconds=time.time() - started)
    if not reply:
        return Result(error="bad_reply", detail="empty", seconds=time.time() - started)
    return Result(reply=reply, seconds=time.time() - started)


def _is_local(url: str) -> bool:
    u = str(url).lower()
    return "://localhost" in u or "://127.0.0.1" in u


# ----------------------------------------------------------------- github_bridge
GRAPHQL = "https://api.github.com/graphql"


def _gql(token: str, query: str, variables: dict, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(GRAPHQL, data=json.dumps({"query": query, "variables": variables}).encode(),
                                 headers={"Authorization": "bearer " + token,
                                          "Content-Type": "application/json",
                                          "User-Agent": "StarTyping"}, method="POST")
    with _opener()(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    if data.get("errors"):
        raise ValueError(data["errors"][0].get("message", "graphql"))
    return data.get("data") or {}


POST_COMMENT = ("mutation($id:ID!,$body:String!){addDiscussionComment(input:{discussionId:$id,body:$body})"
                "{comment{id createdAt}}}")
POLL_COMMENTS = ("query($id:ID!){node(id:$id){... on Discussion{comments(last:20){nodes"
                 "{id body createdAt author{login}}}}}}")


def bridge_body(text: str, *, geo: str = "", shots=()) -> str:
    parts = [text.strip()]
    if geo:
        parts.append("📍 " + geo)
    for s in shots or ():
        parts.append(f"🖼 {os.path.basename(str(s))}")   # TODO: загрузка картинок (нет API вложений)
    return "\n\n".join(p for p in parts if p)


def pick_reply(nodes: list[dict], *, after: str, me: str = "") -> str:
    """Первый ответ, пришедший после нашего комментария, не от нас самих."""
    for n in nodes:
        if str(n.get("createdAt") or "") > after and (n.get("author") or {}).get("login") != me:
            return str(n.get("body") or "").strip()
    return ""


def run_github_bridge(record: dict, prompt: str, *, token: str = "", timeout: float = 300.0,
                      poll: float = 10.0, sleep=time.sleep):
    """Отправить сообщение в обсуждение GitHub и дождаться ответа агента опросом."""
    from stamina.orion import Result, read_binding
    started = time.time()
    disc = str(record.get("discussion_id") or "")
    token = token or read_key(str(record.get("cred_ref") or "")) or \
        str(read_binding(str(record.get("id") or "")).get("github_token") or "")
    if not disc:
        return Result(error="config", detail="discussion_id")
    if not token:
        return Result(error="no_key")
    try:
        posted = _gql(token, POST_COMMENT, {"id": disc, "body": bridge_body(prompt)})
        after = posted["addDiscussionComment"]["comment"]["createdAt"]
        me = str(record.get("bridge_login") or "")
        while time.time() - started < timeout:
            sleep(poll)
            data = _gql(token, POLL_COMMENTS, {"id": disc})
            nodes = ((data.get("node") or {}).get("comments") or {}).get("nodes") or []
            reply = pick_reply(nodes, after=after, me=me)
            if reply:
                return Result(reply=reply, seconds=time.time() - started)
    except urllib.error.HTTPError as exc:
        code, detail = _http_error_code(exc)
        return Result(error=code, detail=detail, seconds=time.time() - started)
    except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError) as exc:
        return Result(error="network", detail=str(exc), seconds=time.time() - started)
    return Result(error="timeout", seconds=time.time() - started)


# ----------------------------------------------------------------- проверка связи
def check(record: dict, *, key: str = "") -> tuple[bool, str]:
    """«Проверить связь»: короткий запрос. key — ещё не сохранённый ключ из поля."""
    kind = record.get("kind") or "opencode"
    if kind == "opencode":
        from stamina import orion
        ok, exe = orion.available()
        return ok, exe or "no_cli"
    if kind == "openai_compat":
        rec = dict(record)
        res = _run_with_key(rec, key) if key else run_openai_compat(rec, "ping: ответь одним словом OK", timeout=30)
        return (not res.error), (res.reply[:80] if not res.error else f"{res.error} {res.detail}".strip())
    if kind == "github_bridge":
        if not record.get("discussion_id"):
            return False, "config discussion_id"
        return True, "config ok"
    return False, "kind"


def _run_with_key(rec: dict, key: str):
    from stamina.orion import Result
    req = build_chat_request(rec, "ping: ответь одним словом OK", key=key)
    try:
        with _opener()(req, timeout=30) as resp:
            return Result(reply=parse_chat_response(resp.read()))
    except urllib.error.HTTPError as exc:
        code, detail = _http_error_code(exc)
        return Result(error=code, detail=detail)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return Result(error="network", detail=str(getattr(exc, "reason", exc)))
