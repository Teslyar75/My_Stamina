"""Офлайн-сборка паков глаголов: data/verbs/irregular.json и data/verbs/frequent_1000.json.

Приложение в сеть за глаголами не ходит: всё собирается здесь один раз.

Входы (рабочая папка WORK вне репозитория, скачиваются ОДИН раз, уже скачанное
не перекачивается — см. fetch()):
  kaikki-verbs.jsonl        Wiktionary через Kaikki.org, английские глаголы (CC BY-SA 4.0)
  en_50k.txt                hermitdave/FrequencyWords 2018, частоты (контент CC BY-SA 4.0)
  cefrj.csv, octanove.csv   CEFR-J Wordlist 1.5 и Octanove C1/C2 (уровни и POS)
  eng_sentences.tsv.bz2, rus_sentences.tsv.bz2, eng-rus_links.tsv.bz2
                            еженедельные выгрузки Tatoeba (CC BY 2.0 FR)

Выгрузки Tatoeba используются вместо API: это один файл на язык вместо тысяч
запросов, т.е. ещё бережнее к сервису. Запросов к api.tatoeba.org: 0.

Ничего не выдумывается: у каждой записи source/license, у примера source_id и url;
если примеров меньше 5 — status "incomplete", перевод не найден — gaps ["ru"].

python tools/build_verbs_pack.py WORK [OUT]
"""
from __future__ import annotations

import bz2
import csv
import json
import math
import re
import sys
import time
import unicodedata
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "stamina" / "english"))
import conjugation as cj  # noqa: E402  (чистый модуль без UI и без i18n)

UA = "StarTypingDataBuilder/1.0 (offline pack build; https://github.com/Teslyar75/My_Stamina)"
FILES = {
    "kaikki-verbs.jsonl": "https://kaikki.org/dictionary/English/pos-verb/kaikki.org-dictionary-English-by-pos-verb.jsonl",
    "en_50k.txt": "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/en/en_50k.txt",
    "cefrj.csv": "https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/master/cefrj-vocabulary-profile-1.5.csv",
    "octanove.csv": "https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/master/octanove-vocabulary-profile-c1c2-1.0.csv",
    "eng_sentences.tsv.bz2": "https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences.tsv.bz2",
    "rus_sentences.tsv.bz2": "https://downloads.tatoeba.org/exports/per_language/rus/rus_sentences.tsv.bz2",
    "eng-rus_links.tsv.bz2": "https://downloads.tatoeba.org/exports/per_language/eng/eng-rus_links.tsv.bz2",
}
N_IRREGULAR = 200
N_FREQUENT = 1000
EX_IRREGULAR = 5
EX_FREQUENT = 3
BAD_TAGS = {"obsolete", "archaic", "nonstandard", "dialectal", "rare", "colloquial", "nonstandard",
            "humorous", "slang", "misspelling", "proscribed", "poetic", "Scotland", "Ireland",
            "informal", "pronunciation-spelling", "eye-dialect", "uncommon", "Early-Modern"}

SOURCES = [
    {"id": "kaikki", "name": "Wiktionary via Kaikki.org", "url": "https://kaikki.org/",
     "license": "CC BY-SA 4.0", "use": "forms V2/V3, IPA, Russian translation"},
    {"id": "tatoeba", "name": "Tatoeba", "url": "https://tatoeba.org/",
     "license": "CC BY 2.0 FR", "use": "EN–RU example sentences"},
    {"id": "frequencywords", "name": "hermitdave/FrequencyWords (OpenSubtitles 2018)",
     "url": "https://github.com/hermitdave/FrequencyWords", "license": "CC BY-SA 4.0 (content), MIT (code)",
     "use": "frequency rank"},
    {"id": "cefrj", "name": "CEFR-J Wordlist 1.5 (Tono Laboratory, TUFS) / Octanove C1–C2",
     "url": "https://github.com/openlanguageprofiles/olp-en-cefrj",
     "license": "CEFR-J: free incl. commercial use with attribution; Octanove: CC BY-SA 4.0",
     "use": "verb list and CEFR level"},
]


