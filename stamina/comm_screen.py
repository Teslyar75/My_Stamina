"""Экран «ЭФИР» — общая лента сообщений экипажа.

Пилот выбирает вкладку ЭФИР в шапке, читает, что написали другие, и отвечает.
Данные — `stamina/comm.py` (общий файл экипажа). Пока это прототип на одном
компьютере; экран специально не знает, откуда берутся сообщения, поэтому при
появлении онлайна его не придётся переписывать.
"""
from __future__ import annotations

from stamina.i18n import t as _t

import queue
import threading
import time
import tkinter as tk

from stamina import comm, doc_translate, i18n, pilots, theme
from stamina.adapt import make_vscroll
from stamina.hud import HudButton, HudPanel
from stamina.prompt_box import PromptBox, hud_colors
from stamina.suggest import Suggester, dictionary_from
from stamina.theme import AMBER, BG, BG2, CYAN, LINE, MUTED, PANEL, TEXT, px
from stamina.voice.mic import MicControl

# позывной красим цветом «акцента» пилота из реестра экипажа (сами цвета берём у скина)
ACCENTS = ("cyan", "amber", "green", "red", "purple")


def translate_message(text: str, sl: str, tl: str) -> str:
    """Перевод одного сообщения: Argos офлайн, сеть — запасной путь (doc_translate)."""
    return doc_translate.translate_md(text, tl, sl=sl)


def _label(master, text="", *, fg=None, size=10, bold=False, bg=None, **kw):
    fg = TEXT if fg is None else fg  # токен скина — в момент вызова, не при импорте
    bg = PANEL if bg is None else bg  # токен скина — в момент вызова, не при импорте
    return tk.Label(master, text=text, fg=fg, bg=bg, font=theme.font(size, bold), **kw)


