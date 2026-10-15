# Структура десктопного Star Typing (`stamina/`)

> Карта для паритета веб ↔ десктоп. Веб: `web_star_typing/`.  
> Возможности продукта: [`../CAPABILITIES.md`](../CAPABILITIES.md).  
> **Атлас окон со скринами:** [`SCREEN_ATLAS.md`](./SCREEN_ATLAS.md) ← куда какое окно и как выглядит.  
> UI-очередь: [`UI_DESKTOP_PARITY.md`](./UI_DESKTOP_PARITY.md).

**Цель веба:** повторить экраны, кнопки и связи функций десктопа на другом стеке (React + FastAPI), не ломая `stamina/`.

**Визуал зафиксирован:** эталоны в `screenshots/` + атлас. Пока **не меняем** визуальную часть веба без сверки со скрином.

---

## 0. Быстрые эталоны по экранам

| Экран | Лучший скрин | Детали |
| --- | --- | --- |
| Мостик | [`living_space/bridge_idle.png`](../../screenshots/living_space/bridge_idle.png) | прицел, UPLINK, 3 прибора — атлас §1 |
| Миссии | [`living_space/tab_missions.png`](../../screenshots/living_space/tab_missions.png) | сетка 2×5, ремонт — §2 |
| Свой текст | [`living_space/tab_cargo.png`](../../screenshots/living_space/tab_cargo.png) | обработка, превью — §3 |
| Бортжурнал | [`living_space/tab_log.png`](../../screenshots/living_space/tab_log.png) | 5 карточек, heatmap — §4 |
| Английский | [`living_space/tab_english.png`](../../screenshots/living_space/tab_english.png) | подвкладки `english/tab_*` — §5 |
| Скорочтение | [`living_space/tab_speedread_overview.png`](../../screenshots/living_space/tab_speedread_overview.png) | библиотека / Gutenberg / гипердрайв / настройки — `living_space/tab_speedread_*.png`, `hyperdrive_*.png` — §6–7 |
| Настройки | [`living_space/tab_settings.png`](../../screenshots/living_space/tab_settings.png) | §8 |
| Отдых | [`living_space/tab_lounge.png`](../../screenshots/living_space/tab_lounge.png) | змейка: [`lounge/05_snake_paused.png`](../../screenshots/lounge/05_snake_paused.png) — §9 |
| Радио | [`living_space/tab_radio.png`](../../screenshots/living_space/tab_radio.png) | приёмник: [`radio/02_receiver.png`](../../screenshots/radio/02_receiver.png) — §10 |
| Экипаж | [`pilots/01_login.png`](../../screenshots/pilots/01_login.png) | §11 |

Полные описания + чеклист досъёмки: [`SCREEN_ATLAS.md`](./SCREEN_ATLAS.md).

---

## 1. Точка входа и оболочка

| Файл | Роль |
| --- | --- |
| `stamina/app.py` | `run_app`, выбор пилота, DPI, relaunch |
| `stamina/cockpit.py` | `Cockpit(tk.Tk)` — шапка, нав, `show()`, горячие клавиши, оркестрация |
| `stamina/welcome.py` | Первый запуск / проверка систем |
| `stamina/theme.py` | Палитра, скосы, скины JSON `stamina/themes/` |
| `stamina/storage.py` / `session_storage.py` | Настройки, сессии, прогресс на диске |
| `stamina/pilots.py`, `pilot_screens.py`, `pilot_pin.py`, `avatars.py`, `pilot_migrate.py` | Экипаж, PIN, `.stpilot`, доска почёта |
| `stamina/living_space.py` | Анимированный космос (Pillow) |
| `stamina/sounds.py` + `stamina/sounds/` | Звук клавиш/миссий |
| `stamina/i18n/` | Словари ru/uk/en/de |
| `stamina/keynav.py` | Tab-навигация по HUD |
| `stamina/page_help.py` | F1 / справка по разделу |

### Навбар (`Cockpit.SCREENS`)

База:

1. `bridge` — МОСТИК  
2. `missions` — МИССИИ  
3. `cargo` — СВОЙ ТЕКСТ  
4. `log` — БОРТЖУРНАЛ  
5. `settings` — НАСТРОЙКИ  

Опционально (через hooks, вставляются **перед** settings):

| Hook | KEY | TITLE | Пакет |
| --- | --- | --- | --- |
| `english_hook` | `english` | АНГЛИЙСКИЙ | `stamina/english/` |
| `speedread_hook` | `speedread` | СКОРОЧТЕНИЕ | `stamina/speedread/` |
| `lounge_hook` | `lounge` | ОТДЫХ | `stamina/lounge/` |
| `radio_hook` | `radio` | РАДИОРУБКА | `stamina/radio/` |

Веб-вкладки (`frontend/src/shell/tabs.ts`):  
`bridge | missions | cargo | log | english | speed | lounge | radio | settings`  
(в вебе `speedread` → tab `speed`).

### Горячие клавиши оболочки

