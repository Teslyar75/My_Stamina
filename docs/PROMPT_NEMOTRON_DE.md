# Задание для Nemotron: немецкая грамматика в отсеке «Иностранные языки»

> Это готовый промпт. Скопируй его целиком в Nemotron одним сообщением.
> Всё, что ниже, — не пожелания, а требования приёмки: результат проверяется
> другим агентом по чек-листу в конце.

---

## 0. Роль и цель

Ты — инженер проекта **«Новая Стамина»** (Python 3.14 + Tkinter, папка
`D:\My_New_Stamina`). Твоя задача — довести отсек «Иностранные языки» до
состояния, в котором **немецкий язык можно учить системно**: справочник
грамматических таблиц + уроки, идущие по возрастанию сложности от A1 до C2,
с настоящими упражнениями и проверкой ответов.

Не «каркас на будущее», а рабочий контент. Заглушек быть не должно: ни
`"answer"`, ни `"opt1"`, ни `TODO`.

Работай до конца, не задавая уточняющих вопросов. Если чего-то нельзя —
запиши это в `docs/HANDOFF.md` и продолжай с остальным.

---

## 1. Жёсткие правила репозитория

Читай `AGENTS.md` в корне. Коротко, что тебе нельзя нарушать:

- Работай в **своей ветке** и **своём worktree**:
  ```powershell
  cd D:\My_New_Stamina
  git worktree add C:\Users\mi\grok_x\wt_nemotron -b agent/nemotron/de-grammar master
  cd C:\Users\mi\grok_x\wt_nemotron
  ```
  Дальше все команды — в этом каталоге.
- Запрещено: `git reset --hard`, `git push --force`, `git checkout -- .`,
  `git clean -fd`, `git stash drop`. Это стирает чужую работу.
- Не трогай данные пилота в `%APPDATA%\Stamina` и папку `_orion/`.
- Не коммить чужие неотслеживаемые файлы (`pr_body.md`, `graphify-out/`,
  `.claude/`, `docs/MULTILANG_PLAN.md`, `*.bak` и подобное).
- Перед первой правкой:
  ```powershell
  powershell -ExecutionPolicy Bypass -File tools\snapshot.ps1
  ```
  Скрипт напечатает тег и строку откатa. Сохрани её в отчёт.
- Коммиты по-русски, в стиле репозитория: `feat: …`, `fix: …`, `docs: …`.
  Один коммит — одна мысль (данные, движок, интерфейс, тесты, докуменация
  отдельными коммитами — нормально).
- Консоль Windows в cp1251: для любого скрипта с русским текстом запускай
  `python -X utf8 …`, иначе получишь `UnicodeEncodeError` на выводе.
- В самом конце обнови `docs/HANDOFF.md` (Goal / Done / Next / Decisions /
  Problems) и убери свою строку из `.opencode/agents/ACTIVE.md`, если добавлял.

---

## 2. Что прочитать до первой строки кода

Не изобретай архитектуру — она уже есть. Прочитай **в таком порядке**:

1. `AGENTS.md` — правила корабля.
2. `docs/HANDOFF.md` — где остановились. Учти: файл может отставать от кода,
   правда в коде. В master уже есть отсек «Иностранные языки» (плагины
   de/es/fr/it, словари A1–C2, экран, практика, чтение, сканер), но **нет**
   `stamina/languages/ui.py` и `gloss_lang` — это незалитая работа других
   агентов, тебе она не нужна и создавать её не надо.
3. `stamina/languages/core/base.py` — контракты `GrammarEngine`,
   `GrammarTopic`, `Exercise`, `ValidationResult`, `WordEntry`,
   `GermanMorphology`.
4. `stamina/languages/plugins/de/__init__.py` — текущий `GermanGrammarEngine`
   (там **заглушки**: `generate_exercise` возвращает `"answer"`,
   `get_explanation` — склейку строк). Это и есть главная цель работы.
5. `stamina/languages/screen.py` — экран отсека: `SUBPAGES`, `_show_page`,
   `_build_practice`, `_build_settings`, `_scroller`, клавиатура `on_key`.
6. `stamina/languages/words_page.py` — страница уровня CEFR и сетка слов:
   тот же стиль нужен урокам (плитка рисуется прямо здесь, отдельного
   модуля плитки нет).
7. `stamina/english/pages_reference.py` — `ReferencePanel`: как в английском
   отсеке уже показывают формы глагола по лицам. Это ближайший образец.
8. `stamina/i18n/__init__.py` — `t()` и `LANGS` (в master четыре языка:
   ru, uk, en, de).
