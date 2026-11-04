"""Бортовой чат с внешним агентом через GitHub — «Star Typing (Grok)».

Модуль без tkinter: его проверяют тесты, а экран Ориона только вызывает функции.

Как ходит сообщение пилота:

1. Снимки экрана загружаются в репозиторий (ветка ``ship-chat-media``, contents API),
   чтобы у агента были настоящие ссылки на картинки, а не пути с диска пилота.
2. В обсуждение GitHub Discussions уходит комментарий: текст, отметка корабля,
   «геолокация» (правый клик), картинки и служебная метка ``<!-- star-typing-msg: <id> -->``.
3. Если в профиле задан ``webhook`` — тот же пакет уходит POST-ом (JSON) прямо агенту.
   Ключ отправителя лежит в хранилище ОС под именем ``StarTyping/agent/<id>/webhook``.
4. Ответы корабль забирает опросом в фоне (см. :class:`Watcher`): сначала часто, потом
   реже, до ``WAIT_WINDOW`` секунд на сообщение. Ожидание переживает перезапуск —
   номера сообщений лежат в ``orion/bridge_pending.json``.

Ответ агента — комментарий с меткой ``<!-- star-typing-reply -->`` и, желательно,
``<!-- reply-to: <id> -->``. Метка ``<!-- star-typing-interim -->`` — промежуточный
ответ («взялся»): корабль показывает его и ждёт дальше. Запасной путь — любой новый
комментарий не от ``bridge_login`` (логин пилота на GitHub).
"""
from __future__ import annotations

import base64
import json
import re
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from stamina import agent_connect as ac

API = "https://api.github.com"
MEDIA_BRANCH = "ship-chat-media"
WAIT_WINDOW = 30 * 60.0          # сколько ждём ответа на одно сообщение
PENDING_FILE = "bridge_pending.json"
MAX_SHOT_BYTES = 8 * 1024 * 1024

MSG_MARK = "<!-- star-typing-msg: {0} -->"
REPLY_MARK = "<!-- star-typing-reply -->"
INTERIM_MARK = "<!-- star-typing-interim -->"
_REPLY_TO = re.compile(r"<!--\s*reply-to:\s*([\w-]+)\s*-->")
_MSG_RX = re.compile(r"<!--\s*star-typing-msg:")

DEFAULT_HEADER = "Authorization"
DEFAULT_SCHEME = "Bearer"


# ----------------------------------------------------------------- ключи
def webhook_ref(agent_id: str) -> str:
    return ac.cred_ref(agent_id) + "/webhook"


def token_for(record: dict) -> str:
    """Токен GitHub: хранилище ОС по ``cred_ref`` или привязка агента. Никогда не json."""
    tok = ac.read_key(str(record.get("cred_ref") or ""))
    if tok:
        return tok
    try:
        from stamina.orion import read_binding
        return str(read_binding(str(record.get("id") or "")).get("github_token") or "")
    except Exception:  # noqa: BLE001
        return ""


# ----------------------------------------------------------------- HTTP
def _request(method: str, url: str, *, token: str = "", body=None, headers=None,
             timeout: float = 30.0) -> dict:
    return _request_meta(method, url, token=token, body=body, headers=headers, timeout=timeout)[0]


def _request_meta(method: str, url: str, *, token: str = "", body=None, headers=None,
                  timeout: float = 30.0) -> tuple[dict, dict]:
    """Как _request, но ещё и заголовки ответа (X-OAuth-Scopes и т. п.)."""
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    h = {"User-Agent": "StarTyping", "Accept": "application/vnd.github+json"}
    if body is not None:
        h["Content-Type"] = "application/json"
    if token:
        h["Authorization"] = "bearer " + token
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    with ac._opener()(req, timeout=timeout) as resp:
        raw = resp.read()
        got = {str(k).lower(): str(v) for k, v in dict(getattr(resp, "headers", None) or {}).items()}
    if not raw:
        return {}, got
    try:
        out = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        return {}, got
    return (out if isinstance(out, dict) else {"items": out}), got


