"""Бортовой гид без ИИ: заранее записанные шутки, факты и голосовая справка окон.

Всё работает без сети: фразы озвучены заранее (tools/guide_voice/build.py, голоса
Windows) и лежат в stamina/sounds/guide/<lang>/<voice>/*.mp3 с manifest.json.

Как гид вмешивается (раз в 10–20 мин по умолчанию, «Настройки → Ещё → Бортовой гид»):
приглушает радио → «Капитан, …» (случайный заход) → «Послушаете? Enter — да, Esc — нет».
Enter — шутка или факт, Esc — гид извиняется и замолкает. Три отказа подряд — гид
заходит вдвое реже, пока его снова не выслушают. Заходы и сами шутки/факты берутся
из «мешков»: каждый элемент звучит один раз, пока не прозвучат все, и не повторяется
два раза подряд даже на стыке мешков.

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


# -- данные ------------------------------------------------------------------
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


def help_clip_id(page_key: str) -> str:
    return "help." + page_key


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
        self.data: dict = {"bags": {}, "listened": 0, "declined": 0, "decline_streak": 0}
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
                    self._proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
        self.phase = "idle"          # idle | intro | prompt | item | decline | help
        self.current: tuple[str, str, str] | None = None
        self._timer = None
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

    # настройки
    def _settings(self) -> dict:
        try:
            return self.app.store.settings
        except AttributeError:
            return {}

    def enabled(self) -> bool:
        return bool(self._settings().get("guide_enabled", True))

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
        elif self.phase in ("item", "help") and keysym == "Escape":
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
