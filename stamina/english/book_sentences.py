"""Карточки предложений из прочитанных английских книг (библиотека / скорочтение).

Только предложения до позиции чтения. Практика: русский → английский (как примеры на складе).
Прогресс и переводы кэшируются в english.json → book_sentences.
"""
from __future__ import annotations

from stamina.i18n import t as _t

import hashlib
import re
import time

from . import sm2

MIN_WORDS = 4
FLIP_OK = 60
MAX_REQUEST = 48
_WS = re.compile(r"\s+")


def ensure_store(progress) -> dict:
    store = progress.data.setdefault(
        "book_sentences",
        {"books": {}, "cards": {}, "stats": {"flips": 0, "ok": 0, "by_day": {}}},
    )
    store.setdefault("books", {})
    store.setdefault("cards", {})
    store.setdefault("stats", {"flips": 0, "ok": 0, "by_day": {}})
    st = store["stats"]
    st.setdefault("flips", 0)
    st.setdefault("ok", 0)
    st.setdefault("by_day", {})
    return store


def _sid(tid: str, w0: int) -> str:
    return f"{tid}:{w0}"


def _hash_en(en: str) -> str:
    return hashlib.sha1(en.encode("utf-8")).hexdigest()[:12]


def extract_sentences(text: str, word_pos: int) -> list[dict]:
    """Предложения, полностью прочитанные к слову word_pos (включительно)."""
    from stamina.speedread import rsvp

    words = rsvp.tokenize(text or "")
    if not words:
        return []
    limit = max(0, min(int(word_pos), len(words) - 1))
    out: list[dict] = []
    i = 0
    ord_i = 0
    while i <= limit:
        start = i
        while i < len(words) and not words[i].sent_end:
            i += 1
        if i >= len(words):
            break
        end = i
        if end > limit:
            break
        en = _WS.sub(" ", text[words[start].start:words[end].end]).strip()
        n_words = len(en.split())
        if n_words >= MIN_WORDS and len(en) >= 12:
            out.append({
                "i": ord_i,
                "en": en,
                "w0": start,
                "w1": end,
                "hash": _hash_en(en),
            })
        ord_i += 1
        i = end + 1
    return out


def reading_word(lib, tid: str) -> int:
    m = lib.meta(tid)
    if not m:
        return 0
    return int(m.get("positions", {}).get("reading", {}).get("word", 0) or 0)


# tid -> (позиция, длина текста, хэш начала): книга не менялась - не пересобираем
_SYNC_MEMO: dict[str, tuple] = {}


def _sig(pos: int, text: str) -> tuple:
    """Подпись состояния книги, стабильная между запусками (hash() строки - нет)."""
    return (int(pos), len(text), hashlib.sha1(text[:512].encode("utf-8", "replace")).hexdigest()[:12])


def warm_up(lib) -> None:
    """Тяжёлая часть sync_all без записи в прогресс: извлечь предложения всех книг
    в кэш _EXTRACT (можно звать из фонового потока)."""
    for m in lib.all():
        try:
            tid = m["id"]
            lang = (m.get("lang") or "").lower()
            if lang and lang != "en":
                continue
            text = lib.reading_text(tid)
            if not text or not text.strip():
                continue
            pos = reading_word(lib, tid)
            key = (tid,) + _sig(pos, text)
            if _SYNC_MEMO.get(tid) == key[1:] or key in _EXTRACT:
                continue
            if key not in _EXTRACT:
                _EXTRACT[key] = extract_sentences(text, pos)
        except Exception:  # noqa: BLE001 - прогрев не обязателен
            pass


_EXTRACT: dict[tuple, list] = {}


def sync_book(progress, lib, tid: str, *, save: bool = True, changed: list | None = None) -> dict | None:
    """Обновить список предложений книги по позиции чтения. Возвращает запись книги."""
    m = lib.meta(tid)
    if not m:
        return None
    lang = (m.get("lang") or "").lower()
    if lang and lang != "en":
        return None
    text = lib.reading_text(tid)
    if not text or not text.strip():
        return None
    # без явного lang — только если текст похож на английский
    if not lang:
        from stamina.langdetect import detect
        if detect(text[:4000]) != "en":
            return None

    pos = reading_word(lib, tid)
    store = ensure_store(progress)
    sig = _sig(pos, text)
    if _SYNC_MEMO.get(tid) == sig and tid in store["books"]:
        return store["books"][tid]
    cached = store["books"].get(tid)
    if cached and tuple(cached.get("sig") or ()) == sig:
        # постоянный кэш в english.json: книга и позиция не менялись - не токенизируем заново
        _SYNC_MEMO[tid] = sig
        return cached
    extracted = _EXTRACT.pop((tid,) + sig, None)
    if extracted is None:
        extracted = extract_sentences(text, pos)
    old = store["books"].get(tid) or {}
    old_by_w0 = {int(s["w0"]): s for s in old.get("sentences") or [] if "w0" in s}

    sentences = []
    for s in extracted:
        prev = old_by_w0.get(s["w0"])
        sid = _sid(tid, s["w0"])
        sentences.append({
            "id": sid,
            "i": s["i"],
            "en": s["en"],
            "ru": (prev.get("ru") if prev and prev.get("en") == s["en"] else "") or "",
            "w0": s["w0"],
            "w1": s["w1"],
            "hash": s["hash"],
        })

    book = {
        "id": tid,
        "title": m.get("title") or _t("Без названия"),
        "author": m.get("author") or "",
        "word_pos": pos,
        "updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "sig": list(sig),
        "sentences": sentences,
    }
    store["books"][tid] = book
    if save:
        progress.save()
    elif changed is not None:
        changed.append(tid)
    _SYNC_MEMO[tid] = sig
    return book


