"""Словарь: загрузка data/vocab.json (схема DATA_MODEL §1), индексы, поиск, фильтры."""
from __future__ import annotations

from stamina.i18n import t

import gzip
import json
import random
import threading

from . import paths
from .textutil import lev

SETS = [
    ("top-1000", 1000, "Essential 1000", t("ФУНДАМЕНТ"), "S-1000"),
    ("top-3000", 3000, "Core 3000", t("РАЗГОВОРНЫЙ"), "S-3000"),
    ("top-10000", 10000, "Advanced 10 000", t("СВОБОДНЫЙ"), "S-10K"),
    ("top-20000", 20000, "Master 20 000", t("КАК НОСИТЕЛЬ"), "S-20K"),
    # тематический набор (не по частоте wordfreq) — IT-английский для собеседований
    ("dev-interview", 0, "IT Interview", t("СОБЕСЕДОВАНИЕ"), "S-DEV"),
]
SET_LIMIT = {s[0]: s[1] for s in SETS}
THEMATIC_SETS = {"dev-interview"}  # выборка по полю sets[], а не по rank
POS_NORM = {"adj": "adjective", "adv": "adverb", "prep": "preposition", "conj": "conjunction",
            "pron": "pronoun", "n": "noun", "v": "verb"}
POS_FILTER = [("all", t("ВСЕ")), ("noun", t("СУЩ.")), ("verb", t("ГЛАГ.")), ("adjective", t("ПРИЛ.")),
              ("adverb", t("НАРЕЧ.")), ("pronoun", t("МЕСТ.")), ("preposition", t("ПРЕДЛ.")),
              ("conjunction", t("СОЮЗ")), ("other", t("ДРУГОЕ"))]
POS_SHORT = {"noun": "NOUN", "verb": "VERB", "adjective": "ADJ", "adverb": "ADVERB", "pronoun": "PRONOUN",
             "preposition": "PREP", "conjunction": "CONJ", "interjection": "INTERJ", "determiner": "DET"}
DIFF_RU = {"easy": t("ЛЁГКОЕ"), "medium": t("СРЕДНЕЕ"), "tricky": t("ТРУДНОЕ")}
DIFF_ORDER = {"easy": 0, "medium": 1, "tricky": 2}