9. `tests/test_comm.py` — стиль GUI-тестов (реальный Tk, `pytest.skip` без
   дисплея, проверка раскладки в `test_input_row_is_visible`).
10. `stamina/theme.py`, `stamina/hud.py` — цвета, `px()`, `HudButton`,
    `HudPanel`. Своих hex-цветов и своих шрифтов не вводить.

Ориентиры по объёму: `screen.py` ≈ 980 строк, стиль — русские докстринги,
`from stamina.i18n import t as _t`, отступ 4, длина строки ~100.

---

## 3. Что должно получиться

Три слоя, каждый — отдельный файл. Данные отдельно от логики, логика отдельно
от интерфейса. Контент — только в JSON, чтобы его можно было править без
программиста.

```
stamina/languages/plugins/de/grammar/
    courses.json            # манифест: уровни, порядок уроков, счётчики
    tables.json             # все справочные таблицы (склонения, спряжения, предлоги)
    a1.json                 # уроки уровня A1
    a2.json                 # уроки уровня A2
    b1.json                 # уроки уровня B1
    b2.json                 # уроки уровня B2
    c1.json                 # уроки уровня C1
    c2.json                 # уроки уровня C2
stamina/languages/plugins/de/grammar_engine.py   # загрузка + упражнения + проверка
stamina/languages/grammar_page.py                # страница «ГРАММАТИКА»
tests/test_languages_grammar_de.py               # тесты
```

`stamina/languages/plugins/de/__init__.py` меняется только в одном месте:
`get_grammar_engine()` возвращает `GermanGrammarEngine` из нового модуля.
Старый класс-заглушку удали, `TOPICS`/`PFLEGE_TOPICS` перенеси в данные,
не потеряв ни одного `topic_id` (на них могут опираться другие места —
проверь `grep -rn "partizipialattribute_pflege\|PFLEGE_TOPICS" .`).

### 3.1. Схема `tables.json`

```json
{
  "version": 1,
  "tables": [
    {
      "id": "articles_definite",
      "level": "A1",
      "title": "Определённый артикль",
      "columns": ["", "Maskulin", "Feminin", "Neutrum", "Plural"],
      "rows": [
        ["Nominativ", "der", "die", "das", "die"],
        ["Akkusativ", "den", "die", "das", "die"],
        ["Dativ", "dem", "der", "dem", "den + n"],
        ["Genitiv", "des + s", "der", "des + s", "der"]
      ],
      "note": "Dativ Plural: к существительному добавляется -n, если его ещё нет."
    }
  ]
}
```

Правила:

- `rows[*]` — ровно `len(columns)` ячеек, ни одной пустой строки;
- `title` и `note` — по-русски, немецкие термины в немецком написании;
- никаких `|`, html и markdown внутри ячеек — это данные для сетки Tk;
- все `id` уникальны, `snake_case`, только латиница.

### 3.2. Схема урока (`a1.json` … `c2.json`)

```json
{
  "version": 1,
  "level": "A1",
  "lessons": [
    {
      "id": "a1-06-genus",
      "order": 6,
      "title": "Род существительного",
      "subtitle": "der / die / das и подсказки по окончаниям",
      "topics": ["gender_patterns"],
      "prereq": ["a1-03-praesens-regelmaessig"],
      "minutes": 12,
      "theory": [
        {"kind": "text", "text": "В немецком у каждого существительного свой род…"},
        {"kind": "rule", "title": "Правило", "text": "Все слова на -ung, -heit, -keit, -schaft, -tion — женского рода."},
        {"kind": "table", "ref": "noun_gender_endings"},
        {"kind": "example", "de": "Die Zeitung liegt auf dem Tisch.", "ru": "Газета лежит на столе.", "note": "-ung → die"}
      ],
      "drills": [
        {"id": "a1-06-d01", "type": "choice", "prompt": "___ Zeitung", "options": ["der", "die", "das"], "answer": "die", "why": "-ung всегда женского рода."},
        {"id": "a1-06-d02", "type": "fill", "prompt": "___ Wohnung ist neu. (Nominativ)", "answer": ["die"], "why": "Wohnung → die."},
        {"id": "a1-06-d03", "type": "declension", "prompt": "das Kind · Genitiv Singular", "answer": ["des Kindes"], "why": "Мужской и средний род в Genitiv получают -s/-es."}
      ]
    }
  ]
}
```

Обязательные поля урока: `id`, `order`, `title`, `subtitle`, `topics`,
`prereq`, `minutes`, `theory`, `drills`.

