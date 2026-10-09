import json, os, re, time, torch, sys
from transformers import AutoTokenizer, AutoModelForCausalLM
torch.set_num_threads(7)
V = json.load(open("stage1.json", encoding="utf-8"))
best = json.load(open("tat_best.json", encoding="utf-8"))
MAXRANK = int(sys.argv[1])
CACHE = "gen_cache.json"   # new cache: prompts use only our open (WordNet/Wiktionary) definitions
cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
def forms(w):
    w = w.lower(); f = {w, w + "s", w + "es", w + "ed", w + "d", w + "ing", w + "er", w + "est", w + "ly"}
    if w.endswith("e"): f |= {w[:-1] + "ing"}
    if w.endswith("y"): f |= {w[:-1] + "ies", w[:-1] + "ied"}
    if len(w) > 2 and w[-1] not in "aeiouwxy": f |= {w + w[-1] + "ed", w + w[-1] + "ing"}
    return f
def ok(w, s):
    toks = set(re.findall(r"[a-z]+(?:[-'][a-z]+)*", s.lower()))
    return bool(toks & forms(w)) and 15 <= len(s) <= 140
todo = [w for w in V if w["rank"] <= MAXRANK and w["slug"] not in best and not (cache.get(w["slug"]) or {}).get("has_word")]
print("todo", len(todo), flush=True)
m = "Qwen/Qwen2.5-1.5B-Instruct"
tok = AutoTokenizer.from_pretrained(m); tok.padding_side = "left"
mod = AutoModelForCausalLM.from_pretrained(m, dtype=torch.bfloat16).eval()
SYS = "You write one short, natural, simple English example sentence (6-12 words) for a language learner. The sentence MUST contain the exact given word. Output only the sentence."
def run(batch, sample):
    msgs = [[{"role": "system", "content": SYS}, {"role": "user", "content": f'Word: "{w["word"]}" ({w["pos"]}). Meaning: {w["definition"]} The sentence must include the word "{w["word"]}".'}] for w in batch]
    enc = tok([tok.apply_chat_template(x, tokenize=False, add_generation_prompt=True) for x in msgs], return_tensors="pt", padding=True)
    with torch.no_grad():
        out = mod.generate(**enc, max_new_tokens=40, do_sample=sample, temperature=0.8 if sample else None, top_p=0.9 if sample else None)
    return [tok.decode(o[enc["input_ids"].shape[1]:], skip_special_tokens=True).strip().strip('"').split("\n")[0] for o in out]
t0 = time.time()
for attempt in range(3):
    todo = [w for w in todo if not (cache.get(w["slug"]) or {}).get("has_word")]
    for i in range(0, len(todo), 16):
        b = todo[i:i + 16]
        res = run(b, attempt > 0)
        for w, s in zip(b, res):
            if ok(w["word"], s) or w["slug"] not in cache:
                cache[w["slug"]] = {"en": s, "has_word": ok(w["word"], s)}
        json.dump(cache, open(CACHE + ".tmp", "w", encoding="utf-8"), ensure_ascii=False); os.replace(CACHE + ".tmp", CACHE)
        print(time.strftime("%H:%M:%S"), attempt, i + len(b), "/", len(todo), "rank", b[-1]["rank"], round(time.time() - t0), flush=True)
print("done", sum(1 for v in cache.values() if v["has_word"]))
