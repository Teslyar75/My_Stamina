# Атлас окон десктопа (`screenshots/`)

> **Фиксация визуала.** Этот документ — эталон «как выглядит окно».  
> Пока **не меняем** визуальную часть веба под новые правки вёрстки — сначала сверка со скринами.  
> Верхний ряд вкладок (МОСТИК…НАСТРОЙКИ) на старых кадрах может отличаться — **игнорируем шапку навбара**, смотрим содержимое экрана.

**Код модулей:** [`DESKTOP_STRUCTURE.md`](./DESKTOP_STRUCTURE.md) · **очередь паритета:** [`UI_DESKTOP_PARITY.md`](./UI_DESKTOP_PARITY.md)

**Как читать пути:** от корня репо, например `screenshots/living_space/bridge_idle.png`.

**Если кадра нет** — в таблице стоит `⚠ нужно снять`; пришлите скрин, вставим сюда.

---

## 0. Карта папок `screenshots/`

| Папка / файлы | Что внутри |
| --- | --- |
| `living_space/` | Единый фон «живой космос»: мостик, миссии, груз, журнал, EN, скорость, настройки, login, honor |
| `overview/` | Ранний обзорный ряд основных вкладок |
| `english/` + `warehouse/` + `it-interview/` | Подвкладки английского |
| `speedread/` | Обзор, гипердрайв, тренажёры, библиотека, журнал, F1 |
| `reader/` | Читалка «Книга», темы, Gutenberg, RSVP, bilingual |
| `lounge/` | Лобби + три игры |
| `radio/` | Эфир / приёмник |
| `pilots/` + `quickstart/` | Вход, создание, PIN, доска почёта, welcome |
| Корень (`mission_debrief`, `settings`, `flight_log_heatmap`, i18n…) | Отдельные важные состояния |
| `web_*.png` | Снимки **веба** (не эталон десктопа) |

Ряд `living_space/` — лучший эталон **стекла поверх космоса**. Ряды `overview/` / feature — эталон **содержимого** панелей.

---

## 1. Мостик (печать)

| Состояние | Скрин | Что видно (без навбара) |
| --- | --- | --- |
| Набор / свой текст в полёте | [`living_space/bridge_idle.png`](../../screenshots/living_space/bridge_idle.png) · [`living_space/bridge_typing.png`](../../screenshots/living_space/bridge_typing.png) · [`overview/01_bridge_own_text.png`](../../screenshots/overview/01_bridge_own_text.png) | Заголовок маршрута + прогресс %; **навигационный канал** с прицелом (янтарная рамка, белая буква, треугольники); подсказка пальца; **UPLINK** слово→перевод + предложение; снизу три прибора: **ДВИГАТЕЛЬ** (спидометр + ритм), **НАВИГАЦИЯ ПАЛЬЦЕВ** (зоны + целевая клавиша янтарём + Пауза/Заново/Тепловая карта), **ТЕЛЕМЕТРИЯ** (кольцо точности + время/ошибки/серия/осталось) |
| Ошибка (красный прицел) | [`living_space/bridge_error.png`](../../screenshots/living_space/bridge_error.png) | Прицел **красный**; статус «НАЖАТО «…» — НУЖНО «…»» (+ подсказка раскладки); целевая клавиша на вирт. клавиатуре **красная**; кольцо точности краснеет |
| Пауза | [`living_space/bridge_paused.png`](../../screenshots/living_space/bridge_paused.png) | Оверлей **ПАУЗА** (янтарь, иконка ‖) + «Окно потеряло фокус — полёт на паузе»; UPLINK и приборы видны; целевая клавиша всё ещё янтарём; ПРОДОЛЖИТЬ Esc |
| UPLINK крупно | [`cockpit_uplink_word.png`](../../screenshots/cockpit_uplink_word.png) | Окошко текущего слова под прицелом |
| Отчёт о полёте (миссия) | [`mission_debrief.png`](../../screenshots/mission_debrief.png) · [`overview/02_mission_debrief.png`](../../screenshots/overview/02_mission_debrief.png) | Модалка поверх мостика: ★★★, скорость/точность/ошибки/время/ритм/серия, +XP, частые ошибки, кнопки Повтор / Далее / Ремонт / Закрыть |
| i18n мостик | [`i18n_en_bridge.png`](../../screenshots/i18n_en_bridge.png) · [`typing_uk_bridge.png`](../../screenshots/typing_uk_bridge.png) | Та же компоновка, другой язык UI |
| Heatmap в контексте набора | [`typing_de_heatmap.png`](../../screenshots/typing_de_heatmap.png) | Тепловая окраска клавиш |