def fetch(work: Path) -> None:
    work.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        dst = work / name
        if dst.exists() and dst.stat().st_size > 0:
            continue
        print("качаю:", url)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=300) as r, open(dst, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        time.sleep(3)


def strip_accents(s: str) -> str:
    return unicodedata.normalize("NFC", "".join(
        c for c in unicodedata.normalize("NFD", s) if c not in "\u0301\u0300"))


def load_freq(work: Path) -> dict[str, int]:
    out = {}
    for line in open(work / "en_50k.txt", encoding="utf-8"):
        p = line.split()
        if len(p) == 2:
            out.setdefault(p[0].lower(), int(p[1]))
    return out


def load_nouns_only(work: Path) -> set[str]:
    """Слова, которые в CEFR-списках есть только существительными (lamp, lump)."""
    pos: dict[str, set[str]] = defaultdict(set)
    for fn in ("cefrj.csv", "octanove.csv"):
        for r in csv.DictReader(open(work / fn, encoding="utf-8-sig")):
            for hw in r["headword"].split("/"):
                pos[hw.strip().lower()].add(r["pos"])
    return {w for w, p in pos.items() if p == {"noun"}}


def load_cefr(work: Path, verbs_only: bool = True) -> dict[str, str]:
    out = {}
    order = ["A1", "A2", "B1", "B2", "C1", "C2"]
    for fn in ("cefrj.csv", "octanove.csv"):
        for r in csv.DictReader(open(work / fn, encoding="utf-8-sig")):
            if verbs_only and (not r["pos"].endswith("verb") or r["pos"] == "adverb"):
                continue
            for hw in r["headword"].split("/"):
                hw = hw.strip().lower()
                if re.fullmatch(r"[a-z]+", hw):
                    lv = r["CEFR"].strip().upper()
                    if hw not in out or order.index(lv) < order.index(out[hw]):
                        out[hw] = lv
    return out


_W = re.compile(r"[a-z]+")


def _content(s: str) -> set[str]:
    stop = {"to", "a", "an", "the", "of", "or", "and", "in", "on", "with", "for", "from", "by", "be",
            "something", "someone", "one", "oneself", "as", "at", "into"}
    return {w for w in _W.findall(s.lower()) if w not in stop}


RU_RANK: dict[str, int] = {}


def load_ru_rank(work: Path) -> None:
    """Частотность русских слов (FrequencyWords, CC BY-SA 4.0) — чтобы из нескольких значений
    выбрать самое употребительное («сказать», а не «различать» для tell)."""
    path = work / "ru_50k.txt"
    if not path.exists():
        fetch(FREQ_URL.replace("/en/en_50k", "/ru/ru_50k"), path)
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            parts = line.split()
            if len(parts) == 2:
                RU_RANK.setdefault(parts[0], i + 1)


def _ru_bonus(word: str) -> float:
    w = strip_accents(word).split()[0].lower() if word.split() else ""
    if len(w) <= 3:  # «не», «ли», «да» — служебные, не перевод глагола
        return -1.0
    r = RU_RANK.get(w, 60000)
    return 0.6 * (1 - math.log(r) / math.log(60000))


def pick_ru(entry: dict) -> list[str]:
    trs = [t for t in (entry.get("translations") or []) if t.get("lang_code", t.get("code")) == "ru"
           and t.get("word")]
    for s in entry.get("senses") or []:
        trs += [t for t in (s.get("translations") or []) if t.get("lang_code", t.get("code")) == "ru"
                and t.get("word")]
    if not trs:
        return []
    glosses = [g for s in (entry.get("senses") or []) for g in (s.get("glosses") or [])][:6]
    gsets = [_content(g) for g in glosses]

    def score(t):
        ts = _content(t.get("sense") or "")
        best = 0.0
        for i, gs in enumerate(gsets):
            if ts and gs:
                j = len(ts & gs) / len(ts | gs)
                best = max(best, j - 0.05 * i)
        group = [x["word"] for x in trs if x.get("sense") == t.get("sense")]
        return best + max(_ru_bonus(w) for w in group)

    ranked = sorted(enumerate(trs), key=lambda it: (-score(it[1]), -_ru_bonus(it[1]["word"]), it[0]))
    top_sense = ranked[0][1].get("sense")
    out = []
    for _, t in ranked:
        if t.get("sense") != top_sense:
            continue
        w = strip_accents(t["word"]).strip()
        if w and w not in out:
            out.append(w)
        if len(out) == 2:
            break
    return out


def pick_ipa(entry: dict) -> str:
    sounds = [s for s in (entry.get("sounds") or []) if s.get("ipa")]
    for pref in ("Received-Pronunciation", "UK", "General-American", "US"):
        for s in sounds:
            if pref in (s.get("tags") or []) and "weak" not in (s.get("note") or ""):
                return s["ipa"]
    return sounds[0]["ipa"] if sounds else ""


def kaikki_forms(entry: dict) -> tuple[list[str], list[str]]:
    v2, v3 = [], []
    for f in entry.get("forms") or []:
        tags = set(f.get("tags") or [])
        form = (f.get("form") or "").strip().lower()
        if not form or tags & BAD_TAGS or not re.fullmatch(r"[a-z]+", form):
            continue
        if tags == {"past"} and form not in v2:
            v2.append(form)
        elif tags == {"participle", "past"} and form not in v3:
            v3.append(form)
    if not v3:  # strike: «struck» помечено как past + participle с доп. тегами
        for f in entry.get("forms") or []:
            tags = set(f.get("tags") or [])
            form = (f.get("form") or "").strip().lower()
            if {"participle", "past"} <= tags and not tags & BAD_TAGS and re.fullmatch(r"[a-z]+", form):
                v3.append(form) if form not in v3 else None
    if v2 and not v3 and not any("participle" in (f.get("tags") or []) and "past" in (f.get("tags") or [])
                                 for f in entry.get("forms") or []):
        v3 = list(v2)  # в статье одна форма «past and past participle» (strike → struck)
    return v2, v3


# Ручные исключения с причиной (не выдумка данных, а отсев шума частотного списка)
EXCLUDE = {
    "clive": "в субтитрах это имя Clive, а не глагол «раскалывать»",
}

MARGINAL = {"obsolete", "archaic", "dialectal", "Scotland", "Northern-England", "slang", "vulgar",
            "rare", "nonstandard", "Ireland", "Geordie", "Yorkshire", "colloquial", "informal",
            "Internet", "eye-dialect", "pronunciation-spelling", "misspelling", "humorous",
            "alt-of", "form-of", "Scots", "historical", "poetic", "derogatory", "offensive"}


def load_kaikki(work: Path, wanted: set[str], freq: dict[str, int],
                nouns: frozenset[str] = frozenset()) -> dict[str, dict]:
    """Из нескольких статей-глаголов одной леммы (омонимы: lead «вести» / lead «покрывать
    свинцом») берём ту, чьи V2/V3 чаще встречаются; редкие варианты форм отбрасываем."""
    cand: dict[str, list[dict]] = defaultdict(list)
    with open(work / "kaikki-verbs.jsonl", encoding="utf-8") as fh:
        for line in fh:
            if '"lang_code": "en"' not in line:
                continue
            d = json.loads(line)
            w = d.get("word", "")
            if w not in wanted or d.get("pos") != "verb" or d.get("lang_code") != "en":
                continue
            v2, v3 = kaikki_forms(d)
            clean = any(not (set(sn.get("tags") or []) & MARGINAL) and not sn.get("form_of")
                        and not sn.get("alt_of") for sn in d.get("senses") or [])
            if not clean:  # только устаревшие/диалектные/жаргонные значения (ken, lin, list «нравиться»)
                continue
            cand[w].append({"v2": v2, "v3": v3, "ru": pick_ru(d), "ipa": pick_ipa(d)})
    out = {}
    for w, entries in cand.items():
        def weight(e):
            # limp → lamp/lump: частотность существительных не должна выбирать статью
            return sum(freq.get(x, 0) for x in set(e["v2"]) | set(e["v3"]) if x not in nouns)
        best = max(enumerate(entries), key=lambda it: (bool(it[1]["v2"] and it[1]["v3"]), weight(it[1]),
                                                       -it[0]))[1]
        best = dict(best)
        best["v2"], best["v3"] = _keep_common(best["v2"], freq), _keep_common(best["v3"], freq)
        for e in entries:
            if not best["ru"] and e["ru"]:
                best["ru"] = e["ru"]
            if not best["ipa"] and e["ipa"]:
                best["ipa"] = e["ipa"]
        out[w] = best
    return out


def _keep_common(variants: list[str], freq: dict[str, int]) -> list[str]:
    """Первый вариант оставляем всегда, остальные — если встречаются хотя бы в 3 % случаев."""
    if not variants:
        return []
    top = max(freq.get(v, 0) for v in variants)
    keep = [variants[0]] + [v for v in variants[1:] if freq.get(v, 0) >= max(20, 0.03 * top)]
    if freq.get(variants[0], 0) < max(20, 0.03 * top) and len(keep) > 1:
        keep = keep[1:]
    return keep


def regular_set(b: str) -> set[str]:
    return {b + "ed", b + "d" if b.endswith("e") else b + "ed", b + b[-1:] + "ed", b[:-1] + "ied", b + "ked", cj.regular_past(b)}


def irregular_by_forms(lemma: str, k: dict) -> bool:
    r = regular_set(lemma)
    v2, v3 = k["v2"], k["v3"]
    if v2[0] not in r or v3[0] not in r:
        return True
    return any(v not in r and v != lemma for v in v2[1:] + v3[1:])


def load_tatoeba(work: Path):
    eng = {}
    with bz2.open(work / "eng_sentences.tsv.bz2", "rt", encoding="utf-8") as fh:
        for line in fh:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 3:
                eng[int(p[0])] = p[2]
    rus = {}
    with bz2.open(work / "rus_sentences.tsv.bz2", "rt", encoding="utf-8") as fh:
        for line in fh:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 3:
                rus[int(p[0])] = p[2]
    pairs = {}
    with bz2.open(work / "eng-rus_links.tsv.bz2", "rt", encoding="utf-8") as fh:
        for line in fh:
            a, b = line.split("\t")[:2]
            a, b = int(a), int(b)
            if a in eng and b in rus and a not in pairs:
                pairs[a] = b
    index = defaultdict(list)
    for eid in pairs:
        en = eng[eid]
        n = len(en.split())
        if not (3 <= n <= 14) or len(en) > 90:
            continue
        for tok in set(_W.findall(en.lower())):
            index[tok].append(eid)
    return eng, rus, pairs, index


def pick_examples(fset: list[str], n: int, tat, used: set[int]) -> list[dict]:
    """По кругу берём по предложению на каждую форму (V2, V3, V1, -s, -ing), короткие — первыми.
    Предложения, уже отданные другому глаголу, берём только если других нет."""
    eng, rus, pairs, index = tat
    pools = [sorted(set(index.get(f, [])), key=lambda i: (i in used, abs(len(eng[i].split()) - 7), i))
             for f in fset]
    out, seen, pos = [], set(), [0] * len(fset)
    while len(out) < n:
        progressed = False
        for j, f in enumerate(fset):
            if len(out) >= n:
                break
            p = pools[j]
            while pos[j] < len(p) and p[pos[j]] in seen:
                pos[j] += 1
            if pos[j] >= len(p):
                continue
            eid = p[pos[j]]
            pos[j] += 1
            seen.add(eid)
            progressed = True
            out.append({"en": eng[eid], "ru": rus[pairs[eid]], "form": f, "source": "tatoeba",
                        "source_id": eid, "ru_source_id": pairs[eid],
                        "url": f"https://tatoeba.org/sentences/show/{eid}",
                        "license": "CC BY 2.0 FR"})
        if not progressed:
            break
    used.update(e["source_id"] for e in out)
    return out


def record(lemma: str, k: dict, freq: dict, cefr: dict, tat, n_ex: int, used: set[int],
           *, irregular: bool) -> dict:
    if lemma == "be":
        v2, v3 = "was/were", "been"
    else:
        v2 = "/".join(k["v2"]) if k and k["v2"] else ""
        v3 = "/".join(k["v3"]) if k and k["v3"] else ""
    src_forms = "kaikki" if v2 and v3 else "rule"
    if not v2 or not v3:
        v2 = v2 or cj.regular_past(lemma)
        v3 = v3 or cj.regular_past(lemma)
    f = cj.forms(lemma, v2.split("/")[0], v3.split("/")[0])
    fset = []
    for x in [*v2.split("/"), *v3.split("/"), lemma, f["s"], f["ing"]]:
        if x and x not in fset:
            fset.append(x)
    if lemma == "be":
        fset = ["was", "were", "been", "be", "being"]
    ex = pick_examples(fset, n_ex, tat, used)
    gaps = []
    if not (k and k["ru"]):
        gaps.append("ru")
    if not (k and k["ipa"]):
        gaps.append("ipa")
    if len(ex) < n_ex:
        gaps.append(f"examples:{len(ex)}/{n_ex}")
    rec = {"lemma": lemma, "v2": v2, "v3": v3, "s": f["s"], "ing": f["ing"],
           "ipa": (k or {}).get("ipa", ""), "ru": ", ".join((k or {}).get("ru", [])),
           "cefr": cefr.get(lemma, ""), "rank": freq_rank(lemma, freq),
           "examples": ex, "source": "kaikki", "forms_source": src_forms,
           "license": "CC BY-SA 4.0", "url": f"https://en.wiktionary.org/wiki/{lemma}",
           "status": "ok" if len(ex) >= n_ex else "incomplete"}
    if gaps:
        rec["gaps"] = gaps
    if not irregular:
        rec["irregular"] = cj.is_irregular(lemma, v2, v3)
    return rec


_RANKS: dict[str, int] = {}


def freq_rank(lemma: str, freq: dict) -> int:
    if not _RANKS:
        for i, w in enumerate(freq, 1):
            _RANKS[w] = i
    return _RANKS.get(lemma, 0)


def lemma_weight(lemma: str, k: dict | None, freq: dict) -> int:
    """Частота по V1, -s, -ing (V2/V3 не считаем: saw/found/left — омонимы других слов)."""
    return sum(freq.get(x, 0) for x in {lemma, cj.third_person(lemma), cj.ing_form(lemma)})


def main(work: str = ".", out: str = "stamina/english/data/verbs") -> None:
    work_p, out_p = Path(work), ROOT / out if not Path(out).is_absolute() else Path(out)
    fetch(work_p)
    freq = load_freq(work_p)
    cefr = load_cefr(work_p)                       # глаголы CEFR-J / Octanove
    cefr_any = load_cefr(work_p, verbs_only=False)  # любые слова: weep, awake, forecast…
    print("CEFR-глаголов:", len(cefr))
    load_ru_rank(work_p)
    nouns = frozenset(load_nouns_only(work_p))
    # кандидаты: все слова CEFR + 20 000 самых частых слов (cling, creep, sting… в CEFR нет)
    top = {w for w, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:20000] if w.isalpha()}
    pool = set(cefr_any) | top
    kk = load_kaikki(work_p, pool, freq, nouns)
    irr = []
    for lemma in sorted(pool):
        k = kk.get(lemma)
        if lemma == "be":
            irr.append(lemma)
            continue
        if not k or not k["v2"] or not k["v3"]:
            continue
        if not irregular_by_forms(lemma, k):
            continue
        if lemma not in cefr:
            # в CEFR слово записано не глаголом (weep, awake, pen…): берём, только если
            # особая форма прошедшего реально употребительна и не совпадает с другим словом
            v2 = k["v2"][0]
            if lemma in EXCLUDE or (v2 != lemma and v2 in nouns) or (v2 == lemma and freq.get(lemma, 0) < 200):
                continue
            # shortcut/outburst: совпадение форм ничего не доказывает — нужна живая -ing форма
            if v2 == lemma and freq.get(cj.ing_form(lemma), 0) < 50:
                continue
            if v2 != lemma and (freq.get(v2, 0) < (50 if lemma in cefr_any else 200)
                                or freq.get(v2, 0) < 0.01 * max(1, freq.get(lemma, 0))):
                continue
        irr.append(lemma)
    # saw/found/wound/fell: это прежде всего формы see/find/wind/fall — свои формы у них правильные
    irr.sort(key=lambda l: -lemma_weight(l, kk.get(l), freq))
    owned, dedup = set(), []
    for l in irr:  # doe/git/rin → did/got/ran уже принадлежат do/get/run
        k = kk.get(l)
        if l != "be" and l not in cefr and set(k["v2"]) & owned:
            continue
        if k:
            owned |= set(k["v2"])
        dedup.append(l)
    irr = dedup
    irr_forms = {f for l in irr if l in kk for f in kk[l]["v2"] + kk[l]["v3"]}
    irr = [l for l in irr if not (l in irr_forms and l in kk and kk[l]["v2"][0] in regular_set(l))]
    irr.sort(key=lambda l: -lemma_weight(l, kk.get(l), freq))
    irr = irr[:N_IRREGULAR]
    for l in irr:
        cefr.setdefault(l, cefr_any.get(l, ""))
    print("неправильных:", len(irr))
    tat = load_tatoeba(work_p)
    used: set[int] = set()
    irr_recs = [record(l, kk.get(l), freq, cefr, tat, EX_IRREGULAR, used, irregular=True)
                for l in irr]
    irr_set = set(irr)
    verbs_cefr = load_cefr(work_p)
    rest = [l for l in verbs_cefr if l not in irr_set and l in kk]
    rest.sort(key=lambda l: -lemma_weight(l, kk.get(l), freq))
    rest = rest[:N_FREQUENT]
    freq_recs = [record(l, kk.get(l), freq, cefr, tat, EX_FREQUENT, used, irregular=False)
                 for l in rest]
    meta = {"schema": 1, "built": time.strftime("%Y-%m-%d"), "sources": SOURCES,
            "tatoeba_api_requests": 0,
            "thanks": "Kaikki.org / Wiktionary, Tatoeba, FrequencyWords, CEFR-J, Octanove"}
    out_p.mkdir(parents=True, exist_ok=True)
    for name, recs, kind in (("irregular.json", irr_recs, "irregular"),
                             ("frequent_1000.json", freq_recs, "frequent")):
        doc = {**meta, "kind": kind, "count": len(recs), "verbs": recs}
        (out_p / name).write_text(json.dumps(doc, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    rep = {}
    for name, recs in (("irregular", irr_recs), ("frequent", freq_recs)):
        rep[name] = {"verbs": len(recs),
                     "examples_tatoeba": sum(len(r["examples"]) for r in recs),
                     "incomplete": sum(r["status"] != "ok" for r in recs),
                     "no_ru": sum("ru" in r.get("gaps", []) for r in recs),
                     "no_ipa": sum("ipa" in r.get("gaps", []) for r in recs)}
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    (work_p / "verbs_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(*sys.argv[1:])
