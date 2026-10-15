# Star Typing — план паритета десктоп ↔ веб

> **For agentic workers:** выполнять эпик за эпиком (TDD, частые коммиты в `Wed_Star_Typing_Version`). Перед кодом эпика можно развернуть его в детальный task-plan через `writing-plans`.  
> Чеклисты: `- [ ]`.

**Goal:** закрыть пробелы, из‑за которых веб не дублирует основные возможности десктопа (`stamina/`), сохранив уже сделанное (сегменты, UPLINK, PWA, Caddy).

**Architecture:** логику по возможности **импортировать из `stamina/` на бэкенде** (как сейчас vocab/segment); UI — React-экраны в `web_star_typing/frontend`. Общая позиция текста остаётся `textId + sentence_id` (Zustand + API).

**Tech Stack:** FastAPI + SQLAlchemy, React/Vite/TS, Zustand, i18next, Web Audio, Canvas, Playwright.

**Repos:** `web_star_typing/` → GitHub `Teslyar75/Wed_Star_Typing_Version`. Десктоп `stamina/` **не ломать** — только читать/импортировать.

## Global Constraints

- Не регрессировать фазы 0–8 и углубление из `docs/web/WEB_PLAN.md`.
- Каждый эпик: API-тесты pytest + при UI — vitest и/или один Playwright-сценарий.
- i18n: новые строки сразу в `frontend/src/i18n/setup.ts` (ru/uk/en/de).
- Коммиты только в web-репо; пуш после зелёных тестов эпика.
- Lounge — **последний** приоритет (не учебный core).

## Порядок эпиков (зависимость)

```
P1 Миссии+ремонт+heatmap
 → P2 Библиотека/PDF/полка/каталоги
 → P3 Английский глубина
 → P4 Скорочтение тренажёры+журнал
 → P5 Пилоты (аватары/.stpilot/мультипилот)
 → P6 Звук сэмплы
 → P7 Радио Shortwave-глубина
 → P8 Lounge (опционально)
```

**Почему так:** миссии дают смысл набору; библиотека кормит набор/чтение/английский «из книги»; english/speedread опираются на тексты; пилоты/звук/радио — оболочка; lounge — развлечение.

---

## Карта файлов (ориентиры)

| Эпик | Десктоп (источник) | Веб — трогать |
|---|---|---|
| P1 | `stamina/missions.py`, `adapt.py`, `bridge.py`, `hud.py` | `backend/app/api_missions.py`, новый `missions_service.py`; `frontend/src/bridge/`, `typing/` |
| P2 | `library.py`, `pdf_import.py`, `book_catalog.py`, `bilinguis_catalog.py`, `book_shelf.py` | `api_texts.py`, `api_library.py` (новый); `frontend/src/library/` |
| P3 | `stamina/english/*` | `api_english.py`; `frontend/src/english/` |
| P4 | `stamina/speedread/*` | `api_speedread.py`; `frontend/src/speedread/` |
| P5 | `pilots.py`, `avatars.py`, `pilot_migrate.py`, `pilot_screens.py` | `api_pilots.py`, `api_migrate.py`; `frontend/src/auth/` |
| P6 | `stamina/sounds/` | `frontend/src/fx/sounds.ts`, `public/sounds/` |
| P7 | `stamina/radio/*`, `docs/radio/CURSOR_TASK_RADIO.md` | `frontend/src/radio/*`, `api_radio.py` |
| P8 | `stamina/lounge/*` | `frontend/src/lounge/` (новый) |

---

### Эпик P1: Миссии печати, ★★★, ремонт, тепловая карта — ядро ✅

**Проблема:** веб-миссии — заглушка claim/XP; нет генерации уроков, звёзд, ремонта слабых клавиш, heatmap.

**Критерий готовности:** пилот проходит миссию 1 → открывается следующая; за точность/скорость ★/★★/★★★; «Ремонт» генерирует текст из слабых клавиш; тепловая карта ошибок по сессиям.

**Сделано:** `missions_service`, drills start/complete+★, repair, key-errors heatmap, MissionRail + онбординг.

#### Task P1.1 — Порт каталога миссий + генерация текста

