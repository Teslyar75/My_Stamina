"""«Подключить агента» — общее окно для экрана входа и каюты Ориона.

Клавиатура: Tab — по полям, Ctrl+1/2/3 — вид подключения, F5 — «Проверить связь»,
Ctrl+Enter — сохранить, Esc — отмена. Ключ уходит в хранилище учётных данных ОС,
в профиль агента пишется только ссылка (``agent_connect``).
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk

from stamina import agent_connect as ac
from stamina import orion, theme
from stamina.hud import HudButton
from stamina.i18n import t as _t
from stamina.pilot_screens import Modal
from stamina.theme import AMBER, BG2, CYAN, GREEN, MUTED, PANEL, RED, TEXT, px

KIND_TITLES = (("openai_compat", "API (OpenAI-совместимый)"), ("opencode", "OpenCode CLI"),
               ("github_bridge", "Мост GitHub"))


def _lbl(master, text, *, fg=None, size=9, bold=True, **kw):
    return tk.Label(master, text=text, fg=TEXT if fg is None else fg, bg=PANEL,
                    font=theme.font(size, bold), anchor="w", justify="left", **kw)


def agent_for_pilot(pid: str) -> dict | None:
    """Агент, подключённый к этому пилоту (последний по времени)."""
    if not pid:
        return None
    own = [a for a in orion.agents() if a.get("pilot") == pid]
    return max(own, key=lambda a: float(a.get("created") or 0)) if own else None


class ConnectAgentDialog(Modal):
    """result — сохранённая запись агента или None."""

    def __init__(self, master, *, pilot: str = "", record: dict | None = None) -> None:
        super().__init__(master, _t("ПОДКЛЮЧИТЬ АГЕНТА"), GREEN)
        rec = dict(record or agent_for_pilot(pilot) or {})
        self.pilot = pilot or str(rec.get("pilot") or "")
        self.rid = str(rec.get("id") or "")
        self.kind = str(rec.get("kind") or "openai_compat")
        self._q: queue.Queue = queue.Queue()
        wrap = px(440)
        _lbl(self.body, _t("Подключите своего ИИ-агента к кораблю: он отвечает в чате Ориона "
                           "текстом и голосом."), fg=MUTED, wraplength=wrap).pack(fill=tk.X)
        krow = tk.Frame(self.body, bg=PANEL)
        krow.pack(fill=tk.X, pady=(px(8), px(4)))
        self.kind_btns: dict[str, HudButton] = {}
        for i, (k, title) in enumerate(KIND_TITLES, 1):
            b = HudButton(krow, f"{i} · " + _t(title), lambda k=k: self.set_kind(k), height=30,
                          font_size=8, color=CYAN)
            b.pack(side=tk.LEFT, padx=(0, px(4)))
            self.kind_btns[k] = b
            self.bind(f"<Control-Key-{i}>", lambda _e, k=k: self.set_kind(k))
        self.vars = {k: tk.StringVar(value=str(rec.get(k) or "")) for k in
                     ("name", "base_url", "model", "tts_voice", "discussion_id")}
        self.key_var = tk.StringVar()
        self.entries: dict[str, tk.Entry] = {}
        self.rows: dict[str, tk.Frame] = {}
        for k, title in (("name", "ИМЯ АГЕНТА"), ("base_url", "АДРЕС API (BASE URL)"),
                         ("model", "МОДЕЛЬ"), ("key", "КЛЮЧ API"),
                         ("discussion_id", "ID ОБСУЖДЕНИЯ GITHUB"), ("tts_voice", "ГОЛОС (ИМЯ ГОЛОСА WINDOWS)")):
            row = tk.Frame(self.body, bg=PANEL)
            _lbl(row, _t(title), fg=MUTED, size=8).pack(fill=tk.X)
            var = self.key_var if k == "key" else self.vars[k]
            e = tk.Entry(row, textvariable=var, bg=BG2, fg=TEXT, insertbackground=TEXT,
                         relief="flat", font=theme.font(10), width=48, show="•" if k == "key" else "")
            e.pack(fill=tk.X, ipady=px(3))
            self.entries[k] = e
            self.rows[k] = row
        if rec.get("cred_ref") and ac.read_key(str(rec["cred_ref"])):
            self.key_hint = _t("ключ сохранён в хранилище Windows — оставьте пустым, чтобы не менять")
        else:
            self.key_hint = ""
        self.preset_row = tk.Frame(self.body, bg=PANEL)
        _lbl(self.preset_row, _t("ГОТОВЫЕ АДРЕСА"), fg=MUTED, size=8).pack(side=tk.LEFT, padx=(0, px(6)))
        for name in ac.PRESETS:
            HudButton(self.preset_row, name, lambda n=name: self.use_preset(n), height=26,
                      font_size=8).pack(side=tk.LEFT, padx=px(2))
        self.note = _lbl(self.body, "", fg=AMBER, size=8, wraplength=wrap)
        self.msg = _lbl(self.body, "", fg=MUTED, size=9, wraplength=wrap)
        self.btns = tk.Frame(self.body, bg=PANEL)
        self.test_btn = HudButton(self.btns, _t("ПРОВЕРИТЬ СВЯЗЬ  F5"), self.test, color=CYAN,
                                  height=34, font_size=9)
        self.test_btn.pack(side=tk.LEFT)
        HudButton(self.btns, _t("СОХРАНИТЬ  Ctrl+Enter"), self.save, color=GREEN, height=34,
                  font_size=9).pack(side=tk.LEFT, padx=px(6))
        HudButton(self.btns, _t("ОТМЕНА"), self.cancel, height=34, font_size=9).pack(side=tk.LEFT)
        self.bind("<F5>", lambda _e: self.test())
        self.bind("<Control-Return>", lambda _e: self.save())
        self.set_kind(self.kind)
        self.after(50, lambda: self.entries["name"].focus_set())

    # ------------------------------------------------------------ вид подключения
    def set_kind(self, kind: str) -> None:
        self.kind = kind
        for k, b in self.kind_btns.items():
            b.set_active(k == kind) if hasattr(b, "set_active") else None
        show = {"openai_compat": ("name", "base_url", "model", "key", "tts_voice"),
                "opencode": ("name", "model", "tts_voice"),
                "github_bridge": ("name", "discussion_id", "key", "tts_voice")}[kind]
        for w in (*self.rows.values(), self.preset_row, self.note, self.msg, self.btns):
            w.pack_forget()
        for k in ("name", "base_url", "model", "key", "discussion_id", "tts_voice"):
            if k in show:
                self.rows[k].pack(fill=tk.X, pady=(px(4), 0))
            if k == "model" and kind == "openai_compat":
                self.preset_row.pack(fill=tk.X, pady=(px(4), 0))
        self.note.configure(text=self._note(kind))
        self.note.pack(fill=tk.X, pady=(px(6), 0))
        self.msg.configure(text=self.key_hint if "key" in show else "", fg=MUTED)
        self.msg.pack(fill=tk.X, pady=(px(4), 0))
        self.btns.pack(fill=tk.X, pady=(px(10), 0))

    @staticmethod
    def _note(kind: str) -> str:
        if kind == "openai_compat":
            return _t("Подписка ChatGPT Plus не даёт ключа API: нужен ключ OpenAI API "
                      "(platform.openai.com). Для локальной Ollama ключ не нужен.")
        if kind == "github_bridge":
            return _t("Мост GitHub: сообщения уходят в обсуждение GitHub, ответы корабль забирает "
                      "опросом. Нужен токен GitHub с доступом к обсуждению.")
        return _t("OpenCode CLI должен быть установлен на этом компьютере.")

    def use_preset(self, name: str) -> None:
        url, model = ac.PRESETS[name]
        self.vars["base_url"].set(url)
        self.vars["model"].set(model)
        if not self.vars["name"].get().strip():
            self.vars["name"].set(name.capitalize())

    def record(self) -> dict:
        rec = {k: v.get().strip() for k, v in self.vars.items()}
        rec["kind"] = self.kind
        if self.rid:
            rec["id"] = self.rid
        if self.pilot:
            rec["pilot"] = self.pilot
        return rec

    # ------------------------------------------------------------ проверка связи
    def test(self) -> None:
        rec = self.record()
        if self.rid:
            old = orion.get(self.rid) or {}
            rec["cred_ref"] = old.get("cred_ref", "")
        key = self.key_var.get().strip()
        self.msg.configure(text=_t("Проверяю связь…"), fg=CYAN)
        self.test_btn.set_enabled(False)
        threading.Thread(target=lambda: self._q.put(ac.check(rec, key=key)), daemon=True).start()
        self.after(100, self._poll)

    def _poll(self) -> None:
        try:
            ok, info = self._q.get_nowait()
        except queue.Empty:
            if self.winfo_exists():
                self.after(100, self._poll)
            return
        self.test_btn.set_enabled(True)
        self.msg.configure(text=(_t("Связь есть: {0}") if ok else _t("Нет связи: {0}")).format(info),
                           fg=GREEN if ok else RED)

    # ------------------------------------------------------------ сохранение
    def save(self) -> None:
        rec = self.record()
        if not rec["name"]:
            self.msg.configure(text=_t("Введите имя агента"), fg=RED)
            self.entries["name"].focus_set()
            return
        if self.kind == "openai_compat" and not (rec["base_url"] and rec["model"]):
            self.msg.configure(text=_t("Нужны адрес API и модель"), fg=RED)
            return
        old = orion.get(self.rid) if self.rid else None
        saved = orion.upsert({**(old or {}), **rec})     # права, заметка и ключ-ссылка не теряются
        key = self.key_var.get().strip()
        ref = str((old or {}).get("cred_ref") or "")
        if key:
            try:
                ref = ac.store_key(saved["id"], key)
            except Exception as exc:  # noqa: BLE001
                self.msg.configure(text=_t("Не удалось сохранить ключ в хранилище Windows: {0}")
                                   .format(exc), fg=RED)
                return
        if ref:
            saved = orion.upsert(dict(saved, cred_ref=ref))
        orion.set_active(saved["id"])
        self.result = saved
        self.destroy()
