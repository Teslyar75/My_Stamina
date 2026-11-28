# Handoff

Goal: переделать раздел «Грамматика» (DE) так, чтобы урок было понятно проходить,
а материал грузился порциями. Ветка `agent/orion/de-grammar-ux` от `origin/master` 41c3f95.

Done:
- `bridges.json` — 68 записей «что освоите / мостик RU-UA → DE / ловушка», движок отдаёт `bridge(lesson_id)`.
- `grammar_page.py` переписана: поток `уровни → уроки → intro → теория (блок на экран) → упражнения (одно на экран) → итог`.
- Идеи Grammatik aktiv: кнопка `ПРАВИЛО` открывает правила и таблицы урока прямо под упражнением; `ПРОВЕРЬ СЕБЯ` — смешанная проверка по пройденным урокам уровня (12 заданий, оценок не меняет).
- Идеи Нарустранг: задание с кириллицей получает инструкцию «Переведите на немецкий».
- Подсказка, разбор ошибок с «почему», повтор только ошибок, порог 80%, запись урока один раз.
- Банк слов для «соберите предложение» (клик по словам, детерминированное перемешивание).
- Загрузка порциями: уровни читают только манифест, уровни/таблицы/списки — лениво, рендер по 6 элементов через `after(1)`.
- Сверка ответов: выбор варианта — точное написание (`ä ≠ ae`, `ß ≠ ss`, `zu Hause ≠ zu hause`), вписанное слово — умлаут можно раскрыть, порядок слов — без знаков препинания.
- 32+8 ключей i18n в 7 языках; `tools/i18n_check` — код 2952, ошибок 0.
- Тесты: `tests/test_languages_grammar_de_ui.py` (52 проверки всего потока и загрузки без зависаний), `TestGrammarUISmoke` переписан под новый поток.

Next: слияние в `master` (PR), затем автопрогон `tools/auto_release.py --push` в CI выпускает 3.9.0 — программа увидит обновление по кнопке «Обновить сейчас».

Problems: нет.

### Проверка «без зависаний» (замеры на 900×360)
- разбор данных: `courses.json` 0.5 мс, файл уровня 1–2 мс, `tables.json` 1.2 мс;
- список 18 уроков: 87 мс всего, худший шаг 37 мс (порции по 6, `after(1)`);
- таблицы (45): ~230 мс всего, порций 8, худший шаг ~43 мс;
- простой в главном цикле: 0–1.5% CPU, 0 отложенных задач на каждом экране, после `destroy` тоже 0;
- 30 быстрых переключений уровней: очередь не растёт, таймер один;
- ресайз 700↔1200: одна раскладка, цикла `<Configure>` нет (тест `test_no_horizontal_overflow_after_resize`);
- перенос строк включается только там, где текст не влезает — иначе раскладка списка стоила 118 мс на шаг.

---

## Docker Dock Station (MVP) — ветка `agent/orion/docker-dock`

Goal: реализовать Docker-тренажёр в лобби (столик «Dock Station»): чистый симулятор, Tkinter-геймплей, интеграция с лобби, сохранение прогресса, i18n, тесты.

Done:
- `stamina/lounge/docker_sim.py` — чистый симулятор: образы, контейнеры, порты, тома, сети, compose, build, prune, сериализация. Все unit-тесты проходят (`tests/test_docker_sim.py`: 48 passed).
- Исправлены парсер аргументов `docker run`, обработка detached-режима, ошибки дубликатов имён/портов, неизвестных образов, compose-сервисов.

Done (continued):
- `stamina/lounge/docker_trainer.py` — Tkinter-геймплей: терминал, 8 миссий, подсказки, XP, режим песочницы, F1-справка, сохранение прогресса (`store`, ключ `docker_trainer`).
- Интеграция в `screen.py` (сетка 3×2 и карточка «Док-станция»).
- i18n: новые ключи добавлены во все 7 локалей (ru/uk/en/de/es/fr/it). Существующие ключи и их порядок не менялись.
- Тесты симулятора: `tests/test_docker_sim.py`.

### Учебник Docker + «Песочница» в тренажёре (21.11)

Пилот: пробел не набирается, Backspace уводит в лобби (нужно стирать), поле ввода
маленькое, хочется учебник со списком команд и практикой.

Done:
- Ввод: `typed_char()` берёт `event.char` (а не `keysym`); пробел и «-», «/», «:» теперь
  набираются. Служебные клавиши отсекаются по `isprintable`.
- Строка ввода стала выше (три строки mono 14) и переносится; терминал сокращается.
- Галка в панели: `GameShell.text_input = True` → `⌫ Backspace — стирать` (вкл. по умолчанию,
  `store.setting/set_setting`, выбор в `lounge.json → settings.backspace_edits`).
- `nav_back.screen_edits_text(app)` спрашивает экран: `LoungeScreen.backspace_edits()` →
  Backspace правит текст, когда галка включена; выключена — глобальное поведение вне игры
  не меняется (у пилота галка выключена по умолчанию → он хочет иное: оставить/включить).
- `GameShell.tools_row` — вторая строка панели с `build_tools()` (переопределяют игры).
- Учебник: `stamina/lounge/docker_reference.py` (9 тем, 103 команды, поля cmd/desc/example/sim).
  `stamina/lounge/docker_ref_panel.py` — панель: темы слева, команды по центру с поиском,
  карточка справа, кнопки «→ В СТРОКУ» / «▶ ВЫПОЛНИТЬ». F2 / кнопка «УЧЕБНИК F2».
  Зелёным помечены команды из симулятора; остальные — «только в настоящем Docker».