| Клавиша | Действие | Где |
| --- | --- | --- |
| Ctrl+1…N | `show(screen)` | `cockpit.py` |
| Ctrl+Shift+P | сменить пилота | `switch_pilot` |
| F1 | справка | `open_help` |
| F5 | перезапуск текущего | `restart_current` → `_last_action` |
| F9 | звук | `toggle_sound` |
| Esc | пауза (на мостике / играх) | экранный handler |

---

## 2. Связи экранов (граф)

```
                    ┌──────────── Cockpit ────────────┐
                    │  show(name)  ·  start_mission     │
                    │  start_repair · start_cargo       │
                    │  get_translator · apply_settings  │
                    └───────┬──────────────────────────┘
        ┌───────────┬───────┼───────┬──────────┬─────────┐
        ▼           ▼       ▼       ▼          ▼         ▼
     Bridge    Missions   Cargo    Log     English*   Speed*
        │           │       │       │          │         │
        │◄─start────┘       │       │          │         │
        │◄─repair───────────┘       │       warehouse  book/RSVP
        │◄─cargo text───────────────┘          │         │
        │                                      └──from book◄┘
        ▼
   TypingEngine + Viewport + HudKeyboard + UPLINK
        │
        └─► sessions / stars / XP / heatmap ──► Log + Honor

* плюс Lounge, Radio (не учебный core)
```

Ключевые оркестрации в `Cockpit`:

- `start_mission(m)` → Bridge + текст миссии  
- `start_repair(lang)` → Bridge + текст слабых клавиш  
- `start_cargo` / `resume_cargo` → Bridge со своим текстом  
- `cargo_process` → обработка текста (регистр/знаки)  
- `get_translator()` → общий UPLINK-переводчик  

---

## 3. Мостик (печать)

| Файл | Роль |
| --- | --- |
| `bridge.py` | `Bridge` — layout приборов, состояние idle/ready/run/pause/done |
| `hud.py` | Viewport (прицел), SpeedGauge, RingGauge, HudKeyboard, TranslatorPanel, debrief |
| `engine.py` | `TypingEngine` — символы, ошибки, CPM, пауза |
| `layouts.py` | Раскладки EN/RU, зоны пальцев |
| `adapt.py` | Генерация «ремонта» по слабым клавишам |
| `missions.py` | Каталог миссий, текст, ★, XP |
| `translator.py` | UPLINK: слово + предложение |
| `text_processing.py` / `textmap.py` | Нормализация / карта текста |

### Layout мостика (десктоп)

```
MissionStrip (прогресс / заголовок)
Viewport (строка + прицел)
TranslatorPanel / UPLINK (слово + перевод)
┌ ДВИГАТЕЛЬ ┐  ┌ НАВИГАЦИЯ ПАЛЬЦЕВ ┐  ┌ ТЕЛЕМЕТРИЯ ┐
│ SpeedGauge│  │ HudKeyboard       │  │ RingGauge  │
│ Rhythm    │  │ Pause·Again·Heat  │  │ Readouts   │
└───────────┘  └───────────────────┘  └────────────┘
```

Колонки: боковые `minsize≈220`, центр `weight=1` (клавиатура шире).

### Прицел и клавиатура (поведение)

- **Прицел:** янтарная двойная рамка, тёмный fill, **белая** буква; при ошибке — красный (`hud.py` Viewport ~597–616).
- **Клавиатура:** подсветка **целевой** клавиши (`HudKeyboard.highlighted` = символ под прицелом) **янтарём/AMBER**. Не «вспышка после успеха», а «куда бить сейчас».
- Зоны пальцев цветные; heatmap — отдельный режим (`toggle_heat`).

Веб: карта кнопок [`BRIDGE_BUTTON_MAP.md`](./BRIDGE_BUTTON_MAP.md).

---

## 4. Миссии / Свой текст / Бортжурнал / Настройки

| Экран | Файл | Главные действия |
| --- | --- | --- |
| Миссии | `screens.py` → `MissionsScreen`, `MissionCard` | EN/RU карта, старт → `app.start_mission`, ремонт → `start_repair`, свой текст снизу |
| Свой текст | `CargoScreen` | файл / буфер / PDF / полка / Gutenberg; опции обработки; старт/продолжить → Bridge |
| Бортжурнал | `LogScreen` | рекорды, график, heatmap по языку, слабые клавиши, сброс |
| Настройки | `SettingsScreen` | звук, зоны, шрифт, космос, скин, glow, язык UI → `apply_settings` |
| Справка | `HelpScreen` + `page_help.py` | F1 по текущему разделу |
| Доска почёта | `pilot_screens` / honor | рейтинг экипажа |

Связанные модули груза/книг:

- `library.py`, `book_shelf.py`, `book_catalog.py`, `bilinguis_catalog.py`
- `pdf_import.py`, `pdf_dialog.py`, `bilingual_dialog.py`, `langdetect.py`

---

## 5. Английский (`stamina/english/`)

