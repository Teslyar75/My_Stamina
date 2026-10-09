"""«UPLINK» — перевод текущего предложения через интернет.

* Запросы идут в фоновом потоке, поэтому печать никогда не тормозит.
* Сначала бесплатный Google Translate (без ключа), запасной вариант —
  MyMemory. Оба работают через стандартный ``urllib``.
* Направление: язык книги определяется сам (stamina.langdetect, без сети) или берётся из
  библиотеки; язык перевода — настройка «UPLINK: перевод на» (по умолчанию язык интерфейса).
  Кэш отдельный для каждой пары языков (ключ «de|ru|фраза»).
* Без интернета переводятся только уже встречавшиеся фразы (из кэша) — офлайн-переводчика нет.
* Все переводы кэшируются в JSON (``cache/translations.json`` в папке
  программы), так что уже встречавшиеся предложения работают без сети.

Адаптированный текст тренажёра не содержит знаков препинания, поэтому
границы предложений берутся из оригинального текста (если он сохранён),
иначе текст режется на куски по ~14 слов.
"""

from __future__ import annotations

from stamina.i18n import t

import bisect
import json
import queue
import re
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from stamina.storage import CACHE_DIR, DATA_DIR, write_json
from stamina.text_processing import adapt_for_typing

CHUNK_WORDS = 14
MAX_SOURCE_CHARS = 1200
TIMEOUT = 7
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) StarTyping/3.1"

_SENTENCE_RE = re.compile(r"(?<=[.!?…])[\"'»”)\]]*\s+")


# --- Разбиение на фрагменты --------------------------------------------------

class Segments:
    """Фрагменты адаптированного текста с исходным текстом для перевода."""

    def __init__(self, adapted: str, original: str | None = None, process=None) -> None:
        self._process = process or adapt_for_typing
        self.starts: list[int] = []
        self.ends: list[int] = []
        self.sources: list[str] = []
        self.from_original = False
        words = adapted.split(" ") if adapted else []
        offsets = []
        pos = 0
        for w in words:
            offsets.append(pos)
            pos += len(w) + 1
        if not words:
            return
        if original and self._from_original(adapted, original, words, offsets):
            self.from_original = True
            return
        for i in range(0, len(words), CHUNK_WORDS):
            chunk = words[i:i + CHUNK_WORDS]
            start = offsets[i]
            self._add(start, start + len(" ".join(chunk)), " ".join(chunk))

    def _add(self, start: int, end: int, source: str) -> None:
        self.starts.append(start)
        self.ends.append(end)
        self.sources.append(source[:MAX_SOURCE_CHARS])

    def _from_original(self, adapted, original, words, offsets) -> bool:
        process = self._process
        if process(original) != adapted:
            return False
        flat = " ".join(original.split())
        sentences = [s.strip() for s in _SENTENCE_RE.split(flat) if s.strip()]
        if len(sentences) < 2 and len(words) > CHUNK_WORDS * 2:
            return False  # в оригинале нет знаков конца предложения
        counts = [len(process(s).split()) for s in sentences]
        if sum(counts) != len(words):
            return False
        wi = 0
        for sentence, n in zip(sentences, counts):
            if n == 0:
                continue
            start = offsets[wi]
            last = wi + n - 1
            end = offsets[last] + len(words[last])
            if n <= 2 and self.starts:      # «Ok?», «e.g.» — приклеиваем к предыдущему
                self.ends[-1] = end
                self.sources[-1] = (self.sources[-1] + " " + sentence)[:MAX_SOURCE_CHARS]
            else:
                self._add(start, end, sentence)
            wi += n
        return True

    def __len__(self) -> int:
        return len(self.starts)

    def index_at(self, char_index: int) -> int | None:
        if not self.starts:
            return None
        i = bisect.bisect_right(self.starts, char_index) - 1
        return max(0, min(i, len(self.starts) - 1))


# --- Сетевой переводчик ------------------------------------------------------