def gql(token: str, query: str, variables: dict) -> dict:
    data = _request("POST", API + "/graphql", token=token,
                    body={"query": query, "variables": variables})
    if data.get("errors"):
        raise ValueError(data["errors"][0].get("message", "graphql"))
    return data.get("data") or {}


# ----------------------------------------------------------------- обсуждение
Q_RESOLVE = ("query($o:String!,$n:String!,$num:Int!){viewer{login}"
             "repository(owner:$o,name:$n){hasDiscussionsEnabled discussion(number:$num){id number title}}}")
Q_NODE = ("query($id:ID!){viewer{login} node(id:$id){... on Discussion{id number title "
          "repository{nameWithOwner}}}}")
POST_COMMENT = ("mutation($id:ID!,$body:String!){addDiscussionComment(input:{discussionId:$id,body:$body})"
                "{comment{id createdAt url}}}")
POLL_COMMENTS = ("query($id:ID!){node(id:$id){... on Discussion{comments(last:30){nodes"
                 "{id body createdAt author{login} replies(last:10){nodes{id body createdAt author{login}}}}}}}}")


def discussion_info(record: dict, token: str) -> dict:
    """{node_id, number, repo, title, login}. Бросает ValueError, если обсуждения нет."""
    repo = str(record.get("bridge_repo") or "").strip()
    num = str(record.get("discussion_number") or "").strip()
    node = str(record.get("discussion_id") or "").strip()
    if repo and num.isdigit():
        owner, _, name = repo.partition("/")
        data = gql(token, Q_RESOLVE, {"o": owner, "n": name, "num": int(num)})
        r = data.get("repository") or {}
        if not r:
            raise ValueError("repo not found")
        if not r.get("hasDiscussionsEnabled"):
            raise ValueError("discussions disabled")
        d = r.get("discussion") or {}
        if not d:
            raise ValueError("discussion not found")
        return {"node_id": d["id"], "number": d.get("number"), "repo": repo,
                "title": d.get("title", ""), "login": (data.get("viewer") or {}).get("login", "")}
    if node:
        data = gql(token, Q_NODE, {"id": node})
        d = data.get("node") or {}
        if not d.get("id"):
            raise ValueError("discussion not found")
        return {"node_id": d["id"], "number": d.get("number"),
                "repo": (d.get("repository") or {}).get("nameWithOwner", repo),
                "title": d.get("title", ""), "login": (data.get("viewer") or {}).get("login", "")}
    raise ValueError("discussion_id")


# ----------------------------------------------------------------- права токена
TOKEN_SETTINGS = "https://github.com/settings/personal-access-tokens"
_PERM_RE = re.compile(r"not accessible|bad credentials|could not resolve|must have|forbidden|"
                      r"repo not found|discussion not found|insufficient|scope", re.I)


def is_permission_error(code: int | None, detail: str = "") -> bool:
    """401/403/404 или «Resource not accessible by personal access token» в ответе GraphQL."""
    return code in (401, 403, 404) or bool(_PERM_RE.search(str(detail or "")))


def permission_hint(repo: str = "", need: str = "") -> str:
    """Что включить у токена GitHub — по-человечески, со ссылкой на настройки."""
    from stamina.i18n import t
    lines = [t("Токену GitHub не хватает прав для моста."),
             t("Откройте {url}, выберите токен и проверьте:").format(url=TOKEN_SETTINGS),
             "• " + t("Repository access — выбран репозиторий {repo}").format(
                 repo=repo or t("обсуждения")),
             "• " + t("Discussions — Read and write (писать комментарии в обсуждение)"),
             "• " + t("Contents — Read and write (класть снимки экрана в ветку ship-chat-media)")]
    if need == "media":
        lines.insert(1, t("Не прошла загрузка снимка экрана — скорее всего, нет Contents: Read and write."))
    elif need == "comment":
        lines.insert(1, t("Не прошёл комментарий — скорее всего, нет Discussions: Read and write."))
    return "\n".join(lines)