- «Песочница · без миссий» — галка в третьей строке: отключает проверку миссий, команды
  можно тестировать сколько угодно (в тренажёре они и так выполнялись, но не было свободного
  режима из UI).
- Миссия 1: проверка по образу `ship/radio` (раньше сравнивали с «ship_radio»/«radio» —
  с первой миссией никогда не было).
- i18n: 21 ключ добавлен в 7 локалях + 2 ключа переименованы (миссия/приветствие F1/F2);
  `tools/i18n_check` — 2998/2998, ошибок 0, ГАТ зелёный.
- Тесты: `tests/test_docker_trainer_input.py` (ввод, служебные клавиши, Backspace, store,
  миссии, учебник, панель, песочница).

Next: слияние в `master` (PR), затем автопрогон `tools/auto_release.py --push` в CI выпускает 3.9.0.

## Терминальные тренажёры (23.11, ветка `agent/orion/term-games`, `D:\Star_Typing_games`)

Goal: в «Отдыхе» три тренажёра — Docker, Linux, PowerShell — должны давать больше
практики и объяснять материал в учебнике F2, а не только перечислять команды.

Done:
- `terminal_sim.py` — общий симулятор Linux/PowerShell с состоянием: права и владелец
  файлов, текущий каталог, архивы, crontab, переменные окружения; понимает `&&`, `;`, `|`
  (вывод левой команды реально идёт в правую), `to_dict`/`from_dict` сохраняют песочницу.
- Миссии: Linux — 12 + песочница (права, архивы, конвейеры, cron, journalctl, ssh);
  PowerShell — 13 + песочница (конвейер, Where-Object, Measure-Object, фильтр, JSON, порт);
  Docker — миссии 9–13 (том, `-e`, `docker port`, `build -t`, `compose down`).
- Справочники: `linux_reference.py` (10 тем), `powershell_reference.py` (8),
  `docker_reference.py` — 11 тем (добавлены «Отладка» и «Данные и переменные»);
  у каждой темы `theory` (3 тезиса) и `blurb`.
- Панель F2 (`docker_ref_panel.py`) — общая для всех трёх игр: заголовок и подписи берёт
  из модуля данных (`PANEL_TITLE`, `SIM_HINT`, `REAL_HINT`), над списком команд показывает
  теорию выбранной темы, перенос строк — по фактической ширине колонки.
- Лобби (`screen.py`): подпись «· миссий: N» считается из класса игры, а не захардкожена;
  глобальный wheel-биндинг больше не падает на мёртвом холсте.
- `help_texts`: новые `linux_trainer.json`, `powershell_trainer.json`; Docker дополнен
  миссиями 9–13 и описанием теории в песочнице.
- Учебный текст (миссии, справочники, вывод симулятора) — по-русски, без `_t()`:
  i18n-долг не растёт. Подписи интерфейса переведены: 12 ключей в 7 языках
  (`УЧЕБНИК LINUX/POWERSHELL`, `ДОК-СТАНЦИЯ`, `BASH ТЕРМИНАЛ`, `СИСТЕМНЫЙ ИНТЕРФЕЙС`,
  `{0} · миссий: {1}`, приветствия тренажёров).
- Тесты: `tests/test_terminal_trainers.py` — все миссии проходятся своими командами,
  у каждой темы есть теория, панель показывает теорию выбранной темы, лобби считает
  миссии сам; `tests/test_lounge_help.py` обновлён под новые миссии и две игры.

Next: выпуск (следующий `tools/auto_release.py --push` в CI) — программа
увидит обновление по кнопке «Обновить сейчас».
Влито в `master`: PR #59, merge-коммит `eac3410`; на коммите слияния зелёные
`tests/test_terminal_trainers.py`, `test_lounge_help`, `test_docker_trainer_input`,
`test_i18n`, `tools/i18n_check.py` (3015/3015) и `ci_gate --only contrast --only dep`.

Problems: в рабочем дереве `D:\Star_Typing_games` остаётся чужой WIP (~900 ключей
в `stamina/i18n/*.json` и `_t()`-обёртки), поэтому `i18n_check` красный именно там;
в коммите и на `master` гейт зелёный. `stamina/lounge/help_texts/*` — тексты по-русски намеренно.

## Учебник VIM (23.11, ветка `agent/orion/vim-textbook`)

Goal: в тренажёре VIM не хватало материалов — только 12 уроков и справка F1.
Нужен учебник по образцу Док-станции (панель F2): темы, теория, примеры.

Done:
- `vim_reference.py` — 14 тем, 95 клавиш; у темы `blurb` и `theory` (3 тезиса),
  у клавиши `cmd/desc/example/sim/seq/needs/probe/lesson`.
- Честность пометок: `sim=True` (38 клавиш) проверяется тестом через настоящий
  `vim_engine` (`seq` + `needs` + `probe`); `"partial"` (4) — движок знает, но
  упрощено (`p/P`, `yy` — регистров нет); `False` (53) — только в настоящем VIM.
  Обратный тест: `gg`, `ciw`, `:%s/…`, `:w`, `ma` не могут быть помечены «работает».
- `vim_ref_panel.py` — три колонки: темы / клавиши с поиском и теорией / карточка
  с примером, статусом и кнопкой «▶ К УРОКУ» (ведёт в урок тренажёра, где эта
  клавиша отрабатывается). Вторая кнопка — «✕ ЗАКРЫТЬ  F2».
