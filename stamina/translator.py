"""«UPLINK» — перевод через интернет (фоновые потоки, кэш, приоритеты).

* 2 воркера + приоритетная очередь: текущее слово/страница не ждут хвост prefetch.
* Группы запросов (rsvp / book): устаревшие можно отменить, не засоряя сеть.
* Backoff при 429/ошибках — короткий, с паузой между вызовами (не «заморозка» на 15 с).
* Кэш: cache/translations.json (или DATA_DIR).
"""

from __future__ import annotations

from stamina.i18n import t

import bisect
import json
import queue
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from stamina.storage import CACHE_DIR, DATA_DIR, write_json
from stamina.text_processing import adapt_for_typing

CHUNK_WORDS = 14
MAX_SOURCE_CHARS = 900
TIMEOUT = 5
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) StarTyping/3.1"
WORKERS = 1              # один поток — меньше 429 от Google
MIN_GAP = 0.45          # мин. пауза между сетевыми вызовами (анти-429)
MAX_BACKOFF = 8.0
MAX_QUEUE = 48          # сверх — дропаем низкий приоритет при постановке
MAX_RETRIES = 3

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
            return False
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
            if n <= 2 and self.starts:
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
    from stamina import i18n
    lang = i18n.language()
    return lang if lang in TARGETS else "ru"


def direction(text_lang: str, target: str | None = None) -> tuple[str, str]:
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
    """Перевод с кэшем. ``request`` / ``poll`` — из GUI-потока."""

    def __init__(self) -> None:
        self.path = _cache_path()
        try:
            self.cache: dict[str, str] = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            self.cache = {}
        self._jobs: queue.PriorityQueue = queue.PriorityQueue()
        self._results: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._seq = 0
        self._alive: set[str] = set()          # ключи, которые ещё нужны
        self._groups: dict[str, str] = {}      # key -> group
        self._pending_n = 0
        self._dirty = False
        self._last_save = time.monotonic()
        self.online: bool | None = None
        self._next_net = 0.0                   # когда можно следующий HTTP
        self._fail_streak = 0
        self._net_lock = threading.Lock()
        for i in range(WORKERS):
            threading.Thread(target=self._worker, name=f"uplink-{i}", daemon=True).start()

    @staticmethod
    def key(text: str, sl: str, tl: str) -> str:
        return f"{sl}|{tl}|{text}"

    def cached(self, text: str, sl: str, tl: str) -> str | None:
        return self.cache.get(self.key(text, sl, tl))

    def request(self, text: str, sl: str, tl: str, *,
                priority: int = 5, group: str = "default") -> None:
        """Поставить перевод в очередь. priority: 0 — срочно, 9 — prefetch."""
        src = (text or "").strip()
        if not src:
            return
        if len(src) > MAX_SOURCE_CHARS:
            src = src[:MAX_SOURCE_CHARS]
        k = self.key(src, sl, tl)
        with self._lock:
            if k in self.cache:
                return
            if k in self._alive:
                # уже в очереди — можно повысить приоритет новым job с меньшим priority
                self._groups[k] = group
            else:
                if self._pending_n >= MAX_QUEUE and priority >= 5:
                    return  # не раздуваем хвост prefetch
                self._alive.add(k)
                self._groups[k] = group
                self._pending_n += 1
            self._seq += 1
            seq = self._seq
        self._jobs.put((int(priority), seq, k, src, sl, tl, 0))

    def cancel_group(self, group: str, keep: set[str] | None = None) -> None:
        """Отменить незавершённые запросы группы (кроме keep)."""
        keep = keep or set()
        with self._lock:
            dead = [k for k, g in self._groups.items()
                    if g == group and k not in keep and k not in self.cache]
            for k in dead:
                self._alive.discard(k)
                self._groups.pop(k, None)

    def inflight(self, group: str | None = None) -> int:
        """Сколько ключей ещё ждут ответа (опционально по группе)."""
        with self._lock:
            if group is None:
                return len(self._alive)
            return sum(1 for k, g in self._groups.items() if g == group and k in self._alive)

    def poll(self) -> list[tuple[str, str | None]]:
        out = []
        while True:
            try:
                k, result = self._results.get_nowait()
            except queue.Empty:
                break
            with self._lock:
                self._alive.discard(k)
                self._groups.pop(k, None)
                self._pending_n = max(0, self._pending_n - 1)
                if result is not None:
                    self.cache[k] = result
                    self._dirty = True
                    self.online = True
                    self._fail_streak = 0
                else:
                    self.online = False
            out.append((k, result))
        if self._dirty and time.monotonic() - self._last_save > 20:
            # сохранение в фоне — не блокировать GUI на большом JSON
            threading.Thread(target=self.save, daemon=True).start()
        return out

    def save(self) -> None:
        with self._lock:
            if not self._dirty:
                return
            data = dict(self.cache)
            self._dirty = False
            self._last_save = time.monotonic()
        try:
            write_json(self.path, data)
        except OSError:
            with self._lock:
                self._dirty = True

    def _throttle(self) -> None:
        """Общий темп + backoff после ошибок (без удержания job на 15 с)."""
        with self._net_lock:
            now = time.monotonic()
            wait = self._next_net - now
            if wait > 0:
                time.sleep(wait)
            self._next_net = time.monotonic() + MIN_GAP

    def _on_fail(self, rate_limited: bool) -> None:
        with self._lock:
            self._fail_streak += 1
            streak = self._fail_streak
        delay = min(MAX_BACKOFF, (0.8 if rate_limited else 0.4) * (1.6 ** min(streak, 6)))
        with self._net_lock:
            self._next_net = max(self._next_net, time.monotonic() + delay)

    def _worker(self) -> None:
        while True:
            item = self._jobs.get()
            if len(item) == 6:
                _prio, _seq, k, text, sl, tl = item
                retries = 0
            else:
                _prio, _seq, k, text, sl, tl, retries = item
            with self._lock:
                if k in self.cache:
                    continue  # уже в кэше — pending снял poll
                if k not in self._alive:
                    self._pending_n = max(0, self._pending_n - 1)
                    continue
            self._throttle()
            with self._lock:
                if k in self.cache:
                    continue
                if k not in self._alive:
                    self._pending_n = max(0, self._pending_n - 1)
                    continue
            result = None
            rate_limited = False
            backends = (_google,) if sl == "auto" else (_google, _mymemory)
            for backend in backends:
                try:
                    result = backend(text, sl, tl)
                    break
                except urllib.error.HTTPError as e:
                    rate_limited = rate_limited or (e.code == 429)
                    continue
                except Exception:
                    continue
            if result is None:
                self._on_fail(rate_limited)
                if retries < MAX_RETRIES:
                    # ещё попытка — не отдаём None в GUI
                    with self._lock:
                        if k not in self._alive:
                            self._pending_n = max(0, self._pending_n - 1)
                            continue
                        self._seq += 1
                        seq = self._seq
                    self._jobs.put((_prio + 1, seq, k, text, sl, tl, retries + 1))
                    continue
            self._results.put((k, result))