**Визуальный эталон стекла/приборов:** `living_space/bridge_*.png`.

---

## 2. Миссии

| Состояние | Скрин | Что видно |
| --- | --- | --- |
| Звёздная карта | [`living_space/tab_missions.png`](../../screenshots/living_space/tab_missions.png) · [`overview/03_missions.png`](../../screenshots/overview/03_missions.png) · [`missions_star_map.png`](../../screenshots/missions_star_map.png) | Заголовок + правила ★/92%; переключатель **ENGLISH QWERTY / РУССКИЙ ЙЦУКЕН**; сетка **2×5** карточек (id, сектор, имя, новые клавиши, цель зн/мин, ★ или «закрыто»); снизу **Ремонт систем** + блок **Свой текст / продолжить** |
| i18n | [`i18n_uk_missions.png`](../../screenshots/i18n_uk_missions.png) | Та же карта, украинский UI |

---

## 3. Свой текст (груз)

| Состояние | Скрин | Что видно |
| --- | --- | --- |
| Подготовка текста | [`living_space/tab_cargo.png`](../../screenshots/living_space/tab_cargo.png) · [`overview/04_own_text.png`](../../screenshots/overview/04_own_text.png) · [`own_text_cargo.png`](../../screenshots/own_text_cargo.png) | Тулбар: **Полка книг** / Свободные книги / Открыть / PDF / Буфер / Очистить / защита / экспорт; слева **ТЕКСТ** (загруженный); справа **обработка** (ВКЛ/ВЫКЛ) + **предпросмотр**; низ: прогресс на борту + Сохранить / Продолжить / Старт с начала |
| PDF preview | [`pdf_import_preview.png`](../../screenshots/pdf_import_preview.png) | Диалог/превью импорта PDF |
| Полка / Gutenberg с «Свой текст» | ⚠ | На тулбаре есть **Полка книг** и **Свободные книги** — нужен кадр самой полки / каталога, если UI отличается от SR-библиотеки |

---

## 4. Бортжурнал

| Состояние | Скрин | Что видно |
| --- | --- | --- |
| Статистика | [`living_space/tab_log.png`](../../screenshots/living_space/tab_log.png) · [`overview/05_flight_log.png`](../../screenshots/overview/05_flight_log.png) | 5 карточек сводки (время, знаки, скорость, точность, звание); график динамики; кнопка **Доска почёта**; снизу **тепловая карта** (EN/RU) + **слабые клавиши** + Ремонт / Сброс |
| Heatmap крупно | [`flight_log_heatmap.png`](../../screenshots/flight_log_heatmap.png) | Клавиатура с % ошибок |

---

## 5. Английский

Подвкладки (внутренняя полоса): Обзор · Звёздные карты · Сканер · Миссии · Проверка систем · Отсеки · Журнал · Настройки · поиск слова.

