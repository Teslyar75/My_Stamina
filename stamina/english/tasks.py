"""Генерация заданий миссий (SPEC §5): чтение R1–R3, вопросы Q1–Q4, говорение S1–S3, случайный микс.
Аудирования, диктанта и письменной проверки нет (решение пользователя)."""
from __future__ import annotations

import random
import re

from .textutil import tokens, word_forms
from .vocab import POS_SHORT

MODES = {
    "random": ("СЛУЧАЙНАЯ", "M-RND", "Задания всех типов вперемешку"),
    "speaking": ("ГОВОРЕНИЕ", "M-SPK", "Скажи слово, прочитай предложение, переведи вслух"),
    "reading": ("ЧТЕНИЕ", "M-RDG", "Пропуск в предложении, перевод, смысл в контексте"),
    "questions": ("ВОПРОСЫ", "M-QST", "Определение ↔ слово, часть речи, напиши слово"),
}
TYPES = {
    "speaking": ["S1", "S2", "S3"],
    "reading": ["R1", "R2", "R3"],
    "questions": ["Q1", "Q2", "Q3", "Q4"],
}
TYPE_TITLE = {
    "S1": "СКАЖИ СЛОВО", "S2": "ПРОЧИТАЙ ПРЕДЛОЖЕНИЕ", "S3": "СКАЖИ ПО-АНГЛИЙСКИ",
    "R1": "ЗАПОЛНИ ПРОПУСК", "R2": "ВЫБЕРИ ПЕРЕВОД", "R3": "ЧТО ЗНАЧИТ СЛОВО В КОНТЕКСТЕ?",
    "Q1": "ОПРЕДЕЛЕНИЕ → СЛОВО", "Q2": "СЛОВО → ОПРЕДЕЛЕНИЕ", "Q3": "КАКАЯ ЭТО ЧАСТЬ РЕЧИ?",
    "Q4": "НАПИШИ СЛОВО",
}
POS_RU = {"noun": "существительное", "verb": "глагол", "adjective": "прилагательное", "adverb": "наречие",
          "pronoun": "местоимение", "preposition": "предлог", "conjunction": "союз",
          "interjection": "междометие", "determiner": "определитель"}


def find_form(sentence: str, word: str) -> str | None:
    forms = word_forms(word)
    for m in re.finditer(r"[A-Za-z']+", sentence):
        if m.group(0).lower() in forms:
            return m.group(0)
    return None


