"""Страница «ГРАММАТИКА» для отсека «ИНОСТРАННЫЕ ЯЗЫКИ» (de, fr, es, it).

Общий разворот: слева список, справа весь урок.
Языко-специфичные отличия приходят адаптерами (GrammarCatalog):
- мостик RU/UA → целевой язык и ловушка из bridges.json
- таблицы по ссылке в правой панели
- банк слов и подсказки в упражнениях
- инструкции для упражнений с кириллицей («Переведите на …»)
Вкладки источников задаются списком (курс, позже открытые источники) — контент
вкладки подгружается лениво.
"""
from __future__ import annotations

import random
import re
import tkinter as tk

from stamina.hud import HudButton
from stamina.i18n import t as _t
from stamina.languages.core.progress import GRAMMAR_PASS, LanguageProgress
from stamina.languages.core.sqlite_vocab import gloss_lang
from stamina.languages.ctx import LangCtx
from stamina.languages.speech import asr_for
from stamina.theme import GREEN, MUTED, PANEL, TEXT, px
from stamina import theme
from stamina.grammar_ui.model import SourceTab
from stamina.grammar_ui.spread import GrammarSpread, LIST_CHUNK
from stamina.english.ui import L

#: Порог «урок засчитан» — тот же, что в LanguageProgress.record_grammar.
PASS_SCORE = GRAMMAR_PASS
#: Совместимость: размер порции списка (общий разворот рисует по LIST_CHUNK).
CHUNK = LIST_CHUNK

CHOICE_TYPES = {"choice", "match", "identify"}
FILL_TYPES = {"fill", "declension", "conjugation", "gap"}
REORDER_TYPES = {"reorder"}

INSTRUCTION_CHOICE = _t("Выберите один правильный вариант.")
INSTRUCTION_FILL = _t("Впишите пропущенное слово в нужной форме.")
INSTRUCTION_TRANSFORM = _t("Перепишите предложение по заданию.")
INSTRUCTION_REORDER = _t("Составьте предложение: нажимайте на слова по порядку.")

SELF_CHECK_SIZE = 12
SELF_CHECK_ID = "__self_check__"
COURSE_SOURCE = "course"
COURSE_TAB = SourceTab(id=COURSE_SOURCE, title=_t("Курс Star Typing"))

_CYRILLIC = re.compile(_t("[а-яА-ЯёЁіІїЇєЄґҐ]"))

# Language-specific instruction templates
TRANSLATE_INSTRUCTIONS = {
    "de": _t("Переведите на немецкий."),
    "fr": _t("Переведите на французский."),
    "es": _t("Переведите на испанский."),
    "it": _t("Переведите на итальянский."),
}
TRANSLATE_WRITE_INSTRUCTIONS = {
    "de": _t("Переведите на немецкий и впишите ответ."),
    "fr": _t("Переведите на французский и впишите ответ."),
    "es": _t("Переведите на испанский и впишите ответ."),
    "it": _t("Переведите на итальянский и впишите ответ."),
}

# Backward compatibility for tests
INSTRUCTION_TRANSLATE = TRANSLATE_INSTRUCTIONS["de"]
INSTRUCTION_TRANSLATE_WRITE = TRANSLATE_WRITE_INSTRUCTIONS["de"]


def _normalize_sentence(text: str) -> str:
    text = re.sub(r"\s+([,.;:!?])", r"\1", text.strip())
    return re.sub(r"\s+", " ", text)


def _lower(text: str) -> str:
    return (text or "").lower().replace("ä", "ae").replace("ö", "oe") \
        .replace("ü", "ue").replace("ß", "ss")


def _canon(text: str) -> str:
    return re.sub(r"\s+", " ", _lower(text).strip()).strip(" .,;:!?…—–-")


def _canon_plain(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).strip(" .,;:!?…—–-")