**Files:**
- Create: `web_star_typing/backend/app/missions_service.py`
- Modify: `web_star_typing/backend/app/api_missions.py`
- Test: `web_star_typing/backend/tests/test_missions_catalog.py`

**Interfaces:**
- Consumes: `stamina.missions.missions_for`, `generate_mission_text`, `stars_for`, `xp_for` (импорт из монорепо) **или** копия констант, если путь импорта в Docker неудобен
- Produces: `GET /api/missions` → `{id, title, sector, keys, goal_cpm, stars, unlocked, progress}`  
  `POST /api/missions/{id}/start` → `{text, mission_id}`  
  `POST /api/missions/{id}/complete` → `{stars, xp, next_id}`

- [ ] Тест: `missions_for("en")` ≥ 1 миссии; `stars_for(0.99, 250, 200) == 3`
- [ ] Реализовать сервис + эндпоинты
- [ ] Playwright: enroll → start mission → type finish → ★ на доске/в списке

#### Task P1.2 — Слабые клавиши + ремонт

**Files:**
- Modify: `api_sessions.py` (агрегат ошибок по символам)
- Create: `backend/app/key_stats.py`
- Modify: `frontend/src/bridge/BridgeScreen.tsx` — кнопка «Ремонт»
- Test: `tests/test_key_stats.py`

**Interfaces:**
- `GET /api/pilots/me/key-errors` → `[{key, errors, total, rate}]`
- `POST /api/missions/repair/start` → текст из `generate_repair_text`

- [ ] Тест: после сессии с ошибками на `a` ключ `a` в топ-слабых
- [ ] UI: список слабых + старт ремонта на мостике

#### Task P1.3 — Тепловая карта

**Files:**
- Create: `frontend/src/bridge/Heatmap.tsx`
- Modify: `frontend/src/typing/layouts.ts` (уже есть раскладка)
- Test: `frontend/src/bridge/heatmap.test.ts` (окраска по rate)

- [ ] Виртуализация не нужна; клетка клавиши = цвет от зелёного к красному по % ошибок
- [ ] Вкладка/блок в Экипаже или Мостике

**Commit эпика P1:** `feat(missions): catalog, stars, repair, heatmap`

---

### Эпик P2: Библиотека книг (PDF, полка, каталоги, позиции) — ядро ✅

**Проблема:** тексты только через paste/API; нет PDF UI, Gutenberg/bilinguis, единой полки и sync «чтение ↔ печать».

**Критерий:** загрузка PDF → сегменты в БД; полка списка текстов пилота; поиск Gutenberg/bilinguis (прокси API); позиция чтения и набора по одному `sentence_id` (уже есть store — привязать к library item).

**Сделано:** `/api/library` + position debounce, PDF/TXT upload через `stamina.pdf_import`, Gutendex search/import, вкладка Библиотека. Bilinguis — следующий инкремент.

#### Task P2.1 — PDF upload UI + сервер

**Files:**
- Уже есть: `POST /api/texts/upload` — проверить/дожать `stamina.pdf_import`
- Create: `frontend/src/library/LibraryPanel.tsx`, `PdfUpload.tsx`
- Modify: `App.tsx` — вкладка «Библиотека»
- Test: `tests/test_pdf_upload.py` (маленький fixture PDF)

- [ ] UI: выбрать PDF → прогресс → открыть в читалке/на мостике

#### Task P2.2 — Полка пилота + last position

**Files:**
- Create: `backend/app/models_library.py` (`pilot_texts`: pilot_id, text_id, sentence_id, mode)
- Modify: `api_texts.py` / новый `api_library.py`
- Modify: `positionStore.ts` — persist на сервер debounce 1s
- Test: `tests/test_library_position.py`

- [ ] `PUT /api/library/{text_id}/position {sentence_id, mode}`
- [ ] `GET /api/library` — список с прогрессом

#### Task P2.3 — Каталоги Gutenberg / bilinguis

**Files:**
- Create: `backend/app/api_catalog.py` — обёртка над `stamina.book_catalog` / `bilinguis_catalog`
- Create: `frontend/src/library/CatalogPanel.tsx`
- Test: mock HTTP каталога; импорт одной короткой книги в SQLite