def write_access(repo: str, token: str) -> dict:
    """Права на запись без побочных эффектов: только GET /repos/{repo}.

    → {"comment": bool|None, "media": bool|None}; None — заранее узнать нельзя.
    Классический токен присылает свои области в X-OAuth-Scopes — по ним ответ точный.
    Детальный (fine-grained) токен свои права GitHub не сообщает; ``permissions`` репозитория —
    это роль пользователя, а не токена: она может только запретить, но не разрешить.
    """
    info, headers = _request_meta("GET", f"{API}/repos/{repo}", token=token)
    push = (info.get("permissions") or {}).get("push")
    private = bool(info.get("private"))
    out = {"comment": None, "media": None if push is not False else False}
    scopes = headers.get("x-oauth-scopes")
    if scopes is not None:
        have = {x.strip() for x in scopes.split(",") if x.strip()}
        ok = "repo" in have or ("public_repo" in have and not private)
        out["comment"] = ok
        out["media"] = ok and push is not False
    return out


def check(record: dict, *, key: str = "") -> tuple[bool | None, str]:
    """Проверить связь по-настоящему: токен работает, обсуждение существует, писать можно.

    → (True, …) — всё проверено; (None, …) — читать можно, запись заранее не проверить;
    (False, …) — не работает. Ничего не пишет в GitHub.
    """
    if not (record.get("discussion_id") or (record.get("bridge_repo") and record.get("discussion_number"))):
        return False, "config discussion"
    token = key or token_for(record)
    if not token:
        return False, "no_key"
    try:
        info = discussion_info(record, token)
    except urllib.error.HTTPError as exc:
        code, detail = ac._http_error_code(exc)
        return False, f"{code} {detail}".strip()
    except (urllib.error.URLError, OSError) as exc:
        return False, f"network {getattr(exc, 'reason', exc)}"
    except (ValueError, KeyError, TypeError) as exc:
        if is_permission_error(None, str(exc)):
            return False, f"{exc}\n" + permission_hint(str(record.get("bridge_repo") or ""))
        return False, str(exc)
    head = f"#{info.get('number')} «{info.get('title')}» · {info.get('login')}"
    repo = str(info.get("repo") or "")
    if not repo:
        return None, head
    try:
        can = write_access(repo, token)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}\n" + permission_hint(repo)
    except (urllib.error.URLError, OSError) as exc:
        return False, f"network {getattr(exc, 'reason', exc)}"
    from stamina.i18n import t
    if can["comment"] is False:
        return False, head + "\n" + permission_hint(repo, "comment")
    if can["media"] is False:
        return None, head + "\n" + permission_hint(repo, "media")
    if can["comment"] is None or can["media"] is None:
        return None, head + "\n" + t("Чтение работает. Права детального токена на запись GitHub "
                                      "заранее не сообщает — проверьте их в {url}: Discussions и "
                                      "Contents — Read and write.").format(url=TOKEN_SETTINGS)
    return True, head


# ----------------------------------------------------------------- снимки
def _ensure_media_branch(repo: str, token: str) -> None:
    try:
        _request("GET", f"{API}/repos/{repo}/git/ref/heads/{MEDIA_BRANCH}", token=token)
        return
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    info = _request("GET", f"{API}/repos/{repo}", token=token)
    base = info.get("default_branch") or "master"
    ref = _request("GET", f"{API}/repos/{repo}/git/ref/heads/{base}", token=token)
    sha = (ref.get("object") or {}).get("sha")
    try:
        _request("POST", f"{API}/repos/{repo}/git/refs", token=token,
                 body={"ref": f"refs/heads/{MEDIA_BRANCH}", "sha": sha})
    except urllib.error.HTTPError as exc:
        if exc.code != 422:            # 422 — ветку успели создать параллельно
            raise


