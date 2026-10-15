# Навигация: зоны → подменю → крошки

**Статус:** принято 2026-10-14 · web first (`web_star_typing/`)  
**Десктоп (`stamina/`):** не меняем в этом проходе (правило desktop-parity). После стабилизации web — отдельный порт.

## Цель

Верхний ряд = **зоны**. Внутри зоны — **подменю режимов**. Под ними — **путь-крошки** (клик на любой сегмент + копирование slug для Cursor). Модалки добавляют хвост пути.

## Верхний ряд (зоны)

| # | Зона | slug | По клику |
|---|------|------|----------|
| 1 | Мостик | `bridge` | всегда экран набора (полёт) — «домой» |
| 2 | Английский | `english` | зона EN |
| 3 | Скорочтение | `speed` | зона SR |
| 4 | Отдых | `lounge` | лобби игр |
| 5 | Радиорубка | `radio` | зона радио |
| 6 | Настройки | `settings` | хаб настроек |

**Убраны с верхнего ряда:** Миссии · Свой текст · Бортжурнал → подменю Мостика.

Вход в кабину открывает **Мостик** (полёт).

## Подменю Мостика

| Пункт | Tab id | slug |
|-------|--------|------|
| Миссии | `missions` | `missions` |
| Свой текст | `cargo` | `cargo` |
| Бортжурнал | `log` | `log` |

## Крошки

- Строка под зональным/подменю.
- Клик по сегменту → переход на этот уровень (зона / страница / закрытие модалки).
- ⧉ → буфер **slug-пути**.

### API (`shell/routeStore.ts`)

| Вызов | Кто |
|-------|-----|
| `setDeepRoute` / `setPageRoute` | панель зоны (страница) |
| `setModalStack` | модалка / LibraryPanel |
| `registerGoHandler` | активная панель (клик по deep) |
| `goDeep(slugs)` | PathCrumbs → truncate + `st-crumb-go` |

---

## Полная карта путей (канон)

### Мостик

| UI | slug |
|----|------|
| мостик | `bridge` |
| мостик / миссии | `bridge/missions` |
| мостик / свой текст | `bridge/cargo` |
| мостик / бортжурнал | `bridge/log` |
| мостик / … / разбор полёта | `bridge/…/debrief` |

### Английский

| UI | slug |
|----|------|
| английский / обзор | `english/overview` |
| английский / звёздные карты | `english/sets` |
| английский / сканер | `english/scanner` |
| английский / миссии | `english/practice` |
| английский / проверка систем | `english/review` |
| английский / склад | `english/warehouse` |
| английский / из книги | `english/book` |
| английский / отсеки | `english/lists` |
| английский / журнал | `english/log` |
| английский / настройки | `english/settings` |

### Скорочтение

| UI | slug |
|----|------|
| скорочтение / обзор | `speed/overview` |
| скорочтение / гипердрайв | `speed/reader` |
| скорочтение / книга | `speed/book` |
| скорочтение / тренажёры | `speed/trainers` |
| скорочтение / библиотека | `speed/library` |
| скорочтение / журнал | `speed/journal` |
| скорочтение / настройки | `speed/settings` |

#### Модалки библиотеки (хвост)

| UI | slug suffix |
|----|-------------|
| свободные книги (Gutenberg) | `…/gutenberg` |
| 2 языка (каталог) | `…/bilingual` |
| 2 языка / вручную | `…/bilingual/manual` |
| импорт PDF | `…/pdf` |
| вставить текст | `…/paste` |
| переименовать | `…/rename` |

Примеры: `speed/library/gutenberg`, `speed/library/bilingual/manual`.

### Отдых

| UI | slug |
|----|------|
| отдых / лобби | `lounge/lobby` |
| отдых / лобби / тетрис | `lounge/lobby/tetris` |
| отдых / лобби / змейка | `lounge/lobby/snake` |
| отдых / лобби / арканоид | `lounge/lobby/breakout` |

### Радиорубка

| UI | slug |
|----|------|
| радиорубка / эфир | `radio/air` |
| радиорубка / эфир / мои волны | `radio/air/favs` |
| радиорубка / эфир / поиск | `radio/air/search` |
| радиорубка / приёмник | `radio/rx` |

### Настройки

| UI | slug |
|----|------|
| настройки / системы | `settings/cabin` |
| настройки / ещё | `settings/cabinMore` |
| настройки / скины | `settings/skins` |
| настройки / экипаж | `settings/crew` |

Библиотека и читалка «2 языка» — только в зоне **Скорочтение** (`speed/library`, `speed/reader`), не в общих настройках.

## Клавиатура

- **Ctrl+1…6** — зоны.
- **Backspace** — предыдущее окно.
- **Ctrl+K** — палитра (зоны + missions/cargo/log).

## Чек-лист внедрения

1. [x] Документ + `STATUS.md`
2. [x] `zones` / `routes` / `routeStore` / `PathCrumbs`
3. [x] `App.tsx` зоны + подменю мостика
4. [x] EN + SR deep + goHandler
5. [x] Lounge / Radio / Settings deep
6. [x] Модалки: Gutenberg (+ manual), PDF, paste, rename, debrief
7. [x] Стиль подменю мостика / SR ≈ EN
8. [x] Docker rebuild (tsc OK)
9. [ ] Десктоп-порт — позже
