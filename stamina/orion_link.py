"""Индикатор связи с бортовым ИИ-агентом (Орион / пассажиры).

Лёгкая проверка без генерации: OpenCode CLI на месте, для OpenAI-совместимых —
GET /models. Результат кэшируется; опрос с UI-потока не блокирует Tk.
Состояния для пилота: Нет связи / Подключение / На связи / Ошибка.
"""

from __future__ import annotations

import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

from stamina.i18n import t as _t

POLL_SEC = 30.0
CACHE_TTL = 25.0

_cache: dict[str, tuple[float, "Health"]] = {}
_cache_lock = threading.Lock()


@dataclass(frozen=True)
class Health:
    available: bool
    reason: str
    state: str = "off"          # off | busy | ok | down
    kind: str = ""
    agent_id: str = ""
    model: str = ""
    name: str = ""
    cached: bool = False


@dataclass(frozen=True)
class LinkView:
    """Что показать на индикаторе."""
    tone: str                   # off | busy | ok | down
    reason: str
    label: str                  # короткая подпись (уже через t())
    tip: str                    # tooltip
    name_fg: str                # green | amber | red — токен для цвета имени


def label_for(tone: str) -> str:
    # Литералы здесь — чтобы tools/i18n_check.py видел ключи.
    if tone == "busy":
        return _t("Подключение")
    if tone == "ok":
        return _t("На связи")
    if tone == "down":
        return _t("Ошибка")
    return _t("Нет связи")


def reason_text(reason: str) -> str:
    if not reason:
        return _t("Связь есть")
    table = {
        "login": _t("Нужен вход пилота"),
        "no_agent": _t("Агент не выбран"),
        "agent_off": _t("Агент выключен"),
        "no_cli": _t("Нет OpenCode CLI"),
        "bridge_down": _t("Мост OpenCode не запущен"),
        "no_key": _t("Нет ключа API"),
        "no_url": _t("Нет адреса API"),
        "bad_key": _t("Ключ не принят"),
        "bad_url": _t("Неверный адрес API"),
        "timeout": _t("Таймаут ответа"),
        "provider_error": _t("Провайдер недоступен"),
        "github_bridge_later": _t("Мост GitHub пока без автопроверки"),
        "network": _t("Нет сети"),
    }
    return table.get(reason, _t("Связи нет"))


def tip_text(reason: str, *, tone: str = "") -> str:
    if tone == "ok" or not reason:
        return _t("Связь с агентом в порядке")
    table = {
        "login": _t("Войдите пилотом, чтобы говорить с агентом"),
        "no_agent": _t("Выберите пассажира во вкладке АГЕНТЫ"),
        "agent_off": _t("Включите «На борту: ДА» и сохраните"),
        "no_cli": _t("Установите OpenCode CLI на этом компьютере"),
        "bridge_down": _t("Проверьте установку OpenCode и перезапустите корабль"),
        "no_key": _t("Вставьте API-ключ в привязке агента и сохраните"),
        "no_url": _t("Укажите адрес API (https://…/v1) в карточке"),
        "bad_key": _t("Проверьте ключ API в привязке агента"),
        "bad_url": _t("Исправьте адрес API в карточке пассажира"),
        "timeout": _t("Провайдер не ответил — проверьте сеть"),
        "provider_error": _t("Проверьте адрес, ключ и доступность сервиса"),
        "github_bridge_later": _t("Связь GitHub проверяется при отправке сообщения"),
        "network": _t("Проверьте интернет и адрес API"),
    }
    return table.get(reason, _t("Откройте ОРИОН → АГЕНТЫ и проверьте привязку"))


def name_fg_for(tone: str) -> str:
    """Цвет имени: зелёный на связи, янтарный при подключении, красный без связи/ошибка."""
    if tone == "ok":
        return "green"
    if tone == "busy":
        return "amber"
    return "red"


