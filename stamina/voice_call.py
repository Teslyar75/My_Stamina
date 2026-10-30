"""Голосовой вызов агента с мостика: кнопка «ОРИОН» / клавиша Home.

Пилот говорит → тишина отправляет вопрос → сразу звучит короткая фраза-заглушка
голосом агента (готовый WAV из кэша) → приходит настоящий ответ и озвучивается.
Вопрос и ответ пишутся в общую историю Ориона — их видно в кабине.

Повторное нажатие или Esc — отмена. Потоки не трогают виджеты: всё через
очередь и after().
"""
from __future__ import annotations

import queue
import random
import threading
import time
import wave

FILLERS: dict[str, list[str]] = {
    "ru": [
        "Принял, капитан, анализирую.", "Секунду, капитан, сверяюсь с данными.",
        "Вас понял. Обрабатываю запрос.", "Есть, капитан. Думаю.", "Принято. Запускаю анализ.",
        "Минуту, капитан, прокладываю курс к ответу.", "Слышу вас. Собираю информацию.",
        "Понял задачу. Работаю.", "Запрос принят, ищу ответ.", "Так точно. Сканирую базы.",
        "Капитан, дайте мне пару секунд.", "Обрабатываю. Не отключайтесь.",
        "Принял. Подключаю вычислительные модули.", "Хороший вопрос, капитан. Анализирую.",
        "Сигнал получен. Расшифровываю.", "Есть контакт. Готовлю ответ.",
        "Понял вас. Сверяю звёздные карты.", "Минутку. Запрашиваю бортовой компьютер.",
        "Принято к исполнению. Думаю.", "Капитан, уже работаю над этим.",
        "Слушаю и анализирую.", "Запрос в обработке, капитан.", "Принял. Считаю варианты.",
        "Ясно. Прогоняю через анализатор.", "Секунду, формулирую ответ.",
        "Понял. Связываюсь с центром данных.", "Есть, капитан. Изучаю вопрос.",
        "Принято. Включаю дальний радар.", "Капитан, ответ уже в пути.",
        "Так. Собираю данные по вашему запросу.", "Понял. Ещё мгновение.",
        "Вас слышу. Обрабатываю сигнал.",
    ],
    "uk": [
        "Прийняв, капітане, аналізую.", "Секунду, капітане, звіряюся з даними.",
        "Вас зрозумів. Обробляю запит.", "Є, капітане. Думаю.", "Прийнято. Запускаю аналіз.",
        "Хвилинку, капітане, прокладаю курс до відповіді.", "Чую вас. Збираю інформацію.",
        "Зрозумів завдання. Працюю.", "Запит прийнято, шукаю відповідь.", "Так точно. Сканую бази.",
        "Капітане, дайте мені кілька секунд.", "Обробляю. Не відключайтеся.",
        "Прийняв. Підключаю обчислювальні модулі.", "Гарне питання, капітане. Аналізую.",
        "Сигнал отримано. Розшифровую.", "Є контакт. Готую відповідь.",
        "Зрозумів вас. Звіряю зоряні мапи.", "Хвилинку. Запитую бортовий комп'ютер.",
        "Прийнято до виконання. Думаю.", "Капітане, вже працюю над цим.",
        "Слухаю та аналізую.", "Запит в обробці, капітане.", "Прийняв. Рахую варіанти.",
        "Ясно. Проганяю через аналізатор.", "Секунду, формулюю відповідь.",
        "Зрозумів. Зв'язуюся з центром даних.", "Є, капітане. Вивчаю питання.",
        "Прийнято. Вмикаю далекий радар.", "Капітане, відповідь уже в дорозі.",
        "Так. Збираю дані за вашим запитом.", "Зрозумів. Ще мить.",
        "Чую вас. Обробляю сигнал.",
    ],
    "en": [
        "Copy that, captain, analyzing.", "One moment, captain, checking the data.",
        "Understood. Processing your request.", "Aye, captain. Thinking.", "Roger. Starting analysis.",
        "Stand by, captain, plotting a course to the answer.", "I hear you. Gathering information.",
        "Task received. Working on it.", "Request accepted, searching for an answer.",
        "Affirmative. Scanning the databases.", "Captain, give me a few seconds.",
        "Processing. Stay on the line.", "Copy. Bringing the compute modules online.",
        "Good question, captain. Analyzing.", "Signal received. Decoding.",
        "Contact established. Preparing a reply.", "Understood. Checking the star charts.",
        "Just a moment. Querying the ship's computer.", "Acknowledged. Thinking it through.",
        "Captain, I'm already on it.", "Listening and analyzing.", "Request in progress, captain.",
        "Copy. Weighing the options.", "Clear. Running it through the analyzer.",
        "One second, putting the answer together.", "Understood. Contacting the data center.",
        "Aye, captain. Looking into it.", "Roger. Switching on long-range radar.",
        "Captain, the answer is on its way.", "Right. Collecting data on your request.",
        "Got it. Just a moment more.", "I read you. Processing the signal.",
    ],
    "de": [
        "Verstanden, Kapitän, ich analysiere.", "Einen Moment, Kapitän, ich prüfe die Daten.",
        "Verstanden. Ich bearbeite die Anfrage.", "Jawohl, Kapitän. Ich denke nach.",
        "Empfangen. Analyse läuft.", "Moment, Kapitän, ich setze Kurs auf die Antwort.",
        "Ich höre Sie. Sammle Informationen.", "Aufgabe verstanden. Ich arbeite daran.",
        "Anfrage angenommen, suche die Antwort.", "Jawohl. Durchsuche die Datenbanken.",
        "Kapitän, geben Sie mir ein paar Sekunden.", "In Bearbeitung. Bleiben Sie dran.",
        "Verstanden. Schalte die Rechenmodule zu.", "Gute Frage, Kapitän. Ich analysiere.",
        "Signal empfangen. Entschlüssele.", "Kontakt hergestellt. Bereite die Antwort vor.",
        "Verstanden. Prüfe die Sternkarten.", "Einen Augenblick. Frage den Bordcomputer.",
        "Bestätigt. Ich denke nach.", "Kapitän, ich bin schon dabei.",
        "Ich höre zu und analysiere.", "Anfrage wird bearbeitet, Kapitän.",
        "Verstanden. Wäge die Optionen ab.", "Klar. Schicke es durch den Analysator.",
        "Eine Sekunde, ich formuliere die Antwort.", "Verstanden. Kontaktiere das Datenzentrum.",
        "Jawohl, Kapitän. Ich prüfe die Frage.", "Empfangen. Schalte das Fernradar ein.",
        "Kapitän, die Antwort ist unterwegs.", "Gut. Sammle Daten zu Ihrer Anfrage.",
        "Verstanden. Noch einen Moment.", "Ich höre Sie. Verarbeite das Signal.",
    ],
}

