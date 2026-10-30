"""Инструменты отсека «Документы»: язык диктовки (RU/UK/EN, модель Vosk по требованию),
перевод на EN/DE (весь документ или выделение), проверка текста у Ориона.

Фоновые потоки не трогают Tk: результаты кладутся в очередь `_tool_q`,
экран разбирает её в своём таймере (`poll_tools`).
"""
from __future__ import annotations

import queue
import re
import threading
import tkinter as tk

from stamina import doc_translate, docs, orion
from stamina.i18n import t as _t
from stamina.theme import AMBER, CYAN, GREEN, MUTED, PANEL, RED, TEXT
from stamina.voice import models as vmodels

LANG_LABEL = {"ru": "RU", "uk": "UK", "en": "EN"}
TR_SUFFIX = {"en": "EN", "de": "DE"}


def doc_check_prompt(chunk: str) -> str:
    """Запрос Ориону: орфография, пунктуация, опечатки — только пары «было → стало»."""
    return "\n".join([
        _t("Ты корректор. Найди в тексте орфографические, пунктуационные ошибки и опечатки."),
        _t("Смысл и стиль не меняй, разметку Markdown (**, #, -, >) не трогай."),
        _t("Ответь одним JSON-массивом без пояснений, «bad» — фрагмент как в тексте, «good» — исправленный:")
        + ' [{"bad": "...", "good": "..."}]. ' + _t("Если правок нет — ответь []."),
        "",
        _t("ТЕКСТ:"),
        chunk,
    ])


class _QueueAfter:
    """`after(ms, fn)` из рабочего потока — через нашу очередь (tk из потоков трогать нельзя)."""

    def __init__(self, post) -> None:
        self._post = post

    def after(self, _ms, fn) -> None:
        self._post(fn)


