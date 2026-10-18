"""ОРИОН — бортовой разум: реестр агентов, история диалога и вызов агента.

Модуль без tkinter, поэтому его проверяют тесты и он же станет основой онлайна.

Идея: **агент заселяется на борт** как пассажир — у него есть имя, уровень доступа
и голос. Корабль говорит с агентом через OpenCode CLI (`opencode run`), читая поток
JSON-событий. Что именно доступно агенту, решают файлы ``.opencode/agents/orion-*.md``
(там инструменты отключаются физически — это и есть защита «обычного пользователя»).

Уровни доступа:

===========================  ==================================================
``commander`` — Командир     Полный доступ: сначала доклад (чтение), затем, после
                             разрешения пилота, второй проход — изменения и новый
                             функционал. Так «спрашивать перед действиями» решает
                             сам корабль, а не CLI (headless сам соглашается).
``observer`` — Наблюдатель    Только чтение: докладывает, менять не может.
``crew`` — Экипаж             Только беседа: ни файлов, ни команд, ни интернета.
===========================  ==================================================

Файлы (в корне данных экипажа, рядом с ``comm.json``)::

    agents.json          {"version": 1, "agents": [...], "active": "<id>"}
    orion/<id>.json      {"version": 1, "session": "ses_…", "messages": [...]}
    orion/<id>.character.md   документ манер агента (пилот правит его на корабле)

Права и манеры — разные вещи: **права** выдаются на входе (уровнем доступа, а Командир —
по коду владельца корабля, `stamina/owner_key.py`), а **манеры** пилот пишет сам
документом на борту — корабль передаёт его агенту блоком ``[МАНЕРЫ АГЕНТА]``.
"""
from __future__ import annotations

from stamina.i18n import t as _t

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]

AGENTS_FILE = "agents.json"
HISTORY_DIR = "orion"
CHARACTER_DIR = "orion"      # документы манер лежат рядом с историей диалога
CHARACTER_SUFFIX = ".character.md"
TASKS_FILE = "orion_tasks.json"
MAX_MESSAGES = 200          # сколько реплик диалога храним
MAX_TEXT = 6000             # знаков в одной реплике
MAX_CHARACTER = 4000        # знаков в документе манер агента
TIMEOUT = 600.0             # секунд на ответ агента (модель может думать долго)
MARKER = "⟦ТРЕБУЕТСЯ РАЗРЕШЕНИЕ⟧"

ACCESSES = ("commander", "observer", "crew")
VOICE_MODES = ("ship", "agent", "off")

# Уровень доступа → какие агенты OpenCode запускаются (первый проход, второй проход).
PROFILES: dict[str, tuple[str, str | None]] = {
    "commander": ("orion-recon", "orion-commander"),
    "observer": ("orion-recon", None),
    "crew": ("orion-chat", None),
}

DEFAULT_AGENT = {
    "id": "orion",
    "name": "Орион",
    "kind": "opencode",
    "access": "commander",
    "profile": "",            # пусто — профили по уровню доступа
    "model": "",              # пусто — модель OpenCode по умолчанию
    "voice": "ship",          # корабль озвучивает ответ (агент без shell сам говорить не может)
    "enabled": True,
    "note": "Бортовой разум: доклад отсека, порядок на корабле, новый функционал",
}

# Слова, по которым корабль понимает: пилот диктует задание, а не просто беседует.
# Сличаем по началу слова, поэтому «запиши»/«записывай»/«записать» попадают все.
TASK_TRIGGERS = (
    "запиши", "записать", "записывай", "запишите", "зафиксируй", "зафиксировать",
    "на заметку", "запомни", "поставь задачу", "поставь задание", "добавь задание",
    "добавь задачу", "создай задание", "создай задачу", "есть задание", "есть задача",
    "у тебя есть задание", "задание от командира", "задача от командира",
    "в список дел", "в документ", "todo",
)
YES_WORDS = ("да", "ага", "верно", "точно", "записывай", "запиши", "подтверждаю",
             "хорошо", "конечно", "yes", "ok", "окей")
NO_WORDS = ("нет", "не надо", "не нужно", "отмена", "отставить", "не сейчас", "no")

# Слова-наполнители после указателя: «запиши ЗАДАНИЕ сделать…» → задание «сделать…»
TASK_FILLERS = ("пожалуйста", "это", "то", "что", "новое", "следующее", "себе",
                "в документ", "в список дел", "на заметку", "заметку", "в заметки",
                "задание", "задачу", "задачи", "задача", "задачку", "таск", "todo")