_last: dict[str, str] = {}


def pick_filler(lang: str, last: str | None = None, rng: random.Random | None = None) -> str:
    """Случайная фраза-заглушка языка lang, никогда не та же, что в прошлый раз."""
    pool = FILLERS.get(lang) or FILLERS["en"]
    prev = _last.get(lang) if last is None else last
    choices = [p for p in pool if p != prev] or pool
    phrase = (rng or random).choice(choices)
    _last[lang] = phrase
    return phrase


def wav_seconds(path) -> float:
    try:
        with wave.open(str(path), "rb") as w:
            return w.getnframes() / float(w.getframerate() or 1)
    except (OSError, wave.Error, EOFError):
        return 0.0


def ui_lang() -> str:
    try:
        from stamina import i18n
        lang = i18n.language()
    except Exception:  # noqa: BLE001
        lang = "ru"
    return lang if lang in FILLERS else "en"


def pick_agent() -> dict:
    """Агент текущего пилота, иначе агент Ориона по умолчанию."""
    from stamina import orion
    try:
        from stamina import agent_dialog, pilots
        p = pilots.active()
        pid = (p or {}).get("id") if isinstance(p, dict) else getattr(p, "id", None)
        if pid:
            rec = agent_dialog.agent_for_pilot(pid)
            if rec:
                return rec
    except Exception:  # noqa: BLE001
        pass
    return orion.active()


def ask_agent(rec: dict, text: str):
    """Запрос агенту (блокирует — из потока). Возвращает Result orion.run_profile."""
    from stamina import orion
    profile = orion.profile_for(rec, "orion-recon")
    session = None
    try:
        session = orion.profile_session(rec["id"], profile)
    except Exception:  # noqa: BLE001
        session = None
    return orion.run_profile(rec, text, profile=profile, session=session)