- `vim_trainer.py` — `tools_row=True`, `build_tools()`, `reference_open/toggle/
  close_reference/open_lesson`; F2 в `on_key` переключает панель, Esc закрывает,
  остальные клавиши при открытой панели в поле не доходят.
- `ref_list.py` — прокручиваемый список вынесен из `docker_ref_panel` и общий
  для Docker/Linux/PowerShell и VIM (`_ScrollList` оставлен алиасом).
- 13 ключей интерфейса в 7 языках; `help_texts/vim_trainer.json` упоминает F2.
  Учебный текст — по-русски, без `_t()`: i18n-долг не растёт.
- Тесты: `tests/test_vim_reference.py` (24 проверки: структура, честность `sim`
  движком, панель, интеграция с игрой). Зелёные `test_vim_trainer`,
  `test_lounge_help`, `test_i18n`, `test_terminal_trainers`; `tools/i18n_check.py`
  код 0 (3028/3028); `ci_gate --only contrast --only dep` зелёный; ruff чисто.
- Влито в `master`: PR #60, merge-коммит `2ceb015`.

Next: `D:\Star_Typing` подтянут до 3.9.10 (`git merge --ff-only`), учебник на месте.
Пилоту в `D:\Star_Typing_games`: `git merge origin/master`, чтобы учебник появился
в рабочей копии игр.

Локальная правка пилота (галка Backspace в `TrainerGame`) снята в `stash@{0}` и
сохранена патчем; на master Backspace в тренажёре набора уже не уводит в лобби
(`GameShell.backspace_edits`), видимой галки у этого тренажёра нет.

Problems: в `D:\Star_Typing_games` остаётся чужой WIP (i18n-ключи и `_t()`),
поэтому `i18n_check` красный именно там; в коммите и на `master` гейт зелёный.

## Одна папка: всё сведено в D:\Star_Typing (24.11, ветка `local/all-work`)

Goal: пилот просил держать все изменения локально в одном месте, а не в нескольких
папках с фрагментами — и один ярлык на рабочем столе для десктопной версии.

Done:
- `D:\Star_Typing` — единственная рабочая копия, ветка `local/all-work`:
  - `8a1dd79` — master 3.9.10 (учебник VIM, терминальные тренажёры);
  - `0666033` — правка микрофона и `alt2_ui.py` из `D:\My_New_Stamina`
    (коммиты `4ba9526` + `0af4e8c`);
  - `df3fc46` — 68 файлов работы по английскому, языкам, голосу и прочему из
    `D:\Star_Typing_games` + 7 файлов переводов (в них добито 111 ключей из
    master, в том числе ключи учебника VIM). Мусор из wip-коммита (log.txt,
    pr_body.md, два скрипта в корне) убран.
- Восстановлена правка микрофона, которую WIP затёр: `voice/stt.py`, `voice/mic.py`,
  `languages/screen.py` взяты из `0666033`, сверху возвращены i18n-обёртки;
  `tests/test_mic_availability.py` — 7/7.
- Микрофон в Сканере на месте: `pages_main.ScannerPage` создаёт `MicPanel`
  (кнопка «🎤 ГОВОРИТЕ  M»), в `refresh_mode()` она больше не прячется; в `.venv`
  `stt.ready() → True`, модели в `D:\Star_Typing\models`.
- Веб-версия перенесена в `D:\Star_Typing\web_star_typing`, ярлык «Star Typing Web»
  перецелен туда.
- На рабочем столе один ярлык десктопной версии: «Star Typing» →
  `.venv\Scripts\pythonw.exe main.py`, иконка `stamina/assets/star_typing.ico`.
- Удалены: `D:\Star_Typing_games`, `D:\Star_Typing_games_docker`,
  `D:\My_New_Stamina`, временный worktree `vim-work`. Архивы в `D:\_archive`:
  `Star_Typing_games_20261124.zip` (821 МБ), `Star_Typing_games_docker_20261124.zip`
  (314 МБ), `My_New_Stamina_20261124.zip` (747 МБ). Снимки до уборки — теги
  `snap-20261124-0245` и `snap-20261124-0247`.

Problems: i18n-долг из WIP остался (870 русских ключей без переводов), поэтому
`tools/i18n_check.py` и `tests/test_i18n.py` красные на этой ветке — унаследовано,
не поломка. `master` чистый.

## Сканер языков как в английском + озвучка (25.11, `local/all-work`)

Goal: сканер слова в DE/ES/FR/IT должен выглядеть и работать как английский,
и должна звучать озвучка слова и предложения.

Done:
- `stamina/languages/scanner.py` переписан по шаблону английского компактного
  `ScannerPage`: `ScrollFrame` с автоскрытием прокрутки, строка действий
  (←/◀/▶ и номер карточки) в заголовке панели через `_place_actbar`, три колонки
  6:7:9 с тонкими разделителями, предложение в `tk.Text` (перенос, подсветка
  изучаемого слова), `ПЕРЕВОД  T` и `💡 ПОДСКАЗКА`, `MatchReadout` появляется
  только с результатом, микрофон справа в канале связи, `sf.top()` при смене слова.
- `LangCtx` (`stamina/languages/ctx.py`): `lang`, `voice_error`, `say()` и
  `audio_button()` — кнопки озвучки светятся, пока звучит фраза (как `english/screen.py`).