def sync_all(progress, lib) -> tuple[int, int]:
    """Синхронизировать все английские книги. → (книг, предложений)."""
    books_n = sent_n = 0
    changed: list = []
    for m in lib.all():
        tid = m["id"]
        book = sync_book(progress, lib, tid, save=False, changed=changed)
        if book:
            books_n += 1
            sent_n += len(book["sentences"])
    if changed:
        progress.save()       # одна запись на всю синхронизацию, а не по книге
    return books_n, sent_n


_BG: dict[int, list] = {}


def busy(progress) -> bool:
    """Идёт ли фоновая синхронизация для этого прогресса."""
    return id(progress) in _BG


def sync_in_background(widget, progress, lib_factory, on_done=None, *, tid: str | None = None,
                       translator=None, tl: str = "ru", poll_ms: int = 60) -> bool:
    """Синхронизация без зависания окна.

    Тяжёлое (чтение и токенизация книг) - в потоке; запись в прогресс, переводы из кэша
    и колбэк on_done(books_n, sent_n) - в главном потоке через widget.after().
    Повторный вызов во время работы только добавляет колбэк. → True, если запущено сейчас.
    """
    key = id(progress)
    if key in _BG:
        if on_done is not None:
            _BG[key].append(on_done)
        return False
    _BG[key] = [on_done] if on_done is not None else []
    import threading
    box: dict = {}

    def work() -> None:
        try:
            lib = lib_factory()
            box["lib"] = lib
            warm_up(lib)
        except Exception as e:  # noqa: BLE001
            box["err"] = e

    th = threading.Thread(target=work, name="book-sentences-sync", daemon=True)
    th.start()

    def finish() -> None:
        books_n = sent_n = 0
        try:
            lib = box.get("lib")
            if lib is not None:
                books_n, sent_n = sync_all(progress, lib)
                if tid:
                    b = sync_book(progress, lib, tid)
                    if b:
                        sent_n = max(sent_n, len(b.get("sentences") or []))
                if translator is not None:
                    fill_ru_from_cache(progress, translator, tl)
                    request_missing_ru(progress, translator, tl)
        except Exception:  # noqa: BLE001
            pass
        for cb in _BG.pop(key, []):
            try:
                cb(books_n, sent_n)
            except Exception:  # noqa: BLE001
                pass

    def wait() -> None:
        if th.is_alive():
            try:
                widget.after(poll_ms, wait)
            except Exception:  # noqa: BLE001 - виджет закрыт
                _BG.pop(key, None)
            return
        finish()

    widget.after(poll_ms, wait)
    return True


def uplink_tl(app) -> str:
    try:
        return (app.store.settings.get("uplink_target") or "ru").lower()
    except Exception:
        return "ru"


def fill_ru_from_cache(progress, translator, tl: str = "ru") -> int:
    """Подставить переводы из кэша UPLINK. → сколько заполнили."""
    if translator is None:
        return 0
    store = ensure_store(progress)
    n = 0
    for book in store["books"].values():
        for s in book.get("sentences") or []:
            if (s.get("ru") or "").strip():
                continue
            en = (s.get("en") or "").strip()
            if not en:
                continue
            hit = translator.cached(en, "en", tl)
            if hit:
                s["ru"] = hit.strip()
                n += 1
    if n:
        progress.save()
    return n


def request_missing_ru(progress, translator, tl: str = "ru", *, limit: int = MAX_REQUEST) -> int:
    """Поставить в очередь UPLINK недостающие RU. → сколько запросов."""
    if translator is None:
        return 0
    store = ensure_store(progress)
    n = 0
    for book in store["books"].values():
        for s in book.get("sentences") or []:
            if (s.get("ru") or "").strip():
                continue
            en = (s.get("en") or "").strip()
            if not en:
                continue
            if translator.cached(en, "en", tl):
                continue
            translator.request(en, "en", tl, priority=4, group="book_cards")
            n += 1
            if n >= limit:
                return n
    return n