Обязательные поля упражнения: `id`, `type`, `prompt`, `answer`, `why`.

Разрешённые `type`: `choice`, `fill`, `declension`, `conjugation`, `reorder`,
`transform`, `match`, `identify`. Для `choice` обязательны `options`
(3–4 штуки, без повторов, правильный ответ среди них).

`answer` — **всегда список допустимых строк**, даже если ответ один
(`"answer": ["die"]`). Учитывай, что пилот может набрать `ae` вместо `ä`.

### 3.3. Схема `courses.json`

```json
{
  "version": 1,
  "language": "de",
  "levels": [
    {"code": "A1", "file": "a1.json", "lessons": 18, "title": "A1 · Выживание"},
    {"code": "A2", "file": "a2.json", "lessons": 18, "title": "A2 · Быт и поездки"}
  ],
  "tables_file": "tables.json"
}
```

`lessons` в манифесте должно совпадать с фактическим числом уроков в файле —
это проверяется тестом, расхождение = красный тест.

---

## 4. Лестница уроков: обязательный состав

Ниже — минимальный набор. Можно добавить, нельзя выбросить. Порядок `order`
строго от 1 и без пропусков внутри уровня. `prereq` ссылается на реальные
`id` (обычно 1–2 предыдущих урока).

### A1 — 18 уроков

1. `a1-01-alphabet-laute` — алфавит и звуки: `ch`, `r`, долгота гласных, `ß`
2. `a1-02-personalpronomen-sein` — личные местоимения и `sein`
3. `a1-03-praesens-regelmaessig` — Präsens: правильные глаголы
4. `a1-04-praesens-starke` — Präsens: сильные глаголы с чередованием
5. `a1-05-haben-modalverben` — `haben` и модальные глаголы
6. `a1-06-genus` — род существительного и подсказки по окончаниям
7. `a1-07-plural` — множественное число
8. `a1-08-artikel` — определённый и неопределённый артикль
9. `a1-09-nominativ-akkusativ` — Nominativ и Akkusativ
10. `a1-10-negation` — `nicht` и `kein`
11. `a1-11-possessiv` — притяжательные артикли
12. `a1-12-satzstellung-v2` — глагол на втором месте
13. `a1-13-fragen` — вопросы: Ja/Nein и W-вопросы
14. `a1-14-trennbare-verben` — отделяемые приставки
15. `a1-15-praepositionen` — предлоги с Akkusativ и Dativ
16. `a1-16-wechselpraepositionen` — девять «двойных» предлогов
17. `a1-17-perfekt` — Perfekt с `haben` и `sein`
18. `a1-18-zeitangaben` — время: `am`, `um`, `im`, `seit`, `vor`

### A2 — 18 уроков

1. `a2-01-dativ` — Dativ: формы и глаголы с Dativ
2. `a2-02-genitiv` — Genitiv
3. `a2-03-praeteritum` — Präteritum: слабые и сильные
4. `a2-04-perfekt-vs-praeteritum` — что когда говорят
5. `a2-05-reflexive` — возвратные глаголы
6. `a2-06-adjektiv-bestimmt` — окончания после определённого артикля
7. `a2-07-adjektiv-unbestimmt` — после неопределённого и без артикля
8. `a2-08-komparativ` — степени сравнения
9. `a2-09-nebensaetze` — придаточные: `dass`, `weil`, `wenn`, `als`
10. `a2-10-tekamolo` — порядок TeKaMoLo
11. `a2-11-praepositionen-genitiv` — предлоги с Genitiv
12. `a2-12-relativsaetze` — относительные придаточные
13. `a2-13-infinitiv-zu` — `um … zu`, `ohne … zu`, `statt … zu`
14. `a2-14-passiv-praesens` — пассив в Präsens
15. `a2-15-n-deklination` — N-Deklination
16. `a2-16-verben-praepositionen` — глаголы с фиксированными предлогами
17. `a2-17-partizip-ii-adjektiv` — Partizip II как прилагательное
18. `a2-18-konjunktionen` — `und/aber/oder/denn/sondern`, `deshalb/trotzdem`

### B1 — 12 уроков