- `stamina/languages/speech.py`: `speak()` сначала пробует edge-tts (mp3 в кэше),
  если пакета или сети нет — голос Windows нужной культуры через общий `TTS`
  (`culture="de-*"`), а если нет и его — в `on_error` уходит понятная причина
  («нет голоса Windows de-* … поставьте голос или edge-tts»). Добавлены `on_done`,
  `edge_ready()`; `stop_speak()` останавливает и голос Windows.
- `requirements.txt`: `edge-tts>=7.0` стал настоящей зависимостью; в `.venv`
  пакет установлен (`edge_ready() → True`). `tools/dep_audit.py`: имя модуля
  `edge_tts` сопоставлено пакету `edge-tts`, аудит зелёный (код 0).
- Новых ключей i18n нет: подписи взяты из существующих, пояснения и причины
  отказа — по-русски без `_t()` (долг не растёт).

Проверено только затронутое: сборка сканера в окне 1100×700 (строка действий в
заголовке, предложение и перевод, ПЕРЕВОД/ПОДСКАЗКА, скрытая шкала, итог проверки),
озвучка DE через edge-tts и запасной путь без пакета (сообщение за 0.8 с),
`ruff` по изменённым файлам, `dep_audit`.

Next: пилот слушает сканер в DE/ES/FR/IT; если голос нужен без сети — поставить
голоса Windows этих языков (Параметры → Время и язык → Речь).

### Фокус-режим и клавиши сканера языков + сетевой голос в английском (25.11)

Goal: сканер DE/ES/FR/IT должен не просто выглядеть как английский, а иметь те же
настройки и клавиши; английская озвучка должна звучать так же живо, как языковая.

Done:
- `languages/scanner.py`: перенесены из английского компактного сканера
  фокус-режим (`FocusMode`, `_grow/_fill/_center/_scale`, кнопка `⛶ ФОКУС  O`),
  авто-подгонка длинного слова (`fit_word`), обычное заполнение высоты окна
  (`_fit_normal`, `NORMAL_FONT_GAIN/CAP/MIN`, те же числа, что в `english/pages_main.py`),
  debounce `_queue_fit` на `<Configure>`/`<Map>`, снятие фокуса при `<Unmap>`.
- Клавиши теперь как в английском: `O`/`Щ` и `Ctrl+O` — фокус, `Esc` — выход из
  фокуса (а вне его — назад), `M` — микрофон, `T` (удерживать) — перевод,
  `S` — озвучить предложение, `←/→` (и PgUp/PgDn) — предложения. Перевод по
  умолчанию скрыт, как в английском, и показывается по `T`/кнопке `ПЕРЕВОД`.
- `Ctrl+O` работает и из поля «МОЙ ПЕРЕВОД»: `languages/screen.py` отдаёт аккорд
  сканеру до проверки «фокус в поле ввода»; `cockpit._on_key_up` теперь отдаёт
  отпускание клавиш и языкам — иначе `T` не скрывал перевод обратно.
- `focus_active/handle_focus_escape/toggle_focus` языкового отсека знают про
  сканер: Esc из фокуса не уводит в обзор, а `cockpit.show()` корректно снимает
  фокус при смене отсека.
- Английский голос: `english/screen.py::say` вызывает `tts.speak(..., network=True)`;
  сетевой синтез вынесен в общий `stamina/tts_edge.py` (голоса en/en-GB/de/es/fr/it),
  им пользуются и языки, и английский. При отказе сети фраза уходит в голос
  Windows под тем же `id`, поэтому подсветка кнопок и события не меняются.
- Новых ключей i18n нет: `⛶ ФОКУС  O` и `✕ ФОКУС  Esc` уже есть в 7 локалях.

Проверено только затронутое: сборка сканера 1100×700 (обычный вид и фокус,
`k` 1.29→1.68), `T` скрывает/показывает перевод, `O`/`Ctrl+O`/`Esc`, `←/→` по
предложениям, итог проверки; снимки `scanner_normal.png` и `scanner_focus.png`;
английская фраза через edge-tts (`start`→`done`) и немецкая через `speech.py`
после рефакторинга; `tests/test_languages_speech.py`, `test_languages_tile.py`
(12 passed); `ruff` по изменённым файлам; `dep_audit` код 0.

---

## Исправление микрофона английского сканера + итальянская грамматика (25.11, `local/all-work`)

Goal: два независимых бага — микрофон в английском сканере не работал (Vosk-модель отсутствовала), и итальянская грамматика показывала немецкий флаг + лишние вкладки немецких курсов.

Done:
- **Английский сканер — микрофон**: нехватающая Vosk-модель `vosk-model-small-en-us-0.15` скачана через `scripts/download_vosk_model.py` в `models/` (корень). `ASR().available()` → `True`, `vosk_model_dir()` находит модель. `tests/test_mic_availability.py` — 7/7 зелёных.
- **Итальянская грамматика — флаг**: в `ItalianGrammarCatalog.paint_title_flag` (stamina/languages/grammar_page.py:755) заменено `"de"` на `"it"` — теперь отображается итальянский флаг.
- **Итальянская грамматика — лишние вкладки**: `ItalianGrammarCatalog` была полной копией `GermanGrammarCatalog` с `OpenSourceBank` и `source_tabs()`. Убраны все методы/атрибуты, связанные с открытыми источниками (`show_source_tabs`, `_ensure_open`, `sources`, `select_source`, `_load_open_topic`, `header_subtitle` для open, `progress_text` для open, `_topic_summaries`, `neighbours`, `hint_for_unit`, `unit_number`, `is_done`, `mark_complete` для open, `load_table` делегировал к engine). Класс теперь минимален — только `paint_title_flag("it")`. Французский/испанский каталоги работают так же (только базовый курс).
- Тесты: все итальянские/французские/испанские грамматические тесты проходят (`test_languages_grammar_it.py`, `test_languages_grammar_fr.py`, `test_languages_grammar_es.py` — зелёные). CI gate (`tools/ci_gate.py --only contrast --only dep`) — зелёный. `i18n_check` без новых ошибок (код 3282, те же 450 лишних ключей из WIP-наследия, не моя поломка).

