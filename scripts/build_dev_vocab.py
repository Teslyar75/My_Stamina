"""Собрать словарь IT-терминов для собеседований из открытого датасета CodersLingo (CC BY 4.0).

Источник: https://coderslingo.com/downloads/coderslingo-1000-it-terms.json
Выход: stamina/english/data/vocab_dev.json

Запуск: python scripts/build_dev_vocab.py
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "stamina" / "english" / "data" / "vocab_dev.json"
RAW_CACHE = ROOT / "stamina" / "english" / "data" / "_coderslingo_raw.json"
SRC_URL = "https://coderslingo.com/downloads/coderslingo-1000-it-terms.json"

# Категории, полезные на собеседованиях (без emoji-статусов и vim-шорткатов).
# Порядок = приоритет в rank (сначала то, что чаще спрашивают на интервью).
CAT_PRIORITY = [
    "core-glossary", "paradigms", "design-patterns", "git-commands", "sql",
    "error-types", "observability", "http-status-codes", "docker", "kubernetes",
    "cloud-services", "cli-commands", "terraform", "http-headers",
    "regex-flags", "cli-flags",
]
INTERVIEW_CATS = set(CAT_PRIORITY)
SKIP_CATS = {"status-emoji", "keyboard-shortcuts"}

# Короткие RU-переводы, если MT вернул оригинал / пусто
RU_GLOSS = {
    "api": "API, программный интерфейс",
    "cache": "кэш",
    "backlog": "бэклог (очередь задач)",
    "commit": "коммит",
    "branch": "ветка",
    "merge": "слияние",
    "pull request": "пул-реквест",
    "deploy": "деплой, выкат",
    "deployment": "развёртывание",
    "container": "контейнер",
    "containerisation": "контейнеризация",
    "continuous integration": "непрерывная интеграция (CI)",
    "continuous delivery": "непрерывная доставка (CD)",
    "asynchronous": "асинхронный",
    "synchronous": "синхронный",
    "latency": "задержка (latency)",
    "throughput": "пропускная способность",
    "scalability": "масштабируемость",
    "idempotent": "идемпотентный",
    "refactoring": "рефакторинг",
    "deadlock": "взаимная блокировка",
    "race condition": "состояние гонки",
    "mutex": "мьютекс",
    "semaphore": "семафор",
    "heap": "куча",
    "stack": "стек",
    "queue": "очередь",
    "tree": "дерево",
    "graph": "граф",
    "hash": "хеш",
    "index": "индекс",
    "transaction": "транзакция",
    "rollback": "откат",
    "schema": "схема",
    "endpoint": "эндпоинт",
    "middleware": "промежуточный слой",
    "microservice": "микросервис",
    "monolith": "монолит",
    "load balancer": "балансировщик нагрузки",
    "blue-green deployment": "сине-зелёное развёртывание",
    "daemon": "демон (фоновый процесс)",
    "dependency injection": "внедрение зависимостей",
    "abstraction": "абстракция",
    "polymorphism": "полиморфизм",
    "encapsulation": "инкапсуляция",
    "inheritance": "наследование",
    "recursion": "рекурсия",
    "iteration": "итерация",
    "algorithm": "алгоритм",
    "complexity": "сложность (в т.ч. Big O)",
    "big o notation": "O-нотация (Big O)",
    "binary search": "бинарный поиск",
    "breadth-first search": "поиск в ширину (BFS)",
    "depth-first search": "поиск в глубину (DFS)",
    "singleton": "одиночка (Singleton)",
    "factory": "фабрика",
    "observer": "наблюдатель",
    "strategy": "стратегия",
    "adapter": "адаптер",
}


def fetch() -> list[dict]:
    if RAW_CACHE.exists():
        data = json.loads(RAW_CACHE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("terms"):
            return data["terms"]
    req = urllib.request.Request(SRC_URL, headers={"User-Agent": "StarTyping-build_dev_vocab"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    RAW_CACHE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data["terms"]


def clean_term(raw: str) -> tuple[str, str]:
    """('API', 'api') из строк вида 'API (Application Programming Interface)' или '--dry-run, -n (Dry Run)'."""
    s = (raw or "").strip()
    # предпочтительно имя в скобках, если это читаемое слово
    m = re.search(r"\(([^)]+)\)\s*$", s)
    if m and re.search(r"[A-Za-z]", m.group(1)) and len(m.group(1)) <= 48:
        name = m.group(1).strip()
        # если в скобках несколько через /
        name = name.split("/")[0].strip()
    else:
        name = s.split(",")[0].strip()
        name = re.sub(r"\s*\([^)]*\)\s*", " ", name).strip()
    # убрать ведущие флаги вида -f если осталось только это
    if re.fullmatch(r"-{1,2}[\w-]+", name) and m:
        name = m.group(1).split("/")[0].strip()
    word = name.strip(" -")
    if not word:
        word = s[:40]
    slug = re.sub(r"[^a-z0-9]+", "-", word.lower()).strip("-") or "term"
    return word, slug


def translate_ru(text: str, cache: dict[str, str]) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if text in cache:
        return cache[text]
    # MyMemory free API (без ключа, с лимитами)
    q = urllib.parse.quote(text[:450])
    url = f"https://api.mymemory.translated.net/get?q={q}&langpair=en|ru"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "StarTyping-build_dev_vocab"})
        with urllib.request.urlopen(req, timeout=20) as r:
            payload = json.loads(r.read())
        ru = (payload.get("responseData") or {}).get("translatedText") or ""
        ru = ru.strip()
        if ru.lower() == text.lower() or "MYMEMORY WARNING" in ru.upper():
            ru = ""
    except Exception:
        ru = ""
    cache[text] = ru
    time.sleep(0.08)
    return ru


def make_sentences(term: str, definition: str, example: str, ru_term: str, cache: dict) -> list[dict]:
    out = []
    if example and example.strip():
        ex = example.strip()
        # если пример — не полноценное предложение, обернём
        if not ex.endswith((".", "?", "!")):
            en = f"In practice: {ex}."
        else:
            en = ex
        ru = translate_ru(en, cache) or None
        out.append({"en": en, "ru": ru, "source": "coderslingo", "context": None, "context_ru": None})
    # интервью-стиль
    en2 = f"In a coding interview, can you explain what {term} means?"
    ru2 = f"На собеседовании: можете объяснить, что такое {ru_term or term}?"
    out.append({"en": en2, "ru": ru2, "source": "generated", "context": None, "context_ru": None})
    en3 = f"A senior engineer should be able to discuss {term} clearly."
    ru3 = f"Старший инженер должен уметь ясно говорить о понятии «{ru_term or term}»."
    out.append({"en": en3, "ru": ru3, "source": "generated", "context": None, "context_ru": None})
    return out[:3]


def difficulty_for(cat: str, word: str) -> str:
    if cat in ("core-glossary", "git-commands", "sql") and len(word) <= 10:
        return "easy"
    if cat in ("design-patterns", "paradigms", "kubernetes", "observability"):
        return "tricky"
    return "medium"


def main() -> None:
    terms = fetch()
    prio = {c: i for i, c in enumerate(CAT_PRIORITY)}
    terms = sorted(
        terms,
        key=lambda t: (prio.get((t.get("category") or "").strip(), 99), (t.get("term") or "").lower()),
    )
    cache: dict[str, str] = {}
    cache_path = ROOT / "stamina" / "english" / "data" / "_dev_ru_cache.json"
    if cache_path.exists():
        cache.update(json.loads(cache_path.read_text(encoding="utf-8")))

    words = []
    seen_slugs: set[str] = set()
    rank = 30001  # после Master 20k
    for i, t in enumerate(terms):
        cat = (t.get("category") or "").strip()
        if cat in SKIP_CATS:
            continue
        if INTERVIEW_CATS and cat not in INTERVIEW_CATS:
            continue
        raw_term = t.get("term") or ""
        word, slug = clean_term(raw_term)
        base = slug
        n = 2
        while slug in seen_slugs:
            slug = f"{base}-{n}"
            n += 1
        seen_slugs.add(slug)
        definition = (t.get("definition") or "").strip()
        example = (t.get("example") or "").strip()
        gloss = RU_GLOSS.get(word.lower())
        ru = translate_ru(f"{word}: {definition}" if definition else word, cache)
        if not ru or ru.lower().startswith(word.lower()):
            ru = gloss or translate_ru(word, cache) or word
        elif gloss and len(ru) > 120:
            ru = gloss
        # укоротить слишком длинный перевод для лица карточки
        if len(ru) > 160:
            ru = ru[:157] + "…"
        sents = make_sentences(word, definition, example, ru.split(":")[0].strip(), cache)
        rec = {
            "id": f"dev{rank - 30000:05d}",
            "word": word,
            "slug": f"dev:{slug}",
            "rank": rank,
            "level": "dev-interview",
            "sets": ["dev-interview"],
            "pos": "noun",
            "pos_all": ["noun"],
            "difficulty": difficulty_for(cat, word),
            "definition": definition,
            "definition_source": "coderslingo",
            "tags": ["it", "interview", cat],
            "ru": ru,
            "ru_src": "mt",
            "ipa": None,
            "respelling": None,
            "syllables": max(1, len(re.findall(r"[A-Za-z]+", word))),
            "syllable_breakdown": None,
            "guide": None,
            "notes": [f"категория: {cat}"] if cat else [],
            "sounds_like": None,
            "example": sents[0]["en"] if sents else None,
            "example_ru": sents[0].get("ru") if sents else None,
            "example_source": "coderslingo" if example else "generated",
            "sentences": sents,
            "category": cat,
            "source": "coderslingo",
        }
        words.append(rec)
        rank += 1
        if (i + 1) % 40 == 0:
            print(f"... {i + 1}/{len(terms)} -> {len(words)} records")
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    OUT.write_text(json.dumps({
        "name": "IT Interview English",
        "description": "IT / software-engineering terms for coding interviews (from CodersLingo open dataset).",
        "license": "CC BY 4.0 — CodersLingo https://coderslingo.com/glossary/ ; adaptations Star Typing",
        "source": SRC_URL,
        "count": len(words),
        "words": words,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK: {len(words)} words -> {OUT}")


if __name__ == "__main__":
    main()