1. `b1-01-konjunktiv-ii` — Konjunktiv II: вежливость и желания
2. `b1-02-konjunktiv-ii-vergangenheit` — Konjunktiv II прошедшего
3. `b1-03-passiv-zeiten` — пассив во всех временах
4. `b1-04-passiv-ersatz` — замена пассива: `man`, `sich lassen`, `-bar`
5. `b1-05-partizip-adjektiv` — Partizip I и II в роли прилагательного
6. `b1-06-partizipialattribute` — распространённые определения
7. `b1-07-da-wo` — `da-` и `wo-` композиты
8. `b1-08-konditional` — условные предложения
9. `b1-09-indirekte-fragen` — косвенные вопросы
10. `b1-10-modalpartikeln` — `ja, doch, mal, schon, eben, halt`
11. `b1-11-verben-praepositionen-2` — продолжение: `sich interessieren für` и др.
12. `b1-12-konnektoren` — `obwohl`, `trotzdem`, `dennoch`, `während`

### B2 — 10 уроков

1. `b2-01-konjunktiv-i` — Konjunktiv I и косвенная речь
2. `b2-02-passiv-vergangenheit` — пассив в Präteritum и Perfekt
3. `b2-03-partizipialsaetze` — свёрнутые придаточные
4. `b2-04-nominalisierung` — существительное вместо глагола и обратно
5. `b2-05-praepositionaladverbien` — `darauf`, `woran`, `hierbei`
6. `b2-06-konzessiv` — уступка: `obwohl`, `selbst wenn`, `wenngleich`
7. `b2-07-final` — цель: `damit`, `um … zu`, `zwecks`
8. `b2-08-funktionsverbgefuege` — `in Frage kommen`, `zur Verfügung stellen`
9. `b2-09-passiv-modal` — пассив с модальными
10. `b2-10-relativ-erweitert` — сложные относительные, `wo`, `was`

### C1 — 6 уроков

1. `c1-01-nominalstil` — Nominalstil против Verbalstil
2. `c1-02-komplexe-syntax` — многоуровневые Satzgefüge
3. `c1-03-akademisch` — научный стиль, осторожные формулировки
4. `c1-04-konnektoren-c1` — связки аргументации
5. `c1-05-modalitaet` — `dürfte`, `müsste`, `sollte`, `mag`
6. `c1-06-wortbildung` — приставки, суффиксы, композиты

### C2 — 4 урока

1. `c2-01-nuancen` — тонкие различия близких слов
2. `c2-02-idiomatik` — идиомы и коллокации
3. `c2-03-stilregister` — высокий, разговорный, профессиональный регистр
4. `c2-04-fehleranalyse` — типичные ошибки и как их ловить

Итого **68 уроков**. В каждом — 3–6 блоков теории, 1–3 таблицы (ссылки на
`tables.json`) и **10–16 упражнений** разных типов, с настоящими ответами.

---

## 5. Обязательные таблицы

Все `id` из списка должны быть в `tables.json` (можно добавить свои):

**Артикли и местоимения:** `articles_definite`, `articles_indefinite`,
`articles_kein`, `possessivartikel`, `personalpronomen`, `reflexivpronomen`,
`relativpronomen`, `frageworter`.

**Существительное:** `noun_gender_endings`, `plural_patterns`,
`n_deklination`, `kasus_uebersicht`.

**Прилагательное:** `adj_decl_definite`, `adj_decl_indefinite`,
`adj_decl_none`, `adj_komparation`.

**Глагол:** `praesens_weak`, `praesens_strong`, `sein_haben_werden`,
`modalverben`, `trennbare_verben`, `praeteritum_weak`,
`praeteritum_strong`, `perfekt_haben_sein`, `partizip_ii`,
`konjunktiv_ii`, `konjunktiv_i`, `passiv_zeiten`, `imperativ`.

**Предлоги:** `praep_akkusativ`, `praep_dativ`, `praep_genitiv`,
`wechselpraepositionen`.

**Синтаксис:** `satzstellung_v2`, `satzklammer`, `tekomolo`,
`nebensatz_wortstellung`, `fragesatz`, `negation`,
`konnektoren_uebersicht`, `da_wo_komposita`, `partizipialattribute`,
`nominalisierung`, `funktionsverbgefuege`.

Это **44 таблицы**. Сетка должна быть полной: если таблица про склонение —
все падежи, все три рода и множественное число; если про спряжение — все
шесть лиц; если про прилагательное — три парадигмы (сильная, слабая,
смешанная).

---

## 6. Точность содержания: что нельзя переврать

Это не «пожелание про качество», а список фактов, которые проверяющий
посмотрит первыми. Ошибка здесь = работа не принята.

- **Определённый артикль:** Nom `der/die/das/die`, Akk `den/die/das/die`,
  Dat `dem/der/dem/den+n`, Gen `des+s/der/des+s/der`.
- **Неопределённый:** Nom `ein/eine/ein/—`, Akk `einen/eine/ein/—`,
  Dat `einem/einer/einem/—`, Gen `eines/einer/eines/—`.
