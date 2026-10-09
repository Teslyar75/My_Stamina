import json, re, collections, unicodedata, math, sys
from nltk.corpus import wordnet as wn
import cmudict, phon
L = json.load(open("wordlist.json"))
K = collections.defaultdict(list)
for l in open("kaikki_en.jsonl", encoding="utf-8"):
    e = json.loads(l); K[e["word"].lower()].append(e)
CMU = cmudict.dict()
POSMAP = {"adj": "adjective", "adv": "adverb", "prep": "preposition", "pron": "pronoun", "conj": "conjunction",
          "intj": "interjection", "noun": "noun", "verb": "verb", "article": "determiner", "det": "determiner",
          "num": "number", "particle": "adverb", "postp": "preposition", "name": "noun", "contraction": "other",
          "phrase": "phrase", "prep_phrase": "phrase", "symbol": "other", "character": "other", "suffix": "other", "prefix": "other"}
WNPOS = {"n": "noun", "v": "verb", "a": "adjective", "s": "adjective", "r": "adverb"}
WEAK = {"slang", "neologism", "rare", "dated", "misspelling", "alt-of", "nonstandard", "dialectal", "obsolete", "archaic",
        "Internet", "eye-dialect", "pronunciation-spelling", "vulgar", "offensive", "derogatory", "form-of"}
CLOSED = {"preposition", "pronoun", "conjunction", "determiner", "number", "interjection"}
def clean_gloss(g):
    g = re.sub(r"\s+", " ", g or "").strip()
    if not g: return ""
    g = g[0].upper() + g[1:]
    if g[-1] not in ".!?": g += "."
    return g[:220]
def entries(item):
    es = K.get(item["slug"], [])
    exact = [e for e in es if e["word"] == item["word"]]
    return exact or es
def real_senses(e):
    return [s for s in e["senses"] if s["g"] and not s["fo"] and not (set(s["tags"]) & WEAK)]
def pos_info(item, ents):
    w = item["slug"]
    kpos = []
    for e in ents:
        if real_senses(e):
            p = POSMAP.get(e["pos"], e["pos"])
            if p not in kpos: kpos.append(p)
    cnt = collections.Counter()
    syns = [s for s in wn.synsets(w) if any(l.name() == item["word"] or (l.name().lower() == w and not item["word"][0].islower()) for l in s.lemmas())]
    for s in syns:
        p = WNPOS[s.pos()]
        cnt[p] += sum(l.count() for l in s.lemmas() if l.name().lower() == w) + 0.01
    closed = [p for p in ("determiner", "preposition", "pronoun", "conjunction", "number", "interjection") if p in kpos[:4]]
    if closed and (not cnt or max(cnt.values()) < 5): prim = closed[0]
    elif kpos and (kpos[0] in CLOSED or not cnt): prim = kpos[0]
    elif cnt: prim = cnt.most_common(1)[0][0]
    else: prim = kpos[0] if kpos else "noun"
    allp = [prim] + [p for p in kpos + [p for p, _ in cnt.most_common()] if p != prim]
    allp = list(dict.fromkeys(allp))[:4]
    return prim, allp, syns
def definition(item, prim, syns, ents):
    for s in syns:
        if WNPOS[s.pos()] == prim:
            return clean_gloss(s.definition()), "wordnet", s.lexname()
    for e in ents:
        if POSMAP.get(e["pos"], e["pos"]) == prim:
            rs = real_senses(e)
            if rs: return clean_gloss(rs[0]["g"]), "wiktionary", None
    for e in ents:
        rs = real_senses(e)
        if rs: return clean_gloss(rs[0]["g"]), "wiktionary", None
    if syns: return clean_gloss(syns[0].definition()), "wordnet", syns[0].lexname()
    return "", "", None
