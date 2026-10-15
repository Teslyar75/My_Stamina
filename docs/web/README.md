# Star Typing — веб-версия (документация)

**Код веб-версии:** отдельный репозиторий  
→ [Teslyar75/Wed_Star_Typing_Version](https://github.com/Teslyar75/Wed_Star_Typing_Version)

Локальная рабочая копия в монорепо: папка `web_star_typing/` (свой `.git`, в `My_Stamina` не коммитится).

## Журнал по дням

**→ [JOURNAL.md](./JOURNAL.md)** — хронология всей проделанной работы (оглавление + ссылки на сессии).

| День | Файл |
| --- | --- |
| 2026-10-15 | [SESSION_2026-10-15.md](./SESSION_2026-10-15.md) |
| 2026-10-14 | [SESSION_2026-10-14.md](./SESSION_2026-10-14.md) |
| 2026-10-13 | [SESSION_2026-10-13.md](./SESSION_2026-10-13.md) |

## Справочники и планы

| Файл | Назначение |
| --- | --- |
| [WEB_PLAN.md](./WEB_PLAN.md) | стек, фазы 0–8, промпты Cursor, узкие места (2 языка, сегментация, UPLINK) |
| [DESKTOP_STRUCTURE.md](./DESKTOP_STRUCTURE.md) | **карта десктопа** `stamina/`: экраны, hooks, связи кнопок/функций |
| [SCREEN_ATLAS.md](./SCREEN_ATLAS.md) | **атлас скринов** `screenshots/`: где какое окно и как выглядит |
| [PARITY_PLAN.md](./PARITY_PLAN.md) | эпики паритета P1–P8 |
| [UI_DESKTOP_PARITY.md](./UI_DESKTOP_PARITY.md) | очередь окон по скринам |
| [BRIDGE_BUTTON_MAP.md](./BRIDGE_BUTTON_MAP.md) | мостик: UI → десктоп → веб |
| [ENGLISH_LINK_MAP.md](./ENGLISH_LINK_MAP.md) | английский: связи 10 окон + раскладка панелей |
| [ENGLISH_PARITY_GAPS.md](./ENGLISH_PARITY_GAPS.md) | **скрин-сверка** web↔desktop: дыры и backlog |
| [WEB_NEXT.md](./WEB_NEXT.md) | **активный план действий** (очередь паритета; контекст агента) |
| [STATUS.md](./STATUS.md) | что уже в веб-проде |
| [NAV_ZONES.md](./NAV_ZONES.md) | зоны / slug / крошки |

## Скины (все версии)

Спека: [docs/skins/SKINS.md](../skins/SKINS.md).  
В веб-репо: `packages/themes/*.json` + `docs/skins/images/`.

## Правила Cursor (монорепо)

| Правило | Когда |
| --- | --- |
| [`.cursor/rules/web-glass-ui.mdc`](../../.cursor/rules/web-glass-ui.mdc) | CSS/TSX веба: стекло, прицел, целевая клавиша янтарём |
| [`.cursor/rules/desktop-parity.mdc`](../../.cursor/rules/desktop-parity.mdc) | любой код в `web_star_typing/`: сначала десктоп + скрин |

## Контекст для агента

При работе над вебом опирайтесь на:

1. **[WEB_NEXT.md](./WEB_NEXT.md)** — что делать дальше (не изобретать новый backlog);
2. [DESKTOP_STRUCTURE.md](./DESKTOP_STRUCTURE.md) + скины + скрин окна;
3. живой код `stamina/` ([My_Stamina](https://github.com/Teslyar75/My_Stamina));
4. `ИНСТРУКЦИЯ.md`, `docs/CAPABILITIES.md` — поведение продукта.
