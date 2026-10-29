"""Сборка наборов CEFR A1–C2 из открытых источников (офлайн, повторяемо).

Входы (кладутся в рабочую папку WORK, скачиваются ОДИН раз — см. fetch.py):
  cefrj-vocabulary-profile-1.5.csv          CEFR-J Wordlist 1.5, Tono Lab (TUFS) — бесплатно, с указанием источника
  octanove-vocabulary-profile-c1c2-1.0.csv  Octanove Labs, CC BY-SA 4.0
  eng_sentences.tsv.bz2, rus_sentences.tsv.bz2, eng-rus_links.tsv.bz2   Tatoeba, CC BY 2.0 FR
  kaikki-en.jsonl.gz                         Kaikki.org (Wiktionary), CC BY-SA 4.0
  vocab.json                                 наш частотный словарь (ранги, переводы с пометкой ru_src)
Выход: stamina/english/data/sets/cefr_*.json — у каждой записи и примера свои source/license.
Ничего не придумывается: чего нет в источниках, помечается как пробел (gaps).
"""
from __future__ import annotations

import bz2, csv, gzip, json, re, sys
from collections import defaultdict
from pathlib import Path

WORK = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "stamina/english/data/sets")
NEED = 5
MAX_WORDS_IN_SENT = 12

SRC = {
    "cefrj": {"name": "CEFR-J Wordlist 1.5 (Tono Laboratory, TUFS)", "url": "http://www.cefr-j.org/download.html",
              "license": "CEFR-J terms: free incl. commercial use with citation"},
    "octanove": {"name": "Octanove Vocabulary Profile C1/C2 1.0 (Octanove Labs)",
                 "url": "https://github.com/openlanguageprofiles/olp-en-cefrj", "license": "CC BY-SA 4.0"},
    "tatoeba": {"name": "Tatoeba", "url": "https://tatoeba.org", "license": "CC BY 2.0 FR"},
    "wiktionary": {"name": "Wiktionary via Kaikki.org", "url": "https://kaikki.org", "license": "CC BY-SA 4.0"},
}
TOPIC_RU = {
    "Work and Jobs": "Работа", "Work and jobs": "Работа", "Education": "Учёба", "Objects and rooms": "Дом и вещи",
    "News, lifestyles and current affairs": "Новости и образ жизни", "Things in the town, shops and shopping": "Город и магазины",
    "Shopping": "Город и магазины", "Food and drink": "Еда и напитки", "Travel and services vocab": "Путешествия",
    "Ways of travelling": "Путешествия", "Holidays": "Путешествия", "Hobbies and pastimes": "Хобби и досуг",
    "Leisure activities": "Хобби и досуг", "Hobbies and lifestyles": "Хобби и досуг", "Nationalities and countries": "Страны",
    "Family life": "Семья", "Personal information": "О себе", "Clothes": "Одежда", "Colours": "Цвета",
    "Books and literature": "Книги и искусство", "Arts": "Книги и искусство", "Film": "Книги и искусство", "Media": "СМИ",
    "Adjectives: personality, description, feelings": "Характер и чувства",
}
POS_TOPIC = {"noun": "Существительные", "verb": "Глаголы", "adjective": "Прилагательные", "adverb": "Наречия"}
LEVELS = ["A1", "A2", "B1.1", "B1.2", "B2.1", "B2.2", "C1", "C2"]
TOK = re.compile(r"[a-z]+(?:'[a-z]+)?")


def headwords(raw: str) -> list[str]:
    return [h.strip() for h in raw.split("/") if h.strip()]