def derive_view(agent: dict | None, health: Health | None, *,
                checking: bool = False, busy: bool = False) -> LinkView:
    """Собрать тон/подпись/tooltip из записи агента и результата health."""
    if agent is None:
        return LinkView("off", "no_agent", label_for("off"),
                        tip_text("no_agent"), name_fg_for("off"))
    if not agent.get("enabled", True):
        return LinkView("off", "agent_off", label_for("off"),
                        tip_text("agent_off"), name_fg_for("off"))
    if busy or checking:
        reason = (health.reason if health else "") or ""
        tip = tip_text(reason, tone="busy") if reason else _t("Проверка связи…")
        return LinkView("busy", reason, label_for("busy"), tip, name_fg_for("busy"))

    if health is None:
        return LinkView("busy", "", label_for("busy"),
                        _t("Проверка связи…"), name_fg_for("busy"))

    if health.available:
        return LinkView("ok", "", label_for("ok"),
                        tip_text("", tone="ok"), name_fg_for("ok"))

    reason = health.reason or "provider_error"
    tone = "off" if reason in ("login", "no_agent", "agent_off") else "down"
    # Для пилота «нет связи» и «ошибка» — разные подписи, имя в обоих случаях красное.
    return LinkView(tone, reason, label_for(tone), tip_text(reason, tone=tone),
                    name_fg_for(tone))


def tooltip_for(view: LinkView, agent: dict | None, health: Health | None) -> str:
    """Tooltip: имя · модель · причина."""
    name = str((agent or {}).get("name") or (health.name if health else "") or "—")
    model = str((agent or {}).get("model") or (health.model if health else "")
                or "").strip() or _t("модель по умолчанию")
    kind = str((agent or {}).get("kind") or (health.kind if health else "") or "")
    bits = [name]
    if kind:
        bits.append(kind)
    bits.append(model)
    head = " · ".join(bits)
    if view.tone == "ok":
        return f"{head}\n{view.tip}"
    detail = reason_text(view.reason) if view.reason else view.label
    return f"{head}\n{detail}\n{view.tip}"


def _cache_key(agent: dict) -> str:
    return "|".join((
        str(agent.get("id") or ""),
        str(agent.get("kind") or "opencode"),
        str(agent.get("base_url") or ""),
        str(agent.get("cred_ref") or ""),
        "1" if agent.get("enabled", True) else "0",
    ))


def _cache_get(key: str) -> Health | None:
    with _cache_lock:
        row = _cache.get(key)
        if not row:
            return None
        ts, data = row
        if time.monotonic() - ts > CACHE_TTL:
            _cache.pop(key, None)
            return None
        return Health(**{**data.__dict__, "cached": True})


def _cache_put(key: str, data: Health) -> Health:
    with _cache_lock:
        _cache[key] = (time.monotonic(), data)
    return data


def clear_cache(agent_id: str | None = None) -> None:
    """Сбросить кэш (вся таблица или один агент)."""
    with _cache_lock:
        if agent_id is None:
            _cache.clear()
            return
        for key in [k for k in _cache if k.startswith(str(agent_id) + "|")]:
            _cache.pop(key, None)


def _probe_openai_models(base_url: str, key: str) -> Health:
    """Дешёвый GET /models — без генерации."""
    from stamina import agent_connect as ac

    base = (base_url or "").rstrip("/")
    if not base:
        return Health(False, "no_url", "down")
    if not key and not getattr(ac, "_is_local", lambda _u: False)(base_url):
        # локальная Ollama может жить без ключа
        try:
            local = ac._is_local(base_url)  # noqa: SLF001
        except Exception:  # noqa: BLE001
            local = False
        if not local:
            return Health(False, "no_key", "down")
    url = base + "/models"
    headers = {"User-Agent": "StarTyping"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            code = getattr(resp, "status", 200) or 200
            if code >= 400:
                return Health(False, f"http_{code}", "down")
            return Health(True, "", "ok")
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return Health(False, "bad_key", "down")
        if exc.code in (404, 405):
            # часть провайдеров режет /models — ключ при этом принят
            return Health(True, "", "ok")
        if exc.code >= 500:
            return Health(False, "provider_error", "down")
        return Health(False, f"http_{exc.code}", "down")
    except TimeoutError:
        return Health(False, "timeout", "down")
    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc) or "")
        if "timed out" in reason.lower():
            return Health(False, "timeout", "down")
        return Health(False, "network", "down")
    except OSError:
        return Health(False, "network", "down")