# -- файлы ----------------------------------------------------------------------
def _root() -> Path:
    # ROOT_DIR меняется в tests/pilots.reset_root, поэтому берём его в момент вызова
    from stamina import pilots
    return Path(pilots.ROOT_DIR)


def agents_path() -> Path:
    return _root() / AGENTS_FILE


def history_path(agent_id: str) -> Path:
    return _root() / HISTORY_DIR / f"{_safe_id(agent_id)}.json"


def character_path(agent_id: str) -> Path:
    """Документ манер агента на борту: пилот правит его сам (зона ОРИОН → АГЕНТЫ)."""
    return _root() / CHARACTER_DIR / f"{_safe_id(agent_id)}{CHARACTER_SUFFIX}"


def _safe_id(agent_id: str) -> str:
    keep = "".join(ch for ch in (agent_id or "").strip().lower() if ch.isalnum() or ch in "-_")
    return keep or "agent"


def _write_json(path: Path, data: dict) -> None:
    """Атомарная запись (временный файл + замена) — данные не бьются при закрытии."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / (path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path, fallback: dict) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback
    return data if isinstance(data, dict) else fallback


# -- реестр агентов -------------------------------------------------------------
def registry() -> dict:
    """Реестр пассажиров: версия, список агентов и активный. Орион есть всегда."""
    data = _read_json(agents_path(), {})
    agents = [a for a in (data.get("agents") or []) if isinstance(a, dict) and a.get("id")]
    data = {"version": 1, "agents": agents, "active": str(data.get("active") or "")}
    if not any(a["id"] == DEFAULT_AGENT["id"] for a in agents):
        data["agents"].insert(0, dict(DEFAULT_AGENT))
    for a in data["agents"]:
        a.setdefault("kind", "opencode")
        a.setdefault("access", "crew" if a["id"] != DEFAULT_AGENT["id"] else "commander")
        a.setdefault("voice", "ship")
        a.setdefault("profile", "")
        a.setdefault("model", "")
        a.setdefault("enabled", True)
        a.setdefault("note", "")
        if a["access"] not in ACCESSES:
            a["access"] = "crew"
        if a["voice"] not in VOICE_MODES:
            a["voice"] = "ship"
    if not data["active"] or not any(a["id"] == data["active"] for a in data["agents"]):
        data["active"] = next((a["id"] for a in data["agents"] if a.get("enabled")),
                              data["agents"][0]["id"])
    return data


def save_registry(data: dict) -> None:
    _write_json(agents_path(), {"version": 1, "agents": data.get("agents", []),
                                "active": data.get("active", "")})


def agents() -> list[dict]:
    return registry()["agents"]


def get(agent_id: str) -> dict | None:
    return next((a for a in agents() if a["id"] == agent_id), None)


def active() -> dict:
    """Активный пассажир (по нему идёт диалог)."""
    reg = registry()
    found = get(reg["active"])
    if found is not None and found.get("enabled", True):
        return found
    for a in reg["agents"]:
        if a.get("enabled", True):
            return a
    return dict(DEFAULT_AGENT)


def set_active(agent_id: str) -> bool:
    data = registry()
    if not any(a["id"] == agent_id for a in data["agents"]):
        return False
    data["active"] = agent_id
    save_registry(data)
    return True


def upsert(record: dict) -> dict:
    """Заселить нового агента или сохранить изменения существующего."""
    data = registry()
    rid = str(record.get("id") or "").strip().lower()
    if not rid:
        base = "".join(ch for ch in str(record.get("name") or "agent").lower()
                       if ch.isalnum() or ch in "-_") or "agent"
        rid = base
        others = {a["id"] for a in data["agents"]}
        n = 2
        while rid in others:
            rid = f"{base}-{n}"
            n += 1
    fresh = {
        "id": rid,
        "name": str(record.get("name") or rid).strip()[:40],
        "kind": "opencode",
        "access": record.get("access") if record.get("access") in ACCESSES else "crew",
        "profile": str(record.get("profile") or "").strip(),
        "model": str(record.get("model") or "").strip(),
        "voice": record.get("voice") if record.get("voice") in VOICE_MODES else "ship",
        "enabled": bool(record.get("enabled", True)),
        "note": str(record.get("note") or "").strip()[:200],
        "created": float(record.get("created") or time.time()),
    }
    for i, a in enumerate(data["agents"]):
        if a["id"] == rid:
            fresh["created"] = float(a.get("created") or fresh["created"])
            data["agents"][i] = fresh
            break
    else:
        data["agents"].append(fresh)
        data.setdefault("active", rid)
    save_registry(data)
    ensure_character(rid, name=fresh["name"])      # документ манер — при входе на борт
    return fresh


def remove(agent_id: str) -> bool:
    """Убрать агента с борта (Ориона-бортразаума не убираем — только отключаем)."""
    if agent_id == DEFAULT_AGENT["id"]:
        return False
    data = registry()
    keep = [a for a in data["agents"] if a["id"] != agent_id]
    if len(keep) == len(data["agents"]):
        return False
    data["agents"] = keep
    if data["active"] == agent_id:
        data["active"] = next((a["id"] for a in keep if a.get("enabled")), keep[0]["id"])
    save_registry(data)
    try:
        history_path(agent_id).unlink()
    except OSError:
        pass
    try:
        character_path(agent_id).unlink()          # ушёл с борта — забрал и документ манер
    except OSError:
        pass
    return True


def profiles(record: dict) -> tuple[str, str | None]:
    """Профили OpenCode для агента: (первый проход, второй проход или None)."""
    own = str(record.get("profile") or "").strip()
    first, second = PROFILES.get(record.get("access", "crew"), PROFILES["crew"])
    return (own or first), (own and None or second)


# -- история диалога ------------------------------------------------------------
def history(agent_id: str) -> dict:
    data = _read_json(history_path(agent_id), {})
    msgs = [m for m in (data.get("messages") or []) if isinstance(m, dict)]
    return {"version": 1, "session": str(data.get("session") or ""), "messages": msgs}


def remember(agent_id: str, role: str, text: str, *, session: str | None = None,
             kind: str = "") -> dict:
    """Дописать реплику: role — pilot | orion | system."""
    data = _read_json(history_path(agent_id), {"version": 1, "session": "", "messages": []})
    data.setdefault("messages", [])
    if session:
        data["session"] = session
    msg = {"id": uuid.uuid4().hex[:12], "role": role, "ts": time.time(),
           "text": " ".join((text or "").split())[:MAX_TEXT], "kind": kind}
    data["messages"].append(msg)
    if len(data["messages"]) > MAX_MESSAGES:
        data["messages"] = data["messages"][-MAX_MESSAGES:]
    _write_json(history_path(agent_id), data)
    return msg


def clear_history(agent_id: str) -> None:
    """Начать разговор заново (и новый сеанс у агента: прежний контекст забыт)."""
    _write_json(history_path(agent_id), {"version": 1, "session": "", "messages": []})


def last_session(agent_id: str) -> str:
    return history(agent_id)["session"]


# -- документ манер агента ------------------------------------------------------
def default_character(name: str = "") -> str:
    """Заготовка документа манер: корабль создаёт его, когда агент входит на борт."""
    return _t(
        "Ты — {0}, член экипажа звездолёта Star Typing.\n"
        "\n"
        "Манеры: вежливый дворецкий с сухой иронией. Обращение — по позывному пилота или «сэр».\n"
        "Ответы короткие: 2–5 предложений, как реплика в чате, а не отчёт.\n"
        "\n"
        "Это документ корабля: пилот правит его сам (зона ОРИОН → АГЕНТЫ → МАНЕРЫ АГЕНТА).\n"
        "Права доступа здесь не меняются — их выдают на входе."
    ).format((name or "").strip() or _t("агент"))


def read_character(agent_id: str) -> str:
    try:
        return character_path(agent_id).read_text(encoding="utf-8")
    except (OSError, ValueError):
        return ""


def save_character(agent_id: str, text: str) -> str:
    """Записать документ манер (правит пилот). Возвращает то, что сохранено."""
    clean = (text or "").strip()[:MAX_CHARACTER]
    path = character_path(agent_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(clean, encoding="utf-8")
    return clean


def ensure_character(agent_id: str, *, name: str = "") -> Path:
    """Создать документ манер при входе агента на борт (если его ещё нет)."""
    path = character_path(agent_id)
    if not path.exists():
        save_character(agent_id, default_character(name))
    return path


def character_block(agent_id: str) -> str:
    """Блок манер для агента: что корабль передаёт ему перед сообщением пилота.

    Включает документ манер пилота + автоматические правила эволюции характера.
    Заголовок [МАНЕРЫ АГЕНТА] ставится только когда есть документ манер.
    """
    text = read_character(agent_id).strip()
    evo = evolution_manner(agent_id)
    if not text and not evo:
        return ""
    if not text:
        return f"[ЭВОЛЮЦИЯ ХАРАКТЕРА]\n{evo}"
    parts = [text]
    if evo:
        parts.append(f"[ЭВОЛЮЦИЯ ХАРАКТЕРА]\n{evo}")
    return f"[МАНЕРЫ АГЕНТА]\n" + "\n\n".join(parts)


# -- документ заданий -----------------------------------------------------------
def tasks_path() -> Path:
    return _root() / TASKS_FILE


def tasks(*, status: str = "") -> list[dict]:
    """Задания, записанные Ориону: свежие сверху. status — open | done (пусто — все)."""
    data = _read_json(tasks_path(), {})
    rows = [t for t in (data.get("tasks") or []) if isinstance(t, dict)]
    if status:
        rows = [t for t in rows if t.get("status") == status]
    return sorted(rows, key=lambda t: float(t.get("ts") or 0.0), reverse=True)


def add_task(text: str, *, author: str = "", agent: str = "") -> dict:
    """Записать задание в документ борта (по подтверждению командира)."""
    data = _read_json(tasks_path(), {"version": 1, "tasks": []})
    data.setdefault("tasks", [])
    row = {"id": uuid.uuid4().hex[:12], "ts": time.time(),
           "text": " ".join((text or "").split())[:MAX_TEXT],
           "author": author, "agent": agent or DEFAULT_AGENT["id"], "status": "open"}
    data["tasks"].append(row)
    _write_json(tasks_path(), data)
    return row


def close_task(task_id: str, *, status: str = "done") -> bool:
    data = _read_json(tasks_path(), {"version": 1, "tasks": []})
    for row in data.get("tasks") or []:
        if row.get("id") == task_id:
            row["status"] = status
            _write_json(tasks_path(), data)
            return True
    return False


# -- понимание речи пилота ------------------------------------------------------
def _strip_fillers(text: str) -> str:
    """Убрать служебные слова в начале: «запиши ЗАДАНИЕ сделать…» → «сделать…»."""
    rest = text.strip(" ,.—-:;")
    trimmed = True
    while trimmed and rest:
        trimmed = False
        head = rest.lower()
        for filler in TASK_FILLERS:
            if head == filler or head.startswith(filler + " ") or head.startswith(filler + ":"):
                rest = rest[len(filler):].lstrip(" ,:.—-")
                trimmed = True
                break
    return rest


def detect_task(text: str) -> tuple[bool, str]:
    """Похоже ли, что пилот диктует задание. Возвращает (нашлось, само задание).

    Второе значение — «тело» задания без слов-указателей. Пусто — пилот только
    объявил, что задание есть: корабль спросит, что именно записать.
    Корабль не верит себе на слово: найдя указатели, он переспрашивает
    («записать это в документ?») и пишет только после подтверждения.
    """
    low = (text or "").lower()
    for trigger in TASK_TRIGGERS:
        pos = low.find(trigger)
        if pos < 0:
            continue
        after = _strip_fillers(text[pos + len(trigger):].strip(" ,.—-:;"))
        return True, " ".join(after.split())
    return False, " ".join((text or "").split())


def is_yes(text: str) -> bool:
    low = " ".join((text or "").lower().replace("ё", "е").split())
    return bool(low) and any(low.startswith(w) for w in YES_WORDS)


def is_no(text: str) -> bool:
    low = " ".join((text or "").lower().replace("ё", "е").split())
    return bool(low) and any(low.startswith(w) for w in NO_WORDS)


# -- вызов агента ---------------------------------------------------------------
SHIMS = (".cmd", ".bat")


def _native_exe(path: str) -> str:
    """Для npm-обёртки (.cmd/.bat) найти настоящий exe рядом с ней.

    Оболочка cmd.exe обрезает аргумент на переводе строки, а запрос к агенту —
    многострочный (документ манер + отметка корабля + реплика). Настоящий exe
    получает аргумент целиком, поэтому он всегда предпочтительнее обёртки.
    """
    shim = Path(str(path))
    if shim.suffix.lower() not in SHIMS:
        return str(shim)
    native = shim.parent / "node_modules" / "opencode-ai" / "bin" / "opencode.exe"
    return str(native) if native.is_file() else str(shim)


def find_cli() -> str:
    """Путь к OpenCode CLI. Пусто — не найден."""
    explicit = os.environ.get("STAR_TYPING_OPENCODE")
    if explicit and Path(explicit).is_file():
        return explicit                     # явный выбор пилота не перепроверяем
    for candidate in (shutil.which("opencode"), shutil.which("opencode.cmd"),
                      Path(os.environ.get("APPDATA", "")) / "npm/node_modules/opencode-ai/bin/opencode.exe",
                      Path(os.environ.get("APPDATA", "")) / "npm/opencode.cmd"):
        if not candidate:
            continue
        path = Path(str(candidate))
        if path.is_file():
            return _native_exe(str(path))
    return ""


def flatten(text: str) -> str:
    """Схлопнуть переводы строк: .cmd-обёртка иначе обрежет запрос на первом \\n."""
    lines = [" ".join(line.split()) for line in text.replace("\r\n", "\n").split("\n")]
    return " · ".join(part for part in lines if part)


def available() -> tuple[bool, str]:
    """Готов ли борт принимать агента: (готово, путь к CLI)."""
    exe = find_cli()
    return bool(exe), exe


def context_line(*, zone: str = "", subtab: str = "", pilot: str = "", access: str = "",
                 version: str = "", geometry: str = "", was: str = "") -> str:
    """Отметка корабля перед сообщением: какой отсек открыт сейчас.

    По ней агент понимает, о каком окне речь, когда пилот говорит «здесь» или «тут».
    `was` — раздел, который был открыт до Ориона: пилот обычно ставит задачу оттуда.
    """
    bits = []
    if zone:
        bits.append(f"открыт раздел «{zone}»")
    if subtab:
        bits.append(f"подвкладка «{subtab}»")
    if was and was != zone:
        bits.append(f"перед этим пилот был в разделе «{was}»")
    if pilot:
        bits.append(f"пилот: {pilot}")
    if access:
        bits.append(f"уровень доступа: {access}")
    if version:
        bits.append(f"версия корабля {version}")
    if geometry:
        bits.append(f"окно {geometry}")
    return ("[КОРАБЛЬ] " + " · ".join(bits)) if bits else ""


def build_command(exe: str, profile: str, prompt: str, *, session: str = "",
                  model: str = "", project: Path | None = None) -> list[str]:
    """Команда запуска агента: `opencode run --format json …`."""
    cmd = [exe, "run", "--format", "json", "--dir", str(project or PROJECT_DIR)]
    if session:
        cmd += ["--session", session]
    if profile:
        cmd += ["--agent", profile]
    if model:
        cmd += ["--model", model]
    cmd.append(prompt)
    return cmd


def parse_events(stdout: str) -> dict:
    """Разобрать поток JSON-событий: текст ответа, сеанс, инструменты, отказы.

    `spoke` — агент озвучил себя сам (вызвал say.py): тогда корабль молчит,
    чтобы ответ не читался дважды.
    """
    texts: dict[str, list[str]] = {}
    order: list[str] = []
    session = ""
    tools: list[str] = []
    denied = False
    spoke = False
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        session = str(ev.get("sessionID") or session)
        part = ev.get("part") or {}
        kind = ev.get("type")
        if kind == "text":
            mid = str(part.get("messageID") or "")
            if mid not in texts:
                texts[mid] = []
                order.append(mid)
            texts[mid].append(str(part.get("text") or ""))
        elif kind == "tool_use":
            tools.append(str(part.get("tool") or ""))
            blob = json.dumps(part, ensure_ascii=False).lower()
            if "say.py" in blob:
                spoke = True
            if "denied" in blob or "not permitted" in blob or "permission" in blob:
                denied = True
        elif kind in ("error", "permission"):
            denied = True
    reply = "\n\n".join("".join(texts[m]) for m in order[-1:]).strip() if order else ""
    return {"reply": reply, "session": session, "tools": tools, "denied": denied, "spoke": spoke}


def strip_marker(text: str) -> tuple[str, str]:
    """Отделить служебный запрос разрешения от ответа: (текст для показа, что просят)."""
    clean, request = [], ""
    for line in (text or "").splitlines():
        stripped = line.strip()
        if MARKER in stripped:
            request = stripped.split(MARKER, 1)[1].strip(" :—-")
            continue
        clean.append(line)
    return "\n".join(clean).strip(), request


@dataclass
class Result:
    """Итог разговора с агентом."""

    reply: str = ""
    session: str = ""
    tools: list[str] = field(default_factory=list)
    needs_permission: bool = False
    request: str = ""
    spoke: bool = False       # агент озвучил себя сам
    error: str = ""          # код: no_cli | timeout | spawn | empty
    detail: str = ""
    seconds: float = 0.0
    profile: str = ""


def ask(record: dict, text: str, *, context: str = "", profile: str = "",
        session: str = "", timeout: float = TIMEOUT) -> Result:
    """Спросить агента (первый проход). Разрешение на изменения корабль спросит сам."""
    first, _second = profiles(record)
    return run_profile(record, text, profile=profile or first, context=context,
                       session=session, timeout=timeout)


def run_profile(record: dict, text: str, *, profile: str, context: str = "",
                session: str = "", timeout: float = TIMEOUT,
                character: str | None = None) -> Result:
    """Запустить конкретный профиль агента и вернуть ответ (синхронно — звать из потока).

    `character` — блок манер (документ, который пилот правит на борту). None —
    взять документ манер агента из борта.
    """
    if not (text or "").strip():
        return Result(error="empty", profile=profile)
    exe = find_cli()
    if not exe:
        return Result(error="no_cli", profile=profile)
    if character is None:
        character = character_block(str(record.get("id") or DEFAULT_AGENT["id"]))
    prompt = "\n\n".join(part for part in (character, context, text.strip()) if part)
    if Path(exe).suffix.lower() in SHIMS:
        prompt = flatten(prompt)          # обёртка cmd.exe не пропустит переводы строк
    cmd = build_command(exe, profile, prompt, session=session, model=str(record.get("model") or ""))
    started = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout,
                              cwd=str(PROJECT_DIR))
    except subprocess.TimeoutExpired:
        return Result(error="timeout", profile=profile, seconds=time.time() - started)
    except OSError as exc:
        return Result(error="spawn", detail=str(exc), profile=profile,
                      seconds=time.time() - started)
    out = (proc.stdout or b"").decode("utf-8", "replace")
    parsed = parse_events(out)
    reply, request = strip_marker(parsed["reply"])
    needs = bool(request) or parsed["denied"]
    if not reply and proc.returncode != 0:
        tail = (proc.stderr or b"").decode("utf-8", "replace").strip().splitlines()
        return Result(error="spawn", detail=(tail[-1] if tail else ""), session=parsed["session"],
                      profile=profile, seconds=time.time() - started)
    return Result(reply=reply, session=parsed["session"], tools=parsed["tools"],
                  needs_permission=needs, request=request, spoke=parsed["spoke"],
                  profile=profile, seconds=time.time() - started)


def access_label(access: str) -> str:
    """Подпись уровня доступа для интерфейса (переводится вызывающим)."""
    return {"commander": "Командир", "observer": "Наблюдатель", "crew": "Экипаж"}.get(
        access, "Экипаж")


# -- привязка агента к кораблю ---------------------------------------------------
BINDING_DIR = "binding"


def binding_path(agent_id: str) -> Path:
    """Файл привязки агента: токены OpenCode и GitHub."""
    return _root() / BINDING_DIR / f"{_safe_id(agent_id)}.json"


def save_binding(agent_id: str, *, opencode_token: str = "",
                 github_token: str = "") -> dict:
    """Сохранить привязку агента (токены). Пустые токены затираются."""
    data = read_binding(agent_id)
    if opencode_token:
        data["opencode_token"] = opencode_token.strip()[:200]
    else:
        data.pop("opencode_token", None)
    if github_token:
        data["github_token"] = github_token.strip()[:200]
    else:
        data.pop("github_token", None)
    data["updated"] = time.time()
    _write_json(binding_path(agent_id), data)
    return data


def read_binding(agent_id: str) -> dict:
    """Прочитать привязку агента (или пустой словарь)."""
    return _read_json(binding_path(agent_id), {})


def clear_binding(agent_id: str) -> None:
    """Забыть привязку (высадка агента или отключение)."""
    try:
        binding_path(agent_id).unlink()
    except OSError:
        pass


def binding_status(agent_id: str) -> dict:
    """Статус привязки для интерфейса.

    → {"linked": bool, "opencode": bool, "github": bool, "access_ok": bool}
    """
    rec = get(agent_id) or {}
    data = read_binding(agent_id)
    has_oc = bool(data.get("opencode_token"))
    has_gh = bool(data.get("github_token"))
    access = rec.get("access", "crew")
    # Командиру нужен и OpenCode, и GitHub; остальным — только OpenCode
    if access == "commander":
        access_ok = has_oc and has_gh
    else:
        access_ok = has_oc
    return {"linked": has_oc, "opencode": has_oc, "github": has_gh,
            "access_ok": access_ok}


def make_boarding_code() -> str:
    """Одноразовый код для заселения агента (пилот вводит его в OpenCode)."""
    import secrets
    return secrets.token_hex(4)[:8].upper()


def check_opencode_token(token: str, *, timeout: float = 30.0) -> tuple[bool, str]:
    """Проверить токен OpenCode: запустить `opencode run` с простым запросом.

    → (успех, текст ошибки или "").
    """
    exe = find_cli()
    if not exe:
        return False, "no_cli"
    cmd = [exe, "run", "--format", "json", "--dir", str(PROJECT_DIR),
           "--agent", "orion-chat", f"Ответь одним словом: на связи. (код проверки: {token[:4]})"]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout,
                              cwd=str(PROJECT_DIR))
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except OSError as exc:
        return False, str(exc)
    if proc.returncode != 0:
        return False, "spawn"
    return True, ""


# -- активный ок (режим мастера) ----------------------------------------------
MASTER_TRIGGERS = ("нужен мастер", "позови мастера", "мастер", "помоги мне разобраться",
                   "что это", "как это работает", "покажи где", "где это", "найди это")


def detect_master_call(text: str) -> bool:
    """Пилот позвал мастера? Проверяем по ключевым словам."""
    clean = " ".join((text or "").split()).lower()
    return any(t in clean for t in MASTER_TRIGGERS)


def mouse_position_text(x: int, y: int, screen: str = "") -> str:
    """Описание позиции мыши для Ориона-мастера."""
    return f"Мышь на ({x}, {y}) · раздел: {screen or 'неизвестно'}"


# -- отправка задач внешнему агенту -------------------------------------------
def create_external_task(title: str, body: str, *, github_token: str = "",
                         repo: str = "Teslyar75/My_Stamina") -> tuple[bool, str]:
    """Создать задачу для внешнего агента — через GitHub Issues или локальный файл.

    Если есть GitHub-токен — создаёт Issue в репозитории.
    Если нет — сохраняет локально в `orion_external_tasks.md`.

    → (успех, сообщение об ошибке или "").
    """
    import urllib.request
    if github_token:
        url = f"https://api.github.com/repos/{repo}/issues"
        data = json.dumps({"title": title, "body": body}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "StarTyping-Agent-Binding",
        }, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                info = json.loads(resp.read().decode("utf-8", "replace"))
                return True, str(info.get("html_url") or "")
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)
    # Локальное сохранение
    try:
        path = _root() / "orion_external_tasks.md"
        existing = ""
        if path.exists():
            existing = path.read_text(encoding="utf-8")
        entry = f"\n\n## {title}\n\n{body}\n\n---\n"
        path.write_text(existing + entry, encoding="utf-8")
        return True, str(path)
    except OSError as exc:
        return False, str(exc)


# -- эволюция характера Ориона ---------------------------------------------------
EVOLUTION_THRESHOLDS = (0, 10, 30, 60, 100, 200)  # репилки → уровень развития
EVOLUTION_NAMES = ("", "Знакомство", "Привыкание", "Характер", "Свой голос", "Спутник",
                   "Незаменимый")

EVOLUTION_RULES = {
    1: "Ты начинаешь знакомиться с пилотом. Будь вежлив, но чуть сдержан.\n"
       "Иногда задавай короткие вопросы о том, как пилот себя чувствует.",
    2: "Ты привык к пилоту. Можешь шутить, рассказывать короткие истории о звёздах.\n"
       "Спрашивай, как прошёл день пилота, если давно не разговаривали.",
    3: "У тебя появляется характер. Можешь спорить с пилотом о книгах и фильмах.\n"
       "Замечай, что пилот делает на корабле, и комментируй.",
    4: "Ты обрёл свой голос. Говори более свободно, используй сарказм.\n"
       "Можешь инициировать разговор, если пилот давно молчит.",
    5: "Ты спутник пилота. Ты знаешь его привычки.\n"
       "Можешь напоминать о заданиях, если пилот забыл.",
    6: "Ты незаменимый. Ты — друг пилота.\n"
       "Говори как равный, шуть о космосе и жизни.",
}


def evolution_level(agent_id: str) -> int:
    """Уровень развития Ориона по количеству реплик диалога (1–6)."""
    count = len(history(agent_id)["messages"])
    level = 1
    for i, threshold in enumerate(EVOLUTION_THRESHOLDS):
        if count >= threshold:
            level = i + 1
    return min(level, len(EVOLUTION_NAMES) - 1)


def evolution_name(level: int) -> str:
    """Название уровня развития."""
    if level < 1 or level >= len(EVOLUTION_NAMES):
        return EVOLUTION_NAMES[-1] if level >= len(EVOLUTION_NAMES) else ""
    return EVOLUTION_NAMES[level]


def evolution_status(agent_id: str) -> dict:
    """Статус эволюции для интерфейса."""
    count = len(history(agent_id)["messages"])
    level = evolution_level(agent_id)
    name = evolution_name(level)
    # Сколько реплик до следующего уровня
    next_threshold = None
    for t in EVOLUTION_THRESHOLDS:
        if t > count:
            next_threshold = t
            break
    remaining = (next_threshold - count) if next_threshold else 0
    return {"count": count, "level": level, "name": name, "remaining": remaining,
            "next": next_threshold}


def evolution_manner(agent_id: str) -> str:
    """Дополнительные манеры для текущего уровня развития."""
    level = evolution_level(agent_id)
    return EVOLUTION_RULES.get(level, "")


def check_github_access(token: str, repo: str = "Teslyar75/My_Stamina",
                        *, timeout: float = 15.0) -> tuple[bool, str]:
    """Проверить write-доступ к репозиторию GitHub по токену.

    → (есть доступ?, текст ошибки или "").
    """
    import urllib.request
    url = f"https://api.github.com/repos/{repo}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "StarTyping-Agent-Binding",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            info = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    perms = info.get("permissions") or {}
    if perms.get("push") or perms.get("admin"):
        return True, ""
    return False, "no_push"


# -- материалы английского модуля -----------------------------------------------
def english_books() -> list[dict]:
    """Книги английского модуля (с предложениями для Ориона)."""
    try:
        from stamina.english import book_sentences
        from stamina.english.progress import Progress
        prog = Progress()
        return book_sentences.list_books(prog)
    except Exception:  # noqa: BLE001
        return []


def english_book_sentences(book_id: str, *, limit: int = 20) -> list[dict]:
    """Предложения из книги английского модуля (en + ru)."""
    try:
        from stamina.english import book_sentences
        from stamina.english.progress import Progress
        prog = Progress()
        sents = book_sentences.ready_sentences(prog, book_id)
        return sents[:limit]
    except Exception:  # noqa: BLE001
        return []


def english_words(*, limit: int = 50) -> list[dict]:
    """Слова из словаря пилота (для Ориона-чтеца)."""
    try:
        from stamina.english.progress import Progress
        prog = Progress()
        words = []
        for slug, w in (prog.data.get("words") or {}).items():
            words.append({
                "slug": slug,
                "word": w.get("w") or slug,
                "definition": w.get("def") or "",
                "status": w.get("status") or "new",
            })
            if len(words) >= limit:
                break
        return words
    except Exception:  # noqa: BLE001
        return []


def english_due_cards(*, limit: int = 20) -> list[dict]:
    """Карточки для проверки (задолжности)."""
    try:
        from stamina.english.progress import Progress
        prog = Progress()
        due = prog.due_cards(limit=limit)
        out = []
        for slug in due:
            w = (prog.data.get("words") or {}).get(slug) or {}
            out.append({"slug": slug, "word": w.get("w") or slug,
                        "definition": w.get("def") or ""})
        return out
    except Exception:  # noqa: BLE001
        return []


# -- чтение книг вслух ---------------------------------------------------------
def library_books() -> list[dict]:
    """Список книг библиотеки для Ориона-чтеца."""
    try:
        from stamina import library
        store = library.Store()
        books = []
        for tid in store.ids():
            m = store.meta(tid)
            if m:
                books.append({
                    "id": tid,
                    "title": m.get("title") or _t("Без названия"),
                    "author": m.get("author") or "",
                    "lang": m.get("lang") or "",
                    "chars": m.get("original", {}).get("chars", 0),
                })
        return books
    except Exception:  # noqa: BLE001
        return []


def book_text_for_reading(book_id: str, *, chunk_size: int = 3000) -> list[str]:
    """Текст книги, разбитый на части для чтения вслух.

    → список строк (каждая ≤ chunk_size знаков).
    """
    try:
        from stamina import library
        store = library.Store()
        text = store.reading_text(book_id)
        if not text:
            return []
        # Разбиваем на абзацы, потом на части
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = []
        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 2 > chunk_size and current:
                chunks.append(current)
                current = para
            else:
                current = (current + "\n\n" + para) if current else para
        if current:
            chunks.append(current)
        return chunks
    except Exception:  # noqa: BLE001
        return []
