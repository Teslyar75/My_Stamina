"""Бортовой гид без ИИ: заранее записанные шутки, факты и голосовая справка окон.

Всё работает без сети: фразы озвучены заранее (tools/guide_voice/build.py, голоса
Windows) и лежат в stamina/sounds/guide/<lang>/<voice>/*.mp3 с manifest.json.

Как гид вмешивается (раз в 10–20 мин по умолчанию, «Настройки → Ещё → Бортовой гид»):
приглушает радио → «Капитан, …» (случайный заход) → «Послушаете? Enter — да, Esc — нет».
Enter — шутка или факт, Esc — гид извиняется и замолкает. Три отказа подряд — гид
заходит вдвое реже, пока его снова не выслушают. Заходы и сами шутки/факты берутся
из «мешков»: каждый элемент звучит один раз, пока не прозвучат все, и не повторяется
два раза подряд даже на стыке мешков.

ONLINE ambient (тумблер «В ONLINE-чате», по умолчанию вкл.): редко, с паузой ~15 мин,
когда агент свободен (нет запроса, пилот не печатает миссию, никто не ждёт ответа),
гид кладёт шутку/факт в историю чата Ориона отдельным ``remember(..., kind=joke|fact)``
— без смешивания с ответом ИИ; переживает перезапуск.

Shift+F1 — гид читает вслух справку F1 текущего окна (запись; если записи нет —
живой офлайн-синтез tts.speak). Обычный F1 не изменился.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
CONTENT_DIR = HERE / "guide_content"
SOUND_ROOT = HERE / "sounds" / "guide"

# Голоса гида: офлайн-голоса Windows OneCore. Ключ — значение настройки guide_voice.
VOICES: dict[str, dict] = {
    "male": {"voice": "Microsoft Pavel", "rate": 1.0, "pitch": ""},
    "female": {"voice": "Microsoft Irina", "rate": 1.0, "pitch": ""},
}
INTERVALS = {"5-10": (5, 10), "10-20": (10, 20), "20-40": (20, 40)}
DEFAULT_INTERVAL = "10-20"
DECLINE_STREAK_SLOWDOWN = 3
PROMPT_TIMEOUT_MS = 30_000
TYPING_QUIET_S = 6.0
# ONLINE ambient (зеркало web guideIdle): реже офлайн-гида, только в чат агента.
ONLINE_COOLDOWN_S = 15 * 60
ONLINE_CHECK_MS = 60_000
AMBIENT_KINDS = frozenset({"joke", "fact"})


# -- данные ------------------------------------------------------------------
def list_langs() -> list[str]:
    """Языки, для которых лежит guide_content/<lang>.json."""
    if not CONTENT_DIR.is_dir():
        return []
    return sorted(p.stem for p in CONTENT_DIR.glob("*.json") if p.is_file())


def load_content(lang: str = "ru") -> dict:
    path = CONTENT_DIR / f"{lang}.json"
    if not path.exists():
        path = CONTENT_DIR / "ru.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest(lang: str = "ru") -> dict:
    path = SOUND_ROOT / lang / "manifest.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


# Озвучка справки: у подраздела может не быть отдельного клипа, тогда
# проигрываем клип родительского раздела (текст F1 при этом свой).
_HELP_CLIP_ALIASES = {"english.verbs": "english.sets"}


def help_clip_id(page_key: str) -> str:
    return "help." + _HELP_CLIP_ALIASES.get(page_key, page_key)


_SPOKEN = [
    (r"Ctrl", "Контрол"), (r"Shift", "Шифт"), (r"\bAlt\b", "Альт"), (r"\bEsc\b", "Эскейп"),
    (r"\bDel\b", "Делит"), (r"PgUp", "Пейдж ап"), (r"PgDn", "Пейдж даун"), (r"\bTab\b", "Таб"),
    (r"\bEnter\b", "Энтер"), (r"\bHome\b", "Хоум"), (r"…", " до "), (r"←", "стрелка влево"),
    (r"→", "стрелка вправо"), (r"↑", "стрелка вверх"), (r"↓", "стрелка вниз"),
]


def spoken_help(title: str, text: str) -> str:
    """Текст справки F1 в виде, удобном для чтения вслух (без маркеров и значков)."""
    body = text.replace("•", "").replace("·", ",").replace("—", ",")
    for pat, rep in _SPOKEN:
        body = re.sub(pat, rep, body)
    body = re.sub(r"\+", " плюс ", body)
    lines = [ln.strip(" \t-") for ln in body.splitlines()]
    out = ". ".join(ln.rstrip(".") for ln in lines if ln)
    return re.sub(r"\s+", " ", f"{title.strip().rstrip('.')}. {out}.").replace(" ,", ",")


def clip_path(manifest: dict, clip_id: str, voice: str, lang: str = "ru") -> Path | None:
    """Путь к записи фразы для голоса (или к записи другого голоса, если этой нет)."""
    clip = (manifest.get("clips") or {}).get(clip_id)
    if not clip:
        return None
    files = clip.get("files") or {}
    for v in [voice] + [k for k in files if k != voice]:
        rel = files.get(v)
        if rel:
            p = SOUND_ROOT / lang / rel
            if p.exists():
                return p
    return None


def help_lookup(page_key: str, manifest: dict) -> str | None:
    """id записи справки: точный подраздел, иначе раздел целиком; None — записи нет."""
    clips = manifest.get("clips") or {}
    for k in (page_key, page_key.split(".", 1)[0]):
        if help_clip_id(k) in clips:
            return help_clip_id(k)
    return None


def interval_ms(setting: str, decline_streak: int = 0, rng: random.Random | None = None) -> int | None:
    """Пауза до следующего захода гида; None — гид выключен."""
    lo_hi = INTERVALS.get(str(setting or ""))
    if lo_hi is None:
        return None
    r = rng or random
    sec = r.uniform(lo_hi[0] * 60, lo_hi[1] * 60)
    if decline_streak >= DECLINE_STREAK_SLOWDOWN:
        sec *= 2
    return int(sec * 1000)


# -- мешок без повторов -----------------------------------------------------
class ShuffleBag:
    """Перемешанная очередь: каждый id звучит один раз за круг, без повтора на стыке.

    `state` — словарь, который сохраняется между запусками ({"queue": [...], "last": id}).
    """

    def __init__(self, ids: list[str], state: dict, rng: random.Random | None = None) -> None:
        self.ids = list(dict.fromkeys(ids))
        self.state = state
        self.rng = rng or random.Random()
        q = [i for i in state.get("queue", []) if i in self.ids]
        state["queue"] = q

    def _refill(self) -> None:
        q = list(self.ids)
        self.rng.shuffle(q)
        last = self.state.get("last")
        if len(q) > 1 and q[0] == last:
            q[0], q[-1] = q[-1], q[0]
        self.state["queue"] = q

    def next(self) -> str | None:
        if not self.ids:
            return None
        if not self.state["queue"]:
            self._refill()
        cid = self.state["queue"].pop(0)
        self.state["last"] = cid
        return cid


class GuideState:
    """Сохраняемое состояние: мешки и счётчики «выслушал / отказался»."""

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.data: dict = {
            "bags": {}, "listened": 0, "declined": 0, "decline_streak": 0,
            "last_online_at": 0.0,
        }
        if path is not None:
            try:
                self.data.update(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass

    def bag(self, name: str, ids: list[str], rng: random.Random | None = None) -> ShuffleBag:
        return ShuffleBag(ids, self.data["bags"].setdefault(name, {}), rng)

    def answered(self, listened: bool) -> None:
        if listened:
            self.data["listened"] += 1
            self.data["decline_streak"] = 0
        else:
            self.data["declined"] += 1
            self.data["decline_streak"] += 1
        self.save()

    def save(self) -> None:
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass


def pick(content: dict, state: GuideState, rng: random.Random | None = None) -> tuple[str, str, str]:
    """Выбрать (вид, заход, шутка/факт). Вид — шутка или факт поровну."""
    r = rng or random
    kind = "joke" if r.random() < 0.5 else "fact"
    items = content["jokes"] if kind == "joke" else content["facts"]
    intros = content["intros"].get(kind, []) + content["intros"].get("any", [])
    intro = state.bag("intro_" + kind, [x["id"] for x in intros], rng).next()
    item = state.bag(kind, [x["id"] for x in items], rng).next()
    state.save()
    return kind, intro or "", item or ""


def texts(content: dict) -> dict[str, str]:
    out = {}
    for lst in list(content["intros"].values()) + [content["system"], content["jokes"], content["facts"]]:
        out.update({x["id"]: x["text"] for x in lst})
    return out


def can_online_ambient(
    *,
    guide_enabled: bool,
    online_enabled: bool,
    busy: bool,
    has_draft: bool,
    waiting: bool,
    listening: bool = False,
    pending_answer: bool = False,
    phase_idle: bool = True,
    now: float,
    last_key_at: float,
    last_online_at: float,
    cooldown_s: float = ONLINE_COOLDOWN_S,
    typing_quiet_s: float = TYPING_QUIET_S,
) -> bool:
    """Можно ли вставить шутку/факт в ONLINE-чат: агент свободен, кулдаун, тумблер вкл.

    Зеркало web ``canOnlineAmbient``: не мешать запросу, набору миссии и ожиданию ответа.
    """
    if not guide_enabled or not online_enabled:
        return False
    if not phase_idle:
        return False
    if busy or has_draft or waiting or listening or pending_answer:
        return False
    if now - last_key_at < typing_quiet_s:
        return False
    if last_online_at and now - last_online_at < cooldown_s:
        return False
    return True


# -- проигрывание -----------------------------------------------------------
class ClipPlayer:
    """MP3 без сети: на Windows — MCI (winmm, есть в любой Windows), иначе ffplay/mpv."""

    ALIAS = "stamina_guide"

    def __init__(self, widget) -> None:
        self.widget = widget
        self._proc: subprocess.Popen | None = None
        self._open = False
        self._job = None
        self._token = 0

    def _mci(self, cmd: str) -> str:
        import ctypes
        buf = ctypes.create_unicode_buffer(128)
        ctypes.windll.winmm.mciSendStringW(cmd, buf, 127, 0)
        return buf.value

    def play(self, path: Path, on_done: Callable[[], None] | None = None) -> bool:
        self.stop()
        self._token += 1
        tok = self._token
        started = False
        if sys.platform == "win32":
            try:
                self._mci(f'open "{path}" type mpegvideo alias {self.ALIAS}')
                self._mci(f"play {self.ALIAS}")
                self._open = True
                started = True
            except Exception:  # noqa: BLE001
                started = False
        else:
            exe = shutil.which("ffplay") or shutil.which("mpv")
            if exe:
                args = [exe, "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)] if "ffplay" in exe \
                    else [exe, "--no-video", "--really-quiet", str(path)]
                try:
                    self._proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    started = True
                except OSError:
                    started = False
        if not started:
            if on_done:
                self.widget.after(10, on_done)
            return False
        self._poll(tok, on_done, time.monotonic())
        return True

    def _busy(self) -> bool:
        if self._open:
            try:
                return self._mci(f"status {self.ALIAS} mode") == "playing"
            except Exception:  # noqa: BLE001
                return False
        return self._proc is not None and self._proc.poll() is None

    def _poll(self, tok: int, on_done, t0: float) -> None:
        if tok != self._token:
            return
        if self._busy() or time.monotonic() - t0 < 0.3:
            self._job = self.widget.after(150, lambda: self._poll(tok, on_done, t0))
            return
        self.stop()
        if on_done:
            on_done()

    def stop(self) -> None:
        self._token += 1
        if self._job is not None:
            try:
                self.widget.after_cancel(self._job)
            except Exception:  # noqa: BLE001
                pass
            self._job = None
        if self._open:
            try:
                self._mci(f"close {self.ALIAS}")
            except Exception:  # noqa: BLE001
                pass
            self._open = False
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
        self._proc = None


# -- контроллер ---------------------------------------------------------------
class GuideController:
    """Таймер гида, подсказка «Enter/Esc», голосовая справка окна (Shift+F1)."""

    def __init__(self, app, lang: str = "ru", state_path: Path | None = None, autostart: bool = True) -> None:
        self.app = app
        self.lang = lang
        self.content = load_content(lang)
        self.texts = texts(self.content)
        self.manifest = load_manifest(lang)
        if state_path is None:
            try:
                from stamina.storage import DATA_DIR
                state_path = Path(DATA_DIR) / "guide_state.json"
            except Exception:  # noqa: BLE001
                state_path = None
        self.state = GuideState(state_path)
        self.player = ClipPlayer(app)
        self.phase = "idle"          # idle | intro | prompt | item | decline | help | online
        self.current: tuple[str, str, str] | None = None
        self._timer = None
        self._online_timer = None
        self._prompt_job = None
        self._toast = None
        self._prev_focus = None
        self._ducked = False
        self._last_key = 0.0
        try:
            app.bind_all("<Key>", self._note_key, add="+")
        except Exception:  # noqa: BLE001
            pass
        if autostart:
            self.schedule()
            self.schedule_online()

    # настройки
    def _settings(self) -> dict:
        try:
            return self.app.store.settings
        except AttributeError:
            return {}

    def enabled(self) -> bool:
        return bool(self._settings().get("guide_enabled", True))

    def online_enabled(self) -> bool:
        """Тумблер «В ONLINE-чате»: шутки/факты в историю, когда агент свободен."""
        return bool(self._settings().get("guide_online_jokes", True))

    def voice(self) -> str:
        v = self._settings().get("guide_voice", "male")
        return v if v in VOICES else "male"

    def _note_key(self, _e=None) -> None:
        self._last_key = time.monotonic()

    def schedule(self, delay_ms: int | None = None) -> None:
        if self._timer is not None:
            try:
                self.app.after_cancel(self._timer)
            except Exception:  # noqa: BLE001
                pass
            self._timer = None
        if delay_ms is None:
            if not self.enabled():
                return
            delay_ms = interval_ms(self._settings().get("guide_interval", DEFAULT_INTERVAL),
                                   self.state.data.get("decline_streak", 0))
            if delay_ms is None:
                return
        self._timer = self.app.after(delay_ms, self.fire)

    def schedule_online(self, delay_ms: int | None = None) -> None:
        """Редкий опрос ONLINE ambient (как web ONLINE_CHECK_MS)."""
        if self._online_timer is not None:
            try:
                self.app.after_cancel(self._online_timer)
            except Exception:  # noqa: BLE001
                pass
            self._online_timer = None
        if not self.enabled() or not self.online_enabled():
            return
        self._online_timer = self.app.after(
            ONLINE_CHECK_MS if delay_ms is None else delay_ms, self._online_tick)

    def _online_tick(self) -> None:
        self._online_timer = None
        try:
            self.maybe_online_ambient()
        finally:
            self.schedule_online()

    def fire(self, force: bool = False) -> None:
        self._timer = None
        if not force:
            if not self.enabled():
                return
            if self.phase != "idle":
                self.schedule(60_000)
                return
            if time.monotonic() - self._last_key < TYPING_QUIET_S:
                self.schedule(20_000)          # пилот печатает — подождём паузы
                return
        elif self.phase != "idle":
            return
        self.current = pick(self.content, self.state)
        _kind, intro, _item = self.current
        self._duck()
        self.phase = "intro"
        self._show_toast(self.texts.get(intro, ""), prompt=True)
        self._say(intro, lambda: self._say("sys_prompt", self._await_answer))

    def agent_free_ctx(self) -> dict:
        """Снимок занятости ONLINE-чата Ориона (для idle-gate)."""
        ctx = {
            "busy": False,
            "has_draft": False,
            "waiting": False,
            "listening": False,
            "pending_answer": False,
            "online_mode": True,
        }
        try:
            from stamina import orion, ship_chat
            scr = None
            screens = getattr(self.app, "screens", None) or {}
            if isinstance(screens, dict):
                scr = screens.get("orion")
            if scr is None:
                scr = getattr(self.app, "orion_screen", None)
            if scr is not None:
                ctx["busy"] = bool(getattr(scr, "_busy", False))
                draft = ""
                try:
                    entry = getattr(scr, "entry", None)
                    if entry is not None and hasattr(entry, "get"):
                        draft = " ".join(str(entry.get() or "").split())
                except Exception:  # noqa: BLE001
                    draft = str(getattr(scr, "_draft_text", "") or "").strip()
                if not draft:
                    draft = str(getattr(scr, "_draft_text", "") or "").strip()
                ctx["has_draft"] = bool(draft)
                ctx["listening"] = bool(getattr(scr, "_listening", False) or
                                        getattr(scr, "_voice_listening", False))
                ctx["pending_answer"] = bool(
                    getattr(scr, "_await_task", False)
                    or getattr(scr, "_pending", None) is not None
                    or getattr(scr, "_pending_task", "")
                )
            try:
                aid = str((orion.active() or {}).get("id") or "")
                ctx["waiting"] = bool(ship_chat.waiting(aid) if aid else ship_chat.waiting())
            except Exception:  # noqa: BLE001
                ctx["waiting"] = False
            # ONLINE = есть активный агент (на desktop Орион всегда на борту).
            ctx["online_mode"] = bool(orion.active())
        except Exception:  # noqa: BLE001
            pass
        return ctx

    def maybe_online_ambient(self, *, force: bool = False, now: float | None = None) -> bool:
        """Редко вставить шутку/факт в чат Ориона, только если агент свободен.

        Не смешивается с ответом агента: отдельное ``remember(..., kind=joke|fact)``.
        """
        if self.phase != "idle" and not force:
            return False
        ctx = self.agent_free_ctx()
        wall = time.time() if now is None else now
        last_online = float(self.state.data.get("last_online_at") or 0.0)
        if not force:
            if not ctx.get("online_mode", True):
                return False
            if not can_online_ambient(
                guide_enabled=self.enabled(),
                online_enabled=self.online_enabled(),
                busy=bool(ctx["busy"]),
                has_draft=bool(ctx["has_draft"]),
                waiting=bool(ctx["waiting"]),
                listening=bool(ctx["listening"]),
                pending_answer=bool(ctx["pending_answer"]),
                phase_idle=self.phase == "idle",
                now=wall,
                last_key_at=wall - max(0.0, time.monotonic() - self._last_key),
                last_online_at=last_online,
            ):
                return False
        return self._inject_online_ambient(wall_now=wall)

    def _inject_online_ambient(self, *, wall_now: float | None = None) -> bool:
        """pick → remember(kind) → toast+аудио; повторная проверка занятости перед записью."""
        ctx = self.agent_free_ctx()
        if ctx["busy"] or ctx["waiting"] or ctx["has_draft"] or ctx["pending_answer"]:
            return False
        if self.phase != "idle":
            return False
        self.current = pick(self.content, self.state)
        kind, _intro, item = self.current
        if kind not in AMBIENT_KINDS or not item:
            return False
        text = self.texts.get(item, "")
        if not text:
            return False
        # Ещё раз: за время pick агент мог заняться.
        ctx = self.agent_free_ctx()
        if ctx["busy"] or ctx["waiting"] or ctx["has_draft"] or ctx["pending_answer"]:
            return False
        saved = self._remember_ambient(kind=kind, text=text, clip_id=item)
        if not saved:
            return False
        self.state.data["last_online_at"] = float(wall_now if wall_now is not None else time.time())
        self.state.save()
        self.phase = "online"
        self._duck()
        self._show_toast(text, prompt=False)
        self._say(item, self.finish)
        return True

    def _remember_ambient(self, *, kind: str, text: str, clip_id: str) -> dict | None:
        """Сохранить ambient в историю чата (формат web POST /api/orion/remember)."""
        try:
            from stamina import orion
            rec = orion.active() or {}
            agent_id = str(rec.get("id") or "")
            if not agent_id:
                return None
            msg = orion.remember(agent_id, "orion", text, kind=kind, clip_id=clip_id)
            # Обновить ленту, если экран Ориона уже открыт.
            screens = getattr(self.app, "screens", None) or {}
            scr = screens.get("orion") if isinstance(screens, dict) else None
            if scr is not None and hasattr(scr, "_render_feed"):
                try:
                    scr._render_feed()
                except Exception:  # noqa: BLE001
                    try:
                        scr.refresh()
                    except Exception:  # noqa: BLE001
                        pass
            return msg
        except Exception:  # noqa: BLE001
            return None

    def _await_answer(self) -> None:
        if self.phase != "intro":
            return
        self.phase = "prompt"
        self._prompt_job = self.app.after(PROMPT_TIMEOUT_MS, self._timeout)

    def handle_key(self, keysym: str) -> str | None:
        """Enter — слушать, Esc — отказаться (пока висит подсказка); во время рассказа Esc — прервать."""
        if self.phase in ("intro", "prompt"):
            if keysym in ("Return", "KP_Enter"):
                self.accept()
                return "break"
            if keysym == "Escape":
                self.decline()
                return "break"
        elif self.phase in ("item", "help", "online") and keysym == "Escape":
            self.finish()
            return "break"
        return None

    def accept(self) -> None:
        if self.phase not in ("intro", "prompt") or not self.current:
            return
        self._cancel_prompt()
        self.state.answered(True)
        self.phase = "item"
        item = self.current[2]
        self._show_toast(self.texts.get(item, ""), prompt=False)
        self._say(item, self.finish)

    def decline(self) -> None:
        if self.phase not in ("intro", "prompt"):
            return
        self._cancel_prompt()
        self.state.answered(False)
        self.phase = "decline"
        self._show_toast(self.texts.get("sys_decline", ""), prompt=False)
        self._say("sys_decline", self.finish)

    def _timeout(self) -> None:
        self._prompt_job = None
        if self.phase == "prompt":
            self.finish()

    def finish(self) -> None:
        self._cancel_prompt()
        self.player.stop()
        self.phase = "idle"
        self._hide_toast()
        self._unduck()
        self.schedule()

    def _cancel_prompt(self) -> None:
        if self._prompt_job is not None:
            try:
                self.app.after_cancel(self._prompt_job)
            except Exception:  # noqa: BLE001
                pass
            self._prompt_job = None

    # речь
    def _say(self, clip_id: str, on_done: Callable[[], None]) -> None:
        path = clip_path(self.manifest, clip_id, self.voice(), self.lang)
        if path is not None and self.player.play(path, on_done):
            return
        self._live(self.texts.get(clip_id, ""), on_done)

    def _live(self, text: str, on_done: Callable[[], None]) -> None:
        """Запасной путь: живой офлайн-синтез Windows, если записи нет."""
        try:
            from stamina.voice import tts
            if text and tts.available():
                tts.speak(text, role="guide")
        except Exception:  # noqa: BLE001
            pass
        self.app.after(max(1500, int(len(text) * 70)), on_done)

    def speak_help(self, page_key: str | None = None) -> str:
        """Shift+F1: прочитать вслух справку F1 текущего окна. Возвращает ключ страницы."""
        from stamina import page_help
        if page_key is None:
            page_key = page_help.resolve_key(self.app)
        if self.phase not in ("idle", "help"):
            return page_key
        self.player.stop()
        self.phase = "help"
        self._duck()
        cid = help_lookup(page_key, self.manifest)
        path = clip_path(self.manifest, cid, self.voice(), self.lang) if cid else None
        if path is None or not self.player.play(path, self._help_done):
            title, text = page_help.content_for(page_key)
            self._live(spoken_help(title, text), self._help_done)
        return page_key

    def _help_done(self) -> None:
        if self.phase == "help":
            self.phase = "idle"
            self._unduck()

    # радио
    def _duck(self) -> None:
        try:
            from stamina.radio.engine import get_engine
            eng = get_engine()
            if getattr(eng, "playing", False):
                eng.duck(15)
                self._ducked = True
        except Exception:  # noqa: BLE001
            pass

    def _unduck(self) -> None:
        if not self._ducked:
            return
        self._ducked = False
        try:
            from stamina.radio.engine import get_engine
            get_engine().unduck()
        except Exception:  # noqa: BLE001
            pass

    # подсказка на экране (мягко: полоска внизу окна)
    def _show_toast(self, text: str, prompt: bool) -> None:
        try:
            import tkinter as tk
            from stamina import theme
            from stamina.i18n import t as _t
        except Exception:  # noqa: BLE001
            return
        try:
            if self._toast is None:
                self._prev_focus = self.app.focus_get()
                f = tk.Frame(self.app, bg=theme.PANEL, highlightthickness=1,
                             highlightbackground=theme.AMBER, takefocus=1)
                self._lbl = tk.Label(f, bg=theme.PANEL, fg=theme.TEXT, font=theme.font(10),
                                     wraplength=720, justify="left")
                self._lbl.pack(side=tk.TOP, anchor="w", padx=10, pady=(6, 2))
                bar = tk.Frame(f, bg=theme.PANEL)
                bar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 6))
                self._hint = tk.Label(bar, bg=theme.PANEL, fg=theme.AMBER, font=theme.font(9, True))
                self._hint.pack(side=tk.LEFT)
                # Явные кнопки: щелчок по самому тексту ничего не делает (раньше он
                # случайно запускал рассказ).
                self._btn_no = tk.Label(bar, bg=theme.PANEL, fg=theme.TEXT, font=theme.font(9, True),
                                        cursor="hand2", padx=8)
                self._btn_no.pack(side=tk.RIGHT)
                self._btn_yes = tk.Label(bar, text=_t("▶ СЛУШАТЬ"), bg=theme.PANEL, fg=theme.AMBER,
                                         font=theme.font(9, True), cursor="hand2", padx=8)
                self._btn_yes.pack(side=tk.RIGHT)
                self._btn_yes.bind("<Button-1>", lambda _e: self.handle_key("Return"))
                self._btn_no.bind("<Button-1>", lambda _e: self.handle_key("Escape"))
                for seq, ks in (("<Return>", "Return"), ("<KP_Enter>", "KP_Enter"), ("<Escape>", "Escape")):
                    f.bind(seq, lambda _e, k=ks: self.handle_key(k))
                self._toast = f
            self._lbl.configure(text="🛰  " + text)
            self._hint.configure(text=_t("Enter — слушать  ·  Esc — отказаться") if prompt
                                 else _t("Esc — прервать"))
            self._btn_no.configure(text=_t("✕ НЕТ") if prompt else _t("✕ ПРЕРВАТЬ"))
            if prompt:
                self._btn_yes.pack(side=tk.RIGHT, after=self._btn_no)
            else:
                self._btn_yes.pack_forget()
            self._toast.place(relx=0.5, rely=1.0, y=-40, anchor="s")
            self._toast.lift()
            self._toast.focus_set()
        except Exception:  # noqa: BLE001
            self._toast = None

    def _hide_toast(self) -> None:
        if self._toast is not None:
            try:
                self._toast.destroy()
            except Exception:  # noqa: BLE001
                pass
            self._toast = None
            try:
                if self._prev_focus is not None and self._prev_focus.winfo_exists():
                    self._prev_focus.focus_set()
                else:
                    self.app.focus_set()  # иначе клавиши (Shift+F1, F1) уходят в никуда
            except Exception:  # noqa: BLE001
                pass
            self._prev_focus = None
