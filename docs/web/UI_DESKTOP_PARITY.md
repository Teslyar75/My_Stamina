# UI: веб ← десктоп (окно за окном)

> **Зачем (WEB_PLAN):** Python/Tkinter → **TypeScript/React + FastAPI**. Онлайн-версия: **похожа** на пульт, быстрее в сети, свой репо, расширение по окнам.  
> **Эталоны:** [`screenshots/`](../../screenshots/). **Логика кнопок:** `stamina/…`. Скины-миры — [`SKINS_DEEP.md`](../skins/SKINS_DEEP.md).

## Как работаем (фиксировано)

1. Скрин из `screenshots/…`.
2. Анализ десктопа (`stamina/…`): кнопка → метод → эндпоинт / локальная логика.
3. Переписать окно и клиентскую логику на **TypeScript/React** (точная копия). По возможности всё новое UI/engine — **только TS**, не Python.
4. Сверить со скрином.
5. Присоединить handlers к уже существующему **backend** `/api/…` (Python FastAPI остаётся сервером; новые фичи UI — в TS).
6. Следующее окно.

Карта мостика: [`BRIDGE_BUTTON_MAP.md`](./BRIDGE_BUTTON_MAP.md).  
Структура десктопа: [`DESKTOP_STRUCTURE.md`](./DESKTOP_STRUCTURE.md).  
Атлас скринов (визуал зафиксирован): [`SCREEN_ATLAS.md`](./SCREEN_ATLAS.md).  
Стекло/прицел/целевая клавиша: `.cursor/rules/web-glass-ui.mdc`.

## Каталог эталонов (`screenshots/`)

| Окно | Главный эталон | Дополнительно |
| --- | --- | --- |
| Мостик / свой текст | [`overview/01_bridge_own_text.png`](../../screenshots/overview/01_bridge_own_text.png) | [`overview/04_own_text.png`](../../screenshots/overview/04_own_text.png), [`own_text_cargo.png`](../../screenshots/own_text_cargo.png), [`living_space/bridge_typing.png`](../../screenshots/living_space/bridge_typing.png), [`cockpit_uplink_word.png`](../../screenshots/cockpit_uplink_word.png) |
| Миссии | [`overview/03_missions.png`](../../screenshots/overview/03_missions.png) | [`missions_star_map.png`](../../screenshots/missions_star_map.png), [`living_space/tab_missions.png`](../../screenshots/living_space/tab_missions.png), [`mission_debrief.png`](../../screenshots/mission_debrief.png) |
| Бортжурнал | [`overview/05_flight_log.png`](../../screenshots/overview/05_flight_log.png) | [`flight_log_heatmap.png`](../../screenshots/flight_log_heatmap.png), [`living_space/tab_log.png`](../../screenshots/living_space/tab_log.png) |
| Английский | [`overview/06_english.png`](../../screenshots/overview/06_english.png) | [`english/tab_*.png`](../../screenshots/english/), склад, IT-interview |
| Скорочтение | [`speedread/sr_01_overview.png`](../../screenshots/speedread/sr_01_overview.png) | `sr_02`…`sr_16`, [`living_space/tab_speedread.png`](../../screenshots/living_space/tab_speedread.png) |
| Настройки | [`overview/08_settings.png`](../../screenshots/overview/08_settings.png) | [`settings.png`](../../screenshots/settings.png), [`living_space/tab_settings.png`](../../screenshots/living_space/tab_settings.png) |
| Читалка / библиотека | [`reader/01_spread_night.png`](../../screenshots/reader/01_spread_night.png) | Gutenberg, bilingual, RSVP в `reader/` |
| Радио | [`radio/01_air.png`](../../screenshots/radio/01_air.png) | [`radio/02_receiver.png`](../../screenshots/radio/02_receiver.png) |
| Вход / экипаж | [`pilots/01_login.png`](../../screenshots/pilots/01_login.png) | create/pin/honor в `pilots/`, [`quickstart/`](../../screenshots/quickstart/) |
| Кают-компания | [`lounge/01_lobby.png`](../../screenshots/lounge/01_lobby.png) | tetris/snake/breakout |
| Шапка пилота | [`pilots/07_header_pilot.png`](../../screenshots/pilots/07_header_pilot.png) | menu, board in cockpit |