| Подвкладка | Скрин | Что видно |
| --- | --- | --- |
| Обзор | [`living_space/tab_english.png`](../../screenshots/living_space/tab_english.png) · [`english/tab_01_overview.png`](../../screenshots/english/tab_01_overview.png) · [`overview/06_english.png`](../../screenshots/overview/06_english.png) | Курс на сегодня (кольцо XP, начать / быстрая миссия); телеметрия уровня; сектора S-1000…S-20k; слово дня |
| Звёздные карты | [`english/tab_02_starmaps.png`](../../screenshots/english/tab_02_starmaps.png) | Плитки/поиск слов по частоте |
| Сканер (полный кадр) | [`living_space/tab_english_scanner.png`](../../screenshots/living_space/tab_english_scanner.png) · [`english/tab_03_scanner_full.png`](../../screenshots/english/tab_03_scanner_full.png) | **СКАНЕР ОБЪЕКТА** (слово, частота, POS); **АНАЛИЗ ПРОИЗНОШЕНИЯ** (IPA/слоги); **ДАННЫЕ ОБЪЕКТА** (определение, пример, мой перевод, повтор); низ: **КАНАЛ СВЯЗИ · практика предложений** + микрофон |
| Сканер (произношение) | [`english/tab_03_scanner_match.png`](../../screenshots/english/tab_03_scanner_match.png) | Слово + голос; IPA; данные объекта; канал связи (говорение) + **СОВПАДЕНИЕ %** |
| Сканер (перевод) | [`english/tab_03b_scanner_translation.png`](../../screenshots/english/tab_03b_scanner_translation.png) | Акцент на перевод/данные |
| Миссии EN | [`living_space/tab_english_missions.png`](../../screenshots/living_space/tab_english_missions.png) · [`english/tab_04_missions.png`](../../screenshots/english/tab_04_missions.png) · [`english/tab_04b_mission_task.png`](../../screenshots/english/tab_04b_mission_task.png) | **ПОЛЁТНЫЙ ПЛАН** (источник/отсек/фильтры/длина); 4 карточки: M-RND / M-SPK / M-RDG / M-QST |
| Проверка систем | [`living_space/tab_english_review.png`](../../screenshots/living_space/tab_english_review.png) · [`english/tab_05_review.png`](../../screenshots/english/tab_05_review.png) · [`english/tab_05b_review_answer.png`](../../screenshots/english/tab_05b_review_answer.png) | Карточка SM-2 поверх космоса; слово; **РАСШИФРОВАТЬ Space**; оценка 1–4 после раскрытия |
| Отсеки | [`living_space/tab_english_compartments.png`](../../screenshots/living_space/tab_english_compartments.png) · [`english/tab_06_lists.png`](../../screenshots/english/tab_06_lists.png) | Слева грузовые отсеки (Избранное / Знаю хорошо…); справа содержимое + Проверка / Миссия / Экспорт; пустой отсек — подсказка про ☰ / «В отсек» |
| Из книги | [`living_space/tab_english_from_book.png`](../../screenshots/living_space/tab_english_from_book.png) · [`english/tab_from_book.png`](../../screenshots/english/tab_from_book.png) | Список книг с предложениями из прочитанного; Сформировать / Практика / К повтору; карточка: RU → скажи EN |
| Журнал | [`living_space/tab_english_journal.png`](../../screenshots/living_space/tab_english_journal.png) · [`english/tab_07_log.png`](../../screenshots/english/tab_07_log.png) | Верх: телеметрия / освоение S-* / точность (кольцо); ниже: активность 12 недель + знаки отличия (Первый шаг…) |
| Журнал (самый низ) | [`living_space/tab_english_journal_scrolled.png`](../../screenshots/living_space/tab_english_journal_scrolled.png) · [`english/tab_07_log_scrolled.png`](../../screenshots/english/tab_07_log_scrolled.png) | Доскролл: полная сетка знаков + блок **ОШИБКИ ЗА 7 ДНЕЙ** + Повторить / Карточками |
| Настройки EN | [`english/tab_08_settings.png`](../../screenshots/english/tab_08_settings.png) | Озвучка, микрофон, цели |
| Склад | [`living_space/tab_english_warehouse.png`](../../screenshots/living_space/tab_english_warehouse.png) · [`english/warehouse/01_list_in_work.png`](../../screenshots/english/warehouse/01_list_in_work.png) · [`02_card_practice.png`](../../screenshots/english/warehouse/02_card_practice.png) · [`03_done.png`](../../screenshots/english/warehouse/03_done.png) | Фильтры НА СКЛАДЕ / В РАБОТЕ / ОТРАБОТАНО + ★; список карточек (RU, POS, прогоны); В работу / Открыть; Перемешать список |
| IT Interview | [`english/it-interview/01_overview_sdev.png`](../../screenshots/english/it-interview/01_overview_sdev.png) · [`02_starmaps_sdev.png`](../../screenshots/english/it-interview/02_starmaps_sdev.png) | Набор S-DEV |
| F1 EN | [`english/help_f1_english_chapter.png`](../../screenshots/english/help_f1_english_chapter.png) | Справка раздела |