def load_lists(vocab):
    rows = []
    for fn, key in (("cefrj-vocabulary-profile-1.5.csv", "cefrj"), ("octanove-vocabulary-profile-c1c2-1.0.csv", "octanove")):
        for r in csv.DictReader(open(WORK / fn, encoding="utf-8-sig")):
            hw = headwords(r["headword"])
            topic = (r.get("CoreInventory 1") or r.get("CoreInventory 2") or "").strip()
            rows.append({"word": hw[0], "variants": hw[1:], "pos": r["pos"].strip(), "cefr": r["CEFR"].strip(),
                         "topic_en": topic, "list": key})
    words: dict[tuple, dict] = {}
    for r in rows:      # одно слово на уровень; несколько частей речи — в pos_all
        k = (r["word"].lower(), r["cefr"])
        if k in words:
            words[k]["pos_all"].append(r["pos"])
            words[k]["topic_en"] = words[k]["topic_en"] or r["topic_en"]
            continue
        r["pos_all"] = [r["pos"]]
        words[k] = r
    seen_lower = {}
    order = {"A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5}
    for w in sorted(words.values(), key=lambda x: order.get(x["cefr"], 9)):   # слово — в самом низком уровне
        seen_lower.setdefault(w["word"].lower(), w)
    out = list(seen_lower.values())
    for w in out:
        v = vocab.get(w["word"].lower())
        w["rank"] = int(v["rank"]) if v and v.get("rank") else 10 ** 6
    # B1/B2 делим пополам по частоте: .1 — частотнее
    for base in ("B1", "B2"):
        grp = sorted([w for w in out if w["cefr"] == base], key=lambda x: (x["rank"], x["word"]))
        half = (len(grp) + 1) // 2
        for i, w in enumerate(grp):
            w["level"] = f"{base}.1" if i < half else f"{base}.2"
    for w in out:
        w.setdefault("level", w["cefr"])
    return out


def word_forms(word: str, kforms: set[str]) -> set[str]:
    w = word.lower()
    f = {w, w + "s", w + "es", w + "ed", w + "d", w + "ing"}
    if w.endswith("e"):
        f.add(w[:-1] + "ing")
    if w.endswith("y"):
        f |= {w[:-1] + "ies", w[:-1] + "ied"}
    return f | kforms


def load_kaikki(need: set[str]):
    info: dict[str, dict] = {}
    with gzip.open(WORK / "kaikki-en.jsonl.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            i = line.find('"word": "')
            if i < 0:
                continue
            j = line.find('"', i + 9)
            if line[i + 9:j].lower() not in need:
                continue
            d = json.loads(line)
            if d.get("lang_code") != "en":
                continue
            w = d["word"].lower()
            e = info.setdefault(w, {"ipa": "", "ru": [], "defs": [], "examples": [], "forms": set()})
            if not e["ipa"]:
                ipas = [s["ipa"] for s in d.get("sounds", []) if s.get("ipa")]
                us = [s["ipa"] for s in d.get("sounds", []) if s.get("ipa") and "US" in (s.get("tags") or [])]
                e["ipa"] = (us or ipas or [""])[0]
            for t in d.get("translations", []):
                if t.get("code") == "ru" and t.get("word") and len(e["ru"]) < 4:
                    clean = t["word"].replace("\u0301", "")
                    if clean not in e["ru"]:
                        e["ru"].append(clean)
            for s in d.get("senses", []):
                if s.get("glosses") and len(e["defs"]) < 2 and "form-of" not in (s.get("tags") or []):
                    e["defs"].append({"pos": d.get("pos", ""), "definition": s["glosses"][0]})
                for ex in s.get("examples", []):
                    if ex.get("type") == "example" and ex.get("text") and len(ex["text"].split()) <= 16:
                        e["examples"].append({"en": ex["text"].strip(), "ru": (ex.get("translation") or "").strip()})
            for f in d.get("forms", []):
                fw = (f.get("form") or "").lower()
                if fw.isalpha():
                    e["forms"].add(fw)
    return info


def load_tatoeba():
    def sents(fn):
        out = {}
        with bz2.open(WORK / fn, "rt", encoding="utf-8") as fh:
            for line in fh:
                p = line.rstrip("\n").split("\t")
                if len(p) >= 3:
                    out[p[0]] = p[2]
        return out
    links = defaultdict(list)
    with bz2.open(WORK / "eng-rus_links.tsv.bz2", "rt", encoding="utf-8") as fh:
        for line in fh:
            a, b = line.split()[:2]
            links[a].append(b)
    eng, rus = sents("eng_sentences.tsv.bz2"), sents("rus_sentences.tsv.bz2")
    pairs = []
    for eid, rids in links.items():
        en = eng.get(eid)
        ru = next((rus[r] for r in rids if r in rus), None)
        if en and ru and 3 <= len(en.split()) <= MAX_WORDS_IN_SENT:
            pairs.append((eid, en, ru))
    pairs.sort(key=lambda p: (len(p[1]), p[0]))      # короткие и простые — первыми
    index = defaultdict(list)
    for n, (_eid, en, _ru) in enumerate(pairs):
        for t in set(TOK.findall(en.lower())):
            index[t].append(n)
    return pairs, index


def main():
    vocab = {w["slug"]: w for w in json.load(open(WORK / "vocab.json", encoding="utf-8"))}
    words = load_lists(vocab)
    need = {w["word"].lower() for w in words}
    print("слов в списках:", len(words), file=sys.stderr)
    kk = load_kaikki(need)
    print("kaikki:", len(kk), file=sys.stderr)
    pairs, index = load_tatoeba()
    print("пар tatoeba:", len(pairs), file=sys.stderr)
    used_global: dict[str, int] = defaultdict(int)
    by_level = defaultdict(list)
    for w in sorted(words, key=lambda x: (x["rank"], x["word"])):
        lw = w["word"].lower()
        k = kk.get(lw, {})
        v = vocab.get(lw) or {}
        rec = {"word": w["word"], "slug": lw, "pos": w["pos"], "pos_all": w["pos_all"], "rank": w["rank"] if w["rank"] < 10 ** 6 else 0,
               "topic": TOPIC_RU.get(w["topic_en"]) or POS_TOPIC.get(w["pos"], "Служебные и другие"), "topic_en": w["topic_en"],
               "word_source": w["list"]}
        if v.get("ru") and v.get("ru_src") in ("wiktionary", "override"):
            rec["ru"], rec["ru_source"] = v["ru"], ("wiktionary" if v["ru_src"] == "wiktionary" else "star-typing")
        elif k.get("ru"):
            rec["ru"], rec["ru_source"] = "; ".join(k["ru"][:3]), "wiktionary"
        elif v.get("ru"):
            rec["ru"], rec["ru_source"] = v["ru"], "machine-translation"      # opus-mt, помечено честно
        else:
            rec["ru"], rec["ru_source"] = "", "gap"
        rec["ipa"] = k.get("ipa") or ""
        rec["ipa_source"] = "wiktionary" if rec["ipa"] else "gap"
        rec["senses"] = k.get("defs") or []
        sents, seen = [], set()
        if " " not in lw:
            forms = word_forms(lw, k.get("forms", set()))
            cand = sorted({n for f in forms for n in index.get(f, [])})
            for n in sorted(cand, key=lambda n: (used_global[pairs[n][0]], n)):
                eid, en, ru = pairs[n]
                if en.lower() in seen:
                    continue
                seen.add(en.lower())
                used_global[eid] += 1
                sents.append({"en": en, "ru": ru, "source": "tatoeba", "license": SRC["tatoeba"]["license"],
                              "tatoeba_id": eid, "url": f"https://tatoeba.org/en/sentences/show/{eid}"})
                if len(sents) >= NEED:
                    break
        else:   # фразы из нескольких слов: ищем подстроку
            for eid, en, ru in pairs:
                if re.search(r"\b" + re.escape(lw) + r"\b", en.lower()) and en.lower() not in seen:
                    seen.add(en.lower())
                    sents.append({"en": en, "ru": ru, "source": "tatoeba", "license": SRC["tatoeba"]["license"],
                                  "tatoeba_id": eid, "url": f"https://tatoeba.org/en/sentences/show/{eid}"})
                    if len(sents) >= NEED:
                        break
        for ex in k.get("examples", []):
            if len(sents) >= NEED:
                break
            if ex["en"].lower() not in seen:
                seen.add(ex["en"].lower())
                sents.append({"en": ex["en"], "ru": ex["ru"], "source": "wiktionary", "license": SRC["wiktionary"]["license"]})
        rec["sentences"] = sents
        gaps = []
        if len(sents) < NEED:
            gaps.append(f"examples:{len(sents)}/{NEED}")
        if any(not s["ru"] for s in sents):
            gaps.append("examples_ru")
        if rec["ru_source"] == "gap":
            gaps.append("ru")
        if not rec["ipa"]:
            gaps.append("ipa")
        if gaps:
            rec["gaps"] = gaps
        by_level[w["level"]].append(rec)
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    names = {"A1": "A1 · Выживание", "A2": "A2 · Быт", "B1.1": "B1.1 · Порог", "B1.2": "B1.2 · Порог+",
             "B2.1": "B2.1 · Свободно", "B2.2": "B2.2 · Свободно+", "C1": "C1 · Продвинутый", "C2": "C2 · Мастерство"}
    for lv in LEVELS:
        ws = by_level.get(lv, [])
        # внутри уровня: по темам, внутри темы — по частоте (блоки по 50 идут темами)
        topics = {}
        for r in ws:
            topics.setdefault(r["topic"], []).append(r)
        torder = sorted(topics, key=lambda t: (t in POS_TOPIC.values() or t == "Служебные и другие", -len(topics[t]), t))
        ordered = [r for t in torder for r in topics[t]]
        lst = "octanove" if lv in ("C1", "C2") else "cefrj"
        data = {"id": f"cefr-{lv.lower().replace('.', '-')}", "level": lv, "name": names[lv], "schema": 2,
                "source": SRC[lst], "sources": {k: SRC[k] for k in (lst, "tatoeba", "wiktionary")},
                "topics": [{"name": t, "count": len(topics[t])} for t in torder],
                "words": ordered}
        (OUT / f"cefr_{lv.lower().replace('.', '_')}.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        full = sum(1 for r in ws if len(r["sentences"]) >= NEED)
        report[lv] = {"words": len(ws), "examples_5": full, "examples_0": sum(1 for r in ws if not r["sentences"]),
                      "sentences": sum(len(r["sentences"]) for r in ws),
                      "tatoeba": sum(1 for r in ws for s in r["sentences"] if s["source"] == "tatoeba"),
                      "wiktionary": sum(1 for r in ws for s in r["sentences"] if s["source"] == "wiktionary"),
                      "ru_gap": sum(1 for r in ws if r["ru_source"] == "gap"),
                      "ru_mt": sum(1 for r in ws if r["ru_source"] == "machine-translation"),
                      "ipa_gap": sum(1 for r in ws if not r["ipa"]), "topics": len(topics)}
    (OUT / "cefr_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