class TaskFactory:
    def __init__(self, vocab, progress, rng: random.Random | None = None) -> None:
        self.v, self.p = vocab, progress
        self.rng = rng or random.Random()
        self.pool_all = vocab.in_set("top-3000") or vocab.words

    # -- подбор слов ---------------------------------------------------------
    def pick_words(self, pool: list[dict], n: int, single: dict | None = None) -> list[dict]:
        if single:
            return [single] * n
        slugs = {w["slug"] for w in pool}
        mist = [self.v.get(s) for s in self.p.mistakes(7) if s in slugs]
        due = [self.v.get(s) for s in self.p.due_cards() if s in slugs]
        rest = [w for w in pool if not self.p.is_known(w["slug"])] or list(pool)
        self.rng.shuffle(rest)
        out, count = [], {}
        for w in mist + due + rest:
            if w is None:
                continue
            if count.get(w["slug"], 0) >= 1:
                continue
            count[w["slug"]] = 1
            out.append(w)
            if len(out) >= n:
                break
        while out and len(out) < n:  # маленький пул: слово максимум дважды
            w = self.rng.choice(out[: max(1, len(out))])
            if count[w["slug"]] < 2:
                count[w["slug"]] += 1
                out.append(w)
            elif all(c >= 2 for c in count.values()):
                break
        return out

    # -- дистракторы ----------------------------------------------------------
    def distract_words(self, w: dict, k: int = 3) -> list[dict]:
        same = [x for x in self.pool_all if x["slug"] != w["slug"] and x["pos"] == w["pos"]
                and x["word"].lower() != w["word"].lower()]
        if len(same) < k:
            same = [x for x in self.pool_all if x["slug"] != w["slug"]]
        near = [x for x in same if abs(len(x["word"]) - len(w["word"])) <= 2 or x["word"][0] == w["word"][0]]
        src = near if len(near) >= k * 3 else same
        return self.rng.sample(src, min(k, len(src)))

    # -- задания ---------------------------------------------------------------
    def make(self, w: dict, ttype: str) -> dict | None:
        sents = self.v.sentences(w)
        rng = self.rng
        t = {"type": ttype, "slug": w["slug"], "word": w}
        if ttype == "S1":
            return t
        if ttype in ("S2", "R3"):
            if not sents:
                return None
            t["sentence"] = rng.choice(sents)
            if ttype == "R3":
                opts = [w["definition"]] + [x["definition"] for x in self.distract_words(w, 2)]
                rng.shuffle(opts)
                t.update(options=opts, answer=opts.index(w["definition"]))
            return t
        if ttype == "S3":
            ru = [s for s in sents if s.get("ru")]
            if not ru:
                return None
            t["sentence"] = rng.choice(ru)
            return t
        if ttype == "R1":
            cand = [s for s in sents if find_form(s["en"], w["word"])]
            if not cand:
                return None
            s = rng.choice(cand)
            form = find_form(s["en"], w["word"])
            t["sentence"] = s
            t["cloze"] = re.sub(r"\b" + re.escape(form) + r"\b", "_____", s["en"], count=1)
            opts = [w["word"]] + [x["word"] for x in self.distract_words(w, 3)]
            rng.shuffle(opts)
            t.update(options=opts, answer=opts.index(w["word"]))
            return t
        if ttype == "R2":
            ru = [s for s in sents if s.get("ru")]
            if not ru:
                return None
            s = rng.choice(ru)
            others = []
            for x in rng.sample(self.pool_all, min(60, len(self.pool_all))):
                if x["slug"] == w["slug"]:
                    continue
                xs = [y for y in (x.get("sentences") or []) if y.get("ru")]
                if xs:
                    others.append(rng.choice(xs)["ru"])
                if len(others) >= 2:
                    break
            if len(others) < 2:
                return None
            opts = [s["ru"]] + others
            rng.shuffle(opts)
            t.update(sentence=s, options=opts, answer=opts.index(s["ru"]))
            return t
        if ttype == "Q1":
            opts = [w["word"]] + [x["word"] for x in self.distract_words(w, 3)]
            rng.shuffle(opts)
            t.update(options=opts, answer=opts.index(w["word"]))
            return t
        if ttype == "Q2":
            opts = [w["definition"]] + [x["definition"] for x in self.distract_words(w, 3)]
            rng.shuffle(opts)
            t.update(options=opts, answer=opts.index(w["definition"]))
            return t
        if ttype == "Q3":
            correct = [p for p in (w.get("pos_all") or [w["pos"]]) if p in POS_RU]
            if not correct:
                return None
            others = [p for p in ("noun", "verb", "adjective", "adverb", "preposition", "pronoun")
                      if p not in correct]
            if len(others) < 2:  # слово почти всех частей речи — вопрос бессмысленный
                return None
            opts = [correct[0]] + rng.sample(others, min(3, len(others)))
            rng.shuffle(opts)
            t.update(options=[f"{POS_RU[p]} ({POS_SHORT.get(p, p).lower()})" for p in opts],
                     answers=[i for i, p in enumerate(opts) if p in correct], answer=opts.index(correct[0]))
            return t
        if ttype == "Q4":
            t["revealed"] = 1
            return t
        return None

    def build(self, mode: str, words: list[dict], speech_ok: bool) -> list[dict]:
        if mode == "random":
            types = TYPES["reading"] + TYPES["questions"] + (TYPES["speaking"] if speech_ok else [])
        else:
            types = TYPES[mode]
        out, last, k = [], None, 0
        for w in words:
            if mode == "random":
                order = [t for t in types if t != last]
                self.rng.shuffle(order)
            else:
                order = [types[(k + j) % len(types)] for j in range(len(types))]
            task = None
            for tt in order:
                task = self.make(w, tt)
                if task:
                    break
            if task is None:  # у слова нет предложений — запасной вопрос
                task = self.make(w, "Q1") or self.make(w, "Q2")
            if task:
                out.append(task)
                last = task["type"]
                k += 1
        return out