---

## 6. Скорочтение

Подвкладки: Обзор · Гипердрайв · (Книга) · Тренажёры · Библиотека · Журнал · Настройки.

| Состояние | Скрин | Что видно |
| --- | --- | --- |
| Обзор | [`living_space/tab_speedread_overview.png`](../../screenshots/living_space/tab_speedread_overview.png) · [`living_space/tab_speedread.png`](../../screenshots/living_space/tab_speedread.png) · [`speedread/sr_01_overview.png`](../../screenshots/speedread/sr_01_overview.png) | Текущая книга + прогресс + кнопки Гипердрайв/Книга/Библиотека; график «скорость по сессиям» + цель; тесты/рекорд/серия/XP; сетка **тренажёров обзора** (Шульте/Горбов/Пирамида/Вспышка + 4 «в разработке») |
| Гипердрайв без перевода | [`living_space/hyperdrive_no_tr.png`](../../screenshots/living_space/hyperdrive_no_tr.png) | Режим фокуса: одно слово/кадр (ORP/направляющие), **без** строки перевода; WPM; маршрут; разгон; легенда Пробел/↑↓/←/1–5/±/Enter/Esc |
| Гипердрайв с переводом | [`living_space/hyperdrive_with_tr.png`](../../screenshots/living_space/hyperdrive_with_tr.png) | То же + метка «С ПЕРЕВОДОМ»; под словом **параллельный перевод**; красная буква-фиксация в оригинале |
| Гипердрайв пауза | [`living_space/hyperdrive_paused.png`](../../screenshots/living_space/hyperdrive_paused.png) | Двухколоночный вид: **ОРИГИНАЛ — ПАУЗА** (контекст + стоп на слове с подсветкой) \| **ПЕРЕВОД** контекста; справа панель скорость / настройки полёта / телеметрия; низ: **Продолжить · Пробел**, к началу, Финиш+тест, Книга, Библиотека |
| Гипердрайв (ранний run) | [`speedread/sr_02_hyperdrive_running.png`](../../screenshots/speedread/sr_02_hyperdrive_running.png) | Одно слово + ORP; WPM; прогресс |
| Chunk / пауза (ранние) | [`sr_03_hyperdrive_chunk3.png`](../../screenshots/speedread/sr_03_hyperdrive_chunk3.png) · [`sr_04_hyperdrive_paused.png`](../../screenshots/speedread/sr_04_hyperdrive_paused.png) | Несколько слов в кадре / старая пауза |
| Quiz / debrief | [`sr_05_quiz.png`](../../screenshots/speedread/sr_05_quiz.png) · [`sr_06_debrief.png`](../../screenshots/speedread/sr_06_debrief.png) | Проверка понимания / итог |
| Тренажёры | [`living_space/tab_speedread_trainers.png`](../../screenshots/living_space/tab_speedread_trainers.png) · [`sr_07_trainers.png`](../../screenshots/speedread/sr_07_trainers.png) … [`sr_12_flash.png`](../../screenshots/speedread/sr_12_flash.png) | Сетка 8 плиток: Шульте/Горбов/Пирамида/Вспышка (+ лучший) и 4 «в разработке»; подзаголовок «5–10 мин перед чтением» |
| Шульте (в игре) | [`living_space/tab_speedread_schulte.png`](../../screenshots/living_space/tab_speedread_schulte.png) · [`speedread/sr_08_schulte.png`](../../screenshots/speedread/sr_08_schulte.png) | E-SHL 5×5: слева НАЙДИ + размер/символы; центр сетка + красная точка; справа таймер/рекорд/телеметрия; Заново R · Esc |
| Горбов (в игре) | [`living_space/tab_speedread_gorbov.png`](../../screenshots/living_space/tab_speedread_gorbov.png) · [`speedread/sr_09_gorbov.png`](../../screenshots/speedread/sr_09_gorbov.png) | E-GRB 5×5: чёрные↑ / красные↓ поочерёдно; размер 5×5|7×7; таймер с первого клика; норма ★ |
| Пирамида (в игре) | [`living_space/tab_speedread_pyramid.png`](../../screenshots/living_space/tab_speedread_pyramid.png) · [`speedread/sr_10_pyramid.png`](../../screenshots/speedread/sr_10_pyramid.png) | E-PYR: красная ось; пары букв 6…45 зн.; клик по предельной строке; Новая пирамида R · Esc |
| Библиотека на космосе | [`living_space/tab_speedread_library.png`](../../screenshots/living_space/tab_speedread_library.png) | Слева **ТЕКСТЫ НА БОРТУ**; справа **ПАСПОРТ ТЕКСТА** (теги, знаки/слова, печать закрыта…); кнопки Гипердрайв / Книга / Переименовать / Удалить; ★ Свободные книги + импорт |
| Алерт «Переименовать» | [`living_space/tab_speedread_rename_alert.png`](../../screenshots/living_space/tab_speedread_rename_alert.png) · [`speedread/sr_rename_alert.png`](../../screenshots/speedread/sr_rename_alert.png) | Модалка: Название + Автор; кнопка **СОХРАНИТЬ** (зелёный контур) |
| Свободные книги (модалка поверх библиотеки) | [`living_space/tab_speedread_gutenberg_modal.png`](../../screenshots/living_space/tab_speedread_gutenberg_modal.png) | Алерт/окно Gutenberg поверх списка бортовых текстов: ← Назад, поиск название/автор, языки, Найти / Свободные / По категориям, каталог с обложками, Скачать / К подготовке |
| Свободные книги · 2 языка | [`living_space/tab_speedread_gutenberg_bilingual.png`](../../screenshots/living_space/tab_speedread_gutenberg_bilingual.png) · [`reader/13_gutenberg_bilingual.png`](../../screenshots/reader/13_gutenberg_bilingual.png) | Каталог bilinguis/Gutenberg: ОРИГИНАЛ + ПЕРЕВОД (EN→RU…); ★ Свободные / По категориям; список пар; Скачать 2ЯЗ / Вручную |
| Свободные книги · ★ Свободные (без CEFR) | [`living_space/tab_speedread_gutenberg_free.png`](../../screenshots/living_space/tab_speedread_gutenberg_free.png) · [`reader/12_gutenberg_catalog.png`](../../screenshots/reader/12_gutenberg_catalog.png) | Gutenberg PD: ★ Свободные активна; язык EN; **без** полосы CEFR; каталог с обложками + счётчики |
| Свободные книги · по категориям (CEFR) | [`living_space/tab_speedread_gutenberg_cefr.png`](../../screenshots/living_space/tab_speedread_gutenberg_cefr.png) · [`reader/11_gutenberg_cefr.png`](../../screenshots/reader/11_gutenberg_cefr.png) | То же + **УРОВЕНЬ CEFR** A1–C2; кнопка По категориям активна |
| Настройки скорочтения | [`living_space/tab_speedread_settings.png`](../../screenshots/living_space/tab_speedread_settings.png) | Три блока: **Скорость и разгон**; **Показ и проверка** (кадр, ORP, перевод под словом, тест); **Читалка «Книга»** (шрифт, вид, тема); путь `speedread.json` |
| Библиотека / журнал / F1 (ранние) | [`sr_13_library.png`](../../screenshots/speedread/sr_13_library.png) · [`sr_14_journal.png`](../../screenshots/speedread/sr_14_journal.png) · [`sr_15_settings.png`](../../screenshots/speedread/sr_15_settings.png) · [`sr_16_help_f1.png`](../../screenshots/speedread/sr_16_help_f1.png) | Старые кадры |

