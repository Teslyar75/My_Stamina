import json, collections, unicodedata, re
POSMAP = {"adj": "adjective", "adv": "adverb", "prep": "preposition", "pron": "pronoun", "conj": "conjunction",
          "intj": "interjection", "noun": "noun", "verb": "verb", "article": "adjective", "det": "adjective",
          "num": "adjective", "particle": "adverb", "postp": "preposition", "phrase": "phrase", "name": "name"}
CONTENT = {"noun", "verb", "adjective", "adverb"}
def clean(s):
    s = unicodedata.normalize("NFD", s or "")
    s = s.replace("\u0301", "").replace("\u0300", "")
    s = unicodedata.normalize("NFC", s).strip()
    return s if re.search("[а-яё]", s, re.I) else ""
def senses(entries):
    groups = collections.OrderedDict()
    for e in entries:
        caps = e["word"][:1].isupper()
        for t in e["tr"]:
            w = clean(t.get("w"))
            if not w or len(w) > 30: continue
            tags = t.get("tags") or []
            if set(tags) & {"archaic", "obsolete", "dated", "vulgar", "slang", "colloquial", "derogatory", "offensive", "humorous", "rare", "dialectal", "nonstandard"}: continue
            if "." in w or "!" in w or (w[0].isupper() and not w.isupper() and not caps): continue
            groups.setdefault(t.get("sense") or "", []).append((w, tags))
    return list(groups.values())
import math
FREQ = {}
for i, l in enumerate(open("ru_50k.txt", encoding="utf-8")):
    a = l.split()
    if len(a) == 2: FREQ.setdefault(a[0], int(a[1]))
def fscore(w):
    ws = w.lower().split()
    if len(ws) == 1: return math.log(FREQ.get(ws[0], 0) + 1)
    return 0.5 * min(math.log(FREQ.get(x, 0) + 1) for x in ws if len(x) > 2) if any(len(x) > 2 for x in ws) else 0
def pick(entries, n):
    gs = senses(entries); out = []
    cands = []
    for si, g in enumerate(gs[:8]):
        imp = [(w, tg) for w, tg in g if "perfective" not in tg] or g
        for wi, (w, tg) in enumerate(imp[:4]):
            cands.append((fscore(w) - 0.8 * si - 0.3 * wi + (1.5 if si == wi == 0 else 0), si, w))
    cands.sort(key=lambda x: -x[0])
    used_s = collections.Counter()
    for sc, si, w in cands:
        if len(out) >= n: break
        if used_s[si] >= 2 or w.lower() in [o.lower() for o in out]: continue
        out.append(w); used_s[si] += 1
    return out
def _pick_old(entries, n):
    gs = senses(entries); out = []
    def add(w):
        if w.lower() not in [o.lower() for o in out]: out.append(w)
    for g in gs:
        if len(out) >= n: break
        imp = [w for w, tg in g if "perfective" not in tg] or [w for w, _ in g]
        add(imp[0])
    if len(out) < min(2, n) and gs:
        for w, tg in gs[0][1:]:
            if len(out) >= min(2, n): break
            if "perfective" not in tg: add(w)
    return out
POSMAP.update({"article": "determiner", "det": "determiner", "num": "number", "name": "noun"})
V = json.load(open("stage1.json", encoding="utf-8"))
K = collections.defaultdict(list)
for l in open("kaikki_en.jsonl", encoding="utf-8"):
    e = json.loads(l); K[e["word"]].append(e)
for k in list(K):
    for e in K[k]:
        e["form_of"] = next((s["fo"] for s in e["senses"] if s["fo"]), None)
ov = json.load(open("overrides.json", encoding="utf-8"))
CONTENT = {"noun", "verb", "adjective", "adverb"}
res = {}; c = collections.Counter(); need_mt = []
for w in V:
    ww = w["word"]; lw = w["slug"]
    if lw in ov: res[lw] = (ov[lw], "override"); c["override"] += 1; continue
    ents = K.get(ww) or K.get(lw) or []
    if not any(e["tr"] for e in ents):
        alt = (K.get(lw.capitalize()) or []) + (K.get(lw.upper()) or [])
        if any(e["tr"] for e in alt): ents = alt
    if lw == "i": ents = K.get("I", [])
    bypos = collections.OrderedDict()
    for e in ents: bypos.setdefault(POSMAP.get(e["pos"], e["pos"]), []).append(e)
    prim = w["pos"]; parts = []
    main = pick(bypos.get(prim, []), 3)
    if main: parts.append(", ".join(main))
    for pos, es in bypos.items():
        if pos == prim or len(parts) >= 2: continue
        if main and not ({pos, prim} <= CONTENT): continue
        if pos in ("name", "phrase") and parts: continue
        x = pick(es, 2 if main else 3)
        if x: parts.append(", ".join(x))
    if parts: res[lw] = ("; ".join(parts), "wiktionary"); c["wiktionary"] += 1
    else: need_mt.append(w); res[lw] = ("", "")
json.dump({k: list(v) for k, v in res.items()}, open("ru_stage.json", "w", encoding="utf-8"), ensure_ascii=False)
json.dump([("to " if w["pos"] == "verb" else "") + w["word"] for w in need_mt], open("mt_words.json", "w"))
print(c, "need mt", len(need_mt))
