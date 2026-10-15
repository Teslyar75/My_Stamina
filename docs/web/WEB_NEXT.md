# Веб: план действий (контекст агента)

**Статус:** активный backlog · обновлено 2026-10-14  
**Код:** `web_star_typing/` → [Wed_Star_Typing_Version](https://github.com/Teslyar75/Wed_Star_Typing_Version) (`6914f26`+)  
**Эталон:** `screenshots/english/`, `screenshots/living_space/tab_english_*.png`  
**Десктоп:** `stamina/` только читать.

Этот файл — **очередь работ**. При любой задаче по веб-паритету начинать отсюда, не изобретать новый backlog.

---

## Правила (не нарушать)

1. Не откатывать преимущества веба: 6 зон, крошки, один сканер, библиотека только в Скорочтении, 4 карточки каталога, мини-клавиши журнала, duck радио, пауза по фокусу, свечение контура.
2. Микрофон / ASR / VU / MatchReadout / самооценку **не трогать**.
3. Сверять окно со скрином (`SCREEN_ATLAS` / `english/tab_*.png`), не с плоским рядом вкладок десктопа.
4. После кода: pytest/vitest по затронутому; `docker compose up -d --build frontend` при CSS/UI; пуш в web-репо по запросу.

## Вне очереди

- Порт зонной IA на десктоп.
- Подсветка целевой клавиши на мостике.
- Длинный скролл каталога вместо 4 карточек.

---

## Сделано

| # | Что | Коммит / место |
| --- | --- | --- |
| 1 | SQL-страница `GET /api/english/set/{set_id}` | `api_english.py` (`_set_word_query`, `_ordered_set_page`); тест `test_set_page_limit_in_sql` |
| 2 | Плотность звёздных карт 6×4 | denser `.en-starmaps` в `frontend/src/index.css` (сканер не затронут) |

---

## Очередь (делать по порядку)

### 3. Сканер в один кадр ← **следующая**

**Цель:** на низкой высоте stage видны режимы и канал; фон космоса не перекрывает HUD.

| | |
| --- | --- |
| Эталон | `screenshots/english/tab_03_scanner*.png`, living_space `tab_english_scanner.png` |
| Код | `frontend/src/english/ScannerPage.tsx`, CSS `.en-sc*` / `.en-scanner*` в `index.css`, при необходимости `stageFit` / z-index фона в `EnglishPanel` |
| Не трогать | MicTransmit, vosk, MatchReadout, speak |
| Готово когда | Один кадр без вертикального обрезания режимов/канала; фон `z-index` ниже панелей |

**Шаги:** открыть сканер → сравнить со скрином → ужать padding/gap strip и mid-grid → проверить z-index `.skin-backdrop` / `.space-canvas` → Ctrl+F5.

### 4. Плотность остальных окон EN

По одному окну, со скрином. Скролл «Из книги» уже OK — не ломать.

| Окно | Эталон | Файлы |
| --- | --- | --- |
| Миссии | `tab_04_missions` | `MissionsPage.tsx` + CSS |
| Проверка | `tab_05_review` | `ReviewPage.tsx` + Dialog |
| Склад | warehouse | `WarehousePage.tsx` |
| Из книги | from_book | `FromBookPage.tsx` |
| Отсеки | lists | `ListsPage.tsx` |

**Готово когда:** полосы/карточки/футер помещаются как на эталоне; сетки не «растянуты» лишним gap.

### 5. Подписи EN (chrome)

**Цель:** подвкладки ALL CAPS + бейджи `(N)` где есть счётчики.

| | |
| --- | --- |
| Код | `EnglishPanel.tsx`, `en-nav`, i18n `setup.ts` |
| Эталон | верхний ряд EN на любом `tab_english_*.png` |
| Готово когда | все 10 пунктов в одном стиле; числа на due/склад/мискиях где на десктопе |

### 6. F1 — глава «Английский»

**Цель:** в веб-справке (F1 / HelpDrawer) есть раздел про английский.

| | |
| --- | --- |
| Код | `frontend/src/shell/HelpDrawer.tsx` (+ i18n при новых строках) |
| Источник смысла | десктоп help / `ENGLISH_LINK_MAP.md` (кратко: 10 окон, сканер, карты) |
| Готово когда | F1 → видна глава; без портянного копипаста всего десктопа |

### 7. Хвосты библиотеки

После EN. Каталог 4 карточки/вкладку **не** менять на длинный скролл.

| Подзадача | Где |
| --- | --- |
| Пары Gutenberg не только EN↔RU/UK + download pair | `GutenbergModal` / `api_catalog` / bilinguis |
| «＋ ВРУЧНУЮ» в модалке 2ЯЗ | `BilingualManualModal` (API bilingual уже есть) |
| Паспорт: позиция подготовки/набора, attach original, full_source_offer | `LibraryPanel` + library API |
| Превью диапазона страниц PDF | `PdfImportModal` |

---

## Как работать в чате

1. Взять **следующий незакрытый** номер из очереди (сейчас **3**).
2. Прочитать эталон + текущий файл из таблицы задачи.
3. Сделать минимальный diff; не смешивать задачу 3 с 4–7 в одном коммите без запроса.
4. Отметить в этой таблице «сделано» + обновить `STATUS.md` / `ENGLISH_PARITY_GAPS.md`.
5. Пуш в web-репо — только по явной просьбе.

## Связанные docs

- Сверка EN: [ENGLISH_PARITY_GAPS.md](./ENGLISH_PARITY_GAPS.md)
- Статус прода: [STATUS.md](./STATUS.md)
- Связи кнопок EN: [ENGLISH_LINK_MAP.md](./ENGLISH_LINK_MAP.md)
- Зоны IA: [NAV_ZONES.md](./NAV_ZONES.md)