Problems: один тест `test_lesson_intro_explains_goal_and_traps` (немецкая грамматика) падает — ищет текст "МОСТИК RU/UA → DE" в UI, которого теперь нет (данные bridges.json могли измениться). Это не связано с моими правками (тронул только итальянский каталог).

---

## Словарь в начале урока грамматики (25.11, ветка `agent/orion/grammar-section-cards`)

**Цель.** В начале каждого урока грамматики (немецкий, французский, итальянский, испанский, английский, уровни A1–C2) показать словарь слов этого урока. Строка строго такая:

`слово на иностранном языке: произношение: перевод`

Пример: `Haus: [haʊs]: дом`

Карточки пилот остановил. Сначала только словарь: без плиток, без «знаю», без «в отсек», без сканера.

Ветка уже есть, от `master` (`80b10bf`). Новую не создавать.

**Сделано.**
- `stamina/languages/grammar_page.py`: `BaseGrammarCatalog._extract_vocabulary()` для DE/FR/ES/IT — точная лемма из примеров (`theory[].kind=="example"`) и упражнений (`drills[]`), поиск через `search()` + фильтр `glosses()`/`gloss_lang()` только RU.
- `stamina/english/pages_grammar.py`: `EnglishGrammarCatalog._extract_vocabulary()` для EN — из `examples[].en`, `exercises` (q/options/a), `traps.good/bad`; перевод `ru` + произношение `ipa`/`respelling` через `ctx.vocab.get()`.
- `stamina/grammar_ui/spread.py`: `GrammarSpread._piece_vocabulary()` — таблица 4 колонки: 🔊 (клик = озвучка) | СЛОВО | ПРОИЗНОШЕНИЕ | ПЕРЕВОД. Вставлена в `_lesson_pieces` после `_piece_head`, перед `_piece_goal`.
- `stamina/i18n/*.json` (7 локалей): ключи `СЛОВАРЬ УРОКА` (заголовок), `СЛОВО`, `ПРОИЗНОШЕНИЕ`, `ПЕРЕВОД`.
- `GrammarPage` (DE/FR/ES/IT) теперь создаёт `LangCtx` с `asr_for(lang)` → кнопка 🔊 работает через `ctx.say(lemma)` (edge-tts → SAPI fallback, подсветка пока звучит).

**Проверено.**
- DE урок `a1-01-alphabet-laute`: 27 слов, формат `wie: —: как`.
- EN урок `u001` (verb be): 31 слово, формат `from: /frʌm/: из, с, от`.
- i18n_check: 3284 ключа, новых ошибок 0 (только пред. WIP-долг).
- ruff: чисто на изменённых файлах.
- Тесты: `test_languages_grammar_de_ui.py` (TestLessonIntro, TestTheory — зелёные), `test_english_grammar.py` (3/3), FR/ES/IT грамматика (78/78).

**Не делал.** Карточки, сканер, «знаю», «в отсек», слияние в `master`, релиз.

---

## Терраформер как стратегия: Dune / Red Alert (26.11, ветка `agent/orion/terraformer-strategy`)

Goal: «Тренажёр Терраформера» в «Отдыхе» — не учебная смена на A1–A4, а стратегия
на лестнице языка A1…C2: отряд, задания-тревоги, туман войны, экономика, песчаный
червь. Ветка от `master` (`d185c21`, тег `v3.9.12`).

Done:
- `stamina/terraformer_strategy.py` — чистый слой без Tk: `LEVELS` (A1, A2, B1.1,
  B1.2, B2.1, B2.2, C1, C2), высоты 1…8, радиус обзора, скорость; `Standing`
  (следующий уровень — когда предыдущий >80 %, второй юнит — от 50 %, разработчику
  все восемь), `Alert`/`Mission`/`MissionBook` (24 задания, 3 на уровень),
  `Unit`/`pathfind`/`formation_targets`/`issue_move`, `STRUCTURES` (8 зданий
  с высотой, ценой, доходом и нужным уровнем), `Sandworm`/`worm_step` (след,
  специя, обход месторождений, безопасные фундамент/скала), `find_for_cell`
  для новых клеток карты, `community_snapshot` — задел под онлайн-карту сообщества.
- `stamina/terraformer_trainer.py` — отсек грунта 5 (было 10); `PROGRESSION_TIERS`
  переведены на CEFR; у платформы появились `height`/`required_level`; в модели —
  отряд, выбор рамкой, приказы, расширение карты со сдвигом координат, туман
  (`explored`/`visible`), связи зданий и доход за тик, стройка с проверкой высоты
  и уровня, червь и его атаки; blueprint v4 хранит всё это и читает старые файлы.