class ToolsMixin:
    """Подмешивается в DocsScreen (нужны text, mic, _say, _mic_status, save_now…)."""

    # -- общее
    def init_tools(self) -> None:
        self._tool_q: queue.Queue = queue.Queue()
        self._dl_cancel: threading.Event | None = None
        self._busy_tr = False
        self._busy_check = False
        self.apply_dict_lang()

    def _post(self, fn) -> None:
        self._tool_q.put(fn)

    def poll_tools(self) -> None:
        while True:
            try:
                fn = self._tool_q.get_nowait()
            except queue.Empty:
                return
            try:
                fn()
            except tk.TclError:
                pass

    def _settings(self) -> dict:
        store = getattr(getattr(self, "app", None), "store", None)
        return getattr(store, "settings", None) if store is not None else None

    def _save_settings(self) -> None:
        store = getattr(getattr(self, "app", None), "store", None)
        try:
            store.save_settings()
        except Exception:  # noqa: BLE001
            pass

    # -- язык диктовки
    @property
    def dict_lang(self) -> str:
        s = self._settings() or {}
        lang = s.get("docs_dict_lang") or getattr(self, "_dict_lang", "ru")
        return lang if lang in vmodels.LANGS else "ru"

    def set_dict_lang(self, lang: str) -> None:
        self._dict_lang = lang
        s = self._settings()
        if s is not None:
            s["docs_dict_lang"] = lang
            self._save_settings()
        self.apply_dict_lang()

    def apply_dict_lang(self) -> None:
        lang = self.dict_lang
        path = vmodels.model_for(lang)
        self.mic.model_path = path
        btn = getattr(self, "lang_btn", None)
        if btn is not None:
            btn.set_text(LANG_LABEL[lang] + ("" if path else " ⬇"))

    def dict_lang_menu(self) -> None:
        have = vmodels.installed()
        m = tk.Menu(self, tearoff=0, bg=PANEL, fg=TEXT, activebackground=CYAN)
        names = {"ru": _t("Русский"), "uk": _t("Українська"), "en": "English"}
        for lang in vmodels.LANGS:
            mark = "● " if lang == self.dict_lang else "   "
            tail = "" if lang in have else _t(" — скачать ~{0} МБ").format(vmodels.MODELS[lang][1])
            m.add_command(label=mark + names[lang] + tail, command=lambda l=lang: self.choose_dict_lang(l))
        b = self.lang_btn
        m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

    def choose_dict_lang(self, lang: str) -> None:
        self.set_dict_lang(lang)
        if vmodels.model_for(lang) is None:
            self.download_model(lang)
        else:
            self._mic_status(_t("Диктовка: {0}").format(LANG_LABEL[lang]), GREEN)

    def download_model(self, lang: str) -> None:
        if self._dl_cancel is not None:
            self._mic_status(_t("Модель уже скачивается…"), AMBER)
            return
        self._dl_cancel = threading.Event()
        mb = vmodels.MODELS[lang][1]
        self._mic_status(_t("Скачиваю модель речи {0} (~{1} МБ)…").format(LANG_LABEL[lang], mb), CYAN)

        def prog(done, total):
            pct = int(done * 100 / total) if total else 0
            self._post(lambda: self._mic_status(
                _t("Скачиваю модель речи {0}: {1}%").format(LANG_LABEL[lang], pct), CYAN))

        def done(path, err):
            def ui():
                self._dl_cancel = None
                self.apply_dict_lang()
                if path:
                    self._mic_status(_t("Модель {0} готова — диктуйте (F9)").format(LANG_LABEL[lang]), GREEN)
                else:
                    self._mic_status(_t("Модель не скачалась: {0}").format(err), RED)
            self._post(ui)

        vmodels.download_in_background(lang, on_progress=prog, on_done=done, cancel=self._dl_cancel)

    def start_dictation(self) -> None:
        """Кнопка/F9: нет модели выбранного языка — сначала скачать."""
        if self.mic.busy:
            self.mic.toggle()
            return
        self.apply_dict_lang()
        if self.mic.model_path is None:
            self.download_model(self.dict_lang)
            return
        self.mic.toggle()

    # -- перевод
    def translate_menu(self) -> None:
        m = self._fill_translate_menu(tk.Menu(self, tearoff=0, bg=PANEL, fg=TEXT, activebackground=CYAN))
        b = self.tr_btn
        m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

    def _fill_translate_menu(self, m: tk.Menu) -> tk.Menu:
        sel = bool(self.text.tag_ranges("sel"))
        for tl, name in (("en", "English"), ("de", "Deutsch")):
            if sel:
                m.add_command(label=_t("Выделенное → {0}, ниже").format(name),
                              command=lambda t=tl: self.translate(t, "below"))
            m.add_command(label=_t("Документ → {0}, новый документ").format(name),
                          command=lambda t=tl: self.translate(t, "new"))
            m.add_command(label=_t("Документ → {0}, ниже").format(name),
                          command=lambda t=tl: self.translate(t, "below_all"))
            m.add_separator()
        m.add_command(label=_t("Движок: {0}").format(
            _t("Argos (офлайн)") if doc_translate.argos_available() else _t("онлайн (нет argostranslate)")),
            state=tk.DISABLED)
        return m

    def translate(self, tl: str, where: str, *, wait: bool = False) -> None:
        if self._busy_tr:
            return
        self.save_now()
        if where == "below" and self.text.tag_ranges("sel"):
            src = self.text.get("sel.first", "sel.last")
            anchor = self.text.index("sel.last lineend")
        else:
            src = "\n".join(s["t"] for s in self.segments() if "t" in s)
            anchor = "end-1c"
            where = "new" if where == "new" else "below"
        if not src.strip():
            self._say(_t("Нечего переводить"), AMBER)
            return
        title = self.title_var.get().strip()
        self._busy_tr = True
        self._say(_t("Перевожу → {0}…").format(TR_SUFFIX[tl]), CYAN)

        def prog(done, total):
            self._post(lambda: self._say(_t("Перевожу → {0}: {1}/{2}").format(TR_SUFFIX[tl], done, total), CYAN))

        def done(out, err):
            self._post(lambda: self._translated(out, err, tl, where, anchor, title))

        th = doc_translate.translate_in_background(src, tl, on_done=done, on_progress=prog)
        if wait:
            th.join()
            self.poll_tools()

    def _translated(self, out, err, tl, where, anchor, title) -> None:
        self._busy_tr = False
        if out is None:
            self._say(_t("Перевод не удался: {0}").format(err), RED)
            return
        if where == "new":
            self.save_now()
            new_title = f"{title or _t('Без названия')} ({TR_SUFFIX[tl]})"
            doc = docs.Document(title=new_title, segments=[{"t": out}])
            doc.path = docs.new_path()
            docs.save(doc)
            self._show_doc(doc)
            self.refresh()
            self._say(_t("Перевод — новый документ «{0}»").format(new_title), GREEN)
        else:
            self.text.insert(anchor, "\n\n" + out)
            self.text.see(anchor)
            self.highlight()
            self._changed()
            self._say(_t("Перевод вставлен ниже"), GREEN)

    # -- проверка у Ориона
    def check_text(self, *, ask=None) -> None:
        from stamina import book_check
        if self._busy_check:
            return
        raw = self.text.get("1.0", "end-1c")
        if len(raw.strip()) < 3:
            self._say(_t("Сначала введите текст"), AMBER)
            return
        rec = None
        if ask is None:
            ok, _exe = orion.available()
            if not ok:
                self._say(_t("Орион недоступен: не найдена связь с OpenCode"), RED)
                return
            rec = orion.active()
        self._busy_check = True
        self.check_btn.set_enabled(False)
        self._say(_t("Проверяю у Ориона…"), CYAN)
        book_check.check_in_background(
            _QueueAfter(self._post), raw, rec or {}, ask=ask, prompt=doc_check_prompt,
            on_done=self._checked,
            on_progress=lambda i, n: self._say(_t("Проверяю кусок {0} из {1}").format(i, n), CYAN))

    def _checked(self, fixes) -> None:
        from stamina import book_check
        self._busy_check = False
        self.check_btn.set_enabled(True)
        if not fixes:
            self._say(_t("Орион не нашёл правок — текст чистый"), GREEN)
            return
        self._say(_t("Орион нашёл правок: {0}").format(len(fixes)), AMBER)
        self._fixes_win = book_check.FixesWindow(self.app, fixes, self.apply_text_fixes)

    def apply_text_fixes(self, chosen) -> None:
        """Применить правки внутри текстовых кусков — картинки остаются на месте."""
        n = 0
        for bad, good in chosen:
            pos = "1.0"
            while True:
                pos = self.text.search(bad, pos, "end", nocase=False)
                if not pos:
                    break
                end = f"{pos}+{len(bad)}c"
                self.text.delete(pos, end)
                self.text.insert(pos, good)
                pos = f"{pos}+{len(good)}c"
                n += 1
        self.highlight()
        self._changed()
        self._say(_t("Применено правок: {0}").format(n), GREEN)


