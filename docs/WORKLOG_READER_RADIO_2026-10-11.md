# Отчёт о работе: читалка «Книга» + радиорубка (11.10.2026)

Проект: **Star Typing** (`Teslyar75/My_Stamina`). Ветка: `feature/radio-cabin` (читалка — также в `feature/reader-readest-layout`).

## Цель

1. Переделать читалку **КНИГА** по задаче [`docs/reader/CURSOR_TASK_READER.md`](reader/CURSOR_TASK_READER.md): сплошной текст без «лесенок» Gutenberg, разворот / прокрутка, понятный HUD, i18n.
2. Добавить отсек **РАДИОРУБКА** по [`docs/radio/CURSOR_TASK_RADIO.md`](radio/CURSOR_TASK_RADIO.md): поиск станций, приёмник, мини-бар, ducking TTS/микрофон.
3. Починить каталог свободных книг Gutenberg после переименования панели.
4. Сделать так, чтобы эфир играл на Windows после `winget install shinchiro.mpv` даже если `mpv` не в PATH.

---

## Что сделано

### Читалка «Книга»

| Было | Стало |
| --- | --- |
| Жёсткие переносы Gutenberg → «лесенка» абзацев | Нормализация текста: склейка `\n` и `слово-\n`, абзац только по `\n\n` |
| Мало текста на странице, пустота снизу | Пагинация по реальной высоте (`font.metrics` / накопление строк) |
| Кнопки «1 / РАЗВ. / D P S» | Подписи **1 СТР / РАЗВОРОТ / ПРОКРУТКА**, темы **БУМАГА / НОЧЬ / СЕПИЯ** |
| Зависание при переносе длинных строк | Кэш `font.measure`, аккуратная вёрстка |
| Пропала вкладка СКОРОЧТЕНИЕ | Исправлена ошибка цвета `blend("#000")` → `#000000` |

Режимы разворота: текст течёт **слева направо** на две колонки; счётчик страниц вида `53–54 / 750`; прогресс и оценка времени внизу.

### Каталог Gutenberg

После рефакторинга импорт `BookSearchDialog` ломал загрузку. Восстановлены обёртки в полке: диалог снова открывается, идёт «Загрузка каталога…», список с обложками и кнопкой «СКАЧАТЬ В БИБЛИОТЕКУ».

### Радиорубка