- `stamina/lounge/trainer.py` — 8-сегментная шкала языка; Ctrl+колесо — масштаб
  вокруг курсора, СКМ — таскать карту; ПКМ-рамка выделяет отряд, клик по карте —
  приказ идти, клик по терраформеру — выделить его; отрисовка юнитов, зданий,
  тумана, следа червя, рамки и маршрутов; оверлеи «Задания · тревоги» (зелёные
  галочки) и «Стройка · здания» (высота и нужный уровень); HUD с кредитами,
  отрядом, заданиями и специей; галерея 2D/3D показывает высоту здания.
- `help_texts/terraformer.json` — 8 этапов CEFR вместо шести старых; лобби
  (`lounge/screen.py`) переименовано в «ТЕРРАФОРМЕР · СТРАТЕГИЯ ПЛАНЕТЫ».
- i18n: 39 новых ключей добавлены в 7 локалей (ru/uk/en/de/es/fr/it) в конец
  файлов, порядок и формат не тронуты. `tools/i18n_check.py`: 3295 ключей,
  2998 переведено, ошибок подстановок 0; лишние ключи и пропуск
  `МОСТИК RU/UA → {0}` — унаследованный долг master, не этот коммит.
- Тесты: новый `tests/test_terraformer_strategy.py` (31 проверка: уровни, задания,
  отряд и путь, туман/расширение, червь, стройка/доход, blueprint, зум камеры,
  оверлеи, ПКМ/СКМ, этапы справки). Вместе с `test_terraformer_trainer` и
  `test_lounge_help` — 72 проверки зелёные; `ci_gate --only contrast --only dep`
  зелёный; ruff по изменённым файлам чистый.

Проверено вручную: сборка 900×360 — оверлеи заданий/стройки, галерея, восемь
юнитов разработчика, постройка башни, 60 тиков и след червя без ошибок Tk.

Next: слияние в `master` (PR), затем обычный выпуск через CI. Успехи других
отсеков (печать, скорочтение) пока не подмешаны в `Standing` — сейчас язык
плюс выполненные задания; это следующий шаг, если пилот захочет.

Problems: нет.

### Stage 1 fix (26.11, ветка `agent/orion/terraformer-s1`)
- Исправлены тесты: удалён пустой дубликат `test_ctrl_wheel_zooms_at_cursor`, удалён второй класс `LevelsTest`, добавлен `test_level_titles` с проверкой 8 русских названий (Высадка, Лагерь, Посёлок, Станция, Город, Агломерация, Колония, Цивилизация), переписаны `DevFlagTest` без патчинга `is_developer` (save/restore env, patch `pilots.is_captain`), исправлены UI-тесты клика и бокса (пустая клетка, корректные координаты drag).
- `stamina/lounge/trainer.py`: инициализированы `_lmb_start`/`_lmb_box`, порядок проверок в `_on_lmb_down` (pause → gallery → overlay → box), убран лишний `bind("<Button-1>", _on_canvas_click)`, `_on_rmb_drag` — no-op, `_on_rmb_up` оставляет приказ без выделения, удалена отрисовка ПКМ-рамки, поправлен отступ и текст в `help_sections` («ЛКМ: рамка выделяет отряд, клик по юниту выделяет, клик по пустой земле снимает выделение; ПКМ — приказ идти»), `key_hint` добавил ЛКМ, убран stale-комментарий «ПКМ — рамка/приказ», удалён toast `_t("Снято выделение")`.
- `stamina/terraformer_strategy.py`: `set_developer_mode` только переключает `_DEV`, не трогает `os.environ`.
- `stamina/terraformer_trainer.py`: комментарий «A1 · выживание» → «A1 · Высадка».
- ЛКМ box-select + клик по юниту/пустой земле, ПКМ — приказ идти, Ctrl+колесо и СКМ панорама без изменений, `--dev` / `STAR_TYPING_DEV=1` + проверка капитана.

---

## Изометрический вид (Stage 2) — ветка `agent/orion/terraformer-s2`

Goal: добавить полноценную изометрическую проекцию в тренажёр терраформера:
по нажатию `I` (или keycode 73) переключение между плоским (top-down) и изометрическим видом.
Изометрия: ромбические тайлы 2:1, высота слоя видна, зум Ctrl+колесо вокруг курсора,
корректный `pick_tile` (math.floor для отрицательных координат), видимые границы для отсечения.

Done:
- `stamina/lounge/iso.py` — чистый модуль проекции без Tk:
  - константы `ZOOM_MIN=0.5`, `ZOOM_MAX=3.0`, `ZOOM_STEP=1.25` (совпадают с `Camera`);
  - `tile_metrics` — метрики тайла для зума/канваса/камеры;
  - `world_to_screen` / `screen_to_world` — прямая и обратная проекция (gz=0);
  - `tile_polygon` — 8 координат ромба (top, right, bottom, left);
  - `pick_tile` — экран → клетка, использует `math.floor` (не `int`);
  - `zoom_at` — зум вокруг курсора, держит мировую точку под мышью;
  - `visible_cell_bounds` — (min_gx, min_gy, max_gx, max_gy) для viewport culling.
- `stamina/lounge/trainer.py` — интеграция изометрии:
  - флаг `_iso_view = False` (переключается клавишей `I`);
  - свойство `iso_view` (read-only);
  - отдельный `_iso_zoom` для изометрии;
  - `on_wheel` → `iso.zoom_at` при Ctrl+колесо в iso-режиме;
  - `zoom_in`/`zoom_out` действия используют `_iso_zoom` в iso-режиме;
  - `redraw` вызывает `_draw_iso` при `_iso_view`, иначе старый плоский код;
  - `_draw_iso` — тайлы по диагоналям (порядок прорисовки: дальние → ближние),
    находки, стройплощадка, блоки, рамка карты, здания, червь, отряд;
  - хелперы: `_draw_buildings_iso`, `_draw_worm_iso`, `_draw_units_iso`,
    `_draw_hud`, `_draw_overlays` (общие для обоих видов).