- **Окончания прилагательного после определённого артикля:** `-e` только в
  Nominativ всех родов и в Akkusativ женского и среднего; во всех остальных
  12 клетках — `-en`.
- **После неопределённого артикля (смешанное склонение):** Nominativ
  `-er/-e/-es`, Akkusativ `-en/-e/-es`, Dativ всегда `-en`, Genitiv всегда
  `-en` (мужской, женский, средний).
- **Без артикля (сильное склонение):** Nominativ `-er/-e/-es/-e`, Akkusativ
  `-en/-e/-es/-e`, Dativ `-em/-er/-em/-en`, Genitiv `-en/-er/-en/-er`.
- **Wechselpräpositionen:** девять — `an, auf, hinter, in, neben, über,
  unter, vor, zwischen`; Akkusativ при направлении (`Wohin?`), Dativ при
  месте (`Wo?`). Ни одного лишнего, ни одного пропущенного.
- **Предлоги Akkusativ:** `durch, für, gegen, ohne, um, bis, entlang`.
  **Dativ:** `aus, bei, mit, nach, seit, von, zu, gegenüber`.
  **Genitiv:** `wegen, trotz, während, statt/anstatt, innerhalb, außerhalb,
  aufgrund`.
- **Perfekt с `sein`:** движение и смена состояния (`gehen, kommen, fahren,
  fliegen, aufstehen, einschlafen, aufwachen, sterben`) плюс `sein`,
  `bleiben`, `werden`, `passieren`. Всё остальное — `haben`.
- **Порядок слов:** в главном предложении спрягаемый глагол строго на втором
  месте; в придаточном (`dass, weil, wenn, als, obwohl, ob, damit`) — в
  конце; модальный и Perfekt образуют рамку (спрягаемое — на втором месте,
  инфинитив/Partizip II — в конце); отделяемая приставка уходит в конец.
- **TeKaMoLo:** Temporal → Kausal → Modal → Lokal.
- **Konjunktiv II:** `hätte`, `wäre`, `würde + Infinitiv`; прошедшее —
  `hätte gemacht`, `wäre gegangen`.
- **Passiv:** `werden + Partizip II`; Präteritum — `wurde`; Perfekt —
  `ist … geworden`; с модальным — `muss gemacht werden`.
- **N-Deklination:** `der Herr — des/dem/den Herrn`; также `der Junge`,
  `der Mensch`, `der Student`, `der Polizist`, `der Nachbar`.
- **Спряжение `sein`:** `bin, bist, ist, sind, seid, sind`.
  **`haben`:** `habe, hast, hat, haben, habt, haben`.
  **`werden`:** `werde, wirst, wird, werden, werdet, werden`.
- **Сильные глаголы с чередованием в Präsens:** только 2-е и 3-е лицо
  единственного числа (`fahren → du fährst, er fährt`; `nehmen → du nimmst,
  er nimmt`; `laufen → du läufst, er läuft`).
- **Смешанные глаголы в Präteritum:** `bringen → brachte`, `denken → dachte`,
  `kennen → kannte`, `wissen → wusste`, `rennen → rannte`, `nennen → nannte`.

Если сомневаешься в форме — не пиши её. Лучше меньше упражнений на тему, чем
одно неверное. Источники, на которые можно ссылаться в поле `source`:
Duden («Die Grammatik»), Goethe-Institut (Wortlisten A1–C2), DTZ. Никогда не
выдумывай номера страниц и ссылки.

---

## 7. `grammar_engine.py`: что должен уметь

```python
class GermanGrammarEngine(GrammarEngine):
    def __init__(self, folder: Path | None = None) -> None: ...
    # контракт из base.py
    def get_topics(self, cefr: str) -> list[GrammarTopic]
    def generate_exercise(self, topic_id: str, difficulty: str, seed: int) -> Exercise
    def validate_answer(self, exercise: Exercise, answer: str) -> ValidationResult
    def get_explanation(self, topic_id: str, learner_lang: str) -> str
    # новое — для страницы
    def levels(self) -> list[dict]                    # из courses.json
    def lessons(self, cefr: str | None = None) -> list[dict]
    def lesson(self, lesson_id: str) -> dict | None
    def table(self, table_id: str) -> dict | None
    def tables(self, level: str | None = None) -> list[dict]
```

Требования к поведению:

- **Ленивая загрузка.** Уровень читается с диска при первом обращении и
  кэшируется в памяти. Построение страницы не должно читать все восемь файлов.