_MD_NOISE = re.compile(r"[*_`#>]|^\s*(?:[-+]|\d+\.)\s|\]\([^)]*\)|\[", re.M)


def speakable(chars: str) -> str:
    """Разметку Markdown — в пробелы той же длины: смещения фраз = позиции в редакторе."""
    return _MD_NOISE.sub(lambda m: " " * len(m.group(0)), chars)


class ReadAloudMixin:
    """Чтение документа вслух — тот же ReaderQueue и голос, что у читалки книг.

    ▶ ЧИТАТЬ / ❚❚ ПАУЗА / ▶ ДАЛЬШЕ, ■ — стоп, ⏮ ⏭ — главы (# заголовки).
    Читается выделенное, иначе весь документ — с курсора или с места, где остановились
    (место запоминается по документу). Текущая фраза подсвечена, экран едет за ней.
    Движок говорит в своём потоке, интерфейс только опрашивает его — длинная книга не тормозит."""

    tts = None
    _tts_job = None
    _tts_base = "1.0"
    _tts_whole = False
    _read_mem: dict = {}

    # -- место чтения --------------------------------------------------------------
    def _read_key(self) -> str:
        d = getattr(self, "doc", None)
        return str(getattr(d, "path", "") or "")

    def _read_positions(self) -> dict:
        st = self._settings()
        if st is None:
            return self._read_mem
        pos = st.get("docs_read_pos")
        if not isinstance(pos, dict):
            pos = st["docs_read_pos"] = {}
        return pos

    def saved_read_pos(self) -> int:
        try:
            return int(self._read_positions().get(self._read_key(), 0))
        except (TypeError, ValueError):
            return 0

    def _remember_pos(self) -> None:
        q, key = self.tts, self._read_key()
        if q is None or not key or not self._tts_whole:
            return
        pos = self._read_positions()
        pos[key] = int(q.current_char)
        if len(pos) > 200:                       # не копить бесконечно
            for k in list(pos)[:-200]:
                pos.pop(k, None)
        self._save_settings()

    # -- текст ---------------------------------------------------------------------
    def _editor_chars(self, start: str, end: str) -> str:
        """Текст как в индексах Tk: картинка = один пробел (get() её пропускает)."""
        out = []
        for kind, val, _idx in self.text.dump(start, end, text=True, image=True, window=True):
            out.append(val if kind == "text" else " ")
        return "".join(out)

    def _char_of(self, index: str) -> int:
        if not self.text.compare(index, ">", self._tts_base):
            return 0
        n = self.text.count(self._tts_base, index, "chars")
        if isinstance(n, (tuple, list)):
            n = n[0] if n else 0
        return int(n or 0)

    @staticmethod
    def heading_chars(chars: str) -> list[int]:
        return [m.start() for m in re.finditer(r"(?m)^#{1,6} ", chars)]

    # -- движок --------------------------------------------------------------------
    def _tts_ensure(self):
        if self.tts is not None:
            return self.tts
        try:
            from stamina.voice.engine import make_engine_for
            from stamina.voice.reader_tts import ReaderQueue
        except Exception as exc:  # noqa: BLE001
            self._say(_t("Озвучка недоступна: {0}").format(exc), AMBER)
            return None
        st = self._settings() or {}
        eng, voice = make_engine_for(str(st.get("book_speech_voice", "") or ""))
        if not getattr(eng, "available", False):
            self._say(eng.why_unavailable() or _t("Движок озвучки недоступен"), AMBER)
            return None
        self.tts = ReaderQueue(eng, rate=int(st.get("book_speech_rate", 0) or 0), voice=voice or "",
                               duck_radio=bool(st.get("book_speech_duck_radio", True)))
        return self.tts

    def read_toggle(self) -> None:
        q = self._tts_ensure()
        if q is None:
            return
        if q.state == "playing":
            q.pause()
            self._remember_pos()
        elif q.state == "paused":
            q.resume()
        else:
            self._read_start(q)
        self._sync_read_btn()
        self._read_status()

    def _read_start(self, q) -> None:
        t = self.text
        try:
            a, b = t.index("sel.first"), t.index("sel.last")
            whole = False
        except tk.TclError:
            a, b, whole = "1.0", "end-1c", True
        raw = self._editor_chars(a, b)
        chars = speakable(raw)
        if not chars.strip():
            self._say(_t("Нечего читать"))
            return
        self._tts_base, self._tts_whole, self._tts_raw = a, whole, raw
        start = 0
        if whole:
            cur = self._char_of(t.index("insert"))
            saved = self.saved_read_pos()
            # курсор в начале — продолжаем с запомненного места; иначе — с курсора
            start = saved if cur == 0 and 0 < saved < len(chars) else cur
        try:
            from stamina.voice.engine import guess_lang
            q.lang = guess_lang(chars[max(0, start - 2000):start + 2000])
        except Exception:  # noqa: BLE001
            pass
        q.load(chars, start)
        q.play(from_char=start)
        if self._tts_job is None:
            self._tts_job = self.after(200, self._tts_tick)

    def read_stop(self) -> None:
        if self.tts is not None:
            if self.tts.state != "idle":
                self._remember_pos()
            self.tts.stop()
        self.text.tag_remove("speak", "1.0", "end")
        self._sync_read_btn()

    def read_chapter(self, delta: int) -> None:
        """⏮ / ⏭ — к началу этой/предыдущей или следующей главы (строка с #)."""
        q = self.tts
        reading = q is not None and q.state != "idle" and self._tts_whole
        if reading:
            heads, here = self.heading_chars(self._tts_raw), q.current_char
        else:
            self._tts_base = "1.0"
            heads = self.heading_chars(self._editor_chars("1.0", "end-1c"))
            here = self._char_of(self.text.index("insert"))
        if delta > 0:
            nxt = [h for h in heads if h > here]
        else:
            nxt = [h for h in heads if h < here - (40 if reading else 0)]
            nxt = nxt[-1:] or [0]
        if not nxt:
            self._say(_t("Дальше глав нет"))
            return
        pos = nxt[0]
        if reading:
            q.jump_to(pos)
            self._remember_pos()
        idx = f"{self._tts_base}+{pos}c"
        self.text.mark_set("insert", idx)
        self.text.see(idx)

    def _read_status(self) -> None:
        q = self.tts
        if q is None or q.state == "idle" or not q.text:
            return
        done, total = q.progress()
        word = _t("пауза") if q.state == "paused" else _t("читаю")
        self._say(f"{word} · {int(100 * done / max(1, total))}%", GREEN)

    def _tts_tick(self) -> None:
        self._tts_job = None
        q = self.tts
        if q is None:
            return
        for kind, seg in q.poll():
            if kind == "segment" and seg is not None:
                a = f"{self._tts_base}+{int(seg.start)}c"
                b = f"{self._tts_base}+{int(seg.end)}c"
                self.text.tag_remove("speak", "1.0", "end")
                self.text.tag_add("speak", a, b)
                self.text.see(b)
                self.text.see(a)
                if seg.index % 10 == 0:
                    self._remember_pos()
            elif kind == "finished":
                self.text.tag_remove("speak", "1.0", "end")
                if self._tts_whole:
                    self._read_positions().pop(self._read_key(), None)
                    self._save_settings()
                self._say(_t("Дочитано"), GREEN)
            elif kind == "error" and seg:
                self._say(str(seg)[:60], AMBER)
        self._sync_read_btn()
        self._read_status()
        if q.state != "idle":
            self._tts_job = self.after(200, self._tts_tick)

    def _sync_read_btn(self) -> None:
        b = getattr(self, "read_btn", None)
        if b is None:
            return
        st = self.tts.state if self.tts is not None else "idle"
        b.set_text({"playing": _t("❚❚ ПАУЗА"), "paused": _t("▶ ДАЛЬШЕ")}.get(st, _t("▶ ЧИТАТЬ")))