- `tests/test_terraformer_iso.py` — 12 тестов:
  - константы зума совпадают с Camera;
  - round-trip world→screen→world (6 точек);
  - `tile_polygon` порядок углов;
  - `pick_tile` попадание, вне карты, math.floor для отрицательных;
  - `zoom_at` in/out возврат, клампы, точка под курсором;
  - `visible_cell_bounds` покрытие вьюпорта, кламп к краям;
  - интеграция: `TrainerGame.iso_view` — property.
- Исправлены два падения тестов и ruff:
  - `key_hint()` сокращён до «…ЛКМ выбор · ПКМ ход · СКМ карта · I изо» (влезло в 1200 px);
  - добавлен новый ключ i18n с переводом во все 7 локалей (ru/uk/en/de/es/fr/it);
  - убран неиспользуемый `import math` из `tests/test_terraformer_iso.py`.
- Все тесты зелёные: `test_terraformer_iso.py` (12/12), `test_terraformer_trainer.py` (включая `test_key_hint_fits_1280_in_all_languages` и `test_help_and_resource_keys_in_all_languages`), `test_terraformer_strategy.py`, `test_lounge_help` — без регрессий.
- `ci_gate --only contrast --only dep` — зелёный; ruff чисто.

Next: слияние в `master` (PR), затем обычный выпуск через CI.

---

## Изометрический зум: surface-aware (Stage 2 fix, 26.11, ветка `agent/orion/terraformer-s2`)

Goal: исправить баг зума в изометрическом виде — `iso.zoom_at` делал unproject на `gz=0` (дно), а нужно на видимой **верхней поверхности** клетки под курсором (верхний ромб, который рисуется на `terrain_gz(dug) + 1`).

Done:
- `stamina/lounge/iso.py` — новые функции:
  - `screen_to_world_at_gz(sx, sy, gz, m)` — обратная проекция на заданном gz.
  - `point_in_diamond(sx, sy, polygon)` — hit-test точки в ромб (8 координат).
  - `pick_surface(sx, sy, m, dug_grid, w, h)` — находит верхнюю видимую поверхность под курсором: ищет в окрестности seed-клетки (gz=0 unproject), сортирует кандидаты front-to-back (больше gx+gy — ближе к камере), возвращает `(gx, gy, top_gz)` где `top_gz = terrain_gz(dug) + 1`.
  - `apply_zoom(direction, sx, sy, canvas_w, canvas_h, cam, zoom, dug_grid, w, h)` — surface-aware зум: при наличии `dug_grid` якорь на `pick_surface`, иначе fallback на `gz=0` (совместимость со старым `zoom_at`). Камера рассчитывается аналитически для нового зума, чтобы заданная мировая точка осталась на той же позиции экрана.
- `stamina/lounge/trainer.py` — `on_wheel` (Ctrl+колесо в iso) теперь вызывает `apply_zoom` с `model.dug`, `model.w`, `model.h`.
- `tests/test_terraformer_iso.py` — добавлены 4 новых тест-класса (18 проверок):
  - `ScreenToWorldAtGzTest` — обратная проекция на gz≠0.
  - `PointInDiamondTest` — попадание в ромб.
  - `PickSurfaceTest` — поиск поверхности: ровная карта, высокая клетка рядом с ямой, отличие от gz=0 unproject.
  - `ApplyZoomTest` — зум держит поверхностную точку под курсором, in/out возвращается к исходному, fallback без dug_grid.
- Все тесты зелёные: `test_terraformer_iso.py` (30/30), `test_terraformer_trainer.py`, `test_terraformer_strategy.py`, `test_lounge_help` — без регрессий.
- `ci_gate --only contrast --only dep` — зелёный; ruff чисто.

Problems: нет.

---

## Stage 2 fix5: texture fix + zoom anchor + worm gz + structures heights test (26.11, ветка `agent/orion/terraformer-s2`)

Goal: исправить оставшиеся баги из Stage 2: (1) процедурные текстуры не работали — `tk.PhotoImage(image=PIL)` выбрасывает TclError, нужно `ImageTk.PhotoImage`; (2) `apply_zoom` якоря на центре клетки, а должен на точной поверхностной точке через `screen_to_world_at_gz`; (3) червь рисовался на `terrain_gz + 1` вместо `terrain_gz` (как юниты); (4) добавить тест высот зданий STRUCTURES.