class VoiceCall:
    """Состояния: idle → listening → thinking → speaking → idle.

    on_state(state, text) — показать статус (кнопка ОРИОН в шапке).
    Зависимости подменяются в тестах: listener_factory, ask, tts, remember.
    """

    POLL_MS = 120

    def __init__(self, root, on_state=None, *, listener_factory=None, ask=None,
                 tts=None, remember=None, agent=None, lang=None):
        self.root = root
        self.on_state = on_state or (lambda s, t="": None)
        self._listener_factory = listener_factory
        self._ask = ask or ask_agent
        self._tts = tts
        self._remember = remember
        self._agent = agent or pick_agent
        self._lang = lang or ui_lang
        self.state = "idle"
        self.listener = None
        self.rec: dict | None = None
        self._gen = 0                 # номер вызова: ответ отменённого вызова молча в историю
        self._q: queue.Queue = queue.Queue()
        self._filler_until = 0.0
        self._next_filler: dict[tuple, str] = {}

    # --- зависимости по умолчанию ---
    def _tts_mod(self):
        if self._tts is None:
            from stamina.voice import tts
            self._tts = tts
        return self._tts

    def _save(self, role: str, text: str, session=None) -> None:
        try:
            if self._remember is not None:
                self._remember(self.rec["id"], role, text, session=session)
            else:
                from stamina import orion
                orion.remember(self.rec["id"], role, text, session=session, kind="voice")
        except Exception:  # noqa: BLE001
            pass

    def _set(self, state: str, text: str = "") -> None:
        self.state = state
        try:
            self.on_state(state, text)
        except Exception:  # noqa: BLE001
            pass

    def active(self) -> bool:
        return self.state != "idle"

    # --- управление ---
    def toggle(self) -> None:
        """Кнопка ОРИОН / Home: начать вызов или отменить текущий."""
        if self.state == "idle":
            self.start()
        else:
            self.cancel()

    def start(self) -> bool:
        from stamina import i18n
        tr = i18n.t
        self.rec = self._agent()
        self._gen += 1
        try:
            self.listener = self._make_listener()
            ok = self.listener.start() if self.listener is not None else False
        except Exception:  # noqa: BLE001
            ok = False
        if not ok:
            self.listener = None
            self._set("idle")
            self._error(tr("Микрофон недоступен: нет модели распознавания речи"))
            return False
        self._set("listening")
        self._prepare_filler()
        self.root.after(self.POLL_MS, self._poll_mic, self._gen)
        return True

    def _make_listener(self):
        if self._listener_factory is not None:
            return self._listener_factory(self._lang())
        from stamina.voice import stt
        model = stt.find_model(prefer=self._lang())
        if not model:
            return None
        return stt.Listener(model_path=model, silence_sec=1.6, max_sec=40, idle_sec=10)

    def cancel(self) -> None:
        """Отмена: слушает — выкинуть фразу; думает — ответ уйдёт только в историю; говорит — замолчать."""
        self._gen += 1
        if self.listener is not None:
            try:
                self.listener.stop()
            except Exception:  # noqa: BLE001
                pass
            self.listener = None
        try:
            self._tts_mod().stop()
        except Exception:  # noqa: BLE001
            pass
        self._set("idle")

    # --- микрофон ---
    def _poll_mic(self, gen: int) -> None:
        if gen != self._gen or self.listener is None:
            return
        text, finished, err = "", False, ""
        try:
            events = self.listener.poll()
        except Exception:  # noqa: BLE001
            events, finished = [], True
        for ev in events:
            kind, val = (ev[0], ev[1]) if isinstance(ev, tuple) else (ev, "")
            val = str(val or "") if kind in ("final", "error") else ""
            if kind == "final":
                text = (text + " " + val).strip()
                finished = True       # одна фраза на вызов: тишина её закрыла
            elif kind == "error":
                err = val or "mic"
                finished = True
            elif kind == "done":
                finished = True
        if text or finished:
            try:
                self.listener.stop()
            except Exception:  # noqa: BLE001
                pass
            self.listener = None
            if text:
                self._send(text)
            else:
                from stamina import i18n
                self._set("idle")
                self._error(i18n.t("Не расслышал вопрос") if not err else i18n.t("Ошибка микрофона"))
            return
        self.root.after(self.POLL_MS, self._poll_mic, gen)

    # --- заглушка ---
    def _voice(self) -> str:
        return str((self.rec or {}).get("tts_voice") or "")

    def _prepare_filler(self) -> None:
        """Пока пилот говорит — заранее отрисовать следующую фразу в WAV (в потоке)."""
        lang, voice = self._lang(), self._voice()
        key = (lang, voice)
        if key in self._next_filler:
            return
        phrase = pick_filler(lang)
        self._next_filler[key] = phrase
        tts = self._tts_mod()
        if hasattr(tts, "render"):
            threading.Thread(target=lambda: tts.render(phrase, voice=voice, lang=lang, role="dev"),
                             daemon=True).start()

    def _play_filler(self) -> None:
        lang, voice = self._lang(), self._voice()
        phrase = self._next_filler.pop((lang, voice), None) or pick_filler(lang)
        tts = self._tts_mod()
        self._filler_until = 0.0
        played = False
        if hasattr(tts, "play_cached"):
            try:
                played = tts.play_cached(phrase, voice=voice, lang=lang, role="dev")
            except Exception:  # noqa: BLE001
                played = False
        if played and hasattr(tts, "cache_path"):
            self._filler_until = time.monotonic() + wav_seconds(
                tts.cache_path(phrase, voice=voice, lang=lang, role="dev"))
        elif not played:
            try:
                tts.speak(phrase, voice=voice, lang=lang, role="dev")
            except Exception:  # noqa: BLE001
                pass
        self._prepare_filler()   # следующая фраза — уже другая, рисуем впрок

    # --- агент ---
    def _send(self, text: str) -> None:
        gen = self._gen
        self._save("pilot", text)
        self._set("thinking", text)
        self._play_filler()
        rec = self.rec

        def work():
            try:
                res = self._ask(rec, text)
            except Exception as exc:  # noqa: BLE001
                res = exc
            self._q.put((gen, res))

        threading.Thread(target=work, daemon=True).start()
        self.root.after(self.POLL_MS, self._poll_answer)

    def _poll_answer(self) -> None:
        try:
            gen, res = self._q.get_nowait()
        except queue.Empty:
            self.root.after(self.POLL_MS, self._poll_answer)
            return
        self._on_answer(gen, res)

    def _on_answer(self, gen: int, res) -> None:
        reply = "" if isinstance(res, Exception) else str(getattr(res, "reply", "") or "").strip()
        if reply:
            self._save("orion", reply, session=getattr(res, "session", None))
        else:
            err = self._error_text(res)
            self._save("system", err)
        if gen != self._gen:
            return                    # вызов отменён: ответ лишь в истории
        if not reply:
            self._set("idle")
            self._error(err)
            return
        wait = max(0.0, self._filler_until - time.monotonic())
        self._set("speaking", reply)
        self.root.after(int(wait * 1000) + 50, self._speak_reply, gen, reply)

    def _speak_reply(self, gen: int, reply: str) -> None:
        if gen != self._gen:
            return
        try:
            self._tts_mod().speak(reply, voice=self._voice(), role="dev")
        except Exception:  # noqa: BLE001
            self._set("idle")
            return
        self.root.after(600, self._poll_speaking, gen)

    def _poll_speaking(self, gen: int) -> None:
        if gen != self._gen:
            return
        try:
            busy = self._tts_mod().speaking()
        except Exception:  # noqa: BLE001
            busy = False
        if busy:
            self.root.after(300, self._poll_speaking, gen)
        else:
            self._set("idle")

    # --- ошибки ---
    @staticmethod
    def _error_text(res) -> str:
        from stamina import i18n
        if isinstance(res, Exception):
            return i18n.t("Агент не ответил: ошибка запуска")
        try:
            from stamina.orion_screen import OrionScreen
            txt = OrionScreen._error_text(None, res)
            if txt:
                return txt
        except Exception:  # noqa: BLE001
            pass
        return i18n.t("Агент не ответил")

    def _error(self, text: str) -> None:
        self._set("error", text)
        try:
            self._tts_mod().speak(text, voice=self._voice(), role="dev")
        except Exception:  # noqa: BLE001
            pass
        gen = self._gen
        self.root.after(3500, lambda: self.state == "error" and gen == self._gen and self._set("idle"))
