# Handoff

Goal: паритет отсека «Иностранные языки» с «Английским»; зелёный CI на master.

Done:
- Снимки в чат Ориона: Ctrl+V работает из любого места экрана (живая линия `Text`
  забирала фокус — теперь `_strip_key` и toplevel-биндинг отдают вставку в сообщение).
  Предварительная редакция: `stamina/shot_editor.py::ShotEditor` — рамка обрезки мышью,
  поворот, «Применить»/«Убрать». Клик по миниатюре над полем ввода открывает редактор,
  ПКМ — просмотр целиком (`compose.ShotTray(on_edit=…)`). Ветка `agent/orion/shots-editor`,
  коммит 78dc866; `tests/test_shot_editor.py` (3) + тест Ctrl+V в `test_orion_strip.py`.
- Карточки слов в языках = английская `Tile`: новый `stamina/languages/ui.py::WordTile`
  (Canvas, чемфер, `#ранг`, `⟳`-оборот с переводом, плашки «часть речи + уровень CEFR»,
  «✓ ЗНАЮ» и «⊞ В ОТСЕКЕ» на лице). `languages/words_page.py::_tile` отдаёт плитку,
  фокус держит `set_focus()`. Ветка `agent/orion/lang-cards`, коммит 29e3e28.
- `tests/test_languages_tile.py` — 8 тестов (данные карточки + смоук Canvas), зелёные.
- i18n не потребовал новых ключей: 2867/2867, ошибок подстановок 0.
- Ранее: i18n 281 ключ (reading_page, vim_trainer, languages/screen) в ru/en/uk/de;
  Ruff по stamina/tools/tests/main.py; ветка `agent/orion/ci-i18n-ruff` — локально зелёная.

Next:
- Язык перевода карточек = язык интерфейса (если не выбран другой): `gloss_lang()` в
  `languages/core/sqlite_vocab.py`, настройка отсека «ЯЗЫК ПЕРЕВОДА» (ui/ru/en/uk/de).
  Ветка `agent/orion/lang-gloss`, коммит dcdbbda, `tests/test_languages_gloss.py` (9).
  Данные: у ES 805k английских глоссов, у DE 350k, у IT и FR — 0 (нужна дозаправка).
- Выбор es/fr/it для интерфейса: 2886 ключей × 3, только машинный перевод + вычитка.
- Показать пилоту плитки в живом корабле (DE/ES/IT/FR), поправить отступы по месту.
- Отдельная задача: потеря первых слов в микрофоне «Английского» (pre-buffer в `english/asr.py`).
- Push + PR в master по обеим веткам; позже — нормальный MT для uk/de.

Decisions: uk/de для новых строк = русский ключ (placeholder-safe), en — MT + fallback.
Плитка языков берёт данные из `WordEntry` (`frequency_rank`, `pos`, `cefr_level`,
перевод — `gloss_lang()`: язык интерфейса или выбранный в настройках отсека), а не из
английского `vocab`; `word_line()` даёт артикль/род.

Problems: нет. `pr_body.md` в корне — чужой untracked, не трогать.
