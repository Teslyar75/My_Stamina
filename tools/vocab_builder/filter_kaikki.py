import sys, json
want = set(json.load(open("cand.json")))
out = open("kaikki_en.jsonl", "w", encoding="utf-8")
n = k = 0
def isru(t): return t.get("code") == "ru" or t.get("lang_code") == "ru" or t.get("lang") == "Russian"
for line in sys.stdin:
    n += 1
    if n % 200000 == 0: print(n, k, flush=True)
    try: e = json.loads(line)
    except Exception: continue
    w = e.get("word", "")
    if w.lower() not in want: continue
    tr = [{"w": t.get("word"), "sense": t.get("sense"), "tags": t.get("tags")} for t in (e.get("translations") or []) if isru(t)]
    senses = []
    for s in e.get("senses") or []:
        for t in s.get("translations") or []:
            if isru(t): tr.append({"w": t.get("word"), "sense": t.get("sense") or (s.get("glosses") or [""])[0], "tags": t.get("tags")})
        fo = s.get("form_of") or s.get("alt_of")
        senses.append({"g": (s.get("glosses") or [""])[0], "tags": s.get("tags") or [], "fo": fo[0].get("word") if fo else None,
                       "ex": [x.get("text") for x in (s.get("examples") or [])][:0]})
    ipa = [x.get("ipa") for x in (e.get("sounds") or []) if x.get("ipa")]
    ipa_t = [(x.get("ipa"), x.get("tags") or []) for x in (e.get("sounds") or []) if x.get("ipa")]
    hy = [h.get("parts") for h in (e.get("hyphenations") or []) if h.get("parts")] or ([e["hyphenation"]] if e.get("hyphenation") else [])
    out.write(json.dumps({"word": w, "pos": e.get("pos"), "tr": tr, "senses": senses[:8], "ipa": ipa_t[:6], "hy": hy[:1]}, ensure_ascii=False) + "\n"); k += 1
print("done", n, k, flush=True)