- Вкладка **РАДИОРУБКА**: **ЭФИР** (фильтры страна/язык/жанр, поиск, топ, ★ мои волны) и **ПРИЁМНИК** (станция, ICY-трек, «В ЭФИРЕ», эквалайзер, громкость, история сеанса).
- Источник: [radio-browser.info](https://www.radio-browser.info).
- Проигрывание: внешний **mpv** (предпочтительно) или **ffplay**, без pip-пакетов.
- Мини-приёмник в шапке при фоновом эфире; приглушение при TTS и микрофоне; опция «приглушать во время набора».
- i18n: ru / uk / en / de; запись в инструкцию пилота (F1) и `install.bat` / `deps.py`.

### mpv на Windows

`winget install -e --id shinchiro.mpv` ставит плеер в `C:\Program Files\MPV Player\mpv.exe`, но часто **не добавляет** его в PATH. Добавлен поиск известных путей (`resolve_mpv` / `MPV_PATH` / `STAMINA_MPV`). После перезапуска в шапке: **приёмник: MPV**.

---

## Описание скриншотов (сессия 11.10.2026)

### Читалка и скорочтение

| Файл | Что на снимке |
| --- | --- |
| [`screenshots/reader/01_spread_night.png`](../screenshots/reader/01_spread_night.png) | **Frankenstein**, режим **РАЗВОРОТ**, тема **НОЧЬ**: две полные колонки сплошного текста, HUD на русском, прогресс `53–54 / 750`. |
| [`screenshots/reader/02_spread_paper.jpg`](../screenshots/reader/02_spread_paper.jpg) | Тот же разворот, тема **БУМАГА** (кремовая «бумага»), страницы `41–42 / 586`. |
| [`screenshots/reader/03_spread_sepia.jpg`](../screenshots/reader/03_spread_sepia.jpg) | Разворот, тема **СЕПИЯ**, страницы `37–38`. |
| [`screenshots/reader/04_toc_sepia.jpg`](../screenshots/reader/04_toc_sepia.jpg) | Оверлей **ОГЛАВЛЕНИЕ** поверх разворота (главы 1–17, кнопка «ПЕРЕЙТИ»). |
| [`screenshots/reader/05_gutenberg.png`](../screenshots/reader/05_gutenberg.png) | Диалог **Свободные книги · Project Gutenberg**: фильтр EN, каталог с обложками, «Загрузка каталога…». |
| [`screenshots/reader/06_journal.png`](../screenshots/reader/06_journal.png) | **ЖУРНАЛ** скорочтения: график скорости vs цель 600, сессии «ЧТЕНИЕ» / «ТРЕНАЖЁР» (1984, Шульте). |
| [`screenshots/reader/07_settings_book.png`](../screenshots/reader/07_settings_book.png) | **НАСТРОЙКИ** скорочтения: блок «ЧИТАЛКА КНИГА» с видом **РАЗВОРОТ** и темой **СЕПИЯ**. |

До/после для задачи читалки: [`docs/reader/our_current.png`](reader/our_current.png) → [`docs/reader/our_after_spread.png`](reader/our_after_spread.png).

### Радиорубка

| Файл | Что на снимке |
| --- | --- |
| [`screenshots/radio/01_air.png`](../screenshots/radio/01_air.png) | **ЭФИР**: фильтры волн, открыт список стран, частоты (Dance Wave!, Techno, Trance…). |
| [`screenshots/radio/02_receiver.png`](../screenshots/radio/02_receiver.png) | **ПРИЁМНИК**: Kiss FM Ukrainian в эфире, ICY-трек, эквалайзер, громкость 70; в шапке **приёмник: MPV**. |
| [`screenshots/radio/03_receiver_dancewave.png`](../screenshots/radio/03_receiver_dancewave.png) | ПРИЁМНИК на Dance Wave!, история треков сеанса, чекбокс приглушения при наборе. |
| [`screenshots/radio/04_air_ukrainian.png`](../screenshots/radio/04_air_ukrainian.png) | ЭФИР с языком **ukrainian**, ~80 станций (Hit FM, Люкс FM, Kiss FM…). |
| [`docs/radio/our_air_before_mpv.png`](radio/our_air_before_mpv.png) | Состояние до фикса PATH: предупреждение «нет mpv/ffplay». |

---

## Обновления документации в репозитории

- **README.md** — скриншоты читалки (разворот/темы/TOC/Gutenberg) и радиорубки (эфир/приёмник); уточнён `winget install shinchiro.mpv`.
- **ИНСТРУКЦИЯ.md** — глава о радиорубке и установка mpv.
- **docs/CAPABILITIES.md** — пункты читалки и радиорубки.
- **docs/reader/**, **docs/radio/** — эталонные «наши» снимки рядом с задачами Cursor.
- **install.bat** / **stamina/deps.py** — предложение установить `shinchiro.mpv`.

---

## Критерий «готово»

- [x] Frankenstein в развороте — сплошной текст без лесенок.
- [x] Вкладка СКОРОЧТЕНИЕ на месте; журнал и настройки читалки видны.
- [x] Gutenberg загружает каталог.
- [x] РАДИОРУБКА в меню; эфир и приёмник; звук через MPV.
- [x] Скриншоты в `docs/radio/`, `docs/reader/`, `screenshots/reader/`, `screenshots/radio/`.
- [x] PR в `master` репозитория Teslyar75/My_Stamina (ветка `feature/radio-cabin`).
