import json, re, math, collections, heapq
V = json.load(open("stage1.json", encoding="utf-8"))
fm = json.load(open("formmap.json"))
rank = {w["slug"]: w["rank"] for w in V}
LOWER = {w["slug"]: w["word"][:1].islower() for w in V}
# frequency rank of any token for "ease" scoring
import wordfreq
pairs = json.load(open("pairs.json", encoding="utf-8"))
TOK = re.compile(r"[a-z]+(?:[-'][a-z]+)*")
def lem(t):
    if t in rank: return [t] + ([fm[t]] if t in fm and fm[t] != t else [])
    out = []
    if t in fm: out.append(fm[t])
    for suf, rep in (("ies", "y"), ("es", ""), ("s", ""), ("ed", ""), ("ed", "e"), ("ing", ""), ("ing", "e"), ("ied", "y"), ("er", ""), ("est", ""), ("ly", "")):
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            b = t[: -len(suf)] + rep
            if b in rank: out.append(b)
    if len(t) > 4 and t[-3:] in ("ing",) and t[-4] == t[-5]:
        b = t[:-4]
        if b in rank: out.append(b)
    return out
zipf = {}
def ease(t):
    if t not in zipf: zipf[t] = wordfreq.zipf_frequency(t, "en")
    return zipf[t]
cands = collections.defaultdict(list)
for sid, en, rus in pairs:
    if not (12 <= len(en) <= 100) or not en[0].isupper() or en[-1] not in ".!?": continue
    raw = re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*", en)
    caps = {t.lower() for i, t in enumerate(raw) if i > 0 and t[0].isupper()}
    toks = TOK.findall(en.lower())
    n = len(toks)
    if n < 3 or n > 15: continue
    ru = min(rus, key=len)
    if len(ru) > 130: continue
    ez = [ease(t) for t in toks]
    for t in set(toks):
        for l in lem(t):
            if t in caps and l in rank and LOWER.get(l): continue
            others = [z for tt, z in zip(toks, ez) if tt != t] or [7]
            score = -sum(others) / len(others) + 0.12 * abs(n - 8) + (0.4 if "tom" in toks or "mary" in toks else 0) + (0.3 if t != l else 0)
            h = cands[l]
            item = (-score, sid, en, ru)
            if len(h) < 8: heapq.heappush(h, item)
            elif item > h[0]: heapq.heapreplace(h, item)
best = {}
for w in V:
    h = sorted(cands.get(w["slug"], []), reverse=True)
    lim = 5 if w["rank"] <= 10000 else 3
    seen = set(); sel = []
    for s, sid, en, ru in h:
        k = en.lower()[:25]
        if k in seen: continue
        seen.add(k); sel.append([en, ru, sid])
        if len(sel) >= lim: break
    if sel: best[w["slug"]] = sel
json.dump(best, open("tat_best.json", "w", encoding="utf-8"), ensure_ascii=False)
cov = collections.Counter((w["level"], w["slug"] in best) for w in V)
print(sorted(cov.items()))
for s in ["hit", "leader", "anger", "development", "untenable", "the"]: print(s, best.get(s, [None])[:2])
