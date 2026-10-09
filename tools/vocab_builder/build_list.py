import json, re, collections
from nltk.corpus import wordnet as wn
cand = json.load(open("cand.json"))
K = collections.defaultdict(list)
for l in open("kaikki_en.jsonl", encoding="utf-8"):
    e = json.loads(l); K[e["word"].lower()].append(e)
BAD = {"vulgar", "offensive", "derogatory", "slur", "ethnic", "obsolete", "archaic"}
WEAK = {"slang", "neologism", "rare", "dated", "misspelling", "alt-of", "nonstandard", "dialectal", "obsolete", "archaic", "Internet", "eye-dialect", "pronunciation-spelling"}
CLOSED = {"pron", "det", "article", "prep", "conj", "num", "particle", "intj", "postp"}
FORMTAGS = {"form-of", "alt-of", "plural", "past", "participle", "third-person", "comparative", "superlative", "present", "abbreviation", "misspelling", "alternative", "initialism", "acronym", "obsolete"}
NAMEBAD = re.compile(r"given name|surname|male name|female name|placename|place name|county|city|town|village|river|unisex|diminutive of|nickname|hypocoristic|state of|province|company|brand|band|film|novel|island|region|mountain|capital", re.I)
NAMEOK = re.compile(r"month of|day of the week|\bcountry\b|continent|ocean|\blanguage\b|inhabitant|native of|people of|Christmas|holiday|festival|God\b|planet", re.I)
def lemma_of(w):
    ents = K.get(w, [])
    real = []; fos = []
    for e in ents:
        if e["word"] != w and e["word"].lower() == w and e["pos"] != "name": pass
        for s in e["senses"]:
            if s["fo"]:
                if "form-of" in s["tags"] and not (set(s["tags"]) & WEAK): fos.append(s["fo"])
            elif s["g"] and not (set(s["tags"]) & (BAD | WEAK)):
                real.append((e, s))
    return real, fos
def ok_name(e):
    gl = e["senses"][0]["g"] if e["senses"] else ""
    if e["pos"] == "adj": return bool(e["tr"])
    if e["pos"] != "name": return bool(e["tr"]) and bool(NAMEOK.search(gl))
    if not NAMEOK.search(gl) or re.search(r"given name|surname", gl, re.I): return False
    return True
TOK = re.compile(r"^[a-z]+(?:['-][a-z]+)?$")
STOP_SINGLE = {"a", "i"}
out = []; seen = {}; formmap = {}
for i, w in enumerate(cand):
    if not TOK.match(w) or (len(w) == 1 and w not in STOP_SINGLE) or "'" in w: continue
    real, fos = lemma_of(w)
    lowreal = [(e, s) for e, s in real if e["word"] == w and e["pos"] not in ("name",)]
    capreal = [(e, s) for e, s in real if e["word"] != w and e["word"].lower() == w and ok_name(e) and e["word"][0].isupper()]
    wnok = bool(wn.synsets(w)) and any(l.name() == w for s in wn.synsets(w) for l in s.lemmas())
    target = None
    isname = any(e["pos"] == "name" and e["senses"] and re.search(r"given name|surname|placename|place name|city|town|county|state of", e["senses"][0]["g"], re.I) and not NAMEOK.search(e["senses"][0]["g"]) for e in K.get(w, []))
    isname = isname and not any(e["pos"] == "name" and e["senses"] and NAMEOK.search(e["senses"][0]["g"]) and not NAMEBAD.search(e["senses"][0]["g"]) for e in K.get(w, []))
    anyname = any(e["pos"] == "name" and re.search(r"given name|surname", " ".join(x["g"] for x in e["senses"]), re.I) for e in K.get(w, []))
    if (isname and len(lowreal) <= 2 and not capreal) or (anyname and not capreal and not wnok and len(lowreal) <= 2 and not any(e["word"] == w and e["pos"] in ("verb", "adj", "adv") for e, s in lowreal)): continue
    # inflection: no own (non-name) lemma senses with substance, but form_of exists
    lowabbr = all(set(s["tags"]) & {"abbreviation", "initialism", "acronym", "misspelling", "alternative", "nonstandard", "pronunciation-spelling", "informal"} for e, s in lowreal) if lowreal else True
    if fos and not any(e["pos"] in CLOSED for e, s in lowreal) and (not lowreal or len(lowreal) <= 3 or len(fos) >= len(lowreal)):
        lem = fos[0].lower()
        if TOK.match(lem) and lem != w and (len(lem) > 1 or lem in STOP_SINGLE): target = lem
    if target is None:
        if lowreal and (not lowabbr or wnok): target = w; disp = w
        elif capreal: target = w; disp = capreal[0][0]["word"]
        elif wnok and lowreal: target = w; disp = w
        else: continue
    else:
        formmap[w] = target
        disp = target
        if target in seen: continue
        # lemma must itself be valid
        r2, _ = lemma_of(target)
        if not any(e["word"] == target for e, s in r2) and not wn.synsets(target): continue
    if target in seen: continue
    seen[target] = len(out)
    out.append({"word": disp, "slug": target, "wf_index": i})
    if len(out) >= 20000: break
json.dump(out, open("wordlist.json", "w"), ensure_ascii=False)
json.dump(formmap, open("formmap.json", "w"))
print(len(out), "last index", out[-1]["wf_index"])
print([o["word"] for o in out[:120]])
print([o["word"] for o in out[2990:3040]])
print([o["word"] for o in out[19950:]])