def _words(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", _lower(text))


def _answer_matches(kind: str, value: str, expected: list[str]) -> bool:
    if kind in REORDER_TYPES or kind == "transform":
        got = _words(value)
        return bool(got) and any(got == _words(item) for item in expected)
    if kind in CHOICE_TYPES:
        return any(_canon_plain(value) == _canon_plain(item) for item in expected)
    return any(_canon(value) == _canon(item) for item in expected)


def _prompt_words(prompt: str) -> list[str]:
    match = re.search(r"'([^']+)'", prompt or "")
    if not match:
        return []
    return [w.strip() for w in match.group(1).split("/") if w.strip()]


def _word_bank(drill: dict) -> list[str]:
    answer = drill.get("answer") or [""]
    expected = answer[0] if isinstance(answer, (list, tuple)) else str(answer)
    words = _prompt_words(drill.get("prompt", ""))
    expected_tokens = [w for w in re.split(r"\s+", expected.strip()) if w]

    def key(token: str) -> str:
        return token.strip(".,;:!?").lower()

    if words and sorted(map(key, words)) == sorted(map(key, expected_tokens)):
        return words
    return [w for w in expected_tokens if w]


def _shuffled(words: list[str], seed_text: str) -> list[str]:
    rng = random.Random(seed_text)
    out = list(words)
    rng.shuffle(out)
    return out


def _instruction(drill: dict, lang: str = "de") -> str:
    kind = drill.get("type")
    prompt = drill.get("prompt", "")
    if kind in REORDER_TYPES:
        return _t(INSTRUCTION_REORDER)
    if _CYRILLIC.search(prompt or ""):
        if kind in FILL_TYPES or kind == "transform":
            return _t(TRANSLATE_WRITE_INSTRUCTIONS.get(lang, TRANSLATE_WRITE_INSTRUCTIONS["de"]))
        return _t(TRANSLATE_INSTRUCTIONS.get(lang, TRANSLATE_INSTRUCTIONS["de"]))
    if kind == "transform":
        return _t(INSTRUCTION_TRANSFORM)
    if kind in FILL_TYPES:
        return _t(INSTRUCTION_FILL)
    return _t(INSTRUCTION_CHOICE)


def _expected_of(drill: dict) -> list[str]:
    answer = drill.get("answer", drill.get("a", []))
    if isinstance(answer, (list, tuple)):
        return [str(item) for item in answer]
    return [str(answer)]


def _hint_text(drill: dict) -> str:
    expected = _expected_of(drill)
    answer = expected[0] if expected else ""
    if drill.get("type") in REORDER_TYPES:
        first = answer.split(" ")[0] if answer else ""
        return _t("Подсказка: первое слово — «{0}»").format(first)
    letters = [char for char in answer if char.isalpha()]
    if not letters:
        return _t("Подсказка: в ответе только цифры.")
    return _t("Подсказка: ответ из {0} букв, начинается на «{1}»").format(
        len(letters), letters[0])


def _adapt_theory_and_examples(lesson: dict, engine) -> tuple[list[dict], list[dict]]:
    theory: list[dict] = []
    examples: list[dict] = []
    for block in lesson.get("theory") or []:
        kind = block.get("kind")
        if kind == "example":
            examples.append({
                "de": block.get("de") or "",
                "ru": block.get("ru") or "",
                "en": block.get("de") or "",
                "speak": block.get("de") or "",
            })
            if block.get("note"):
                examples[-1]["ru"] = (examples[-1]["ru"] + "\n" + block["note"]).strip()
            continue
        item: dict = {"h": block.get("title") or "", "p": block.get("text") or ""}
        if kind == "table" and block.get("ref"):
            # таблицу с диска не читаем: только ссылка; файл — при открытии в правой панели
            item["table_ref"] = block["ref"]
            item["table_title"] = block.get("title") or block["ref"]
        theory.append(item)
    return theory, examples


def _adapt_drill(drill: dict, lang: str = "de") -> dict:
    kind = drill.get("type") or "fill"
    answers = _expected_of(drill)
    options = list(drill.get("options") or [])
    item = {
        "type": kind,
        "q": drill.get("prompt") or drill.get("q") or "",
        "prompt": drill.get("prompt") or "",
        "options": options,
        "a": drill.get("a", drill.get("answer")),
        "answer": answers,
        "why": drill.get("why") or "",
        "instruction": _instruction(drill, lang),
        "hint_enabled": kind in FILL_TYPES or kind == "transform",
        "raw": drill,
        "id": drill.get("id"),
        "set_id": drill.get("set_id"),
        "set_title": drill.get("set_title"),
    }
    return item


class BaseGrammarCatalog:
    """Базовый каталог грамматики: общая логика для всех языков."""

    show_source_tabs = True
    lang_code = "de"
    translate_lang_name = "немецкий"

    def __init__(self, engine, progress: LanguageProgress | None, page: "GrammarPage") -> None:
        self.engine = engine
        self.progress = progress
        self.page = page
        self._source = COURSE_SOURCE
        self._open = None
        self._self_check: dict | None = None
        self.records_score = True

    def _ensure_open(self):
        return None

    def paint_title_flag(self, slot) -> None:
        from stamina.grammar_ui.flags import paint_title_flag
        paint_title_flag(slot, self.lang_code)

    def sources(self) -> list[SourceTab]:
        return [COURSE_TAB]

    def select_source(self, source_id: str) -> None:
        self._source = source_id
        self._self_check = None
        self.records_score = True

    def current_source_id(self) -> str:
        return self._source

    @property
    def levels(self) -> list[str]:
        if self._source == COURSE_SOURCE:
            return [item["code"] for item in self.engine.levels()] or ["A1"]
        return ["all"]

    def load_index(self) -> None:
        if self._source == COURSE_SOURCE:
            self.engine.levels()
            return

    def index_loaded(self) -> bool:
        if self._source == COURSE_SOURCE:
            return self.engine._courses is not None
        return False

    def header_subtitle(self, level: str) -> str:
        if self._source == COURSE_SOURCE:
            info = next((item for item in self.engine.levels() if item["code"] == level), None)
            if info:
                return "{} · {}".format(info.get("title") or level, info.get("lessons") or "")
            return _t("Курс Star Typing")
        return self._source

    def progress_text(self) -> str:
        if self._source != COURSE_SOURCE:
            topics = self._topic_summaries()
            done = sum(1 for item in topics if self.progress and self.progress.grammar_done(item["id"]))
            return "{}: {} / {}".format(_t("ПРОЙДЕНО"), done, len(topics))
        total = sum(int(item.get("lessons") or 0) for item in self.engine.levels())
        done = 0
        if self.progress:
            for entry in (self.progress.data.get("grammar") or {}).values():
                if isinstance(entry, dict) and entry.get("done"):
                    done += 1
        return "{}: {} / {}".format(_t("ПРОЙДЕНО"), done, total)

    def _topic_summaries(self) -> list[dict]:
        return []

    def list_plan(self, level: str) -> list[tuple[str, object]]:
        plan: list[tuple[str, object]] = []
        if self._source == COURSE_SOURCE:
            for unit in self.engine.lesson_summaries(level):
                plan.append(("unit", {
                    "id": unit["id"],
                    "number": f"{int(unit.get('order') or 0):02d}",
                    "title": unit.get("title") or unit["id"],
                    "level": unit.get("level") or level,
                }))
            return plan
        return plan

    def first_unit(self, level: str):
        plan = self.list_plan(level)
        for kind, item in plan:
            if kind == "unit":
                return item["id"]
        return None

    def level_of(self, unit_id) -> str:
        if unit_id == SELF_CHECK_ID:
            return self.page.spread._level if self.page.spread else (self.levels[0] if self.levels else "A1")
        if self._source == COURSE_SOURCE:
            cefr = self.engine._cefr_of(str(unit_id))
            return cefr or "A1"
        return "all"

    def load_lesson(self, unit_id) -> dict:
        if unit_id == SELF_CHECK_ID:
            return self._self_check or self._build_self_check(self.page.spread._level)
        if self._source == COURSE_SOURCE:
            return self._load_course_lesson(str(unit_id))
        return self._load_open_topic(str(unit_id))

    def _load_course_lesson(self, lesson_id: str) -> dict:
        lesson = self.engine.lesson(lesson_id)
        if not lesson:
            raise FileNotFoundError(lesson_id)
        bridge = self.engine.bridge(lesson_id) or {}
        theory, examples = _adapt_theory_and_examples(lesson, self.engine)
        drills = [_adapt_drill(drill, self.lang_code) for drill in (lesson.get("drills") or [])]
        vocabulary = self._extract_vocabulary(lesson)
        missing = []
        if self.progress:
            titles = []
            for prereq in lesson.get("prereq") or []:
                if self.progress.grammar_done(prereq):
                    continue
                found = self.engine._lesson_lru.get(prereq)
                if found is None:
                    cefr = self.engine._cefr_of(prereq)
                    if cefr and cefr in self.engine._summaries_cache:
                        found = next((item for item in self.engine._summaries_cache[cefr]
                                      if item.get("id") == prereq), None)
                titles.append((found or {}).get("title") or prereq)
            missing = titles
        warning = ""
        if missing:
            warning = _t("Сначала пройдите: {0}").format(", ".join(missing))
        return {
            "n": lesson_id,
            "id": lesson_id,
            "title": lesson.get("title") or lesson_id,
            "en": lesson.get("subtitle") or "",
            "level": lesson.get("level") or self.engine._cefr_of(lesson_id) or "",
            "summary": lesson.get("subtitle") or "",
            "can_do": [bridge["can_do"]] if bridge.get("can_do") else [],
            "can_do_title": _t("ЧТО ВЫ ОСВОИТЕ"),
            "bridge": bridge.get("bridge") or "",
            "trap_text": bridge.get("trap") or "",
            "theory": theory,
            "examples": examples,
            "traps": [],
            "exercises": drills,
            "vocabulary": vocabulary,
            "prereq_warning": warning,
            "raw": lesson,
        }

    def _load_open_topic(self, topic_id: str) -> dict:
        return {
            "n": topic_id,
            "id": topic_id,
            "title": topic_id,
            "en": "",
            "level": "",
            "summary": "",
            "can_do": [],
            "theory": [],
            "examples": [],
            "traps": [],
            "exercises": [],
            "raw": {},
        }

    def _get_vocab_source(self):
        """Lazily load vocabulary source from plugin."""
        if not hasattr(self, "_vocab_source"):
            self._vocab_source = None
            try:
                self._vocab_source = self.page.plugin.load_vocab()
            except Exception:
                self._vocab_source = None
        return self._vocab_source

    def _extract_vocabulary(self, lesson: dict) -> list[dict]:
        """Extract vocabulary from lesson: lemmas from examples and drills that exist in vocab."""
        vocab_source = self._get_vocab_source()
        if not vocab_source:
            return []

        seen = set()
        vocab_items = []

        def add_word(form: str):
            form = (form or "").strip().lower()
            if not form or form in seen:
                return
            seen.add(form)
            results = vocab_source.search(form)
            for word in results:
                if word.lemma.lower() == form and word.translations:
                    target_lang = gloss_lang()
                    # Only use target language translation, don't fall back to en
                    tr = getattr(word, "translations", None) or {}
                    values = [v for v in (tr.get(target_lang) or []) if v]
                    if values:
                        vocab_items.append({
                            "lemma": word.lemma,
                            "translation": ", ".join(values[:3]),
                            "pronunciation": "—",
                        })
                        return

        for block in lesson.get("theory") or []:
            if block.get("kind") == "example":
                lang_field = self.lang_code
                if lang_field in block:
                    add_word(block[lang_field])

        for drill in lesson.get("drills") or []:
            prompt = drill.get("prompt", "")
            for token in re.findall(r"[^\W_]+", prompt, re.UNICODE):
                add_word(token)
            for opt in drill.get("options") or []:
                for token in re.findall(r"[^\W_]+", opt, re.UNICODE):
                    add_word(token)
            answer = drill.get("answer", drill.get("a", []))
            if isinstance(answer, list):
                for ans in answer:
                    for token in re.findall(r"[^\W_]+", str(ans), re.UNICODE):
                        add_word(token)
            elif answer:
                for token in re.findall(r"[^\W_]+", str(answer), re.UNICODE):
                    add_word(token)

        return vocab_items

    def neighbours(self, unit_id):
        if unit_id == SELF_CHECK_ID:
            return None, None
        if self._source == COURSE_SOURCE:
            level = self.level_of(unit_id)
            ids = [item["id"] for item in self.engine.lesson_summaries(level)]
        else:
            ids = [item["id"] for item in self._topic_summaries()]
        try:
            index = ids.index(unit_id)
        except ValueError:
            return None, None
        prev_n = ids[index - 1] if index > 0 else None
        next_n = ids[index + 1] if index + 1 < len(ids) else None
        return prev_n, next_n

    def hint_for_unit(self, unit_id) -> str:
        if unit_id == SELF_CHECK_ID:
            return _t("Самопроверка")
        if self._source == COURSE_SOURCE:
            level = self.level_of(unit_id)
            ids = [item["id"] for item in self.engine.lesson_summaries(level)]
        else:
            ids = [item["id"] for item in self._topic_summaries()]
        try:
            index = ids.index(unit_id) + 1
        except ValueError:
            index = 1
        return _t("Урок {0} из {1}").format(index, len(ids) or 1)

    def unit_number(self, unit_id) -> int:
        if unit_id == SELF_CHECK_ID:
            return 0
        if self._source == COURSE_SOURCE:
            lesson = self.engine.lesson(str(unit_id)) or {}
            return int(lesson.get("order") or 0)
        ids = [item["id"] for item in self._topic_summaries()]
        try:
            return ids.index(str(unit_id)) + 1
        except ValueError:
            return 0

    def is_done(self, unit_id) -> bool:
        if not self.progress or unit_id == SELF_CHECK_ID:
            return False
        return bool(self.progress.grammar_done(str(unit_id)))

    def mark_complete(self, unit_id, ok: int, total: int) -> bool:
        if not self.progress or unit_id == SELF_CHECK_ID or not self.records_score:
            return False
        first = not self.progress.grammar_done(str(unit_id))
        self.progress.record_grammar(str(unit_id), ok, total)
        return first and self.progress.grammar_done(str(unit_id))

    def is_passing(self, ok: int, total: int) -> bool:
        if total <= 0:
            return False
        return (ok / total) >= PASS_SCORE

    def lesson_answers(self, ex: dict) -> list[str]:
        raw = ex.get("raw") or ex
        return _expected_of(raw if "answer" in raw or "a" in raw else ex)

    def gap_ok(self, value: str, ex: dict) -> bool:
        kind = ex.get("type") or "fill"
        return _answer_matches(kind, value, self.lesson_answers(ex))

    def choice_index(self, ex: dict) -> int:
        options = list(ex.get("options") or [])
        answers = self.lesson_answers(ex)
        raw = ex.get("a")
        if isinstance(raw, int) and 0 <= raw < len(options):
            return raw
        for index, option in enumerate(options):
            if any(_canon_plain(option) == _canon_plain(item) for item in answers):
                return index
            if raw is not None and _canon_plain(option) == _canon_plain(str(raw)):
                return index
        return 0

    def hint_text(self, ex: dict) -> str:
        return _hint_text(ex.get("raw") or ex)

    def load_table(self, table_id: str) -> dict | None:
        table = self.engine.table(table_id)
        if not table:
            return None
        return {
            "id": table.get("id"),
            "title": table.get("title") or table_id,
            "head": table.get("columns") or table.get("head") or [],
            "columns": table.get("columns") or [],
            "rows": table.get("rows") or [],
            "note": table.get("note") or "",
        }

    def build_left_extra(self, host: tk.Frame, spread: GrammarSpread) -> None:
        if self._source != COURSE_SOURCE or not self.progress:
            return
        if not self._has_passed_lesson():
            return
        HudButton(host, _t("ПРОВЕРЬ СЕБЯ"), self.page._start_self_check,
                  height=28, font_size=8, color=GREEN).pack(fill=tk.X)

    def _has_passed_lesson(self) -> bool:
        if not self.progress:
            return False
        grammar = self.progress.data.get("grammar") or {}
        return any(isinstance(entry, dict) and entry.get("done") for entry in grammar.values())

    def _build_self_check(self, level: str | None) -> dict:
        level = level or "A1"
        pool = []
        for item in self.engine.lesson_summaries(level):
            if not self.progress or not self.progress.grammar_done(item["id"]):
                continue
            full = self.engine.lesson(item["id"]) or {}
            for drill in full.get("drills") or []:
                pool.append(drill)
        picked = _shuffled(pool, f"check:{level}")[:SELF_CHECK_SIZE]
        self.records_score = False
        self._self_check = {
            "n": SELF_CHECK_ID,
            "id": SELF_CHECK_ID,
            "title": _t("ПРОВЕРЬ СЕБЯ"),
            "en": "",
            "level": level,
            "summary": "",
            "can_do": [],
            "theory": [],
            "examples": [],
            "traps": [],
            "exercises": [_adapt_drill(drill, self.lang_code) for drill in picked],
            "raw": {"drills": picked, "level": level},
        }
        return self._self_check

    def render_exercise(self, spread: GrammarSpread, host, idx: int, ex: dict) -> bool:
        if ex.get("type") not in REORDER_TYPES:
            return False
        card = tk.Frame(host, bg=PANEL, highlightthickness=1, highlightbackground=theme.LINE)
        card.pack(fill=tk.X, padx=px(10), pady=(0, px(6)))
        top = tk.Frame(card, bg=PANEL)
        top.pack(fill=tk.X, padx=px(10), pady=(px(8), px(2)))
        L(top, f"{idx + 1}.", fg=theme.AMBER, size=10, bold=True, mono=True, bg=PANEL, width=3).pack(
            side=tk.LEFT, anchor="n")
        tk.Label(top, text=ex.get("q") or "", fg=TEXT, bg=PANEL, font=theme.font(11),
                 justify="left", anchor="w", wraplength=px(520)).pack(
            side=tk.LEFT, fill=tk.X, expand=True)
        if ex.get("instruction"):
            L(card, ex["instruction"], fg=MUTED, size=8, bg=PANEL, wraplength=px(540),
              justify="left", anchor="w").pack(fill=tk.X, padx=px(14), pady=(0, px(2)))
        raw = ex.get("raw") or ex
        bank = _shuffled(_word_bank(raw), f"bank:{raw.get('id') or idx}")
        state = {"picked": [], "bank": bank, "labels": []}
        sentence = L(card, "…", fg=MUTED, size=11, bg=PANEL, wraplength=px(540),
                     justify="left", anchor="w")
        sentence.pack(fill=tk.X, padx=px(14), pady=(px(2), px(2)))
        bank_row = tk.Frame(card, bg=PANEL)
        bank_row.pack(fill=tk.X, padx=px(14), pady=(0, px(4)))
        note = L(card, "", fg=MUTED, size=8, bg=PANEL, wraplength=px(540),
                 justify="left", anchor="w")

        def refresh() -> None:
            text = " ".join(state["bank"][i] for i in state["picked"]) or "…"
            sentence.configure(text=text, fg=TEXT if state["picked"] else MUTED)

        def pick(index: int) -> None:
            if idx in spread._answers or index in state["picked"]:
                return
            state["picked"].append(index)
            refresh()

        def unpick() -> None:
            if idx in spread._answers or not state["picked"]:
                return
            state["picked"].pop()
            refresh()

        def clear() -> None:
            if idx in spread._answers:
                return
            state["picked"] = []
            refresh()

        def check() -> None:
            if idx in spread._answers:
                return
            value = " ".join(state["bank"][i] for i in state["picked"])
            ok = _answer_matches("reorder", value, _expected_of(raw))
            spread._finish(idx, ok, ex, note)

        for index, word in enumerate(bank):
            btn = HudButton(bank_row, word, lambda i=index: pick(i), height=26, font_size=8)
            btn.pack(side=tk.LEFT, padx=(0, px(4)), pady=px(2))
        actions = tk.Frame(card, bg=PANEL)
        actions.pack(fill=tk.X, padx=px(14), pady=(0, px(4)))
        HudButton(actions, _t("← УБРАТЬ"), unpick, height=26, font_size=8).pack(side=tk.LEFT)
        HudButton(actions, _t("Очистить"), clear, height=26, font_size=8, color=MUTED).pack(
            side=tk.LEFT, padx=(px(4), 0))
        HudButton(actions, _t("ПРОВЕРИТЬ"), check, height=26, font_size=8).pack(
            side=tk.LEFT, padx=(px(6), 0))
        if ex.get("hint_enabled") or True:
            def show_hint() -> None:
                if idx in spread._answers:
                    return
                note.configure(text=_hint_text(raw), fg=MUTED)
            HudButton(actions, _t("ПОДСКАЗКА"), show_hint, height=26, font_size=8,
                      color=MUTED).pack(side=tk.LEFT, padx=(px(6), 0))
        note.pack(fill=tk.X, padx=px(14), pady=(0, px(6)))
        card._reorder_state = state
        spread._exercise_vars = getattr(spread, "_exercise_vars", {})
        spread._exercise_vars[idx] = {"reorder": state, "note": note, "ex": ex, "card": card, "check": check}
        return True


class GermanGrammarCatalog(BaseGrammarCatalog):
    """Каталог немецкой грамматики: курс + открытые источники по вкладкам."""

    lang_code = "de"
    translate_lang_name = "немецкий"

    def _ensure_open(self):
        if self._open is None:
            from stamina.languages.plugins.de.open_sources import OpenSourceBank
            self._open = OpenSourceBank()
        return self._open

    def sources(self) -> list[SourceTab]:
        tabs = [COURSE_TAB]
        try:
            from stamina.languages.plugins.de.open_sources import source_tabs
            tabs.extend(source_tabs())
        except Exception:
            pass
        return tabs

    def load_index(self) -> None:
        if self._source == COURSE_SOURCE:
            self.engine.levels()
            return
        bank = self._ensure_open()
        bank.meta(self._source)
        bank.index(self._source)

    def index_loaded(self) -> bool:
        if self._source == COURSE_SOURCE:
            return self.engine._courses is not None
        return self._source in getattr(self._open, "_index", {})

    def header_subtitle(self, level: str) -> str:
        if self._source == COURSE_SOURCE:
            info = next((item for item in self.engine.levels() if item["code"] == level), None)
            if info:
                return "{} · {}".format(info.get("title") or level, info.get("lessons") or "")
            return _t("Курс Star Typing")
        try:
            meta = self._ensure_open().meta(self._source)
            name = meta.get("name") or self._source
            license_name = meta.get("license") or ""
            return "{} · {}".format(name, license_name).strip(" ·")
        except Exception:
            return self._source

    def progress_text(self) -> str:
        if self._source != COURSE_SOURCE:
            topics = self._topic_summaries()
            done = sum(1 for item in topics if self.progress and self.progress.grammar_done(item["id"]))
            return "{}: {} / {}".format(_t("ПРОЙДЕНО"), done, len(topics))
        total = sum(int(item.get("lessons") or 0) for item in self.engine.levels())
        done = 0
        if self.progress:
            for entry in (self.progress.data.get("grammar") or {}).values():
                if isinstance(entry, dict) and entry.get("done"):
                    done += 1
        return "{}: {} / {}".format(_t("ПРОЙДЕНО"), done, total)

    def _topic_summaries(self) -> list[dict]:
        return self._ensure_open().topics(self._source)

    def list_plan(self, level: str) -> list[tuple[str, object]]:
        plan: list[tuple[str, object]] = []
        if self._source == COURSE_SOURCE:
            for unit in self.engine.lesson_summaries(level):
                plan.append(("unit", {
                    "id": unit["id"],
                    "number": f"{int(unit.get('order') or 0):02d}",
                    "title": unit.get("title") or unit["id"],
                    "level": unit.get("level") or level,
                }))
            return plan
        current = None
        for topic in self._topic_summaries():
            section = topic.get("section") or _t("Темы")
            if section != current:
                plan.append(("mod", {"id": section, "title": section, "en": ""}))
                current = section
            plan.append(("unit", {
                "id": topic["id"],
                "number": "",
                "title": topic.get("title") or topic["id"],
                "level": "all",
                "module_id": section,
            }))
        return plan

    def _load_open_topic(self, topic_id: str) -> dict:
        bank = self._ensure_open()
        topic = bank.load_topic(self._source, topic_id)
        theory = []
        for section in topic.get("sections") or []:
            theory.append({
                "h": section.get("heading") or "",
                "p": section.get("text") or "",
            })
        examples = []
        for ex in topic.get("examples") or []:
            examples.append({
                "de": ex.get("de") or "",
                "en": ex.get("de") or ex.get("en") or "",
                "ru": ex.get("en") or ex.get("ru") or "",
                "speak": ex.get("de") or "",
            })
        exercises = []
        last_set = None
        for drill in topic.get("exercises") or []:
            item = _adapt_drill(drill, self.lang_code)
            item["q"] = drill.get("q") or drill.get("prompt") or ""
            if drill.get("prompt"):
                item["instruction"] = drill["prompt"]
            if drill.get("set_title") and drill.get("set_id") != last_set:
                item["q"] = "{} — {}".format(drill.get("set_title") or "", item["q"]).strip(" —")
                last_set = drill.get("set_id")
            if not item.get("why"):
                item["why"] = ""
            item["hint_enabled"] = item["type"] in FILL_TYPES
            exercises.append(item)
        attr = bank.attribution_line(self._source, "ru")
        return {
            "n": topic_id,
            "id": topic_id,
            "title": topic.get("title") or topic_id,
            "en": topic.get("section") or "",
            "level": topic.get("cefr") or "",
            "summary": "",
            "can_do": [],
            "theory": theory,
            "examples": examples,
            "traps": [],
            "exercises": exercises,
            "attribution": attr,
            "original_url": topic.get("original_url") or "",
            "raw": topic,
        }


class FrenchGrammarCatalog(BaseGrammarCatalog):
    """Каталог французской грамматики."""

    lang_code = "fr"
    translate_lang_name = "французский"


class SpanishGrammarCatalog(BaseGrammarCatalog):
    """Каталог испанской грамматики."""

    lang_code = "es"
    translate_lang_name = "испанский"


class ItalianGrammarCatalog(BaseGrammarCatalog):
    """Каталог итальянской грамматики."""

    lang_code = "it"
    translate_lang_name = "итальянский"

    def paint_title_flag(self, slot) -> None:
        from stamina.grammar_ui.flags import paint_title_flag
        paint_title_flag(slot, "it")


def _catalog_for_plugin(plugin) -> type[BaseGrammarCatalog]:
    """Вернуть класс каталога для кода языка плагина."""
    code = getattr(plugin, "code", "de")
    if code == "fr":
        return FrenchGrammarCatalog
    if code == "es":
        return SpanishGrammarCatalog
    if code == "it":
        return ItalianGrammarCatalog
    return GermanGrammarCatalog


class GrammarPage:
    """Оболочка грамматики (de/fr/es/it): общий разворот + адаптер данных."""

    def __init__(self, parent, plugin, progress: LanguageProgress | None, app,
                 on_back=None) -> None:
        self.parent = parent
        self.plugin = plugin
        self.progress = progress
        self.app = app
        self.on_back = on_back
        self.engine = plugin.get_grammar_engine()
        catalog_cls = _catalog_for_plugin(plugin)
        self.catalog = catalog_cls(self.engine, progress, self)
        lang = getattr(plugin, "code", "de")
        asr = asr_for(lang)
        self.ctx = LangCtx(progress, asr, app, lang=lang)
        self.spread = GrammarSpread(parent, self.catalog, self.ctx)
        self.spread.pack(fill=tk.BOTH, expand=True)
        self.frame = self.spread
        self.content = self.spread
        self.tables_container = None
        self.mode = "lessons"
        self.stage = "list"
        self.current_level = self.spread._level
        self.lesson: dict | None = None
        self.drills: list[dict] = []
        self.all_drills: list[dict] = []
        self.answers: dict = {}
        self.checked = False
        self.rule_shown = False
        self.picked: list[int] = []
        self.bank: list[str] = []
        self.drill_answer_var = tk.StringVar()
        self._pending: list = []
        self.spread.refresh()

    # -- совместимость и тестовые точки ----------------------------------------
    @property
    def level_lessons(self) -> list[dict]:
        if self.catalog.current_source_id() != COURSE_SOURCE:
            return []
        return self.engine.lesson_summaries(self.spread._level)

    def destroy(self) -> None:
        try:
            self.spread.destroy()
        except tk.TclError:
            pass

    def _flush_pending(self) -> None:
        self.spread._flush_pending()
        try:
            self.spread.update_idletasks()
        except tk.TclError:
            pass
        self._sync()

    def _sync(self) -> None:
        self.current_level = self.spread._level
        self.lesson = (self.spread._data or {}).get("raw") if self.spread._data else None
        if self.spread._data and self.spread._unit == SELF_CHECK_ID:
            self.drills = [ex.get("raw") or ex for ex in self.spread._exercises]
            self.all_drills = list(self.drills)
            self.stage = "self_check"
        elif self.spread._table_id:
            self.stage = "table"
        elif self.spread._data:
            self.drills = [ex.get("raw") or ex for ex in self.spread._exercises]
            self.all_drills = list(self.drills)
            self.stage = "lesson"
        else:
            self.stage = "list"
        self.answers = {}
        self.last_ok = False
        for index, ok in self.spread._answers.items():
            raw = {}
            if index < len(self.spread._exercises):
                raw = self.spread._exercises[index].get("raw") or {}
            key = raw.get("id", index)
            self.answers[key] = ok
            self.last_ok = bool(ok)
        self.checked = bool(self.spread._answers)
        self.mode = "tables" if self.stage == "table" else "lessons"

    def _show_lessons(self, level: str) -> None:
        if self.catalog.current_source_id() != COURSE_SOURCE:
            self.catalog.select_source(COURSE_SOURCE)
            self.spread._rebuild_source_tabs()
            self.spread._rebuild_level_buttons()
        code = str(level).upper()
        if not self.spread._index_ready:
            self.catalog.load_index()
            self.spread._index_ready = True
        self.spread._select_level(code)
        self._sync()

    def _open_lesson(self, lesson) -> None:
        lesson_id = lesson["id"] if isinstance(lesson, dict) else lesson
        self._show_lessons(self.engine._cefr_of(str(lesson_id)) or self.spread._level)
        self.spread._unit = None
        self.spread._data = None
        self.spread._open_unit(lesson_id)
        self._sync()

    def _show_lesson(self, lesson) -> None:
        self._open_lesson(lesson)

    def _open_table(self, table_id: str) -> None:
        self.spread._open_table(table_id)
        self.tables_container = self.spread._lesson_sf.inner
        self._sync()

    def _set_mode(self, mode: str) -> None:
        # Отдельной вкладки «Таблицы» больше нет: справочник открывается из урока.
        # Для совместимости показываем первую таблицу в правой панели.
        self.mode = mode
        if mode == "tables":
            tables = self.engine.tables(None)
            if tables:
                self._open_table(tables[0]["id"])
                self.tables_container = self.spread._lesson_sf.inner
        else:
            if self.spread._unit is not None:
                self.spread._back_from_table() if self.spread._table_id else None
        self._sync()

    def _instruction(self, drill: dict) -> str:
        return _instruction(drill)

    def _hint_text(self, drill: dict) -> str:
        return _hint_text(drill)

    def _expected(self, drill: dict) -> list[str]:
        return _expected_of(drill)

    def _current_drill(self) -> dict | None:
        if not self.drills:
            return None
        # В развороте все упражнения видны; «текущее» — первое без ответа.
        for index, drill in enumerate(self.drills):
            if index not in self.spread._answers:
                return drill
        return self.drills[-1]

    def _drill_index(self, drill: dict | None = None) -> int | None:
        if drill is None:
            drill = self._current_drill()
        if not drill or not self.spread._exercises:
            return None
        for index, ex in enumerate(self.spread._exercises):
            raw = ex.get("raw") or ex
            if raw is drill or raw.get("id") == drill.get("id"):
                return index
        return 0

    def _choose(self, option: str, drill: dict | None = None) -> None:
        index = self._drill_index(drill)
        if index is None:
            return
        ex = self.spread._exercises[index]
        options = list(ex.get("options") or [])
        try:
            picked = next(i for i, opt in enumerate(options) if opt == option)
        except StopIteration:
            picked = 0
        right = self.catalog.choice_index(ex)
        self.spread._finish(index, picked == right, ex, self._ensure_note(index))
        self._sync()

    def _ensure_note(self, index: int):
        vars_map = getattr(self.spread, "_exercise_vars", {})
        if index in vars_map and vars_map[index].get("note"):
            return vars_map[index]["note"]
        note = L(self.spread._lesson_sf.inner, "", fg=MUTED, size=8, bg=PANEL)
        return note

    def _check_answer(self, value: str | None = None, drill: dict | None = None) -> None:
        index = self._drill_index(drill)
        if index is None:
            return
        ex = self.spread._exercises[index]
        kind = ex.get("type")
        if kind in REORDER_TYPES:
            vars_map = getattr(self.spread, "_exercise_vars", {})
            state = (vars_map.get(index) or {}).get("reorder")
            raw = ex.get("raw") or ex
            if self.bank:
                bank = list(self.bank)
                picked = list(self.picked)
            elif state is not None:
                bank = list(state.get("bank") or [])
                picked = list(state.get("picked") or [])
            else:
                bank, picked = [], []
            if state is not None:
                state["bank"] = bank
                state["picked"] = picked
            value = " ".join(bank[i] for i in picked if 0 <= i < len(bank))
            ok = _answer_matches("reorder", value, _expected_of(raw))
            self.spread._finish(index, ok, ex, self._ensure_note(index))
            self._sync()
            return
        if value is None:
            value = self.drill_answer_var.get()
        ok = self.catalog.gap_ok(value, ex)
        self.spread._finish(index, ok, ex, self._ensure_note(index))
        self._sync()

    def _check_drill(self, drill: dict | None = None) -> None:
        if drill is not None:
            # Сместить «текущее», если передали конкретное упражнение.
            for index, ex in enumerate(self.spread._exercises):
                raw = ex.get("raw") or ex
                if raw is drill or raw.get("id") == drill.get("id"):
                    if index not in self.spread._answers:
                        # temporarily prefer this one
                        break
        self._check_answer(drill=drill)

    def _start_self_check(self, level: str | None = None) -> None:
        level = (level or self.spread._level or "A1")
        self.catalog.select_source(COURSE_SOURCE)
        self.catalog.records_score = False
        data = self.catalog._build_self_check(level)
        self.spread._unit = None
        self.spread._data = None
        # не ходить на диск: сразу показать собранный набор
        self.spread._token += 1
        token = self.spread._token
        self.spread._cancel("lesson")
        self.spread._clear_lesson()
        self.spread._unit = SELF_CHECK_ID
        self.spread._on_lesson(token, SELF_CHECK_ID, data, None)
        self._sync()

    def _start_theory(self) -> None:
        # Теория уже на развороте; метод оставлен для совместимости.
        self._sync()

    def _start_practice(self) -> None:
        self._sync()



    def in_focus(self) -> bool:
        return self.spread.in_focus()

    def toggle_focus(self, on: bool | None = None, *, remember: bool = True) -> None:
        self.spread.toggle_focus(on, remember=remember)

    def apply_session_focus(self) -> None:
        self.spread.apply_session_focus()

    def handle_focus_escape(self) -> bool:
        return self.spread.handle_focus_escape()

    def on_key(self, e) -> str | None:
        return self.spread.on_key(e)

    @property
    def _focus(self):
        return self.spread._focus

    @_focus.setter
    def _focus(self, value) -> None:
        self.spread._focus = value


class _NoGrammarProgress:
    """Заглушка прогресса, когда пилот ещё не выбран (в тестах и на первом экране)."""

    def grammar_done(self, _unit_id) -> bool:
        return False

    def grammar_mark(self, _unit_id, _ok: int, _total: int) -> bool:
        return False


def build_grammar_page(parent, plugin, progress, app, vocab=None) -> GrammarPage:
    """Собрать страницу грамматики для языка плагина.

    Английский приходит сюда через общую сетку языков, но у него уже есть
    полноценный каталог уроков Murphy на том же GrammarSpread. Используем его,
    а не заглушку EnglishGrammarEngine, чтобы вкладка не падала.
    """
    if getattr(plugin, "code", "") == "en":
        from stamina.english.pages_grammar import GrammarPage as EnglishGrammarPage
        from stamina.languages.ctx import LangCtx

        ctx = LangCtx(progress if progress is not None else _NoGrammarProgress(),
                      None, app, lang="en")
        ctx.vocab = vocab
        return EnglishGrammarPage(parent, ctx)
    return GrammarPage(parent, plugin, progress, app)