- **Детерминизм.** `generate_exercise(topic, difficulty, seed)` при одном и
  том же `seed` возвращает один и тот же результат и **не** трогает глобальный
  `random`. Никакой сети, никакого времени.
- **Валидация терпима к форме, но не к смыслу.** Принимается: лишние пробелы,
  регистр (кроме случаев, где регистр важен — существительные с большой
  буквы; сравнивай без регистра, но в подсказке показывай правильное
  написание), `ae/oe/ue` вместо `ä/ö/ü`, `ss` вместо `ß`, точка в конце.
  Не принимается другой падеж, другое лицо, другое время.
- **Обратная связь.** `ValidationResult.feedback` содержит `why` из
  упражнения, `correct_answer` — первый допустимый ответ.
- **`get_explanation`** возвращает текст теории урока по `topic_id`
  (склеенные `text`/`rule`), по-русски. Если `learner_lang == "en"` — можно
  вернуть английский вариант, если он есть; иначе русский. Пустой строки быть
  не должно ни для одного `topic_id`.
- **Никаких исключений на битых данных.** Отсутствующий файл, битый JSON,
  неизвестный `topic_id` → пустой результат и запись в `stamina/logs` любым
  существующим в проекте способом либо просто `None`. Интерфейс не должен
  падать.

---

## 8. Страница «ГРАММАТИКА» (`stamina/languages/grammar_page.py`)

Добавь `("grammar", _t("ГРАММАТИКА"))` в `SUBPAGES` между `practice` и
`reading`, ветку в `_show_page` и метод `_build_grammar(plugin, progress)`.

Экран состоит из двух режимов, переключаемых кнопкой в шапке.

### 8.1. Режим «УРОКИ»

- Строка уровней `A1 … C2` — кнопки как в `words_page.level_row`, с
  подписью «пройдено 4 из 18».
- Список уроков уровня: номер, название, подзаголовок, метка статуса
  (✓ пройден / ▶ следующий / · не начат). Клик открывает урок.
- Кнопка «СЛЕДУЮЩИЙ УРОК» ведёт к первому непройденному по порядку.
- Замков нет: пилот вправе открыть любой урок. Порядок — рекомендация,
  а не запрет.

### 8.2. Экран урока

Сверху вниз, с вертикальной прокруткой (`_scroller` уже есть в `screen.py`,
переиспользуй подход):

1. заголовок `A1 · 6` + название, кнопка `← К СПИСКУ`;
2. теория по блокам: `text`, `rule` (в рамке, с заголовком), `table`
   (настоящая сетка: шапка `columns`, строки `rows`, первый столбец —
   подпись падежа/лица), `example` (`de` крупно, `ru` мельче, `note` курсивом).
   Клик по примеру — озвучить (`stamina.languages.speech.speak(text, "de")`),
   рядом значок 🔊, если TTS доступен;
3. упражнения: по одному на экране, счётчик «3 / 12», кнопка `ПРОВЕРИТЬ`
   (и Enter), после проверки — строка «Верно» зелёным или «Неверно.
   Правильно: …» красным плюс `why`; кнопка `ДАЛЬШЕ`;
4. в конце — итог «Пройдено 10 из 12» и кнопки `ЗАНОВО` / `К СПИСКУ`.

Типы упражнений в интерфейсе:

- `choice` — кнопки-варианты, стрелки + Enter;
- `fill`, `declension`, `conjugation`, `transform` — поле ввода (`tk.Entry`)
  и проверка;
- `reorder` — поле, куда пишут готовую фразу (перетаскивание не нужно);
- `match`, `identify` — как `choice`.

### 8.3. Режим «ТАБЛИЦЫ»

Справочник: фильтр по уровню + список всех таблиц, каждая таблица — сетка
целиком, без раскрытия. Кнопка «СКОПИРОВАТЬ» кладёт таблицу в буфер обмена
текстом (столбцы через `\t`, строки через `\n`) — этого достаточно, чтобы
вставить в тетрадь или документ. Своих файлов не создавать.

### 8.4. Требования к интерфейсу

- Только `theme`-цвета, `px()`, `HudButton`, `HudPanel`, `theme.font`.
  Своих hex-значений не добавлять: `tools/contrast_audit.py` проверяет
  контраст по скинам и должен остаться зелёным.
- Окно 900×360 — рабочий минимум. Проверь, что таблица не раздувает
  страницу: широкие таблицы кладутся в `Canvas` с горизонтальной прокруткой,
  а не вылезают за экран. При 1280×800 всё помещается без прокрутки по
  горизонтали.
