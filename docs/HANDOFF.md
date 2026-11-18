# Handoff

Goal: контент EGIU по уровням — уроки грамматики в «Английском» (ветка `agent/orion/english-grammar`).

Done:
- PR **#48** смержен в `master` (навигация EN, GrammarPage, i18n, hotkeys/тесты).
  Цепочка: `a15c275` (тесты), `b868af9` (Ctrl+9), `ce85f51` (i18n alt), …
- «Грамматика» переделана из списка тем в уроки по Essential Grammar in Use (115 юнитов, A1 — 1–30, A2 — 31–90, B1 — 91–115).
  - `stamina/english/grammar/lessons/index.json` — 19 модулей, 115 юнитов (~22 КБ).
  - `lessons/u001.json` … `u115.json` — **все 115 уроков написаны**: цель, 3–7 блоков теории с формулами/таблицами,
    3–8 примеров с переводом, 2–4 ловушки, 6–12 упражнений (`choice` / `gap` / `translate`) с объяснением.
  - `lessons.py` — загрузчик: индекс один раз, урок по клику (`lru_cache(32)`), `normalize` / `answer_ok` / `lesson_answers`.
  - `pages_grammar.py` — панель уроков по уровням и сам урок; всё рисуется порциями (`LIST_CHUNK=8`, `LESSON_CHUNK=2`).
  - Доставка из фоновых потоков — через `queue.Queue` + опрос в главном потоке (`_ensure_pump` / `_pump`):
    `self.after(0, …)` из воркера падал с «main thread is not in main loop».
  - Переход по ← → через границу уровня теперь переключает и список (`_follow_level`).
  - Прогресс уроков — ключ `grammar.units` в `%APPDATA%\Stamina\english.json`; пройден при ≥ половины верных, +25 XP за первый проход.
  - `tools/grammar_lessons_check.py` — валидатор схемы и упражнений: `python tools/grammar_lessons_check.py` → 115 готово, 0 ошибок.
  - `tests/test_english_grammar_lessons.py` — индекс, загрузка, проверка ответов, прогресс (15 тестов).
  - i18n: 11 ключей во всех 7 словарях; `python tools/ci_gate.py --only i18n --only dep` → «ГАТ: зелёный».

Next:
- Коммит ветки и слияние в `master` (после зелёного гейта).
- По желанию: озвучка теории целиком (сейчас 🔊 только у примеров), фильтр «показать непройденные».

Problems:
- Полный `python -m pytest tests/ -q` на этой машине не укладывается в 15 минут (GUI-части);
  точечно зелено: `tests/test_english_grammar*.py`, `test_english_hub_ui.py`, `test_json_bom.py`, `test_i18n.py`.
- `python tools/i18n_check.py` по-прежнему сообщает о «лишних» ключах в каждом словаре — это было и до правок, на код возврата не влияет.
