import json, os, sys, torch
from transformers import MarianMTModel, MarianTokenizer
CACHE = "mt_cache.json"
def translate(texts, bs=32, beams=4):
    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    todo = sorted({t for t in texts if t and t not in cache}, key=len)
    if todo:
        torch.set_num_threads(6)
        m = "Helsinki-NLP/opus-mt-en-ru"; tok = MarianTokenizer.from_pretrained(m); mod = MarianMTModel.from_pretrained(m).eval()
        for i in range(0, len(todo), bs):
            b = todo[i:i + bs]
            with torch.no_grad():
                enc = tok(b, return_tensors="pt", padding=True, truncation=True, max_length=256)
                out = mod.generate(**enc, num_beams=beams, max_new_tokens=200)
            for s, o in zip(b, out): cache[s] = tok.decode(o, skip_special_tokens=True)
            if (i // bs) % 20 == 0:
                json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False); print(i, len(todo), flush=True)
        json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return cache
if __name__ == "__main__":
    texts = json.load(open(sys.argv[1], encoding="utf-8"))
    translate(texts)
    print("done")