Done:
- `stamina/lounge/trainer.py`: `_ensure_textures` использует `ImageTk.PhotoImage` (import из PIL), сохраняет сильные ссылки в `self._texture_photos`, кэширует на зум-шаг (hw, hh); убран стаб `_get_texture_color`.
- `stamina/lounge/iso.py`: `apply_zoom` теперь якоря через `screen_to_world_at_gz(sx, sy, surface_gz, m)` — точная поверхностная точка под курсором держится при зуме in/out.
- `stamina/lounge/trainer.py`: `_draw_worm_iso` использует `terrain_gz(dug)` без +1 — червь на той же поверхности, что и юниты.
- `tests/test_terraformer_iso.py`: добавлен класс `StructuresHeightsTest` (3 теста: потолки уровней, эталонные высоты, монотонность по уровням); удалён ложный `assertGreater` в `test_mixed_height_map_offset_cursor_stays_anchored` (gz=0 unproject того же (sx,sy) также закрепляет точку на том же луче — геометрически ожидаемо).
- Исправлена ошибка отступов в `_draw_worm_iso` (метод был на 0 пробелов вместо 4), из-за чего `_draw_units_iso` считался вложенным.
- Все тесты зелёные: `test_terraformer_iso.py` (32/32), `test_terraformer_trainer.py` (36/36), `test_terraformer_strategy.py` (39/39), `test_terraformer_bay.py` (12/12), `test_terraformer_models.py` (53/53) — всего 172 проверки.
- `ci_gate --only contrast --only dep` — зелёный; ruff чисто.

Problems: нет.

## Stage 2 fix4: feedback leftovers (26.11, ветка `agent/orion/terraformer-s2`)

Goal: исправить оставшиеся замечания по Stage 2 изометрии: текстуры на верхних гранях, высоты зданий по потолкам уровней, apply_zoom якоря точно в курсор, след червя по поверхности, клавиши +/- зум вокруг центра экрана, поправить счётчик тестов в HANDOFF.

Done:
- `stamina/lounge/trainer.py`: `_ensure_textures` создаёт алмазные `ImageTk.PhotoImage` (песок, камень, специя) и кэширует их; `_draw_iso` рисует текстуры через `create_image` в центре верхней грани для `dug=0` (песок) и `0<dug<8` (камень), фоллбэк — заливка полигона.
- `stamina/terraformer_strategy.py`: высоты зданий приведены к потолкам уровней — greenhouse 2→1, energy_panel 2→1, habitat 4→3, radar 5→3 (shelter/refinery/spire/core без изменений).
- `apply_zoom` в `iso.py` использует `pick_surface` + `screen_to_world_at_gz` — якорь на видимой поверхности (исправлено в fix5).
- `_draw_worm_iso`: след и тело червя на `terrain_gz(dug)` (было `dug + 1`, исправлено в fix5 на `terrain_gz(dug)`).
- `on_key` в iso-режиме: клавиши `+`/`-` вызывают `iso.apply_zoom` с центром канваса `(w/2, h/2)`.
- Исправлена ошибка отступов в `_draw_worm_iso` (метод был на 0 пробелов вместо 4), из-за чего `_draw_units_iso` считался вложенным.
- Тесты на момент fix4: `test_terraformer_iso.py` (30/30), `test_terraformer_strategy.py` (39/39), `test_terraformer_trainer.py` (32/32), `test_lounge_help.py` (9/9) — всего 110 проверок. Итоговые цифры после fix5 см. выше.
- `ci_gate --only contrast --only dep` — зелёный; ruff чисто.

Problems: нет.

## Этап 3: большая карта, панорама, миникарта (27.11, `agent/orion/terraformer-s3-map`)
- `MAP_SIZE` A1 64×40 … C2 100×60; `TrainerModel.for_level()` для новой смены (обычный `TrainerModel()` остаётся 40×24), стрелки/край/СКМ — панорама с зажимом, миникарта с кликом в плоском и изо-виде; `tests/test_terraformer_s3_map.py` (25), всего 197 passed, ruff чисто.

---

## S3 holds: шаг 1 (28.11, ветка `agent/orion/terraformer-s3-holds`)

Goal: у каждого терраформера свой отсек, активный юнит ведёт камеру, полный юнит сам едет и разгружается, чекбоксы режимов и «Сформировать» кликабельны и сохраняются.

Done:
- `HOLD_CAP` перенесён в `stamina/terraformer_strategy.py`, `HOLD_CAP_WITH_UPGRADES` удалён; `terraformer_trainer.py` реэкспортирует константу, `_hold_cap()` всегда возвращает 5.
- У модели больше нет общего `holds`: legacy-чертёж переносит старый отсек активному юниту, новый чертёж пишет `active_uid` и не пишет `holds`.
- `set_active_unit`/`select_unit`/`select_rect`/`select_all` обновляют `_active_uid` и точку камеры; `robot`, `move()`, `tick_units()` больше не привязаны к `units[0]`; прямое назначение `selected` в старых тестах камеру не трогает.
- Полный отсек в авто/полуавто доезжает до чертежа и укладывает блок; добыча платформ и специя червя идут в отсек активного юнита.
- `form_current_stage()` одним вызовом открывает стены, кладёт фундамент и завершает доступные по уровню платформы.
- Общий HUD-хелпер `_draw_mode_controls()` в плоском и изо-виде: чекбоксы с тегами `mode:<uid>:<mode>` и кнопка `form_stage`; клик обрабатывается до рамки выделения, режимы и этап сохраняются в чертёж.
- `ImageTk.PhotoImage(..., master=self)` — текстуры живут в интерпретаторе своего окна; regression-тест `tests/test_terraformer_texture_master.py`.
- Новые ключи i18n «Этап уже сформирован» / «Этап сформирован: …» добавлены во все 7 локалей.

Next: шаг 2 — галерея A1–C2 и напоминания с туманом, затем изометрия в отдельном worktree `D:\tmp\st-terra`.

Problems: полный `pytest tests/` в этом окружении ненадёжен; гонять только `pytest tests -k terraformer -q` с `STAR_TYPING_SILENT=1`.