- Клавиатура: `Esc` — назад (к списку / к уровням), `←/→` — варианты,
  `Enter` — проверить/дальше. Ничего не перехватывать глобально.
- Страница обязана строиться без исключений при `progress is None`
  (пилот не выбран) — как это делают остальные страницы.

---

## 9. Прогресс

В `stamina/languages/core/progress.py`:

- в `_load()` в `base` добавь `"grammar": {}` — старые файлы прогресса
  читаются как раньше (`setdefault`);
- методы:
  - `record_grammar(lesson_id: str, correct: int, total: int) -> None` —
    пишет `{"done": bool, "score": float, "best": float, "ts": float,
    "attempts": n}`;
  - `grammar_done(lesson_id: str) -> bool` — `score >= 0.8`;
  - `grammar_summary(level: str, lesson_ids: list[str]) -> tuple[int, int]` —
    сколько пройдено из скольких;
- `save()` вызывается один раз после записи, атомарно, как сейчас.
- XP: за первый пройденный урок +10 через существующий `add_xp`, не больше
  одного раза на урок (проверяй `attempts`).

Данные — только в `lang_de.json` пилота. Ничего вне папки пилота не писать.

---

## 10. i18n

- Все подписи интерфейса — через `_t("…")`, по-русски как ключ.
- Новые ключи добавить **во все четыре** файла
  `stamina/i18n/{ru,uk,en,de}.json`. `ru` — точный, `en` — английский,
  `uk`/`de` — перевод или русский ключ как placeholder (в проекте так уже
  делают, см. `docs/HANDOFF.md`), но подстановки `{0}`, `{1}` обязаны
  совпадать во всех четырёх — это проверяет `tools/i18n_check.py`.
- **Теория уроков не переводится.** Текст теории — по-русски, немецкие
  примеры — по-немецки. Это содержимое, а не интерфейс.
- Вставляй ключи аккуратно, текстовой вставкой рядом с похожими, **не
  переформатируй файлы целиком** (иначе дифф на 400 строк и конфликты).
- Перед коммитом: `python -X utf8 tools/i18n_check.py` → все языки
  `2867+N/2867+N`, ошибок подстановок `0`.

---

## 11. Тесты: `tests/test_languages_grammar_de.py`

Не меньше 25 тестов. Стиль — как в `tests/test_languages_core.py` и
`tests/test_comm.py` (pytest, чистые проверки без Tk; интерфейс — через
реальный Tk и `pytest.skip`, если дисплея нет).

Обязательные проверки:

1. `courses.json` читается; уровни ровно `A1..C2`; `lessons` совпадает с
   фактическим числом.
2. В каждом уровне `order` идёт `1..N` без пропусков; `id` уникальны по
   всему проекту; `id` начинается с кода уровня (`a1-…` в A1).
3. `level` в файле совпадает с уровнем уровня.
4. `prereq` ссылается только на существующие уроки и только «раньше».
5. Каждый `ref` таблицы существует; `tables.json` без дублей `id`.
6. У каждой таблицы `len(row) == len(columns)`, нет пустых ячеек.
7. Точечные проверки фактов (жёстко зашиты в тест):
   - определённый артикль, 4 падежа × 4 колонки — точное совпадение;
   - `sein`, `haben`, `werden` в Präsens — точное совпадение;
   - `praesens_weak` для `machen` — `mache/machst/macht/machen/macht/machen`;
   - в `adj_decl_definite` ровно 16 клеток, и `-e` стоит ровно в пяти:
     Nominativ все три рода + Akkusativ женский и средний;
   - `wechselpraepositionen` содержит все девять предлогов;
   - `praep_akkusativ` содержит `durch, für, gegen, ohne, um`.
8. У каждого урока ≥ 10 упражнений; типы только из разрешённого списка.
9. У каждого `choice` — 3–4 уникальных варианта и правильный ответ среди них.
10. У каждого упражнения непустые `prompt`, `answer`, `why`; `answer` — список.
11. Нет мусора: в данных нет строк `answer`, `opt1`, `TODO`, `lorem`, `xxx`.
12. `generate_exercise("a1-06-genus", "easy", 42)` детерминирован (два вызова
    равны) и его ответ принимается `validate_answer`.
13. `validate_answer` принимает `die`, ` die `, `DIE`, `ue` вместо `ü`,
    `ss` вместо `ß`; отвергает `der` там, где правильный `die`.
14. `get_topics("A1")` — только A1; `get_topics("B1")` — A1+A2+B1.
15. `get_explanation` непуст для **каждого** `topic_id` из данных.
16. `progress.record_grammar` + `grammar_done`: 7/10 → False, 9/10 → True,
    сохраняется в `lang_de.json`.