def upload_shots(repo: str, token: str, message_id: str, paths, *, now: float | None = None) -> list[dict]:
    """Загрузить снимки в ветку ``ship-chat-media``. → [{name, url}] (ошибка — без url)."""
    out: list[dict] = []
    files = [Path(p) for p in (paths or ()) if p]
    if not files:
        return out
    day = time.strftime("%Y-%m-%d", time.localtime(now or time.time()))
    ready = False
    for i, path in enumerate(files, 1):
        item = {"name": path.name, "url": ""}
        try:
            blob = path.read_bytes()
            if len(blob) > MAX_SHOT_BYTES:
                raise ValueError("too big")
            if not ready:
                _ensure_media_branch(repo, token)
                ready = True
            ext = path.suffix.lower() or ".png"
            rel = f"shots/{day}/{message_id}-{i}{ext}"
            res = _request("PUT", f"{API}/repos/{repo}/contents/{rel}", token=token,
                           body={"message": f"ship-chat: {message_id} #{i}", "branch": MEDIA_BRANCH,
                                 "content": base64.b64encode(blob).decode("ascii")})
            item["url"] = str((res.get("content") or {}).get("download_url")
                              or f"https://raw.githubusercontent.com/{repo}/{MEDIA_BRANCH}/{rel}")
        except Exception as exc:  # noqa: BLE001
            item["error"] = str(exc)[:200]
        out.append(item)
    return out


# ----------------------------------------------------------------- пакет
def new_message_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]


