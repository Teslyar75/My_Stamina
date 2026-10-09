import bz2, csv, json, re, collections, sys
csv.field_size_limit(10**9)
def rd(fn):
    with bz2.open(fn, "rt", encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            yield p
links = collections.defaultdict(list)
for p in rd("eng-rus_links.tsv.bz2"):
    links[p[0]].append(p[1])
rus = {}
need_r = {r for v in links.values() for r in v}
for p in rd("rus_sentences.tsv.bz2"):
    if p[0] in need_r: rus[p[0]] = p[2]
pairs = []
for p in rd("eng_sentences.tsv.bz2"):
    if p[0] in links:
        r = [rus[x] for x in links[p[0]] if x in rus]
        if r: pairs.append((p[0], p[2], r))
json.dump(pairs, open("pairs.json", "w", encoding="utf-8"), ensure_ascii=False)
print("eng-rus pairs:", len(pairs))