class CommScreen(tk.Frame):
    """Лента эфира: сообщения экипажа, поле ввода и отправка."""

    def __init__(self, master, app) -> None:
        super().__init__(master, bg=BG)
        self.app = app
        self._accents: dict[str, str] = {}
        # перевод сообщений: язык определяем один раз, перевод кэшируем по (id, язык)
        self._tr_lang: dict[str, str] = {}
        self._tr_cache: dict[tuple[str, str], str] = {}
        self._tr_shown: set[str] = set()      # какие сообщения сейчас показаны переводом
        self._tr_pending: set[str] = set()    # ждём ответ переводчика
        self._tr_errors: dict[str, str] = {}
        self._tr_widgets: list[tk.Widget] = []
        self._tr_vars: list[tk.BooleanVar] = []
        self._tr_results: queue.Queue = queue.Queue()

        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(14), pady=(px(10), px(4)))
        _label(top, _t("ЭФИР — СВЯЗЬ ЭКИПАЖА"), size=16, bold=True, bg=BG).pack(side=tk.LEFT)
        self.info = _label(top, "", fg=MUTED, size=9, bg=BG)
        self.info.pack(side=tk.LEFT, padx=(px(10), px(6)))
        HudButton(top, "?", lambda: self.app.open_help(), height=32, font_size=10,
                  width=32, color=AMBER).pack(side=tk.RIGHT)
        HudButton(top, _t("ОБНОВИТЬ"), self.refresh, height=32, font_size=10,
                  color=CYAN).pack(side=tk.RIGHT, padx=(0, px(8)))

        # Строку ввода пакуем к низу и ДО ленты: лента расширяемая (expand) и,
        # если упаковать её первой, на низком окне она съедает место — строка
        # ввода уезжает за край и «окна для ответа» не видно.
        row = tk.Frame(self, bg=BG)
        row.pack(side=tk.BOTTOM, fill=tk.X, padx=px(14), pady=(px(6), px(10)))
        self.suggester = Suggester()
        self._suggest_seen = -1
        self.entry = PromptBox(row, on_send=self._send, font=theme.font(11),
                               colors=hud_colors(), suggester=self.suggester)
        self.entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, px(8)))
        self.send_btn = HudButton(row, _t("ОТПРАВИТЬ"), self._send, height=36, font_size=11)
        self.send_btn.pack(side=tk.LEFT)
        # голос пилота прямо в эфир: сказал — проверил текст — Enter
        store = getattr(self.app, "store", None)      # у облегчённых «кораблей» его нет
        self.mic = MicControl(row, on_text=self._insert_text, on_status=self._mic_status,
                              label=_t("ГОЛОС"), height=36, font_size=10,
                              settings=getattr(store, "settings", None),
                              save=getattr(store, "save_settings", None))
        self.mic.button.pack(side=tk.LEFT, padx=(px(8), 0))
        self.mic.hold_button.pack(side=tk.LEFT, padx=(px(6), 0))
        self.mic_hint = _label(self, "", fg=MUTED, size=9, bg=BG, anchor="w", justify="left",
                               wraplength=px(900))
        self.mic_hint.pack(side=tk.BOTTOM, fill=tk.X, padx=px(14))
        self.after(160, self._tick_mic)

        panel = HudPanel(self, title=_t("ОБЩИЙ КАНАЛ"))
        panel.pack(fill=tk.BOTH, expand=True, padx=px(14), pady=px(4))
        sb = make_vscroll(panel.body)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text = tk.Text(panel.body, wrap=tk.WORD, bg=PANEL, fg=TEXT, relief=tk.FLAT,
                            font=theme.font(10), padx=px(8), pady=px(6), cursor="arrow",
                            height=6, state=tk.DISABLED, highlightthickness=0, bd=0,
                            yscrollcommand=sb.set)
        self.text.pack(fill=tk.BOTH, expand=True)
        sb.configure(command=self.text.yview)
        self._apply_tags()
        # колесо мыши: Windows/macOS — <MouseWheel>, Linux (X11) — кнопки 4/5
        for w in (self.text, panel.body):
            w.bind("<MouseWheel>", self._wheel)
            w.bind("<Button-4>", lambda _e: self.text.yview_scroll(-3, "units"))
            w.bind("<Button-5>", lambda _e: self.text.yview_scroll(3, "units"))

    # -- данные -------------------------------------------------------------
    def _pid(self) -> str:
        return (self.app.pilot or {}).get("id", "")

    def _callsign(self) -> str:
        return (self.app.pilot or {}).get("callsign", "")

    def _wheel(self, e) -> str:
        self.text.yview_scroll(int(-e.delta / 120) * 3, "units")
        return "break"

    # -- отрисовка ----------------------------------------------------------
    def _apply_tags(self) -> None:
        """Цвета берём у текущего скина в момент отрисовки (токены, без хардкода)."""
        self.text.tag_configure("time", foreground=theme.MUTED, font=theme.font(8))
        self.text.tag_configure("body", foreground=theme.TEXT, font=theme.font(10))
        self.text.tag_configure("hint", foreground=theme.MUTED, font=theme.font(10))
        for name in ACCENTS:
            color = getattr(theme, name.upper(), theme.CYAN)
            self.text.tag_configure(f"acc_{name}", foreground=color, font=theme.font(10, True))

    def refresh(self) -> None:
        """Перечитать эфир, показать ленту и отметить прочитанным."""
        self._accents = {p["id"]: p.get("accent", "cyan") for p in pilots.pilots()}
        self._apply_tags()
        pid = self._pid()
        fresh = comm.unread(pid)
        self._render()
        if pid:
            comm.mark_read(pid)
        total = len(comm.messages())
        tail = f" · {_t('Новых: {0}').format(fresh)}" if fresh else ""
        self.info.configure(text=_t("Сообщений: {0}").format(total) + tail)
        has_pilot = bool(pid)
        self.entry.set_enabled(has_pilot)
        self.send_btn.set_active(has_pilot)
        self._refresh_suggest()

    def _refresh_suggest(self) -> None:
        """Пульт учится на эфире: подсказки из того, что экипаж уже писал."""
        msgs = comm.messages()
        if len(msgs) == self._suggest_seen:
            return
        self._suggest_seen = len(msgs)
        texts = [str(m.get("text") or "") for m in msgs[-300:]]
        texts += [str(p.get("callsign") or "") for p in pilots.pilots()]
        self.suggester = Suggester(dictionary_from(texts))
        self.entry.set_suggester(self.suggester)

    def _target_lang(self) -> str:
        """Основной язык пилота — язык интерфейса (ru/uk/en/de)."""
        return i18n.language()

    def _message_lang(self, msg: dict) -> str:
        mid = str(msg.get("id") or "")
        lang = self._tr_lang.get(mid)
        if lang is None:
            lang = comm.message_language(str(msg.get("text") or ""))
            self._tr_lang[mid] = lang
        return lang

    def _toggle_translation(self, mid: str, text: str, sl: str) -> None:
        """Кнопка у сообщения: перевод → оригинал → перевод (из кэша)."""
        if mid in self._tr_pending:
            return
        if mid in self._tr_shown:
            self._tr_shown.discard(mid)
            self._render()
            return
        tl = self._target_lang()
        if (mid, tl) in self._tr_cache:
            self._tr_shown.add(mid)
            self._render()
            return
        self._tr_pending.add(mid)
        self._tr_errors.pop(mid, None)
        self._render()          # сразу показываем «перевод…», не ждём сеть
        threading.Thread(target=self._translate_worker, args=(mid, text, sl, tl),
                         name="comm-translate", daemon=True).start()

    def _translate_worker(self, mid: str, text: str, sl: str, tl: str) -> None:
        try:
            out = translate_message(text, sl, tl)
        except Exception as exc:  # noqa: BLE001 — сеть/Argos могут отказать
            self._tr_results.put((mid, tl, None, str(exc) or exc.__class__.__name__))
        else:
            self._tr_results.put((mid, tl, out, ""))

    def _poll_translations(self) -> None:
        """Забрать готовые переводы в потоке Tk и перерисовать ленту."""
        changed = False
        while True:
            try:
                mid, tl, out, err = self._tr_results.get_nowait()
            except queue.Empty:
                break
            self._tr_pending.discard(mid)
            changed = True
            if out:
                self._tr_cache[(mid, tl)] = out
                self._tr_errors.pop(mid, None)
                self._tr_shown.add(mid)
            else:
                self._tr_errors[mid] = err
                self.info.configure(text=_t("Перевод не удался: {0}").format(err))
        if changed:
            self._render()

    def _render(self) -> None:
        for w in self._tr_widgets:
            try:
                w.destroy()
            except tk.TclError:
                pass
        self._tr_widgets.clear()
        self._tr_vars.clear()
        msgs = comm.messages()
        pid = self._pid()
        target = self._target_lang()
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        if not pid:
            self.text.insert(tk.END, _t("Войдите в кабину пилота — тогда можно писать в эфир.") + "\n", "hint")
        if not msgs:
            self.text.insert(tk.END, _t("Пока в эфире пусто. Передайте первое сообщение экипажу.") + "\n", "hint")
        for m in msgs:
            accent = self._accents.get(m.get("author", ""))
            if accent not in ACCENTS:
                accent = "cyan"
            self.text.insert(tk.END, str(m.get("callsign") or "—"), f"acc_{accent}")
            if m.get("author") == pid:
                self.text.insert(tk.END, " ▸", "time")     # своё сообщение
            when = time.strftime("%d.%m %H:%M", time.localtime(float(m.get("ts", 0.0))))
            self.text.insert(tk.END, f"  {when}\n", "time")

            mid = str(m.get("id") or "")
            text = str(m.get("text") or "")
            lang = self._message_lang(m)
            translated = self._tr_cache.get((mid, target)) if mid in self._tr_shown else None
            if translated is None:
                self._tr_shown.discard(mid)
                body = text
            else:
                body = translated
            self.text.insert(tk.END, body + " ", "body")
            if lang != "und" and lang != target:
                pending = mid in self._tr_pending
                label = "⇄ " + _t("ОРИГИНАЛ") if translated is not None else "⇄ " + _t("ПЕРЕВОД")
                if pending:
                    label += "…"
                var = tk.BooleanVar(value=translated is not None)
                cb = tk.Checkbutton(
                    self.text, text=label, command=lambda mid=mid, text=text, sl=lang:
                    self._toggle_translation(mid, text, sl),
                    indicatoron=False, variable=var,
                    bg=PANEL, fg=CYAN, activebackground=BG2, activeforeground=CYAN,
                    selectcolor=BG2, disabledforeground=MUTED, font=theme.font(8, True),
                    bd=0, relief=tk.FLAT, highlightthickness=0, padx=px(6), pady=px(1),
                    cursor="hand2", takefocus=0, state=tk.DISABLED if pending else tk.NORMAL,
                )
                self.text.window_create(tk.END, window=cb, padx=px(2), pady=px(1))
                self._tr_widgets.append(cb)
                self._tr_vars.append(var)      # Tk не держит Python-ссылку на переменную
            self.text.insert(tk.END, "\n\n", "body")
        self.text.configure(state=tk.DISABLED)
        self.text.see(tk.END)

    # -- ввод ---------------------------------------------------------------
    def focus_input(self) -> None:
        """Фокус в поле ввода (при входе в раздел)."""
        if self.entry.state() != "disabled":
            self.entry.focus_set()

    def _send(self) -> None:
        pid = self._pid()
        if not pid:
            return
        text = " ".join(self.entry.get().split())
        if not text:
            return
        if comm.send(pid, self._callsign(), text) is not None:
            self.entry.clear()
            self.refresh()
            self.app.after(30, self._refresh_chrome)

    def _insert_text(self, text: str) -> None:
        """Распознанная речь — в поле ввода (пилот проверит и нажмёт Enter)."""
        if not text:
            return
        self.entry.insert_text(text)

    def _mic_status(self, text: str, color=None) -> None:
        color = MUTED if color is None else color  # токен скина — в момент вызова, не при импорте
        self.mic_hint.configure(text=text, fg=color)

    def _tick_mic(self) -> None:
        """Микрофон и переводчик работают в потоках — забираем события в интерфейс."""
        try:
            self.mic.poll()
        except Exception:  # noqa: BLE001
            pass
        try:
            self._poll_translations()
        except Exception:  # noqa: BLE001
            pass
        self.after(160, self._tick_mic)

    def _refresh_chrome(self) -> None:
        """Обновить счётчик непрочитанного на кнопке раздела."""
        try:
            self.app.update_comm_badge()
        except Exception:  # noqa: BLE001
            pass

    def page_help_key(self) -> str:
        return "comm"

    def on_key(self, _e) -> None:
        """Клавиши раздела: поле ввода само обрабатывает набор и Enter."""