---

## 7. Читалка «Книга» (внутри скорочтения)

| Состояние | Скрин | Что видно |
| --- | --- | --- |
| Разворот + сепия (живой космос) | [`living_space/tab_speedread_book_spread_sepia.jpg`](../../screenshots/living_space/tab_speedread_book_spread_sepia.jpg) | Тулбар: **РАЗВОРОТ** + **СЕПИЯ** (янтарь); две страницы сепия-бумаги со сгибом; Сформировать карточки; стр. / ~мин |
| Прокрутка + сепия | [`living_space/tab_speedread_book_scroll_sepia.png`](../../screenshots/living_space/tab_speedread_book_scroll_sepia.png) | **ПРОКРУТКА** + **СЕПИЯ**; одна широкая колонка + скроллбар |
| 2 языка + сепия | [`living_space/tab_speedread_book_bilingual_sepia.jpg`](../../screenshots/living_space/tab_speedread_book_bilingual_sepia.jpg) | **2 ЯЗЫКА** + **СЕПИЯ**; ОРИГИНАЛ — EN \| ПЕРЕВОД — RU; прогресс % |
| Разворот ночь | [`reader/01_spread_night.png`](../../screenshots/reader/01_spread_night.png) | Тулбар: библиотека, ←→, A±, **1 стр / разворот / прокрутка**, темы бумага/ночь/сепия, огл., RSVP, экран; две страницы; прогресс % / стр / время |
| Бумага / сепия / огл. (ранние) | [`02_spread_paper.jpg`](../../screenshots/reader/02_spread_paper.jpg) · [`03_spread_sepia.jpg`](../../screenshots/reader/03_spread_sepia.jpg) · [`04_toc_sepia.jpg`](../../screenshots/reader/04_toc_sepia.jpg) | Темы и оглавление |
| Gutenberg / CEFR | [`05_gutenberg.png`](../../screenshots/reader/05_gutenberg.png) · [`11_gutenberg_cefr.png`](../../screenshots/reader/11_gutenberg_cefr.png) · [`12_gutenberg_catalog.png`](../../screenshots/reader/12_gutenberg_catalog.png) | Каталог свободных книг (+ живой кадр с обложками) |
| Журнал / настройки книги | [`06_journal.png`](../../screenshots/reader/06_journal.png) · [`07_settings_book.png`](../../screenshots/reader/07_settings_book.png) | |
| 2 языка (ранний) | [`08_bilingual_book.png`](../../screenshots/reader/08_bilingual_book.png) | Оригинал \| перевод |
| RSVP + перевод | [`09_rsvp_word_tr.png`](../../screenshots/reader/09_rsvp_word_tr.png) · [`10_rsvp_pause_tr.png`](../../screenshots/reader/10_rsvp_pause_tr.png) | Слово + перевод / пауза |
| Тулбар справа | [`reader/_toolbar_right.png`](../../screenshots/reader/_toolbar_right.png) | Деталь кнопок |

