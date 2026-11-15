# Немецкий и испанский: 5 фраз, «знаю», отсек, склад

Пилот утвердил этот план 2026-11-15. Делать. План заново не согласовывать.
Ветка: `agent/orion/multilang-core`. В `master` не сливать. Коммит и push — только если пилот прямо попросил.

Обзор языков уже собран по английскому образцу (карточки секторов, «Курс на сегодня», «Слово дня»). Его не переписывать.

## Нельзя

- Не трогать поведение `stamina/english`: пороги, голос, модель Vosk, плитки.
- Английский в сетке языков по-прежнему открывает `app.show("english")`.
- Сырые выгрузки только в `data/vocab_sources/` (в git не входят). Не коммитить архивы Tatoeba и jsonl.
- Фразы не генерировать и не брать из словаря «на лету».
- Не менять общие ключи ВЫБРАТЬ / WÄHLEN / PICK / ВИБРАТИ и английское «{0} out of {1}».
- Новые строки интерфейса — во все четыре файла `stamina/i18n/{ru,uk,en,de}.json`, ключ — русская фраза. Не перезаписывать файл целиком.
- Не трогать `%APPDATA%\Stamina`, кроме кода, который и так пишет прогресс пилота.
- `git reset --hard`, force-push, `git clean` — нельзя.
- Перед рискованной правкой: `powershell -ExecutionPolicy Bypass -File tools\snapshot.ps1`.

## 1. Пять фраз с русским

Как у английского A1: до 5 пар «фраза + русский», источник Tatoeba, CC BY 2.0 FR.

Сейчас:

- `stamina/languages/plugins/de/vocab_a1.json` — 546 слов, почти у всех по 2 примера.
- `stamina/languages/plugins/es/vocab_a1.json` — 460 слов, так же по 2.
- Поля примера: `id`, `text`, `translation`, `source`, `cefr_level`, `word_slugs`.
- Сборщик: `tools/build_lang_vocab_a1.py`. Потолок в `collect_examples`: `del bucket[2:]`. Поднять до 5.
- Уже записанные две фразы оставить. Добавить ещё до трёх других фраз с тем же словом и русским переводом, без повторов текста.
- Запуск из корня: `python tools/build_lang_vocab_a1.py`. Повторно архивы не качает, если они уже лежат.
- В sqlite Kaikki колонка `example` — одна строка, это не замена пяти фраз. Учебные примеры A1 важнее.

Английский образец, только смотреть:

- `stamina/english/data/sets/cefr_a1.json` — у 1056 из 1063 слов ровно 5 фраз. Поля `en`, `ru`, `source`, `license`, `tatoeba_id`, `url`.
- `stamina/english/cefr.py`: `MAX_SENTENCES = 5`.
- Сканер читает `stamina/english/vocab.py`, метод `sentences()`.

Сканер немецкого и испанского уже листает примеры сам: `stamina/languages/scanner.py`, `on_speech`, `advance_later`. Порог `stamina/english/speech_std.py`: `ITEM_OK = 80`, пауза `ADVANCE_MS = 900`. Числа не менять. Когда фраз станет пять, канал заработает сам.

## 2. «Знаю» и «В отсек»

Образец:

- Плитка: `stamina/english/ui.py`, класс `Tile`. Кнопки «знаю» и «В отсек».
- Меню отсеков: `stamina/english/screen.py`, `list_menu`, `_toggle_list`, `_new_list`.
- Данные: `stamina/english/progress.py` — `set_known`, `create_list`, `toggle_in_list`, `lists_of`.

В языках флаг уже есть: `stamina/languages/core/progress.py`, `is_known` / `set_known`. Список `data["lists"]` в файле прогресса заведён, методов меню нет. Добавить те же операции и повесить «✓ ЗНАЮ» и «⊞ В ОТСЕК» на плитку `stamina/languages/words_page.py` и на сканер `stamina/languages/scanner.py`.

Отдельной кнопки «хорошо знаю» в английском нет. «Выучено» — карточка SM-2 с интервалом от 21 дня (`is_learned`).

## 3. Склад повторов

Образец: `stamina/english/quality.py` и `stamina/english/warehouse.py`, экран `stamina/english/pages_warehouse.py`.

- На склад попадает слово «знаю» или выученное, у которого есть фразы.
- Цель: 5, 10, 15 или 20 (`GOAL_CHOICES`, по умолчанию 20). В языковом прогрессе поле `quality_goal` уже есть.
- Блок чтения — фразы вслух, до двух зачётов на фразу.
- В день не больше 4 зачётов одной карточки (`DAILY_CAP`).
- Зачёт одной попытки — те же 80%. Следующая фраза — через 900 мс.
- Вкладка «СКЛАД» в `stamina/languages/screen.py` сейчас заглушка. Собрать её по английскому экрану, тексты фраз брать из примеров слова, не из английского `vocab.json`.

## Проверка

- `python -m py_compile` по затронутым файлам.
- `python -m pytest tests/test_languages_sqlite.py tests/test_languages_vocab.py tests/test_languages_speech.py -q`
- На одном немецком и одном испанском слове: 5 фраз, у новых есть русский, старые две на месте.
- Кнопки «знаю» и «в отсек» пишут `lang_de.json` / `lang_es.json` пилота и не пишут английский прогресс.
- После правки обновить `docs/HANDOFF.md` (короче 60 строк).

## Уже сделано в рабочей копии, не откатывать

- Сетка наборов A1–C2, 24 плитки, сканер, русский перевод по лемме, озвучка edge-tts (`de-DE-KatjaNeural`, `es-ES-ElviraNeural`), отдельные модели Vosk в `models/lang/`.
- Обзор: короткие карточки уровней, «Курс на сегодня» (занятие и быстрая миссия на 10), «Слово дня» с голосом и кнопкой «Сканировать».
- В git это ещё не отправлено. Последний коммит ветки: `99282da`.
