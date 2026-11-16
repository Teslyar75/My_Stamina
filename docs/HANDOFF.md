# Handoff

Goal: паритет отсека «Иностранные языки» с «Английским»; зелёный CI на master.

Done:
- Карточки слов в языках = английская `Tile`: новый `stamina/languages/ui.py::WordTile`
  (Canvas, чемфер, `#ранг`, `⟳`-оборот с переводом, плашки «часть речи + уровень CEFR»,
  «✓ ЗНАЮ» и «⊞ В ОТСЕКЕ» на лице). `languages/words_page.py::_tile` отдаёт плитку,
  фокус держит `set_focus()`. Ветка `agent/orion/lang-cards`, коммит 29e3e28.
- `tests/test_languages_tile.py` — 8 тестов (данные карточки + смоук Canvas), зелёные.
- i18n не потребовал новых ключей: 2867/2867, ошибок подстановок 0.
- Ранее: i18n 281 ключ (reading_page, vim_trainer, languages/screen) в ru/en/uk/de;
  Ruff по stamina/tools/tests/main.py; ветка `agent/orion/ci-i18n-ruff` — локально зелёная.

Next:
- Показать пилоту плитки в живом корабле (DE/ES/IT/FR), поправить отступы по месту.
- Отдельная задача: потеря первых слов в микрофоне «Английского» (pre-buffer в `english/asr.py`).
- Push + PR в master по обеим веткам; позже — нормальный MT для uk/de.

Decisions: uk/de для новых строк = русский ключ (placeholder-safe), en — MT + fallback.
Плитка языков берёт данные из `WordEntry` (`frequency_rank`, `pos`, `cefr_level`,
`translations["ru"]`), а не из английского `vocab`; `word_line()` даёт артикль/род.

Problems: нет. `pr_body.md` в корне — чужой untracked, не трогать.