---

## 8. Настройки

| Состояние | Скрин | Что видно |
| --- | --- | --- |
| Бортовые системы | [`living_space/tab_settings.png`](../../screenshots/living_space/tab_settings.png) · [`overview/08_settings.png`](../../screenshots/overview/08_settings.png) · [`settings.png`](../../screenshots/settings.png) | Список: звук F9, громкость I–IV, UPLINK, звёздное поле, **живой космос** выкл/лёгкий/полный, экранная клавиатура, зоны пальцев, размер шрифта, путь данных; внизу легенда хоткеев |
| i18n DE | [`i18n_de_settings.png`](../../screenshots/i18n_de_settings.png) | Немецкий UI настроек |
| Скин / glow (веб-добавления) | — | На **десктопе пока нет**; свечение контура — только веб (`cabinStore` glow Off/Low/Med/High). Скрин десктопа не нужен |

---

## 9. Отдых (lounge)

| Состояние | Скрин | Что видно |
| --- | --- | --- |
| Лобби на космосе | [`living_space/tab_lounge.png`](../../screenshots/living_space/tab_lounge.png) | Заголовок «КОМНАТА ОТДЫХА ЭКИПАЖА»; 3 стеклянных карточки поверх планеты: Тетрис / Змейка / Арканоид (тон, рекорд, превью, ▶ Играть); внизу Esc/R/← В ЛОББИ |
| Лобби (ранний кадр) | [`lounge/01_lobby.png`](../../screenshots/lounge/01_lobby.png) | Те же 3 карточки, без полного living_space-фона |
| Змейка в игре (пауза) | [`lounge/05_snake_paused.png`](../../screenshots/lounge/05_snake_paused.png) | Шапка: название · рекорд/счёт; кнопки Дальше / Заново / ← В ЛОББИ; поле с сеткой, шнур + маяк; оверлей **ПАУЗА**; легенда стрелки/WASD / Esc / R |
| Арканоид (готов к пуску) | [`lounge/06_breakout_ready.png`](../../screenshots/lounge/06_breakout_ready.png) | «АРКАНОИД · ОТРАЖАТЕЛЬ ЩИТА»; Пауза / Заново / В лобби; рекорд/счёт; поле: 6 рядов цветных блоков, щит + шар, «ПРОБЕЛ — ПУСК», 3 жизни; управление ←→ / AD · Пробел · Esc |
| Тетрис (пауза) | [`lounge/07_tetris_paused.png`](../../screenshots/lounge/07_tetris_paused.png) | «ТЕТРИС · СТЫКОВКА БЛОКОВ»; Дальше / Заново / ← В лобби; рекорд/счёт; колодец по центру, УР./линии, оверлей **ПАУЗА**; стрелки · Пробел · Esc |
| Игры (ранние кадры) | [`02_tetris.png`](../../screenshots/lounge/02_tetris.png) · [`03_snake.png`](../../screenshots/lounge/03_snake.png) · [`04_breakout.png`](../../screenshots/lounge/04_breakout.png) | Ранее снятый HUD |

