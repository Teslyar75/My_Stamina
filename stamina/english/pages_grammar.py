"""Вкладка «Грамматика»: уроки Essential Grammar in Use (красный и синий Murphy).

Слева — список уроков текущего уровня, справа — сам урок: цель, правило, примеры,
частые ошибки и упражнения с проверкой. Каркас — общий GrammarSpread; эта страница
только подключает английский каталог, поэтому внешний вид совпадает с эталоном.
"""
from __future__ import annotations

import re

from stamina.english.grammar import lessons as gl
from stamina.grammar_ui.spread import GrammarSpread
from stamina.i18n import t as _t


class EnglishGrammarCatalog:
    """Каталог синей/красной Murphy: индекс целиком, уроки по одному, LRU в gl."""

    show_source_tabs = False
    levels = list(gl.LEVELS)

    def __init__(self, ctx) -> None:
        self.ctx = ctx

    def paint_title_flag(self, slot) -> None:
        from stamina.grammar_ui.flags import paint_title_flag
        paint_title_flag(slot, "gb")

    def sources(self):
        return []

    def select_source(self, source_id: str) -> None:
        return None

    def current_source_id(self) -> str:
        return "murphy"

    def load_index(self) -> None:
        gl.load_index()

    def index_loaded(self) -> bool:
        return gl.index_loaded()

    def header_subtitle(self, level: str) -> str:
        units = gl.by_level(level)
        book = gl.book_of(int(units[0]["n"])) if units else {}
        title = book.get("title") or "Essential Grammar in Use"
        count = int(book.get("units") or 0)
        return "{} · {}".format(title, count) if count else title

    def progress_text(self) -> str:
        done = len([u for u in gl.units() if self.ctx.progress.grammar_done(int(u["n"]))])
        return "{}: {} / {}".format(_t("ПРОЙДЕНО"), done, gl.total())

    def list_plan(self, level: str) -> list[tuple[str, object]]:
        plan: list[tuple[str, object]] = []
        for module in gl.modules():
            units = [
                u for u in gl.units_of_module(module["id"])
                if str(u.get("level", "")).lower() == level
            ]
            if not units:
                continue
            plan.append(("mod", module))
            for unit in units:
                n = int(unit["n"])
                plan.append(("unit", {
                    "id": n,
                    "number": f"{int(unit.get('unit') or n):02d}",
                    "title": unit.get("title", ""),
                    "level": level,
                    "module_id": module["id"],
                }))
        return plan

    def first_unit(self, level: str):
        first = gl.by_level(level)
        return int(first[0]["n"]) if first else None

    def level_of(self, unit_id) -> str:
        info = gl.unit_info(int(unit_id)) or {}
        return str(info.get("level") or "").lower()

    def load_lesson(self, unit_id) -> dict:
        lesson = gl.load_lesson(int(unit_id))
        vocabulary = self._extract_vocabulary(lesson)
        lesson["vocabulary"] = vocabulary
        return lesson

    def _extract_vocabulary(self, lesson: dict) -> list[dict]:
        """Extract vocabulary from lesson: words from examples and exercises that exist in vocab."""
        vocab = getattr(self.ctx, "vocab", None)
        if not vocab or not getattr(vocab, "ready", False):
            return []

        seen = set()
        vocab_items = []

        def add_word(form: str):
            form = (form or "").strip().lower()
            if not form or form in seen:
                return
            seen.add(form)
            word = vocab.get(form)
            if word:
                translation = word.get("ru", "")
                ipa = word.get("ipa", "")
                respelling = word.get("respelling", "")
                if translation:
                    pronunciation = ipa if ipa else (respelling if respelling else "—")
                    vocab_items.append({
                        "lemma": word.get("word", form),
                        "translation": translation,
                        "pronunciation": pronunciation,
                    })

        for ex in lesson.get("examples") or []:
            en_text = ex.get("en", "")
            for token in re.findall(r"[a-zA-Z']+", en_text):
                add_word(token)

        for ex in lesson.get("exercises") or []:
            q = ex.get("q", "")
            for token in re.findall(r"[a-zA-Z']+", q):
                add_word(token)
            for opt in ex.get("options") or []:
                for token in re.findall(r"[a-zA-Z']+", opt):
                    add_word(token)
            a = ex.get("a", [])
            if isinstance(a, list):
                for ans in a:
                    for token in re.findall(r"[a-zA-Z']+", str(ans)):
                        add_word(token)
            elif a:
                for token in re.findall(r"[a-zA-Z']+", str(a)):
                    add_word(token)

        for trap in lesson.get("traps") or []:
            good = trap.get("good", "")
            for token in re.findall(r"[a-zA-Z']+", good):
                add_word(token)

        return vocab_items

    def neighbours(self, unit_id):
        return gl.neighbours(int(unit_id))

    def hint_for_unit(self, unit_id) -> str:
        n = int(unit_id)
        return _t("Урок {0} из {1}").format(
            gl.unit_number(n), int(gl.book_of(n).get("units") or gl.total()))

    def unit_number(self, unit_id) -> int:
        try:
            return int(gl.unit_number(int(unit_id)))
        except Exception:  # noqa: BLE001
            return int(unit_id)

    def is_done(self, unit_id) -> bool:
        return bool(self.ctx.progress.grammar_done(int(unit_id)))

    def mark_complete(self, unit_id, ok: int, total: int) -> bool:
        return bool(self.ctx.progress.grammar_mark(int(unit_id), ok, total))

    def lesson_answers(self, ex: dict) -> list[str]:
        return list(gl.lesson_answers(ex))

    def gap_ok(self, value: str, ex: dict) -> bool:
        return any(gl.normalize(value) == gl.normalize(v) for v in gl.lesson_answers(ex))

    def choice_index(self, ex: dict) -> int:
        return int(ex.get("a", 0) or 0)


class GrammarPage(GrammarSpread):
    """Страница грамматики английского: оболочка сразу, данные и виджеты — порциями."""

    def __init__(self, master, ctx) -> None:
        super().__init__(master, EnglishGrammarCatalog(ctx), ctx)


def init_grammar_tab(english_screen) -> None:
    """Устарело: грамматика собирается в EnglishScreen._build как GrammarPage."""
