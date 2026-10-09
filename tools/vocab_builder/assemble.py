import json, re, collections, sys
V = json.load(open("stage1.json", encoding="utf-8"))
ru = json.load(open("ru_stage.json", encoding="utf-8"))
mt = json.load(open("mt_cache.json", encoding="utf-8"))
tat = json.load(open("tat_best.json", encoding="utf-8"))
gen = json.load(open("gen2_cache.json", encoding="utf-8")) if __import__("os").path.exists("gen2_cache.json") else {}
c = collections.Counter(); need_mt = []
VULG = re.compile(r"пизд|\bху[йяеёи]|\bеб|\bёб|\bебл|\bёбл|\bебан|\bёбан|\bзаеб|\bвыеб|бляд|\bблять|\bсук[аи]\b|мудак|мудил|дроч|долбо|\bжоп", re.I)
VULGAR_EN = {"fuck", "fucker", "fucking", "bitch", "cunt", "motherfucker", "shit", "bullshit", "asshole", "whore", "slut",
             "pussy", "bastard", "douchebag", "masturbate", "fricking", "dick", "cock", "ass", "damn", "crap", "piss", "prick", "twat", "wanker", "bollocks"}
for w in V:
    r, src = ru.get(w["slug"], ["", ""])
    if not r:
        key = ("to " if w["pos"] == "verb" else "") + w["word"]
        r = (mt.get(key) or "").strip().strip(":").strip()
        r = re.sub(r"^[:\-–—\s]+", "", r).rstrip(".!")
        if w["pos"] == "verb": r = re.sub(r"^(для|чтобы)\s+", "", r)
        if r and w["word"][:1].islower() and r[:1].isupper() and not r.isupper(): r = r[0].lower() + r[1:]
        if r.lower() == w["slug"] or not re.search("[а-яё]", r, re.I): r = ""
        src = "mt" if r else ""
    if r and w["slug"] not in VULGAR_EN and VULG.search(r):
        parts = []
        for part in r.split(";"):
            keep = [x.strip() for x in part.split(",") if x.strip() and not VULG.search(x)]
            if keep: parts.append(", ".join(keep))
        r = "; ".join(parts)
        if not r: src = ""
    w["ru"], w["ru_src"] = r, src; c["ru_" + (src or "none")] += 1
    sents = [{"en": en, "ru": rr, "context": None, "context_ru": None, "level": None, "source": "tatoeba", "tatoeba_id": sid}
             for en, rr, sid in tat.get(w["slug"], [])]
    if not sents and (gen.get(w["slug"]) or {}).get("has_word"):
        en = gen[w["slug"]]["en"]
        tr = mt.get(en)
        if tr is None: need_mt.append(en)
        sents = [{"en": en, "ru": tr, "context": None, "context_ru": None, "level": None, "source": "generated"}]
    if w["slug"] not in VULGAR_EN:
        sents = [x for x in sents if not (x.get("ru") and VULG.search(x["ru"]))] or [dict(x, ru=None) for x in sents[:1] if x["source"] == "generated"]
    w["sentences"] = sents
    w["example"] = sents[0]["en"] if sents else None
    w["example_ru"] = sents[0]["ru"] if sents else None
    w["example_source"] = sents[0]["source"] if sents else None
    c[(w["level"], w["example_source"])] += 1
if "--need" in sys.argv:
    json.dump(need_mt, open("mt_gen_need.json", "w", encoding="utf-8"), ensure_ascii=False); print("need mt", len(need_mt)); sys.exit()
json.dump(V, open("vocab.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
for k in sorted(c, key=str): print(k, c[k])
print("need mt", len(need_mt))