class Vocab:
    def __init__(self) -> None:
        self.words: list[dict] = []
        self.by_slug: dict[str, dict] = {}
        self.ready = False
        self.error = ""
        self.source = ""
        self._lock = threading.Lock()

    # -- загрузка в фоне, чтобы не задерживать запуск Star Typing ------------
    def load_async(self, on_done=None) -> None:
        def work():
            self.load()
            if on_done:
                on_done()
        threading.Thread(target=work, daemon=True).start()

    def load(self) -> None:
        path = paths.vocab_file()
        try:
            if path.suffix == ".gz":
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    raw = json.load(f)
            else:
                raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                raw = raw.get("words", [])
            words = []
            for r in raw:
                if not r.get("word") or not r.get("rank"):
                    continue
                self._normalize_rec(r)
                words.append(r)
            # тематический словарь IT / собеседования (отдельный файл)
            dev_path = paths.DATA_DIR / "vocab_dev.json"
            src = str(path)
            if dev_path.exists():
                try:
                    dev = json.loads(dev_path.read_text(encoding="utf-8"))
                    extra = dev.get("words", dev) if isinstance(dev, dict) else dev
                    n_add = 0
                    for r in extra:
                        if not r.get("word") or not r.get("rank"):
                            continue
                        self._normalize_rec(r)
                        r.setdefault("sets", ["dev-interview"])
                        if "dev-interview" not in r["sets"]:
                            r["sets"].append("dev-interview")
                        words.append(r)
                        n_add += 1
                    if n_add:
                        src = f"{path} + {dev_path.name} ({n_add})"
                except Exception:
                    pass
            words.sort(key=lambda w: w["rank"])
            with self._lock:
                self.words = words
                self.by_slug = {w["slug"]: w for w in words}
                self.source = src
                self.ready = True
        except Exception as exc:  # noqa: BLE001
            self.error = f"{type(exc).__name__}: {exc}"
            self.ready = True

    @staticmethod
    def _normalize_rec(r: dict) -> None:
        r["pos"] = POS_NORM.get((r.get("pos") or "").lower(), (r.get("pos") or "").lower())
        r["pos_all"] = [POS_NORM.get(p, p) for p in (r.get("pos_all") or [r["pos"]]) if p]
        r["slug"] = r.get("slug") or r["word"].lower()
        r["difficulty"] = (r.get("difficulty") or "medium").lower()
        if "sets" in r and not isinstance(r["sets"], list):
            r["sets"] = list(r["sets"]) if r["sets"] else []

    # -- выборки -------------------------------------------------------------
    def in_set(self, set_id: str) -> list[dict]:
        if set_id in THEMATIC_SETS:
            return [
                w for w in self.words
                if set_id in (w.get("sets") or []) or w.get("level") == set_id
            ]
        lim = SET_LIMIT.get(set_id, 1000)
        out = []
        for w in self.words:
            # тематические IT-слова (rank > 20k) не попадают в частотные наборы
            if w["rank"] > 20000:
                continue
            if w["rank"] > lim:
                break
            out.append(w)
        return out

    def get(self, slug: str) -> dict | None:
        return self.by_slug.get(slug)

    def search(self, q: str, extra=None, limit: int = 8) -> list[dict]:
        """Точное → по началу (по частоте) → похожие (Левенштейн ≤ 2). extra(slug) → «мой перевод»."""
        q = q.strip().lower()
        if not q:
            return []
        exact, prefix, ru, fuzzy = [], [], [], []
        for w in self.words:
            lw = w["word"].lower()
            if lw == q:
                exact.append(w)
            elif lw.startswith(q):
                if len(prefix) < limit:
                    prefix.append(w)
            elif extra and q in (extra(w["slug"]) or "").lower():
                ru.append(w)
        res = exact + prefix + ru
        if len(res) < limit and len(q) >= 4:
            for w in self.words:
                lw = w["word"].lower()
                if abs(len(lw) - len(q)) <= 2 and w not in res:
                    d = lev(lw, q)
                    if d <= 2:
                        fuzzy.append((d, w["rank"], w))
            fuzzy.sort(key=lambda x: (x[0], x[1]))
            res += [x[2] for x in fuzzy]
        return res[:limit]

    def filtered(self, set_id: str, *, query="", status="all", length="all", pos="all", diff="all",
                 sort="random", seed=1, progress=None) -> list[dict]:
        q = query.strip().lower()
        out = []
        for w in self.in_set(set_id):
            if q and q not in w["word"].lower() and not (progress and q in progress.tr(w["slug"]).lower()):
                continue
            if progress and status != "all":
                known = progress.is_known(w["slug"])
                if status == "known" and not known:
                    continue
                if status == "unknown" and known:
                    continue
                if status == "review" and (known or not progress.has_card(w["slug"])):
                    continue
            n = len(w["word"])
            if length == "short" and n > 4 or length == "mid" and not 5 <= n <= 7 or length == "long" and n < 8:
                continue
            if pos != "all":
                ps = set(w.get("pos_all") or [w["pos"]])
                if pos == "other":
                    if ps & {p for p, _ in POS_FILTER[1:-1]}:
                        continue
                elif pos not in ps:
                    continue
            if diff != "all" and w["difficulty"] != diff:
                continue
            out.append(w)
        if sort == "random":
            random.Random(seed).shuffle(out)
        elif sort == "alpha":
            out.sort(key=lambda w: w["word"].lower())
        elif sort == "difficulty":
            out.sort(key=lambda w: (DIFF_ORDER.get(w["difficulty"], 1), w["rank"]))
        return out

    def sentences(self, w: dict) -> list[dict]:
        s = [x for x in (w.get("sentences") or []) if x.get("en")]
        if not s and w.get("example"):
            s = [{"en": w["example"], "ru": w.get("example_ru"), "context": None, "context_ru": None}]
        return s