| Файл | Роль |
| --- | --- |
| `screen.py` + `ui.py` | Корень вкладки, подстраницы |
| `pages_main.py` | Обзор, уровень, цели |
| `pages_learn.py` | Сканер / учение слова |
| `pages_book.py` | ИЗ КНИГИ |
| `pages_warehouse.py` | Склад карточек |
| `pages_misc.py` | Отсеки, журнал, настройки EN |
| `vocab.py` | 20k + наборы S-* / S-DEV |
| `warehouse.py`, `sm2.py`, `progress.py` | Карточки, SM-2 |
| `tts.py`, `asr.py`, `mic.py`, `textutil.py` | Озвучка, Vosk, % совпадения |
| `tasks.py`, `book_sentences.py` | Миссии говорения, предложения из книги |

Доки: [`../ENGLISH_TAB.md`](../ENGLISH_TAB.md), [`../WAREHOUSE_CARDS.md`](../WAREHOUSE_CARDS.md), [`../IT_INTERVIEW.md`](../IT_INTERVIEW.md).

---

## 6. Скорочтение (`stamina/speedread/`)

| Файл | Роль |
| --- | --- |
| `screen.py`, `ui.py` | Вкладка, режимы |
| `rsvp.py` | Гипердрайв RSVP |
| `book_reader.py` | Читалка 1 стр / разворот / 2 языка / прокрутка |
| `reader.py` | Обвязка читалки |
| `exercises.py` | Шульте, Горбов, пирамида, вспышка |
| `quiz.py` | Проверка понимания |
| `store.py`, `text_norm.py`, `paper_tex.py` | Состояние, нормализация |

Доки: [`../speedread/SPEC.md`](../speedread/SPEC.md), [`../reader/`](../reader/).

Общая позиция текста с печатью/книгой — критично для веба (`sentence_id`, см. `WEB_PLAN.md`).

---

## 7. Отдых и радио

**Lounge** (`stamina/lounge/`): `screen.py` лобби; `tetris.py`, `snake.py`, `breakout.py`; `store.py` рекорды; `base.py` общий HUD игр.

**Radio** (`stamina/radio/`): `screen.py` рубка; `browser.py` radio-browser.info; `player.py` / `engine.py` (mpv); `store.py` избранное; `minibark.py` мини-бар в шапке Cockpit.

---

## 8. Данные и темы

| Путь | Что хранит |
| --- | --- |
| Windows `%APPDATA%\Stamina`, Linux `~/.local/share/StarTyping` | пилоты, прогресс, настройки |
| `stamina/themes/*.json` | скины (spaceship, neon_city, …) |
| `stamina/assets/`, `backgrounds/` | иконки, фоны |
| `stamina/english/data/` | словари / семплы |

Веб-аналог скинов: `web_star_typing/packages/themes/*.json`.

---

## 9. Соответствие веб-папок

| Десктоп | Веб frontend | Веб backend (ориентир) |
| --- | --- | --- |
| `cockpit.py` | `App.tsx`, `shell/` | — |
| `bridge.py` + `hud.py` | `bridge/` | `api_sessions`, translate |
| `missions.py` + MissionsScreen | `missions/`, MissionRail | `missions_service`, `api_missions` |
| CargoScreen + library | `cargo/`, `library/` | `api_texts`, library API |
| LogScreen | `flightlog/` | sessions / key-errors |
| `english/*` | `english/` | `api_english` |
| `speedread/*` | `speedread/`, `reader/` | speedread API |
| `lounge/*` | `lounge/` | lounge scores |
| `radio/*` | `radio/` | radio API |
| `theme.py` / living_space | `theme/`, `fx/` | — |
| pilots | `auth/` | `api_pilots`, migrate |

---

## 10. Как пользоваться этой картой (агент)

1. Открыть [`SCREEN_ATLAS.md`](./SCREEN_ATLAS.md) — найти окно и скрин (навбар игнорировать).  
2. Найти экран в §3–7 или в `SCREENS` / hooks.  
3. Открыть класс экрана → обработчики кнопок → вызовы `app.*` или локальный engine/store.  
4. Портить в веб; UI-правила стекла — `.cursor/rules/web-glass-ui.mdc`. **Не ломать зафиксированный визуал** без нового эталона.  
5. Обновлять [`STATUS.md`](./STATUS.md) / [`PARITY_PLAN.md`](./PARITY_PLAN.md).

---

## 11. Уже есть рядом (не дублировать зря)

| Документ | Зачем |
| --- | --- |
| [`SCREEN_ATLAS.md`](./SCREEN_ATLAS.md) | **все скрины → окна**, пробелы для досъёмки |
| [`CAPABILITIES.md`](../CAPABILITIES.md) | что умеет продукт глазами пилота |
| [`WEB_PLAN.md`](./WEB_PLAN.md) | стек, фазы, узкие места сегментации |
| [`PARITY_PLAN.md`](./PARITY_PLAN.md) | эпики P1–P8 |
| [`UI_DESKTOP_PARITY.md`](./UI_DESKTOP_PARITY.md) | очередь окон по скринам |
| [`BRIDGE_BUTTON_MAP.md`](./BRIDGE_BUTTON_MAP.md) | мостик: кнопка → handler |
| [`SKINS.md`](../skins/SKINS.md) / [`SKINS_DEEP.md`](../skins/SKINS_DEEP.md) | миры/скины |
| Feature docs | english, speedread, radio, living_space, pilots, warehouse |
