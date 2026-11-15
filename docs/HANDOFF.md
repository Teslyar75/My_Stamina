# HANDOFF

Goal:
- Отсек «ИНОСТРАННЫЕ ЯЗЫКИ» на ветке `agent/orion/multilang-core`. Словари A1 собраны скриптом. Дальше — живые кнопки отсека.

Done:
- `tools/build_lang_vocab_a1.py` сам качает FrequencyWords (CC BY-SA 4.0) и выгрузку Tatoeba deu/spa–rus (CC BY 2.0 FR, автор и номер предложения). Сырьё: `data/vocab_sources/` (в `.gitignore`). Повторный запуск архивы не качает.
- Списки слов: `tools/lang_vocab/a1_de.tsv` (546), `a1_es.tsv` (460). Goethe/Cervantes скриптом не скачать — у них нет открытой выгрузки.
- Готовые словари: `stamina/languages/plugins/de/vocab_a1.json`, `es/vocab_a1.json`. У каждого слова есть русский перевод, ранг и 1–2 примера. У немецких существительных артикль. Подключены в `load_vocab()`.
- `tests/test_languages_vocab.py` и `tests/test_languages_core.py` — зелёные (36).

Next:
- «Наборы»: `_open_set` сейчас `pass`, плюс частотный набор — dataclass, экран разбирает его как кортеж.
- «Миссии»: список есть, ответить и получить XP нельзя.
- «Проверка» и «Склад» — подписи «скоро».

Decisions:
- Примеры короткие (3–12 слов). Немецкие «sein/Sein» и «morgen/Morgen» различаются по регистру, существительное не берётся первым словом фразы.
- Старый отсек `stamina/english` не трогать.

Problems:
- Нет.