Обзорный ряд living_space (все вкладки на одном фоне): [`screenshots/living_space/`](../../screenshots/living_space/).

## Очередь работ

### Верхний ряд — ЗАМОРОЖЕН (9 окон, основной интерфейс не трогаем)

| # | Окно | Веб | Эталон |
| --- | --- | --- | --- |
| 1 | Мостик | `BridgeScreen` | `living_space/bridge_*.png` |
| 2 | Миссии | `MissionsPanel` | `living_space/tab_missions.png` |
| 3 | Свой текст | `CargoPanel` | `living_space/tab_cargo.png` |
| 4 | Бортжурнал | `FlightLogPanel` | `living_space/tab_log.png` |
| 5 | Английский | `EnglishPanel` | `living_space/tab_english.png` |
| 6 | Скорочтение | `SpeedReadPanel` | `living_space/tab_speedread_*.png` |
| 7 | Отдых | `LoungePanel` | `living_space/tab_lounge.png` |
| 8 | Радиорубка | `RadioPanel` | `living_space/tab_radio*.png` |
| 9 | Настройки | `SettingsHub` | `living_space/tab_settings.png` |

### Зафиксировано отдельно

| Что | Статус |
| --- | --- |
| Миссии → плашка **EN-01 «Стыковка»** → канал набора (пауза, F/J, приборы) | **OK · не трогаем** |

### Другие окна (вне верхнего ряда)

| # | Окно | Веб сейчас | Эталон | Статус |
| --- | --- | --- | --- | --- |
| A | **Вход / экипаж** | `AuthPanel` gate + roster | `pilots/*` | **OK** |
| B | Гипердрайв / книга / тренажёры | `HyperdriveView` + `BookReaderView` + trainers | `hyperdrive_*`, book, trainers | **OK** (4 тренажёра «soon» как на desktop) |
| C | Игры отдыха | Snake MVP | `lounge/05–07_*` | очередь |
| D | Модалки (Gutenberg, debrief, F1) | частично | atlas §6–7, help | очередь |
| — | Тонкости мостика (клавиши) | — | — | отложено |

## Окно 1 — Мостик (цель)

Референс: [`screenshots/overview/01_bridge_own_text.png`](../../screenshots/overview/01_bridge_own_text.png).

```
┌─ STAR TYPING ──── МОСТИК · МИССИИ · СВОЙ ТЕКСТ · … ──── пилот / ранг / XP ─┐
│  СВОЙ ТЕКСТ · ДОСТАВКА ГРУЗА              ПРОГРЕСС МАРШРУТА ████░░  %     │
│  ┌─ НАВИГАЦИОННЫЙ КАНАЛ ───────────────────────────────────────────────┐  │
│  │  крупный текст набора + курсор                                       │  │
│  │  UPLINK // переводчик                                                │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  ┌ ДВИГАТЕЛЬ ┐  ┌ НАВИГАЦИЯ ПАЛЬЦЕВ ┐  ┌ ТЕЛЕМЕТРИЯ ┐                     │
│  └───────────┘  └───────────────────┘  └────────────┘                     │
└─ фон: живой космос на весь экран ─────────────────────────────────────────┘
```

Убрать с первого экрана веба при подгонке: полосу frost/FX, онбординг поверх канала, ленту миссий вместо канала.

Критерий: на широком мониторе — пульт (канал по центру, три прибора снизу), не форма с кнопками сверху.

## Связь

- Функции: [`PARITY_PLAN.md`](./PARITY_PLAN.md) · статус: [`STATUS.md`](./STATUS.md)  
- Скины глубже: [`../skins/SKINS_DEEP.md`](../skins/SKINS_DEEP.md)