- [ ] Поиск → «Скачать в библиотеку» → `TextDoc` + сегменты

**Commit:** `feat(library): pdf, shelf, catalogs, positions`

---

### Эпик P3: Английский — глубина склада и «из книги» — ядро ✅

**Проблема:** один список warehouse + grade; нет отсеков, карточек из прочитанного, рангов/знаков english.

**Критерий:** отсеки (избранное / due / выучено); практика «рус → скажи EN» из сегментов книги; XP/ранг english на `/me`.

**Сделано:** bins due/inbox/favorite/learned, `/from-book`, `/progress` + ранг, UI вкладки отсеков.

#### Task P3.1 — Отсеки склада

**Files:**
- Extend: `api_english.py` — `bins`, `move_word`
- Modify: `EnglishPanel.tsx` → вкладки отсеков
- Port UI copy from `stamina/english/pages_warehouse.py`
- Test: `tests/test_english_bins.py`

#### Task P3.2 — Карточки из книги

**Files:**
- Create: `POST /api/english/from-book {text_id, up_to_sentence_id}`
- Uses: сегменты с переводом + `textutil` score уже в ASR
- Modify: `EnglishPanel` режим «Из книги»
- Test: bilingual text → ≥1 sentence card

#### Task P3.3 — Ранги / знаки english

**Files:**
- Port thresholds from `stamina/english/progress.py`
- `GET /api/english/progress` → xp, rank, badges
- UI бейджи в English + Экипаж

**Commit:** `feat(english): bins, from-book, ranks`

---

### Эпик P4: Скорочтение — тренажёры и журнал — ядро ✅

**Проблема:** только RSVP + Schulte 5×5 + quiz stub.

**Критерий:** E-Pyr (пирамида), тахистоскоп (вспышка), Горбов (опционально 2-й приоритет внутри P4); журнал результатов с фильтром по режиму; настройки WPM/шаг разгона как на десктопе (минимум: start WPM, target, words/frame).

**Сделано:** tachi + E-Pyr + журнал с `?mode=`; Горбов/Шульте (`TableExView`); разгон WPM — настройки есть.

#### Task P4.1 — Тахистоскоп + E-Pyr ✅

**Files:**
- Create: `FlashExView.tsx` + `flashEx.ts`, `PyramidExView.tsx` + `epyr.ts` (паритет `PyramidEx`/`FlashEx`)
- Logic port: `stamina/speedread/exercises.py`
- Test: `epyr.test.ts`, `flashEx.test.ts`

#### Task P4.2 — Журнал + настройки гипердрайва

**Files:**
- Extend: `api_speedread.py` modes + list UI
- Create: `SpeedSettings.tsx` (start/target WPM, ORP on/off)
- Persist settings в `localStorage` + опционально pilot prefs

#### Task P4.3 — Горбов (после P4.1–2) ✅

**Files:** `TableExView.tsx` + `tableEx.ts` — Шульте/Горбов как desktop `SchulteEx` (НАЙДИ / РЕЖИМ / сетка+красная точка / ТАЙМЕР / ТЕЛЕМЕТРИЯ; нормы ×1.7; ошибка +2 с; 5×5|7×7)

**Commit:** `feat(speedread): trainers, journal, settings`

---

### Эпик P5: Пилоты — аватары, личное дело, .stpilot, мультипилот — ядро ✅

**Проблема:** callsign+PIN; нет аватара, карточки пилота, экспорта архива, удобной смены пилота.

**Критерий:** загрузка аватара 256×256; экран «Личное дело»; `GET/POST` export/import `.stpilot` (zip/json совместимый с десктопом по возможности); переключатель пилота без очистки чужих данных (уже JWT isolation — добавить UI switch).

**Сделано:** avatar upload, export `.stpilot.json`, import migrate, recent callsigns + logout.

#### Task P5.1 — Аватар + личное дело

**Files:** `api_pilots.py` avatar blob/URL; `AuthPanel` / `PilotCard.tsx`

#### Task P5.2 — Export/import `.stpilot`

**Files:** align with `stamina/pilot_migrate.py` format; expand `api_migrate.py`

#### Task P5.3 — Мультипилот UI