def probe(agent: dict | None, *, refresh: bool = False) -> Health:
    """Проверить связь с агентом. Без UI. Результат кэшируется ~25 с."""
    if agent is None:
        return Health(False, "no_agent", "off")
    aid = str(agent.get("id") or "")
    kind = str(agent.get("kind") or "opencode")
    name = str(agent.get("name") or "")
    model = str(agent.get("model") or "")
    if not agent.get("enabled", True):
        return Health(False, "agent_off", "off", kind=kind, agent_id=aid,
                      model=model, name=name)

    key = _cache_key(agent)
    if not refresh:
        hit = _cache_get(key)
        if hit is not None:
            return hit

    if kind == "opencode":
        from stamina import orion
        ok, exe = orion.available()
        data = Health(bool(ok), "" if ok else ("no_cli" if not exe else "bridge_down"),
                      "ok" if ok else "down", kind=kind, agent_id=aid,
                      model=model, name=name)
        return _cache_put(key, data)

    if kind == "github_bridge":
        data = Health(False, "github_bridge_later", "down", kind=kind,
                      agent_id=aid, model=model, name=name)
        return _cache_put(key, data)

    # openai_compat
    from stamina import agent_connect as ac
    api_key = ac.read_key(str(agent.get("cred_ref") or ""))
    raw = _probe_openai_models(str(agent.get("base_url") or ""), api_key)
    data = Health(raw.available, raw.reason, raw.state, kind=kind, agent_id=aid,
                  model=model, name=name)
    return _cache_put(key, data)


def list_view(agent: dict) -> LinkView:
    """Оценка для строки списка: кэш или дешёвая локальная проверка (без HTTP)."""
    if not agent.get("enabled", True):
        return derive_view(agent, Health(False, "agent_off", "off",
                                         kind=str(agent.get("kind") or ""),
                                         agent_id=str(agent.get("id") or ""),
                                         name=str(agent.get("name") or "")))
    hit = _cache_get(_cache_key(agent))
    if hit is not None:
        return derive_view(agent, hit)

    kind = str(agent.get("kind") or "opencode")
    aid = str(agent.get("id") or "")
    name = str(agent.get("name") or "")
    model = str(agent.get("model") or "")
    if kind == "opencode":
        # Дешёвая проверка CLI — сразу в кэш, чтобы HUD не висел на «Подключение».
        return derive_view(agent, probe(agent, refresh=False))
    if kind == "github_bridge":
        h = Health(False, "github_bridge_later", "down",
                   kind=kind, agent_id=aid, model=model, name=name)
        return derive_view(agent, _cache_put(_cache_key(agent), h))
    from stamina import agent_connect as ac
    key = ac.read_key(str(agent.get("cred_ref") or ""))
    try:
        local = ac._is_local(str(agent.get("base_url") or ""))  # noqa: SLF001
    except Exception:  # noqa: BLE001
        local = False
    if not key and not local:
        return derive_view(agent, Health(False, "no_key", "down",
                                         kind=kind, agent_id=aid, model=model, name=name))
    if not str(agent.get("base_url") or "").strip():
        return derive_view(agent, Health(False, "no_url", "down",
                                         kind=kind, agent_id=aid, model=model, name=name))
    # Ключ есть — до фонового probe считаем «подключение», не зелёный наугад.
    return derive_view(agent, None, checking=True)


def probe_active(*, refresh: bool = False) -> tuple[dict | None, Health, LinkView]:
    """Активный пассажир + health + view."""
    from stamina import orion
    agent = orion.active()
    health = probe(agent, refresh=refresh)
    return agent, health, derive_view(agent, health)


def probe_async(agent: dict | None, on_done: Callable[[Health], None], *,
                refresh: bool = False) -> None:
    """Запуск probe в фоне; on_done вызывается из рабочего потока — маршалить в Tk сами."""
    def work() -> None:
        try:
            h = probe(agent, refresh=refresh)
        except Exception:  # noqa: BLE001
            h = Health(False, "provider_error", "down",
                       kind=str((agent or {}).get("kind") or ""),
                       agent_id=str((agent or {}).get("id") or ""),
                       name=str((agent or {}).get("name") or ""))
        on_done(h)

    threading.Thread(target=work, daemon=True).start()


# ---------------------------------------------------------------------------
# Tk-виджет индикатора
# ---------------------------------------------------------------------------

