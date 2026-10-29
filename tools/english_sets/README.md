# Наборы CEFR: сборка из открытых источников

Повторяемая сборка `stamina/english/data/sets/cefr_*.json` (схема 2).

1. `python fetch.py` — разовая вежливая загрузка (User-Agent, пауза 3 с, уже скачанное не качается повторно) в рабочую папку вне репозитория.
2. `python build_cefr.py` — уровни A1, A2, B1.1, B1.2, B2.1, B2.2, C1, C2 (B1/B2 делятся пополам по частоте), темы, до 5 примеров на слово, отчёт `cefr_report.json`.

## Источники — спасибо им

| Источник | Что берём | Лицензия |
|---|---|---|
| CEFR-J Wordlist 1.5 (Tono Laboratory, TUFS) | слова A1–B2, темы | бесплатно, в т.ч. коммерчески, со ссылкой |
| Octanove Vocabulary Profile C1/C2 | слова C1–C2 | CC BY-SA 4.0 |
| Tatoeba (пары EN–RU) | примеры с переводом | CC BY 2.0 FR |
| Wiktionary через Kaikki.org | IPA, значения, перевод, недостающие примеры | CC BY-SA 4.0 |

Ничего не выдумывается: у каждого примера `source` и `license` (у Tatoeba ещё `tatoeba_id` и `url`), перевод помечен `ru_source`, а пробелы — в `gaps` (`ru`, `ipa`, `examples:N/5`, `examples_ru`). Сгенерированные предложения не используются.