---

## 10. Радиорубка

| Состояние | Скрин | Что видно |
| --- | --- | --- |
| Эфир на космосе | [`living_space/tab_radio.png`](../../screenshots/living_space/tab_radio.png) | Слева **ФИЛЬТРЫ ВОЛН** (поиск, страна/язык/жанр, Искать / Мои волны / Топ эфира); центр **ЧАСТОТЫ** (список станций: имя, мета, ▶, ★); справа просвечивает планета |
| Эфир (ранние кадры) | [`radio/01_air.png`](../../screenshots/radio/01_air.png) · [`radio/04_air_ukrainian.png`](../../screenshots/radio/04_air_ukrainian.png) | Поиск/список, топ, избранное |
| Приёмник (эфир идёт) | [`living_space/tab_radio_receiver_live.png`](../../screenshots/living_space/tab_radio_receiver_live.png) | Подвкладка **ПРИЁМНИК**: станция + «В ЭФИРЕ»; **живой эквалайзер** (столбики колеблются под музыку — не статичная картинка); prev / Пауза / Стоп / next; громкость; duck при наборе; история треков сеанса. Минибар в шапке тоже в эфире |
| Приёмник (ранние кадры) | [`radio/02_receiver.png`](../../screenshots/radio/02_receiver.png) · [`radio/03_receiver_dancewave.png`](../../screenshots/radio/03_receiver_dancewave.png) | Тот же layout; на старых кадрах спектр может быть спокойнее |

---

