import json, re, sys
from transformers import MarianMTModel, MarianTokenizer
keys = list(json.load(open('/workspace/qs/repo/stamina/i18n/ru.json')))
CY = re.compile('[А-Яа-яЁё]')
LET = re.compile(r'[A-Za-zА-Яа-яЁё0-9{]')
def load(m):
    tok = MarianTokenizer.from_pretrained(f'Helsinki-NLP/opus-mt-{m}')
    mod = MarianMTModel.from_pretrained(f'Helsinki-NLP/opus-mt-{m}')
    def tr(texts):
        out = []
        for i in range(0, len(texts), 32):
            b = tok(texts[i:i+32], return_tensors='pt', padding=True, truncation=True)
            g = mod.generate(**b, num_beams=3, max_new_tokens=200)
            out += tok.batch_decode(g, skip_special_tokens=True)
        return out
    return tr
# segments: split key into lines and " · " parts, strip prefix/suffix symbols, protect placeholders
def segs(key):
    res = []  # list of (prefix, core, suffix, caps) or literal str
    for li, line in enumerate(key.split('\n')):
        if li: res.append('\n')
        for pi, part in enumerate(line.split(' · ')):
            if pi: res.append(' · ')
            if not CY.search(part):
                res.append(part); continue
            m = re.match(r'^([^A-Za-zА-Яа-яЁё0-9{«"(]*)(.*?)([\s:.,!?…→←↑↓►▸•★%)»"]*)$', part, re.S)
            pre, core, suf = m.group(1), m.group(2), m.group(3)
            if suf and core.endswith(('.', '!', '?')) is False and suf.strip() in ('.', '!', '?'):
                pass
            caps = core.upper() == core and len(re.sub(r'[^А-ЯЁ]', '', core)) >= 2
            ph = re.findall(r'\{[^{}]*\}', core)
            c = core
            for i, p in enumerate(ph):
                c = c.replace(p, f'{900 + i}', 1)
            if caps:
                c = c.lower(); c = c[:1].upper() + c[1:]
            res.append((pre, c, suf, caps, ph))
    return res
all_segs = {k: segs(k) for k in keys}
cores = sorted({s[1] for v in all_segs.values() for s in v if isinstance(s, tuple)})
print('segments', len(cores), file=sys.stderr)
def assemble(trmap):
    out = {}
    for k, v in all_segs.items():
        r = []
        ok = True
        for s in v:
            if isinstance(s, str): r.append(s); continue
            pre, c, suf, caps, ph = s
            x = trmap[c].strip()
            if caps: x = x.upper()
            for i, p in enumerate(ph):
                if f'{900+i}' in x: x = x.replace(f'{900+i}', p, 1)
                else: ok = False
            # avoid double punctuation
            if suf.strip() and x.endswith(suf.strip()[:1]): x = x[:-1]
            r.append(pre + x + suf)
        out[k] = ''.join(r) if ok else ''
    return out
lang = sys.argv[1]
import os
def cached(name, model, src_of):
    path = f'/workspace/i18n_mt/core_{name}.json'
    d = json.load(open(path)) if os.path.exists(path) else {}
    miss = [c for c in cores if c not in d]
    if miss:
        d.update(zip(miss, load(model)([src_of(c) for c in miss])))
        json.dump(d, open(path, 'w'), ensure_ascii=False)
    return d
if lang == 'en':
    trmap = cached('en', 'ru-en', lambda c: c)
elif lang == 'de':
    en = cached('en', 'ru-en', lambda c: c)
    trmap = cached('de', 'en-de', lambda c: en[c])
else:
    trmap = cached('uk', 'ru-uk', lambda c: c)
json.dump(assemble(trmap), open(f'/workspace/i18n_mt/{lang}.json','w'), ensure_ascii=False, indent=1)
print('done', lang, file=sys.stderr)