**Files:** список пилотов на устройстве (local last callsigns) + logout/login flow; e2e два пилота не видят сессии друг друга (уже есть задел)

**Commit:** `feat(pilots): avatar, dossier, stpilot, switcher`

---

### Эпик P6: Звук — сэмплы десктопа — каркас ✅

**Проблема:** только oscillator beeps.

**Критерий:** click / error / finish / UI hover из `stamina/sounds/` (конвертировать в mp3/ogg → `frontend/public/sounds/`); fallback на synth если файла нет; mute сохраняется.

**Сделано:** `sounds.ts` грузит `/sounds/{click,error,finish}.{ogg|mp3|wav}` с synth fallback; папка + README. Файлы сэмплов — добавить когда появятся в десктопе.

#### Task P6.1

**Files:**
- Copy/convert samples → `web_star_typing/frontend/public/sounds/`
- Modify: `fx/sounds.ts` — `AudioBuffer` cache
- Test: mock AudioContext decodeAudioData

**Commit:** `feat(audio): desktop sample pack`

---

### Эпик P7: Радио — глубина Shortwave — ядро ✅

**Проблема:** есть поиск/fav/minibar/ICY; нет шкалы избранного, prev/next, duck при наборе, автозапуск последней станции.

**Источник ТЗ:** `docs/radio/CURSOR_TASK_RADIO.md`

**Сделано:** вкладка Приёмник, prev/next + dial по избранному, duck-on-type на мостике, auto last station, minibar next/prev.

#### Task P7.1 — Приёмник: prev/next по «Мои волны», громкость, last station

#### Task P7.2 — Duck при наборе (опция) + уже есть duck TTS/mic

#### Task P7.3 — UI ближе к ТЗ (эфир / приёмник), без копирования GTK Shortwave

**Commit:** `feat(radio): receiver depth, duck-on-type, last station`

---

### Эпик P8: Lounge (низкий приоритет) — Snake ✅

**Проблема:** snake/tetris/breakout только на десктопе.

**Критерий:** одна вкладка «Кают-компания», одна игра (Snake) MVP → Tetris → Breakout; очки в `pilot` XP опционально.

**Сделано:** вкладка Lounge + Snake (Esc пауза/рестарт, WASD, рекорд). Tetris/Breakout — опционально позже.

**Commit:** `feat(lounge): snake mvp` (и далее)

---

## Вне объёма этого плана

- Переписывание десктопа под веб-архитектуру
- PixiJS/three.js вместо Canvas (достаточно living_space)
- Полный bertalign вместо Gale–Church (уже ≥90% на фикстуре)
- Нативные магазины (iOS/Android) — только PWA

## Метрики прогресса

| Эпик | Оценка (ориентир) | Зависимость |
|---|---|---|
| P1 | 1–1.5 нед | — |
| P2 | 1.5–2 нед | P1 желателен |
| P3 | 1.5 нед | P2 (из книги) |
| P4 | 1 нед | — |
| P5 | 1 нед | — |
| P6 | 2–3 дня | — |
| P7 | 3–5 дней | — |
| P8 | 1 нед | — |

После каждого эпика: обновить таблицу в `docs/web/WEB_PLAN.md` § «Углубление / паритет» и README web.

## Самопроверка покрытия

| Пробел из аудита | Эпик |
|---|---|
| Миссии / ★★★ / ремонт / heatmap | P1 |
| Библиотека / PDF / полка / каталоги / позиции | P2 |
| Английский склад / из книги / ранги | P3 |
| E-Pyr / тахистоскоп / Горбов / журнал / настройки | P4 |
| Аватары / личное дело / .stpilot / мультипилот | P5 |
| Сэмплы звука | P6 |
| Радио глубже Shortwave | P7 |
| Lounge | P8 |

---

## Как запускать

**Plan complete and saved to `docs/web/PARITY_PLAN.md`.**

Два варианта исполнения:

1. **Subagent-Driven** — свежий субагент на задачу, ревью между задачами (рекомендуется для P1→P2).
2. **Inline** — делать эпик в этом чате по `executing-plans`, чекпоинты после каждого Task.

Напиши **«делай P1»** (или номер эпика) / **«subagent P1»** — начну с миссий.