class LinkIndicator:
    """Цветная точка + короткая подпись. Клик → ОРИОН → АГЕНТЫ.

    compact=True — только точка и короткий текст (HUD / список пассажиров).
    Имя агента красится снаружи через name_fg токена view.
    """

    DOT = 11          # логические px; ~10–12 на экране при UI M

    def __init__(self, master, *, compact: bool = True, on_click=None,
                 bg: str | None = None) -> None:
        import tkinter as tk
        from stamina import theme as th
        from stamina.theme import BG, MUTED, PANEL, px

        self._on_click = on_click
        self.compact = compact
        self.view: LinkView | None = None
        self._pulse_job = None
        self._pulse_on = True
        self._pulse_color = MUTED
        self._tip = None
        self._tip_text = ""

        bg = bg if bg is not None else (PANEL if compact else BG)
        self.frame = tk.Frame(master, bg=bg, cursor="hand2")
        size = px(self.DOT)
        pad = max(2, px(2))
        self.dot = tk.Canvas(self.frame, width=size + pad * 2, height=size + pad * 2,
                             bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.dot.pack(side=tk.LEFT)
        self._dot_size = size
        self._dot_pad = pad
        self.lab = tk.Label(self.frame, text=label_for("off"), bg=bg, fg=MUTED,
                            font=th.font(8 if compact else 9, True), cursor="hand2")
        self.lab.pack(side=tk.LEFT, padx=(px(4), 0))
        for w in (self.frame, self.dot, self.lab):
            w.bind("<Button-1>", self._click)
            w.bind("<Enter>", self._enter)
            w.bind("<Leave>", self._leave)
        self.apply(derive_view(None, None, checking=False))

    def pack(self, **kw):
        return self.frame.pack(**kw)

    def grid(self, **kw):
        return self.frame.grid(**kw)

    def destroy(self) -> None:
        self._stop_pulse()
        self._hide_tip()
        try:
            self.frame.destroy()
        except Exception:  # noqa: BLE001
            pass

    def _click(self, _e=None) -> None:
        if self._on_click:
            self._on_click()

    def _enter(self, _e=None) -> None:
        if self._tip_text:
            self._show_tip(self._tip_text)

    def _leave(self, _e=None) -> None:
        self._hide_tip()

    def _show_tip(self, text: str) -> None:
        import tkinter as tk
        from stamina import theme as th
        from stamina.theme import BG2, LINE, TEXT, px
        self._hide_tip()
        tip = tk.Toplevel(self.frame)
        tip.wm_overrideredirect(True)
        try:
            tip.attributes("-topmost", True)
        except tk.TclError:
            pass
        try:
            tip.configure(bg=LINE)
        except tk.TclError:
            pass
        lbl = tk.Label(tip, text=text, justify="left", bg=BG2, fg=TEXT,
                       font=th.font(8), padx=px(8), pady=px(4),
                       wraplength=px(280))
        lbl.pack(padx=1, pady=1)
        self.frame.update_idletasks()
        x = self.frame.winfo_rootx()
        y = self.frame.winfo_rooty() + self.frame.winfo_height() + 4
        tip.geometry(f"+{x}+{y}")
        self._tip = tip

    def _hide_tip(self) -> None:
        tip = self._tip
        self._tip = None
        if tip is not None:
            try:
                tip.destroy()
            except Exception:  # noqa: BLE001
                pass

    def apply(self, view: LinkView, *, tip: str = "") -> None:
        from stamina.theme import AMBER, GREEN, MUTED, RED

        self.view = view
        self._tip_text = tip or view.tip
        color = {"ok": GREEN, "busy": AMBER, "down": RED, "off": MUTED}.get(view.tone, MUTED)
        try:
            self.lab.configure(text=view.label, fg=color)
        except Exception:  # noqa: BLE001
            return
        self._draw_dot(color, glow=(view.tone in ("ok", "busy", "down")))
        if view.tone == "busy":
            self._start_pulse(color)
        else:
            self._stop_pulse()
            self._pulse_color = color

    def _draw_dot(self, color: str, *, glow: bool = True, dim: bool = False) -> None:
        from stamina.theme import BG, blend

        c = self.dot
        try:
            c.delete("all")
        except Exception:  # noqa: BLE001
            return
        s, p = self._dot_size, self._dot_pad
        fill = blend(color, BG, 0.45) if dim else color
        # Обводка + лёгкое «свечение»: точка читается на любом фоне панели/скина.
        if glow:
            halo = blend(fill, "#FFFFFF", 0.55)
            c.create_oval(p - 2, p - 2, p + s + 2, p + s + 2,
                          fill="", outline=halo, width=2)
        c.create_oval(p, p, p + s, p + s, fill=fill,
                      outline=blend(fill, "#FFFFFF", 0.25), width=1)

    def _start_pulse(self, color: str) -> None:
        self._pulse_color = color
        if self._pulse_job is not None:
            return
        self._pulse_on = True
        self._pulse_tick()

    def _stop_pulse(self) -> None:
        job = self._pulse_job
        self._pulse_job = None
        if job is not None:
            try:
                self.frame.after_cancel(job)
            except Exception:  # noqa: BLE001
                pass

    def _pulse_tick(self) -> None:
        if self.view is None or self.view.tone != "busy":
            self._pulse_job = None
            return
        self._pulse_on = not self._pulse_on
        self._draw_dot(self._pulse_color, glow=True, dim=not self._pulse_on)
        try:
            self._pulse_job = self.frame.after(550, self._pulse_tick)
        except Exception:  # noqa: BLE001
            self._pulse_job = None


class LinkWatcher:
    """Фоновый опрос активного агента; слушатели получают view на UI-потоке.

    Результат probe кладётся в очередь — Tk ``after`` из чужого потока нельзя
    (RuntimeError: main thread is not in main loop), поэтому UI сам забирает
    ответы коротким poll, как в ``agent_dialog``.
    """

    def __init__(self, root) -> None:
        import queue
        self.root = root
        self._q: queue.SimpleQueue = queue.SimpleQueue()
        self._listeners: list[Callable[[dict | None, Health, LinkView], None]] = []
        self._poll_job = None
        self._tick_job = None
        self._alive = True
        self._checking = False
        self.agent: dict | None = None
        self.health: Health | None = None
        self.view = derive_view(None, None, checking=True)

    def subscribe(self, fn: Callable[[dict | None, Health, LinkView], None]) -> None:
        self._listeners.append(fn)

    def start(self) -> None:
        self.refresh(False)
        self._schedule_tick()
        self._schedule_poll()

    def stop(self) -> None:
        self._alive = False
        for attr in ("_poll_job", "_tick_job"):
            job = getattr(self, attr)
            setattr(self, attr, None)
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except Exception:  # noqa: BLE001
                    pass

    def _schedule_tick(self) -> None:
        if not self._alive:
            return
        try:
            self._tick_job = self.root.after(int(POLL_SEC * 1000), self._on_tick)
        except Exception:  # noqa: BLE001
            self._tick_job = None

    def _on_tick(self) -> None:
        self.refresh(False)
        self._schedule_tick()

    def _schedule_poll(self) -> None:
        if not self._alive:
            return
        try:
            self._poll_job = self.root.after(100, self._poll)
        except Exception:  # noqa: BLE001
            self._poll_job = None

    def _poll(self) -> None:
        """Забрать готовые health с фоновых потоков."""
        import queue
        try:
            while True:
                agent, health = self._q.get_nowait()
                if not self._alive:
                    continue
                self._checking = False
                self.agent = agent
                self.health = health
                self.view = derive_view(agent, health)
                self._emit()
        except queue.Empty:
            pass
        self._schedule_poll()

    def on_agent_switch(self) -> None:
        clear_cache()
        self.refresh(True)

    def publish(self, agent: dict | None, health: Health, view: LinkView) -> None:
        """Внешний probe (список пассажиров) сообщает актуальный статус активного агента."""
        self.agent = agent
        self.health = health
        self.view = view
        self._checking = False
        self._emit()

    def refresh(self, force: bool = False) -> None:
        if self._checking and not force:
            return
        from stamina import orion
        agent = orion.active()
        self.agent = agent
        key = _cache_key(agent) if agent else ""
        cached = _cache_get(key) if key else None
        if cached is not None and not force:
            self.health = cached
            self.view = derive_view(agent, cached)
            self._emit()
            return
        # Нет кэша или принудительно — «Подключение», затем фон.
        self.view = derive_view(agent, cached, checking=True)
        self._emit()
        self._checking = True

        def done(h: Health) -> None:
            try:
                self._q.put((agent, h))
            except Exception:  # noqa: BLE001
                pass

        probe_async(agent, done, refresh=force)

    def _emit(self) -> None:
        for fn in list(self._listeners):
            try:
                fn(self.agent, self.health, self.view)
            except Exception:  # noqa: BLE001
                pass