def _google(text: str, sl: str, tl: str) -> str:
    url = ("https://translate.googleapis.com/translate_a/single?client=gtx&dt=t"
           f"&sl={sl}&tl={tl}&q={urllib.parse.quote(text)}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    parts = [p[0] for p in (data[0] or []) if p and p[0]]
    result = "".join(parts).strip()
    if not result:
        raise ValueError(t("пустой ответ"))
    return result


def _mymemory(text: str, sl: str, tl: str) -> str:
    url = ("https://api.mymemory.translated.net/get?"
           + urllib.parse.urlencode({"q": text[:480], "langpair": f"{sl}|{tl}"}))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    result = (data.get("responseData") or {}).get("translatedText") or ""
    if int(data.get("responseStatus", 200)) != 200 or "MYMEMORY WARNING" in result.upper():
        raise ValueError(t("лимит MyMemory"))
    if not result.strip():
        raise ValueError(t("пустой ответ"))
    return result.strip()


TARGETS = ("ru", "uk", "en", "de")


def default_target() -> str:
    """Язык перевода по умолчанию — язык интерфейса (если это ru/uk/en/de)."""
    from stamina import i18n
    lang = i18n.language()
    return lang if lang in TARGETS else "ru"


def direction(text_lang: str, target: str | None = None) -> tuple[str, str]:
    """(язык источника, язык перевода). Неизвестный язык → auto (определит Google).
    Если книга уже на языке перевода: русский/украинский текст → английский, остальное → русский."""
    sl = text_lang if text_lang and text_lang != "und" else "auto"
    tl = target if target in TARGETS else default_target()
    if sl == tl:
        tl = "en" if sl in ("ru", "uk", "be") else "ru"
    return sl, tl


def _cache_path() -> Path:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        probe = CACHE_DIR / ".probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return CACHE_DIR / "translations.json"
    except OSError:
        return DATA_DIR / "translations.json"


class Translator:
    """Перевод с кэшем. ``request`` — из GUI-потока, ``poll`` — тоже."""

    def __init__(self) -> None:
        self.path = _cache_path()
        try:
            self.cache: dict[str, str] = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            self.cache = {}
        self._jobs: queue.Queue = queue.Queue()
        self._results: queue.Queue = queue.Queue()
        self._pending: set[str] = set()
        self._dirty = False
        self._last_save = time.monotonic()
        self.online: bool | None = None   # None — ещё не проверяли
        self._offline_until = 0.0
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    @staticmethod
    def key(text: str, sl: str, tl: str) -> str:
        return f"{sl}|{tl}|{text}"

    def cached(self, text: str, sl: str, tl: str) -> str | None:
        return self.cache.get(self.key(text, sl, tl))

    def request(self, text: str, sl: str, tl: str) -> None:
        k = self.key(text, sl, tl)
        if k in self.cache or k in self._pending:
            return
        self._pending.add(k)
        self._jobs.put((k, text, sl, tl))

    def poll(self) -> list[tuple[str, str | None]]:
        """Готовые результаты: (ключ, перевод или None при ошибке)."""
        out = []
        while True:
            try:
                k, result = self._results.get_nowait()
            except queue.Empty:
                break
            self._pending.discard(k)
            if result is not None:
                self.cache[k] = result
                self._dirty = True
                self.online = True
            else:
                self.online = False
            out.append((k, result))
        if self._dirty and time.monotonic() - self._last_save > 10:
            self.save()
        return out

    def save(self) -> None:
        if self._dirty:
            write_json(self.path, self.cache)
            self._dirty = False
            self._last_save = time.monotonic()

    def _worker(self) -> None:
        while True:
            k, text, sl, tl = self._jobs.get()
            # После неудачи не долбим сеть каждую секунду.
            wait = self._offline_until - time.monotonic()
            if wait > 0:
                time.sleep(min(wait, 15))
            result = None
            for backend in ((_google,) if sl == "auto" else (_google, _mymemory)):
                try:
                    result = backend(text, sl, tl)
                    break
                except Exception:  # сеть, лимиты, неожиданный ответ
                    continue
            self._offline_until = 0.0 if result else time.monotonic() + 15
            self._results.put((k, result))