17. Смоук интерфейса: страница строится, список уроков непуст, урок
    открывается, верный ответ помечается верным, неверный — неверным,
    режим «ТАБЛИЦЫ» рисует сетку.
18. Раскладка: на окне 900×360 ни один виджет страницы не шире окна
    (сравнивай `winfo_reqwidth()` с шириной окна, как это делает
    `test_input_row_is_visible` в `tests/test_comm.py`).

---

## 12. Гейты и команды

Запускай из `C:\Users\mi\grok_x\wt_nemotron`:

```powershell
python -X utf8 -m pytest tests/test_languages_grammar_de.py -q
python -X utf8 -m pytest tests/test_languages_core.py tests/test_languages_reading.py tests/test_languages_speech.py tests/test_languages_sqlite.py tests/test_languages_vocab.py tests/test_i18n.py -q
python -X utf8 tools/ci_gate.py --only i18n --only dep --only contrast
```

Первая и третья — зелёные обязательно. Во второй **одно падение было до
тебя**: `test_languages_vocab.py::test_plugins_load_a1_sets` — в испанском
словаре A1 на этом стенде 233 слова вместо 300 (недокачанные данные, не
код). Это не твоя тема: не чини и не подгоняй порог, просто запиши в отчёт.
Всё остальное в этом наборе — зелёное.

Полный `tests/` может быть красным по чужим темам; если так — сверься с
`docs/HANDOFF.md` и **не чини чужое**, только запиши в отчёт, какие тесты
падали до твоих правок.

Python: `C:\Users\mi\AppData\Local\Programs\Python\Python314\python.exe`.
`ruff` в системе не установлен — простота важнее, но имена, отступы и
докстринги держи в стиле файла.

---

## 13. Критерии приёмки (проверяющий пройдёт по этому списку)

- [ ] Ветка `agent/nemotron/de-grammar`, работа в отдельном worktree, снапшот
      сделан, тег записан в отчёт.
- [ ] 68 уроков по списку из раздела 4, порядок без пропусков, `prereq`
      корректен.
- [ ] 44 таблицы из раздела 5, сетки полные, без пустых ячеек.
- [ ] В каждом уроке 10–16 настоящих упражнений с ответами и объяснением.
- [ ] Нет ни одной заглушки, ни одного `TODO`, ни одного выдуманного факта
      из раздела 6.
- [ ] `GermanGrammarEngine` реализует контракт `base.py` и новые методы;
      ленивая загрузка, детерминизм по `seed`, устойчивость к битым данным.
- [ ] Страница «ГРАММАТИКА» в `SUBPAGES`, оба режима работают, `Esc`/`Enter`
      работают, 900×360 не ломается.
- [ ] Прогресс пишется в `lang_de.json`, старые файлы читаются.
- [ ] i18n: 4 языка, подстановки совпадают, файлы не переформатированы.
- [ ] Тесты: ≥ 25, все зелёные; существующие тесты отсека зелёные.
- [ ] `ci_gate --only i18n --only dep --only contrast` — зелёный.
- [ ] `docs/HANDOFF.md` обновлён; чужие файлы не затронуты; коммиты по-русски.

---

## 14. Формат отчёта в конце

Напиши в `docs/HANDOFF.md` и продублируй в ответе:

1. **Goal** — одной строкой.
2. **Done** — что реально сделано: файлы, число уроков, число таблиц, число
   упражнений, что в интерфейсе.
3. **Checks** — вывод трёх команд из раздела 12 (с числами: сколько тестов
   прошло, сколько ключей в i18n).
4. **Decisions** — 3–5 решений и почему (например, почему поле ввода вместо
   перетаскивания).
5. **Problems** — что не удалось, где сомневался, что стоит проверить руками.
6. **Next** — что осталось за рамками.

---

## 15. Границы работы

Не делать в этом задании:

- не переводить интерфейс на новые языки и не чинить чужие MT-строки;
- не менять `words_page.py`, `scanner.py`, английский отсек;
- не трогать `stamina/lounge/trainer.py` и тесты терраформера;
- не добавлять внешних зависимостей (только стандартная библиотека; Pillow —
  опционально и уже используется);
- не делать сетевых запросов и не скачивать данные;
- не пушить в `origin` и не открывать PR — это сделает командир после
  проверки.

---

*Конец задания. Начинай с раздела 2: прочитай файлы, потом `snapshot.ps1`,
потом worktree, потом данные A1, потом движок, потом интерфейс, потом тесты.*
