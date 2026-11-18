"""Разведка повторов в наборах DE/FR/IT/ES: чем именно отличаются карточки одного слова."""
import collections
import json
import pathlib

ROOT = pathlib.Path("stamina/languages/plugins")
LANGS = ("de", "fr", "it", "es")


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def ex_ids(card):
    return tuple(str(e.get("id")) for e in (card.get("examples") or []))


for lang in LANGS:
    for path in sorted((ROOT / lang).glob("vocab_*.json")):
        data = load(path)
        words = data.get("words") or []
        groups = collections.defaultdict(list)
        for card in words:
            groups[str(card.get("lemma"))].append(card)
        dup = {k: v for k, v in groups.items() if len(v) > 1}
        same_ex = same_pos = diff_gender = diff_tr = 0
        extra = 0
        for k, cards in dup.items():
            sets = {ex_ids(c) for c in cards}
            same_ex += len(sets) == 1
            extra += sum(len(s) for s in sets) - len(set().union(*sets))
            pos = {c.get("pos") for c in cards}
            same_pos += len(pos) == 1
            if len({c.get("gender") for c in cards}) > 1:
                diff_gender += 1
            tr = {json.dumps(c.get("translations") or {}, ensure_ascii=False, sort_keys=True) for c in cards}
            if len(tr) > 1:
                diff_tr += 1
        print(f"{lang} {path.name:14} cards={len(words):6} lemmas={len(groups):6} "
              f"dup_lemmas={len(dup):5} same_examples={same_ex:5} same_pos={same_pos:5} "
              f"diff_gender={diff_gender:4} diff_translations={diff_tr:4} lost_examples_if_naive={extra:5}")