def list_books(progress) -> list[dict]:
    store = ensure_store(progress)
    out = []
    for book in store["books"].values():
        sents = book.get("sentences") or []
        ready = sum(1 for s in sents if (s.get("ru") or "").strip())
        out.append({
            "id": book["id"],
            "title": book.get("title") or _t("Без названия"),
            "author": book.get("author") or "",
            "word_pos": int(book.get("word_pos") or 0),
            "total": len(sents),
            "ready": ready,
            "due": count_due(progress, book["id"]),
        })
    out.sort(key=lambda b: (b["title"].lower(), b["id"]))
    return out


def sentences_of(progress, tid: str) -> list[dict]:
    store = ensure_store(progress)
    book = store["books"].get(tid) or {}
    return list(book.get("sentences") or [])


def ready_sentences(progress, tid: str | None = None) -> list[dict]:
    """Предложения с RU, в порядке чтения."""
    store = ensure_store(progress)
    tids = [tid] if tid else list(store["books"])
    out = []
    for t in tids:
        book = store["books"].get(t)
        if not book:
            continue
        title = book.get("title") or ""
        for s in book.get("sentences") or []:
            if not (s.get("ru") or "").strip() or not (s.get("en") or "").strip():
                continue
            out.append({**s, "tid": t, "title": title})
    out.sort(key=lambda s: (s.get("tid", ""), int(s.get("i", 0)), int(s.get("w0", 0))))
    return out


def card_key(sent: dict) -> str:
    return sent.get("id") or _sid(sent.get("tid", "?"), int(sent.get("w0", 0)))


def get_card(progress, key: str) -> dict:
    store = ensure_store(progress)
    cards = store["cards"]
    if key not in cards:
        cards[key] = sm2.new_card(key)
    return cards[key]


def _is_due(card: dict | None, day: str) -> bool:
    if card is None:
        return True
    return (card.get("due") or day) <= day


def count_due(progress, tid: str | None = None) -> int:
    day = sm2.today()
    store = ensure_store(progress)
    cards = store["cards"]
    n = 0
    for s in ready_sentences(progress, tid):
        if _is_due(cards.get(card_key(s)), day):
            n += 1
    return n


def count_ready(progress) -> int:
    return len(ready_sentences(progress))


def build_queue(progress, tid: str | None = None, *, due_only: bool = True,
                limit: int = 40) -> list[dict]:
    """Очередь практики в порядке книги."""
    day = sm2.today()
    store = ensure_store(progress)
    cards = store["cards"]
    out = []
    for s in ready_sentences(progress, tid):
        if due_only and not _is_due(cards.get(card_key(s)), day):
            continue
        out.append(s)
        if len(out) >= limit:
            break
    return out


def grade(progress, sent: dict, q: int) -> dict:
    store = ensure_store(progress)
    key = card_key(sent)
    card = get_card(progress, key)
    store["cards"][key] = sm2.next_state(card, q)
    st = store["stats"]
    st["flips"] = int(st.get("flips", 0)) + 1
    if q >= 3:
        st["ok"] = int(st.get("ok", 0)) + 1
    day = sm2.today()
    by = st.setdefault("by_day", {})
    by[day] = int(by.get(day, 0)) + 1
    progress.save()
    return store["cards"][key]


_last_notify = 0.0


def notify_reading(app, lib, tid: str) -> None:
    """После сохранения позиции чтения — донабрать предложения (с троттлингом)."""
    global _last_notify
    now = time.monotonic()
    if now - _last_notify < 8.0:
        return
    if not tid or app is None or lib is None:
        return
    eng = None
    try:
        eng = (getattr(app, "screens", None) or {}).get("english")
    except Exception:
        eng = None
    progress = getattr(eng, "progress", None) if eng is not None else None
    if progress is None:
        return
    _last_notify = now
    try:
        book = sync_book(progress, lib, tid)
        if not book:
            return
        tr = None
        try:
            tr = app.get_translator()
        except Exception:
            tr = None
        tl = uplink_tl(app)
        fill_ru_from_cache(progress, tr, tl)
        request_missing_ru(progress, tr, tl, limit=16)
        if eng is not None and hasattr(eng, "changed"):
            eng.changed()
    except Exception:
        pass


def record_speech(progress, sent: dict, score: int) -> tuple[bool, int]:
    """Зачесть ответ голосом. → (ok, q для SM-2)."""
    ok = score >= FLIP_OK
    q = 5 if score >= 85 else 4 if score >= FLIP_OK else 2 if score >= 40 else 1
    grade(progress, sent, q)
    try:
        progress.add_xp(3 if ok else 1)
    except Exception:
        pass
    return ok, q