## 11. Экипаж / вход / welcome

| Состояние | Скрин | Что видно |
| --- | --- | --- |
| Выбор пилота | [`pilots/01_login.png`](../../screenshots/pilots/01_login.png) · [`living_space/login.png`](../../screenshots/living_space/login.png) | Карточки пилотов (эмблема, ранг, XP, статы), «зачислить», Войти / Личное дело / Экспорт / Списать |
| Создание / PIN | [`pilots/02_create_pilot.png`](../../screenshots/pilots/02_create_pilot.png) … [`04_set_pin_first_launch.png`](../../screenshots/pilots/04_set_pin_first_launch.png) · [`12_reset_pin.png`](../../screenshots/pilots/12_reset_pin.png) | |
| Доска почёта | [`pilots/05_honor_board.png`](../../screenshots/pilots/05_honor_board.png) · [`06_honor_board_week.png`](../../screenshots/pilots/06_honor_board_week.png) · [`living_space/tab_honor.png`](../../screenshots/living_space/tab_honor.png) · [`09_board_in_cockpit.png`](../../screenshots/pilots/09_board_in_cockpit.png) | Рейтинг экипажа |
| Шапка пилота / меню | [`07_header_pilot.png`](../../screenshots/pilots/07_header_pilot.png) · [`08_header_menu.png`](../../screenshots/pilots/08_header_menu.png) | Позывной, ранг, XP, выпадающее меню |
| Удаление | [`11_delete_pilot.png`](../../screenshots/pilots/11_delete_pilot.png) | |
| Welcome | [`quickstart/1_welcome.png`](../../screenshots/quickstart/1_welcome.png) · [`welcome_without_pillow.png`](../../screenshots/quickstart/welcome_without_pillow.png) · [`2_create_pilot.png`](../../screenshots/quickstart/2_create_pilot.png) · [`3_bridge.png`](../../screenshots/quickstart/3_bridge.png) | Первый запуск, проверка систем |

---

## 12. Справка и прочее

| Скрин | Назначение |
| --- | --- |
| [`help_manual.png`](../../screenshots/help_manual.png) | Общая инструкция / F1 |
| [`web_browser_now.png`](../../screenshots/web_browser_now.png), [`web_english_*.png`](../../screenshots/web_english_overview.png) | Снимки **веба** для сравнения, не эталон десктопа |

---

## 13. Набор эталонов — закрыт

Съёмка живых окон для атласа **завершена** (мостик, миссии, груз, журнал, EN, скорочтение+читалка+тренажёры, отдых, радио, настройки; модалки Gutenberg / rename; ошибка на мостике).

- [x] Полка «Свой текст»: отдельный кадр не обязателен — тулбар есть на `tab_cargo.png`, каталог свободных книг тот же, что в SR (`tab_speedread_gutenberg_*`)  
- [x] Glow контура — только веб, на десктопе нет  
- Визуальный код веба по-прежнему **заморожен** до явной команды сверки (§14) 

---

## 14. Связь с вебом (не менять визуал сейчас)

| Окно | Веб-компонент (ориентир) | Эталон для сверки |
| --- | --- | --- |
| Мостик | `bridge/BridgeScreen` | `living_space/bridge_*.png` |
| Миссии | `missions/MissionsPanel` | `living_space/tab_missions.png` |
| Груз | `cargo/CargoPanel` | `living_space/tab_cargo.png` |
| Журнал | `flightlog/FlightLogPanel` | `living_space/tab_log.png` |
| Английский | `english/EnglishPanel` | `english/tab_*.png` |
| Скорочтение | `speedread/*` | `speedread/sr_*.png` |
| Читалка | `reader/BilingualReader` | `reader/*` |
| Настройки | `settings/SettingsHub` | `living_space/tab_settings.png` |
| Отдых | `lounge/LoungePanel` | `lounge/*` |
| Радио | `radio/RadioPanel` | `radio/*` |
| Экипаж | `auth/AuthPanel` | `pilots/*` |