def build_payload(*, message_id: str, text: str, context: dict | None = None, geo: str = "",
                  screenshots=(), discussion: dict | None = None, pilot: str = "",
                  app_version: str = "", agent_id: str = "") -> dict:
    ctx = dict(context or {})
    return {
        "message_id": message_id,
        "text": text,
        "context": {"compartment": ctx.pop("compartment", ""), "tab": ctx.pop("tab", ""),
                    "details": ctx},
        "geo": geo,
        "screenshots": [{"name": s.get("name", ""), "url": s.get("url", "")} for s in screenshots or ()],
        "discussion": {"repo": (discussion or {}).get("repo", ""),
                       "number": (discussion or {}).get("number"),
                       "node_id": (discussion or {}).get("node_id", "")},
        "pilot": pilot,
        "app_version": app_version,
        "agent_id": agent_id,
        "sent_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


def comment_body(payload: dict) -> str:
    """Комментарий в обсуждение: человеку читать, агенту разбирать."""
    parts = [str(payload.get("text") or "").strip()]
    c = payload.get("context") or {}
    where = " · ".join(x for x in (c.get("compartment"), c.get("tab")) if x)
    meta = []
    if where:
        meta.append(f"🧭 {where}")
    if payload.get("geo"):
        meta.append(f"📍 {payload['geo']}")
    if payload.get("pilot"):
        meta.append(f"👤 {payload['pilot']}")
    if payload.get("app_version"):
        meta.append(f"🚀 v{payload['app_version']}")
    if meta:
        parts.append("> " + "  \n> ".join(meta))
    for s in payload.get("screenshots") or ():
        if s.get("url"):
            parts.append(f"![{s.get('name', 'shot')}]({s['url']})")
        else:
            parts.append(f"🖼 {s.get('name', '')} (не загрузился)")
    details = (c.get("details") or {}).get("raw")
    if details:
        parts.append("<details><summary>контекст корабля</summary>\n\n```\n"
                     + str(details).replace("```", "'''") + "\n```\n</details>")
    parts.append(MSG_MARK.format(payload.get("message_id", "")))
    return "\n\n".join(p for p in parts if p)


def send_webhook(record: dict, payload: dict, *, key: str | None = None, timeout: float = 20.0) -> str:
    """POST пакета агенту. → "" при успехе, иначе код ошибки. Без адреса — "off"."""
    url = str(record.get("webhook") or "").strip()
    if not url:
        return "off"
    if key is None:
        key = ac.read_key(webhook_ref(str(record.get("id") or "")))
    headers = {"X-StarTyping-Message": str(payload.get("message_id") or "")}
    if key:
        name = str(record.get("webhook_header") or DEFAULT_HEADER).strip() or DEFAULT_HEADER
        scheme = record.get("webhook_scheme")
        scheme = DEFAULT_SCHEME if scheme is None else str(scheme).strip()
        headers[name] = f"{scheme} {key}".strip() if scheme and scheme != "-" else key
    try:
        _request("POST", url, body=payload, headers=headers, timeout=timeout)
    except urllib.error.HTTPError as exc:
        return f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return f"network {getattr(exc, 'reason', exc)}"
    return ""


def send(record: dict, text: str, *, context: dict | None = None, geo: str = "", shots=(),
         pilot: str = "", app_version: str = "", token: str = "") -> dict:
    """Отправить сообщение. → {ok, error, detail, message_id, after, webhook, payload}."""
    token = token or token_for(record)
    out = {"ok": False, "error": "", "detail": "", "message_id": new_message_id(),
           "after": "", "webhook": "", "payload": {}}
    if not token:
        out["error"] = "no_key"
        return out
    phase = "read"
    repo = str(record.get("bridge_repo") or "")
    try:
        disc = discussion_info(record, token)
        repo = disc.get("repo") or repo
        phase = "media"
        uploaded = upload_shots(repo, token, out["message_id"], shots) if repo else \
            [{"name": Path(p).name, "url": ""} for p in shots or ()]
        payload = build_payload(message_id=out["message_id"], text=text, context=context, geo=geo,
                                screenshots=uploaded, discussion=disc, pilot=pilot,
                                app_version=app_version, agent_id=str(record.get("id") or ""))
        phase = "comment"
        posted = gql(token, POST_COMMENT, {"id": disc["node_id"], "body": comment_body(payload)})
        out["after"] = posted["addDiscussionComment"]["comment"]["createdAt"]
        out["node_id"] = disc["node_id"]
        out["login"] = disc.get("login", "")
        out["payload"] = payload
    except urllib.error.HTTPError as exc:
        out["error"], out["detail"] = ac._http_error_code(exc)
        if is_permission_error(exc.code, out["detail"]):
            out["error"], out["need"], out["repo"] = "bridge_perm", phase, repo
        return out
    except (urllib.error.URLError, OSError) as exc:
        out["error"], out["detail"] = "network", str(getattr(exc, "reason", exc))
        return out
    except (ValueError, KeyError, TypeError) as exc:
        out["error"], out["detail"] = "config", str(exc)
        if is_permission_error(None, out["detail"]):
            out["error"], out["need"], out["repo"] = "bridge_perm", phase, repo
        return out
    out["webhook"] = send_webhook(record, payload)
    out["ok"] = True
    return out


# ----------------------------------------------------------------- ответы
def _flatten(nodes: list[dict]) -> list[dict]:
    flat = []
    for n in nodes or ():
        flat.append(n)
        flat.extend(((n.get("replies") or {}).get("nodes")) or ())
    return flat


def pick_replies(nodes: list[dict], *, message_id: str, after: str, seen=(), me: str = "") -> list[dict]:
    """Новые ответы на сообщение. → [{id, body, interim, createdAt}] по времени.

    Ответ — комментарий с ``REPLY_MARK``; если в нём есть ``reply-to``, он должен
    совпасть с ``message_id``. Без метки — только новый комментарий не от ``me``
    (и не наше собственное сообщение).
    """
    seen = set(seen or ())
    found = []
    for n in sorted(_flatten(nodes), key=lambda x: str(x.get("createdAt") or "")):
        cid = str(n.get("id") or "")
        body = str(n.get("body") or "")
        if not cid or cid in seen or str(n.get("createdAt") or "") <= after or _MSG_RX.search(body):
            continue
        if REPLY_MARK in body:
            to = _REPLY_TO.search(body)
            if to and to.group(1) != message_id:
                continue
        elif not me or (n.get("author") or {}).get("login") == me:
            continue
        found.append({"id": cid, "createdAt": n.get("createdAt"), "interim": INTERIM_MARK in body,
                      "body": clean_reply(body)})
    return found


def clean_reply(body: str) -> str:
    return re.sub(r"<!--.*?-->", "", body or "", flags=re.S).strip()


def poll(record: dict, entry: dict, *, token: str = "") -> list[dict]:
    token = token or token_for(record)
    data = gql(token, POLL_COMMENTS, {"id": entry["node_id"]})
    nodes = ((data.get("node") or {}).get("comments") or {}).get("nodes") or []
    me = str(record.get("bridge_login") or entry.get("login") or "")
    return pick_replies(nodes, message_id=entry["message_id"], after=entry["after"],
                        seen=entry.get("seen", ()), me=me)


def next_delay(age: float) -> float:
    """Опрос: первые 2 минуты — каждые 5 с, до 10 минут — 15 с, дальше — 45 с."""
    if age < 120:
        return 5.0
    if age < 600:
        return 15.0
    return 45.0


# ----------------------------------------------------------------- ожидание (переживает перезапуск)
_LOCK = threading.Lock()


def pending_path() -> Path:
    from stamina import orion
    return orion._root() / orion.HISTORY_DIR / PENDING_FILE


def load_pending() -> list[dict]:
    from stamina import orion
    data = orion._read_json(pending_path(), {})
    return [e for e in data.get("pending", []) if isinstance(e, dict) and e.get("message_id")]


def _save_pending(items: list[dict]) -> None:
    from stamina import orion
    orion._write_json(pending_path(), {"version": 1, "pending": items})


def add_pending(agent_id: str, sent: dict) -> dict:
    entry = {"agent_id": agent_id, "message_id": sent["message_id"], "node_id": sent["node_id"],
             "after": sent["after"], "login": sent.get("login", ""), "started": time.time(),
             "seen": []}
    with _LOCK:
        items = [e for e in load_pending() if e["message_id"] != entry["message_id"]]
        items.append(entry)
        _save_pending(items)
    return entry


def drop_pending(message_id: str = "", agent_id: str = "") -> int:
    with _LOCK:
        items = load_pending()
        keep = [e for e in items if not ((message_id and e["message_id"] == message_id)
                                         or (agent_id and not message_id and e["agent_id"] == agent_id))]
        _save_pending(keep)
    return len(items) - len(keep)


def _mark_seen(message_id: str, ids) -> None:
    with _LOCK:
        items = load_pending()
        for e in items:
            if e["message_id"] == message_id:
                e["seen"] = list(dict.fromkeys(list(e.get("seen") or []) + list(ids)))[-100:]
        _save_pending(items)


def waiting(agent_id: str = "") -> list[dict]:
    return [e for e in load_pending() if not agent_id or e["agent_id"] == agent_id]


# ----------------------------------------------------------------- сообщения без запроса
INBOX_FILE = "ship_chat_inbox.json"
INBOX_EVERY = 15 * 60          # медленный фоновый опрос, секунд
INBOX_BACKLOG = 7 * 24 * 3600  # при первом запуске — показать сообщения за последнюю неделю


def inbox_path() -> Path:
    from stamina import orion
    return orion._root() / orion.HISTORY_DIR / INBOX_FILE


def _inbox_load() -> dict:
    from stamina import orion
    data = orion._read_json(inbox_path(), {})
    return data.get("agents", {}) if isinstance(data.get("agents"), dict) else {}


def _inbox_save(agents: dict) -> None:
    from stamina import orion
    orion._write_json(inbox_path(), {"version": 1, "agents": agents})


def inbox_mark_seen(agent_id: str, ids, after: str = "") -> None:
    """Запомнить комментарии как показанные (ответы на запрос тоже — без дублей)."""
    with _LOCK:
        agents = _inbox_load()
        st = agents.setdefault(agent_id, {"after": "", "seen": []})
        st["seen"] = list(dict.fromkeys(list(st.get("seen") or []) + [str(i) for i in ids]))[-200:]
        if after and after > str(st.get("after") or ""):
            st["after"] = after
        _inbox_save(agents)


def _iso(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def pick_unsolicited(nodes: list[dict], *, after: str, seen=()) -> list[dict]:
    """Сообщения агента без запроса: с ``REPLY_MARK``, но без ``reply-to``; новее after."""
    seen = set(seen or ())
    out = []
    for n in sorted(_flatten(nodes), key=lambda x: str(x.get("createdAt") or "")):
        cid, body = str(n.get("id") or ""), str(n.get("body") or "")
        if (not cid or cid in seen or str(n.get("createdAt") or "") <= after
                or REPLY_MARK not in body or _REPLY_TO.search(body) or _MSG_RX.search(body)):
            continue
        out.append({"id": cid, "createdAt": n.get("createdAt"), "interim": False,
                    "unsolicited": True, "body": clean_reply(body)})
    return out


def check_inbox(record: dict, *, now: float | None = None, token: str = "") -> list[dict]:
    """Новые сообщения агента без запроса (например, еженедельные рекомендации).

    Без токена — пусто и без сети. Ошибки сети пробрасываются: вызывающий молча повторит позже.
    Состояние (последнее время + id показанных) хранится на диске — без дублей между запусками.
    """
    aid = str(record.get("id") or "")
    token = token or token_for(record)
    if not aid or not token:
        return []
    if not (record.get("discussion_id") or (record.get("bridge_repo") and record.get("discussion_number"))):
        return []
    st = _inbox_load().get(aid) or {}
    after = str(st.get("after") or "") or _iso((now or time.time()) - INBOX_BACKLOG)
    seen = set(st.get("seen") or ())
    for e in load_pending():                       # уже разобранные ответы на запросы
        seen.update(e.get("seen") or ())
    node = str(record.get("discussion_id") or "").strip()
    if not node or record.get("bridge_repo"):
        node = discussion_info(record, token)["node_id"]
    data = gql(token, POLL_COMMENTS, {"id": node})
    nodes = ((data.get("node") or {}).get("comments") or {}).get("nodes") or []
    found = pick_unsolicited(nodes, after=after, seen=seen)
    if found:
        inbox_mark_seen(aid, [f["id"] for f in found], str(found[-1]["createdAt"] or ""))
    elif not st.get("after"):
        inbox_mark_seen(aid, [], after)            # зафиксировать отсчёт после первого опроса
    return found


class Watcher:
    """Фоновый опрос всех ожидающих сообщений. События — в ``emit(kind, agent_id, data)``.

    kind: ``reply`` (data — ответ), ``done`` (ожидание закончено), ``expired``, ``error``.
    """

    def __init__(self, emit, *, get_record=None, now=time.time, sleep=None) -> None:
        from stamina import orion
        self.emit = emit
        self.get_record = get_record or orion.get
        self.now = now
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._next: dict[str, float] = {}
        self._errors: dict[str, int] = {}
        self._thread: threading.Thread | None = None
        self._sleep = sleep
        self._inbox_due = 0.0          # 0 — проверить сообщения без запроса при первом проходе

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ship-chat")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def kick(self) -> None:
        self._wake.set()

    def check_inbox_soon(self) -> None:
        """Открыли чат Ориона — проверить сообщения без запроса, не дожидаясь 15 минут."""
        self._inbox_due = 0.0
        self._wake.set()

    def _agents(self) -> list[dict]:
        from stamina import orion
        return [a for a in orion.agents() if a.get("kind") == "github_bridge"]

    def _inbox_tick(self, now: float) -> float:
        if now < self._inbox_due:
            return self._inbox_due - now
        self._inbox_due = now + INBOX_EVERY
        for rec in self._agents():
            try:
                found = check_inbox(rec, now=now)
            except Exception:  # noqa: BLE001 — нет сети: тихо повторим в следующий раз
                continue
            for f in found:
                self.emit("reply", str(rec.get("id")), f)
        return INBOX_EVERY

    def _loop(self) -> None:
        while not self._stop.is_set():
            delay = self.tick()
            if self._sleep:
                self._sleep(delay)
            else:
                self._wake.wait(delay)
                self._wake.clear()

    def tick(self) -> float:
        """Один проход опроса. → через сколько секунд снова."""
        now = self.now()
        items = load_pending()
        soonest = 30.0 if items else float(INBOX_EVERY)
        for e in items:
            mid = e["message_id"]
            age = now - float(e.get("started") or now)
            if age > WAIT_WINDOW:
                drop_pending(mid)
                self.emit("expired", e["agent_id"], e)
                continue
            due = self._next.get(mid, 0.0)
            if now < due:
                soonest = min(soonest, due - now)
                continue
            rec = self.get_record(e["agent_id"])
            if rec is None:
                drop_pending(mid)
                continue
            try:
                found = poll(rec, e)
                self._errors.pop(mid, None)
            except Exception as exc:  # noqa: BLE001
                n = self._errors[mid] = self._errors.get(mid, 0) + 1
                if n in (3, 20):
                    self.emit("error", e["agent_id"], {"message_id": mid, "detail": str(exc)[:200]})
                found = []
            if found:
                _mark_seen(mid, [f["id"] for f in found])
                inbox_mark_seen(e["agent_id"], [f["id"] for f in found])
            final = False
            for f in found:
                self.emit("reply", e["agent_id"], dict(f, message_id=mid))
                final = final or not f["interim"]
            if final:
                drop_pending(mid)
                self._next.pop(mid, None)
                self.emit("done", e["agent_id"], {"message_id": mid})
                continue
            wait = next_delay(age)
            self._next[mid] = now + wait
            soonest = min(soonest, wait)
        # после ответов на запросы: их id уже помечены, сообщения без запроса не задвоятся
        soonest = min(soonest, self._inbox_tick(now))
        return max(1.0, soonest)


# ----------------------------------------------------------------- блокирующий путь (запасной агент)
def run_blocking(record: dict, prompt: str, *, token: str = "", timeout: float = 300.0,
                 sleep=time.sleep):
    """Отправить и дождаться первого окончательного ответа — для цепочки запасных агентов."""
    from stamina.orion import Result
    started = time.time()
    if not (record.get("discussion_id") or (record.get("bridge_repo") and record.get("discussion_number"))):
        return Result(error="config", detail="discussion_id")
    token = token or token_for(record)
    if not token:
        return Result(error="no_key")
    sent = send(record, prompt, token=token)
    if not sent["ok"]:
        return Result(error=sent["error"], detail=sent["detail"], seconds=time.time() - started)
    entry = {"message_id": sent["message_id"], "node_id": sent["node_id"], "after": sent["after"],
             "login": sent.get("login", ""), "seen": []}
    texts: list[str] = []
    while time.time() - started < timeout:
        sleep(next_delay(time.time() - started))
        try:
            found = poll(record, entry, token=token)
        except Exception as exc:  # noqa: BLE001
            return Result(error="network", detail=str(exc), seconds=time.time() - started)
        for f in found:
            entry["seen"].append(f["id"])
            texts.append(f["body"])
            if not f["interim"]:
                return Result(reply="\n\n".join(texts), seconds=time.time() - started)
    return Result(error="timeout", reply="\n\n".join(texts), seconds=time.time() - started)
