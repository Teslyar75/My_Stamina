"""«Подключить агента» — общее окно для экрана входа и каюты Ориона.

Клавиатура: Tab — по полям, Ctrl+1/2/3 — вид подключения, F5 — «Проверить связь»,
Ctrl+Enter — сохранить, Esc — отмена. Ключ уходит в хранилище учётных данных ОС,
в профиль агента пишется только ссылка (``agent_connect``).
"""

from __future__ import annotations

import queue
import re
import threading
import tkinter as tk

from stamina import agent_connect as ac
from stamina import orion, theme
from stamina.hud import HudButton
from stamina.i18n import t as _t
from stamina.pilot_screens import Modal
from stamina.voice import agent_voice, tts
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


#: Linux без Secret Service: ключ хранить негде — в файл открытым текстом не пишем.
NO_STORE = ("Нет защищённого хранилища ключей: установите gnome-keyring (или KWallet) "
            "и пакет keyring — см. docs/LINUX.md")

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
                     ("name", "base_url", "model", "tts_voice", "discussion_id", "bridge_repo",
                      "discussion_number", "bridge_login", "webhook", "webhook_header",
                      "webhook_scheme", "timeout")}
        self.key_var = tk.StringVar()
        self.hook_key_var = tk.StringVar()
        self.entries: dict[str, tk.Entry] = {}
        self.rows: dict[str, tk.Frame] = {}
        for k, title in (("name", "ИМЯ АГЕНТА"), ("base_url", "АДРЕС API (BASE URL)"),
                         ("model", "МОДЕЛЬ"), ("key", "КЛЮЧ API"),
                         ("bridge_repo", "РЕПОЗИТОРИЙ GITHUB (ВЛАДЕЛЕЦ/ИМЯ)"),
                         ("discussion_number", "НОМЕР ОБСУЖДЕНИЯ"),
                         ("discussion_id", "ID ОБСУЖДЕНИЯ GITHUB"),
                         ("bridge_login", "ВАШ ЛОГИН GITHUB (ЗАПАСНОЙ ПРИЗНАК ОТВЕТА)"),
                         ("webhook", "ВЕБХУК АГЕНТА (НЕОБЯЗАТЕЛЬНО)"), ("hook_key", "КЛЮЧ ВЕБХУКА"),
                         ("webhook_header", "ЗАГОЛОВОК КЛЮЧА (ПО УМОЛЧАНИЮ Authorization)"),
                         ("webhook_scheme", "СХЕМА КЛЮЧА (ПО УМОЛЧАНИЮ Bearer, «-» — БЕЗ СХЕМЫ)"),
                         ("timeout", "ЖДАТЬ ОТВЕТА, СЕКУНД (ПО УМОЛЧАНИЮ 900)"),
                         ("tts_voice", "ГОЛОС АГЕНТА (ПУСТО — СВОЙ, НЕ КАК У ОРИОНА)")):
            row = tk.Frame(self.body, bg=PANEL)
            _lbl(row, _t(title), fg=MUTED, size=8).pack(fill=tk.X)
            var = {"key": self.key_var, "hook_key": self.hook_key_var}.get(k) or self.vars[k]
            e = tk.Entry(row, textvariable=var, bg=BG2, fg=TEXT, insertbackground=TEXT,
                         relief="flat", font=theme.font(10), width=48,
                         show="•" if k in ("key", "hook_key") else "")
            if k == "tts_voice":
                vrow = tk.Frame(row, bg=PANEL)
                vrow.pack(fill=tk.X)
                e = tk.Entry(vrow, textvariable=var, bg=BG2, fg=TEXT, insertbackground=TEXT,
                             relief="flat", font=theme.font(10), width=36)
                e.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=px(3))
                self.voice_btn = HudButton(vrow, "▾", self.voice_menu, height=26, font_size=9)
                self.voice_btn.pack(side=tk.LEFT, padx=(px(4), 0))
                HudButton(vrow, _t("ПРОСЛУШАТЬ"), self.preview_voice, height=26, font_size=8,
                          color=CYAN).pack(side=tk.LEFT, padx=(px(4), 0))
            e.pack(fill=tk.X, ipady=px(3)) if k != "tts_voice" else None
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
        # список голосов на Windows — запуск PowerShell: собираем заранее, не держа окно
        threading.Thread(target=tts.voices, daemon=True).start()
        self.after(50, lambda: self.entries["name"].focus_set())

    # ------------------------------------------------------------ голос агента
    def voice_menu(self) -> None:
        """Выпадающий список установленных голосов (поле остаётся и для ручного ввода)."""
        menu = tk.Menu(self, tearoff=0, bg=BG2, fg=TEXT, activebackground=CYAN,
                       activeforeground=BG2, font=theme.font(9))
        menu.add_command(label=_t("Автоматически (не как у Ориона)"),
                         command=lambda: self.vars["tts_voice"].set(""))
        if not tts.voices_ready():
            menu.add_command(label=_t("Список голосов загружается…"), state=tk.DISABLED)
        else:
            names = agent_voice.choices()
            if names:
                menu.add_separator()
            for name in names:
                menu.add_command(label=name, command=lambda n=name: self.vars["tts_voice"].set(n))
            if not names:
                menu.add_command(label=_t("Голоса системы не найдены — впишите имя вручную"),
                                 state=tk.DISABLED)
        try:
            menu.tk_popup(self.voice_btn.winfo_rootx(),
                          self.voice_btn.winfo_rooty() + self.voice_btn.winfo_height())
        finally:
            menu.grab_release()

    def preview_voice(self) -> None:
        """«Прослушать»: короткая фраза тем голосом, каким агент будет отвечать."""
        if not tts.available():
            self.msg.configure(text=_t("Озвучка недоступна: нет голосового движка"), fg=AMBER)
            return
        probe = {"id": self.rid or "new-agent", "tts_voice": self.vars["tts_voice"].get().strip()}
        if not tts.voices_ready() and not probe["tts_voice"]:
            self.msg.configure(text=_t("Список голосов загружается…"), fg=MUTED)
            return
        voice = agent_voice.voice_for(probe, "ru", orion.get(agent_voice.ORION_ID))
        name = self.vars["name"].get().strip() or _t("агент")
        tts.speak(_t("Здравствуйте, пилот. Говорит {name}.").format(name=name), voice=voice,
                  lang="ru", role="dev")
        self.msg.configure(text=_t("Голос: {voice}").format(voice=voice or _t("по умолчанию")), fg=MUTED)

    # ------------------------------------------------------------ вид подключения
    def set_kind(self, kind: str) -> None:
        self.kind = kind
        for k, b in self.kind_btns.items():
            b.set_active(k == kind) if hasattr(b, "set_active") else None
        show = {"openai_compat": ("name", "base_url", "model", "key", "timeout", "tts_voice"),
                "opencode": ("name", "model", "timeout", "tts_voice"),
                "github_bridge": ("name", "bridge_repo", "discussion_number", "discussion_id", "key",
                                  "bridge_login", "webhook", "hook_key", "webhook_header",
                                  "webhook_scheme", "tts_voice")}[kind]
        for w in (*self.rows.values(), self.preset_row, self.note, self.msg, self.btns):
            w.pack_forget()
        for k in self.rows:
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
            return _t("Мост GitHub: сообщения уходят в обсуждение GitHub (снимки — в ветку "
                      "ship-chat-media), ответы корабль забирает опросом до 30 минут. Нужен токен "
                      "GitHub (Discussions: запись, Contents: запись). Вебхук — по желанию.")
        return _t("OpenCode CLI должен быть установлен на этом компьютере.")

    def use_preset(self, name: str) -> None:
        url, model = ac.PRESETS[name]
        self.vars["base_url"].set(url)
        self.vars["model"].set(model)
        if not self.vars["name"].get().strip():
            self.vars["name"].set(name.capitalize())

    def record(self) -> dict:
        rec = {k: v.get().strip() for k, v in self.vars.items()}
        repo = rec.get("bridge_repo", "")
        m = re.match(r"^(?:https?://github\.com/)?([\w.-]+/[\w.-]+?)(?:/discussions/(\d+))?/?$", repo)
        if m:                               # вставили ссылку на обсуждение целиком
            rec["bridge_repo"] = m.group(1)
            if m.group(2) and not rec.get("discussion_number"):
                rec["discussion_number"] = m.group(2)
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
        if ok is None:                 # читать можно, запись заранее не проверить — не «зелёный»
            self.msg.configure(text=_t("Связь есть, запись не подтверждена: {0}").format(info), fg=AMBER)
            return
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
                if str(exc) == "no_store":
                    text = _t(NO_STORE)
                else:
                    text = _t("Не удалось сохранить ключ в хранилище Windows: {0}").format(exc)
                self.msg.configure(text=text, fg=RED)
                return
        hook_key = self.hook_key_var.get().strip()
        if hook_key:
            try:
                from stamina import ship_chat
                ac.store_key(saved["id"], hook_key, ref=ship_chat.webhook_ref(saved["id"]))
            except Exception as exc:  # noqa: BLE001
                self.msg.configure(text=_t("Не удалось сохранить ключ в хранилище Windows: {0}")
                                   .format(exc), fg=RED)
                return
        if ref:
            saved = orion.upsert(dict(saved, cred_ref=ref))
        orion.set_active(saved["id"])
        self.result = saved
        self.destroy()