def ipa_info(item, ents):
    w = item["slug"]
    if w in CMU:
        ph = CMU[w][0]
        return phon.ipa(ph), ph
    for e in ents:
        us = [i for i, t in e["ipa"] if "US" in t or "General-American" in t] or [i for i, t in e["ipa"]]
        if us:
            i = us[0].strip()
            if not i.startswith("/"): i = "/" + i.strip("[]/") + "/"
            return i, None
    return None, None
VOW = re.compile(r"[aeiouy]+")
def syl_guess(w):
    n = len(VOW.findall(w))
    if w.endswith("e") and not w.endswith(("le", "ee")) and n > 1: n -= 1
    return max(1, n)
IRREG = re.compile(r"gh|ough|augh|^kn|^wr|mb$|^gn|^ps|eigh|ould|tch|que$|ph|^x|cq|sc[ei]|eau|ui|ieu")
def difficulty(rank, w, nsyl, ph):
    s = 0 if rank <= 1000 else 1 if rank <= 3000 else 2 if rank <= 10000 else 3
    s += max(0, nsyl - 2)
    if IRREG.search(w): s += 1
    if ph and abs(len(w) - len(ph)) >= 3: s += 1
    if len(w) >= 11: s += 1
    return "easy" if s <= 1 else "medium" if s <= 3 else "tricky"
def setname(r): return "top-1000" if r <= 1000 else "top-3000" if r <= 3000 else "top-10000" if r <= 10000 else "top-20000"
# homophones for sounds_like
pron2 = collections.defaultdict(list)
slugs = {it["slug"] for it in L}
for w, prs in CMU.items():
    if w in slugs or len(w) > 2:
        pron2[" ".join(prs[0])].append(w)
out = []
for i, item in enumerate(L):
    rank = i + 1; w = item["slug"]
    ents = entries(item)
    prim, allp, syns = pos_info(item, ents)
    d, dsrc, lex = definition(item, prim, syns, ents)
    ipa, ph = ipa_info(item, ents)
    if ph:
        sy = phon.syllabify(ph); nsyl = len(sy); resp = phon.respell(ph)
        guide = phon.guide(item["word"], ph); notes = phon.notes(w, ph)
        hom = [x for x in pron2.get(" ".join(ph), []) if x != w and x in slugs][:3] or None
    else:
        nsyl = syl_guess(w); resp = None; guide = None; notes = []; hom = None
    hy = next((e["hy"][0] for e in ents if e.get("hy")), None)
    breakdown = "·".join(hy) if hy and "".join(hy).lower().replace(" ", "") == w.replace(" ", "") else (resp.lower() if resp else None)
    if hy and "".join(hy).lower() == w: nsyl = len(hy) if not ph else nsyl
    tags = [lex.split(".")[1]] if lex and lex.split(".")[1] not in ("all", "pert", "Tops") else []
    out.append({"id": f"w{rank:05d}", "word": item["word"], "slug": w, "rank": rank, "level": setname(rank),
                "sets": [s for s, lim in (("top-1000", 1000), ("top-3000", 3000), ("top-10000", 10000), ("top-20000", 20000)) if rank <= lim],
                "pos": prim, "pos_all": allp, "difficulty": difficulty(rank, w, nsyl, ph),
                "definition": d, "definition_source": dsrc, "tags": tags,
                "ipa": ipa, "respelling": resp, "syllables": nsyl, "syllable_breakdown": breakdown,
                "guide": guide, "notes": notes, "sounds_like": hom, "common_mistakes": None})
json.dump(out, open("stage1.json", "w", encoding="utf-8"), ensure_ascii=False)
c = collections.Counter()
for r in out:
    for k in ("definition", "ipa", "respelling", "syllable_breakdown", "guide"):
        if r[k]: c[(r["level"], k)] += 1
    c[(r["level"], "diff_" + r["difficulty"])] += 1
for k in sorted(c): print(k, c[k])
for r in out[:3] + [out[399], out[2500], out[15000]]: print(json.dumps(r, ensure_ascii=False))
