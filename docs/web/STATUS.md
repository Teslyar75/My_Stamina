# Star Typing Web — статус (Excellence / Parity)

Репозиторий: [Teslyar75/Wed_Star_Typing_Version](https://github.com/Teslyar75/Wed_Star_Typing_Version)  
Планы: [WEB_PLAN.md](./WEB_PLAN.md), [PARITY_PLAN.md](./PARITY_PLAN.md), [UI_DESKTOP_PARITY.md](./UI_DESKTOP_PARITY.md) (оболочка ← скрины десктопа)

## Готово

| Эпик | Что в проде |
| --- | --- |
| W0 | Онбординг кабины, адаптив шапки, фокус мостика |
| P1 | Drill-миссии ★★★, ремонт клавиш, heatmap, карта на мостике |
| P2 | Библиотека: паспорт текста, PDF/TXT/вставка, rename/delete, Gutenberg+CEFR+2ЯЗ, позиция |
| P3 | English: отсеки due/inbox/favorite/learned, из книги, ранг/XP |
| P4 | Тахистоскоп (E-TAC), Пирамида (E-PYR), Горбов/Шульте (как desktop), журнал |
| P5 | Аватар, экспорт/импорт `.stpilot`, недавние позывные, logout |
| P6 | Загрузка сэмплов `/sounds/*` + synth fallback |
| P7 | Радио: приёмник prev/next, шкала избранного, duck при наборе, автозапуск last |
| P8 | Кают-компания: Snake MVP (Esc пауза / рестарт) |
| Фазы 0–8 | MVP: набор, читалка, english/vosk, speed, radio, PWA, Caddy |

## UI-паритет (окно за окном)

| Слой | Статус |
| --- | --- |
| **Верхний ряд = зоны** | **IA 2026-10-14** — см. [NAV_ZONES.md](./NAV_ZONES.md) |
| | Мостик · Английский · Скорочтение · Отдых · Радиорубка · Настройки |
| | Миссии · Свой текст · Бортжурнал → **подменю Мостика** |
| | Крошки пути (RU + copy slug) · web first; desktop позже |
| | Основной интерфейс экранов без трюков — паритет контента с десктопом |
| **Миссии → плашка EN-01 «Стыковка» → набор** | **OK** — клик по карточке открывает канал; не трогаем |
| **Другие окна** (вне верхнего ряда) | адаптив кабины (EN/груз/миссии/лог/lounge/settings) · OK |
| Вход / экипаж (`pilots/`) | gate + roster + PIN + honor · OK |
| Гипердрайв (RSVP fullscreen) | OK — полёт (слово+перевод) · пауза (оригинал/перевод/настройки) |
| Библиотека → книга → гипердрайв | OK — полка+паспорт как desktop · удаление · каталог: язык/CEFR/скачивание со статусом · 4 книги на вкладку |
| Тренажёры Шульте/Горбов | OK — НАЙДИ/РЕЖИМ/сетка+точка/ТАЙМЕР/ТЕЛЕМЕТРИЯ |
| Тренажёры Пирамида / Вспышка | OK — E-PYR ось+14 строк · E-TAC прицел+лестница мс |
| Кают-компания игры | OK — GameShell (Змейка/Тетрис/Арканоид) |
| Модалки (Gutenberg, debrief, F1…) | OK — адаптив + F1 «полная инструкция» |
| Bilinguis / 2ЯЗ каталог | OK — модалка как desktop bilingual |
| Тонкости мостика (подсветка клавиш) | отложено |

## Дальше

**План действий (контекст):** [WEB_NEXT.md](./WEB_NEXT.md).  
Сделано: SQL `/set/{id}`, плотность звёздных карт. **Следующее: п.3 сканер в один кадр.**

## Опциональные хвосты

| Тема | Заметка |
| --- | --- |
| P2+ | Bilinguis-каталог — OK |
| P4+ | Разгон WPM — OK (скорость/разгон + показ, last_wpm, паузы на знаках) |

## API (новые маршруты)

- `GET/POST /api/missions/drills*`, `/repair/start`, `/key-errors`
- `GET/PUT /api/library…`, `GET/POST /api/catalog/gutenberg…`
- `GET /api/english/warehouse?bin=`, `POST /move`, `/from-book`, `GET /progress`
- `GET /api/speedread/results?mode=`
- `POST /api/pilots/me/avatar`, `GET /api/pilots/me/export`

## Проверки

```powershell
cd backend; .\.venv\Scripts\python.exe -m pytest -q
cd ../frontend; npm test
```

После изменений — `git push origin master` в web-репо.
