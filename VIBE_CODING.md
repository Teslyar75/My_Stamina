# Промпты для вайбкодинга Star Typing

Набор **готовых промптов** для Cursor / другого AI-агента: от пустой папки до
полного «пульта пилота». Каждый промпт самодостаточен — его можно вставить
в чат как есть. Ссылки ведут на **эталонную реализацию** в этом репозитории.

| Документ | Зачем |
| --- | --- |
| [README.md](README.md) | обзор продукта, скриншоты, горячие клавиши |
| [ИНСТРУКЦИЯ.md](ИНСТРУКЦИЯ.md) | пользовательская справка (открывается по F1) |
| [CURSOR_TASK.md](CURSOR_TASK.md) | техзадание и ограничения для агента |
| [CHANGELOG.md](CHANGELOG.md) | что менялось по версиям |

---

## Как пользоваться

1. **Идите по этапам по порядку.** Не просите «сделай всё сразу» — вайбкодинг
   лучше работает короткими итерациями с проверкой.
2. **После каждого этапа** запускайте:
   ```powershell
   python main.py
   python -m unittest discover -s tests -v
   ```
3. **Не переименовывайте** `main.py`, пакет `stamina/`, путь данных
   `%APPDATA%\Stamina` — иначе сломается ярлык и прогресс.
4. **Стек:** только стандартная библиотека Python 3.10+ (`tkinter`, `Canvas`,
   `winsound`, `urllib`, `threading`). Без PyQt, CustomTkinter, pygame и т.п.
5. Если агент «уплыл» — вставьте блок **«Системный контекст»** ниже и
   повторите текущий этап.

---

## Системный контекст (вставлять в начало сессии)

```text
Ты пишешь настольный тренажёр слепой печати Star Typing (Python 3.10+, только stdlib + tkinter).

Ограничения:
- точка входа: main.py → stamina.app.run_app() (имя не менять)
- пакет: stamina/
- данные пользователя: %APPDATA%\Stamina\ (Linux: ~/.stamina)
- session.json формат: {text, index, typed, errors, elapsed} — прогресс нельзя терять
- UI в стиле «пульт космического корабля»: тёмный космос #03060C, неон циан #00E5FF, янтарь #FFB000
- без внешних pip-зависимостей

Архитектура (эталон в репо):
- stamina/engine.py — логика набора без UI
- stamina/cockpit.py — главное окно и навигация
- stamina/bridge.py — экран тренировки
- stamina/screens.py — миссии, свой текст, журнал, настройки, справка
- stamina/hud.py — Canvas-виджеты
- stamina/text_processing.py — адаптация текста
- stamina/missions.py — миссии и XP
- stamina/translator.py — UPLINK переводчик
- stamina/sounds.py — синтез WAV
- stamina/storage.py / session_storage.py — сохранение

Правила ответа: пиши код сразу, не раздувай рефакторинг без просьбы, после изменений
запускай тесты. Отвечай на русском.
```

---

## Карта этапов

| # | Этап | Эталон в репо |
| --- | --- | --- |
| 0 | Каркас проекта | [main.py](main.py), [stamina/app.py](stamina/app.py), [stamina/__init__.py](stamina/__init__.py) |
| 1 | Адаптация текста | [stamina/text_processing.py](stamina/text_processing.py), [tests/test_text_processing.py](tests/test_text_processing.py) |
| 2 | Движок набора | [stamina/engine.py](stamina/engine.py), [tests/test_engine.py](tests/test_engine.py) |
| 3 | Тема и HUD-база | [stamina/theme.py](stamina/theme.py), [stamina/hud.py](stamina/hud.py) |
| 4 | Мостик MVP | [stamina/bridge.py](stamina/bridge.py), [stamina/layouts.py](stamina/layouts.py) |
| 5 | Сохранение сессии | [stamina/session_storage.py](stamina/session_storage.py), [stamina/storage.py](stamina/storage.py) |
| 6 | Свой текст (груз) | [stamina/screens.py](stamina/screens.py) (`CargoScreen`) |
| 7 | Миссии и звания | [stamina/missions.py](stamina/missions.py) |
| 8 | Бортжурнал | [stamina/screens.py](stamina/screens.py) (`LogScreen`) |
| 9 | Звук | [stamina/sounds.py](stamina/sounds.py) |
| 10 | Переводчик UPLINK | [stamina/translator.py](stamina/translator.py) |
| 11 | Пульт целиком | [stamina/cockpit.py](stamina/cockpit.py) |
| 12 | Полировка и ярлык | [Stamina.bat](Stamina.bat), [create_shortcut.ps1](create_shortcut.ps1) |

---

## Этап 0 — Каркас

```text
Создай каркас приложения Star Typing на Python 3.10+ (только stdlib).

Структура:
  main.py                 # if __name__ → run_app()
  stamina/__init__.py     # APP_NAME = "Star Typing", __version__
  stamina/app.py          # run_app(): DPI-awareness на Windows, затем окно
  requirements.txt        # пустой / комментарий «только stdlib»
  .gitignore              # __pycache__, .venv, cache/, *.pyc

В app.py на Windows:
- SetProcessDpiAwareness(1) или SetProcessDPIAware
- SetCurrentProcessExplicitAppUserModelID("Teslyar75.StarTyping")

Пока окно — пустой tk.Tk с тёмным фоном #03060C и заголовком "Star Typing".
Не добавляй сторонние пакеты.
```

---

## Этап 1 — Адаптация текста (+ тесты)

```text
Реализуй stamina/text_processing.py и тесты tests/test_text_processing.py.

Нужны функции:
- normalize_spaces(text) — любые whitespace → один пробел, trim краёв
- remove_punctuation(text) — убрать ASCII punctuation + «»„“—–…№ и т.п.; буквы/цифры/пробелы оставить
- to_lowercase(text) — .lower() (кириллица и Ё)
- adapt_for_typing(text) = normalize_spaces(to_lowercase(remove_punctuation(text)))
- is_valid_practice_text(text) — True, если после adapt есть непустой текст
- process_text(text, *, lower, strip_punct, one_space) — три независимых флага (для UI)

Тесты (unittest):
- "  Hello,   World!  " → "hello world"
- «Привет,   мир!» → "привет мир"
- пустая строка и только знаки → невалидно
- флаги process_text по отдельности

Не пиши UI. Только чистые функции.
```

Эталон: [stamina/text_processing.py](stamina/text_processing.py).

---

## Этап 2 — Движок набора (без UI)

```text
Реализуй stamina/engine.py — чистую логику сессии TypingEngine без tkinter.

API:
- __init__(text, index=0, typed=0, errors=0, elapsed=0.0, case_sensitive=False)
- current, finished, progress, started
- press(char, now) → "ok" | "error" | "done" | None
- pause(now) / resume()
- elapsed(now), cpm(now), instant_cpm(), accuracy, rhythm
- segment(now) → dict для журнала
- key_stats: dict[str, [ok, err]]

Правила времени:
- таймер начинает тикать с первого press
- интервал между нажатиями > IDLE_CAP=4.0 сек не засчитывается (min(dt, IDLE_CAP))
- на паузе время не растёт
- CPM = правильно_набранные (index) * 60 / elapsed  (ошибки НЕ увеличивают CPM)
- instant_cpm — по последним ~25 интервалам
- rhythm 0–100 по коэффициенту вариации последних ~30 интервалов

Тесты в tests/test_engine.py: верный/неверный ввод, пауза, idle cap, CPM без ошибок.
Сверься с эталоном stamina/engine.py.
```

---

## Этап 3 — Тема и HUD-примитивы

```text
Сделай визуальную базу «космический пульт»:

stamina/theme.py:
- цвета: BG=#03060C, PANEL=#081221, LINE=#15314D, CYAN=#00E5FF, AMBER=#FFB000,
  RED=#FF3B5C, GREEN=#3DFF8A, TEXT=#D6F4FF, MUTED=#6F90AB
- px(n) — масштаб под DPI
- font(size, bold=False, mono=False) — Bahnschrift / Segoe UI; mono → Cascadia Mono / Consolas
- blend(c1, c2, t) — смешение hex-цветов (для «свечения» без прозрачности)

stamina/hud.py (минимум):
- HudButton(parent, text, command, ...) — кнопка на Canvas со срезанными углами
- Panel(parent, title=...) — рамка с уголками-акцентами
Пока можно заглушки остальных приборов.

Покажи в тестовом окне 2–3 кнопки и одну панель. Без логики набора.
```

Эталон: [stamina/theme.py](stamina/theme.py), [stamina/hud.py](stamina/hud.py).

---

## Этап 4 — Мостик MVP (набор + клавиатура)

```text
Собери экран тренировки stamina/bridge.py и раскладки stamina/layouts.py.

layouts.py:
- QWERTY (EN) и ЙЦУКЕН (RU), зоны пальцев (цвета), lookup символа → клавиша
- подписи EN/RU на клавишах

bridge.py (внутри главного окна):
1) «Иллюминатор» — Canvas-строка набора:
   - граница/прицел ФИКСИРОВАН в центре
   - текст смещается; набранное слева тусклее, текущий символ в янтарной рамке
   - пробелы только между словами (не между буквами)
2) Подсветка следующей клавиши янтарём/красным на виртуальной клавиатуре
3) Подключить TypingEngine: KeyPress → engine.press → обновление UI
4) Esc — пауза/продолжить (без диалога «закрыть программу»)
5) Простая статистика: время, CPM, ошибки

Пока можно без миссий, переводчика и спидометра-дуги — только рабочий набор.
Эталон идей: stamina/bridge.py, stamina/hud.py (Illuminator / Keyboard).
```

---

## Этап 5 — Сохранение сессии и настроек

```text
Добавь персистентность.

stamina/session_storage.py:
- путь: %APPDATA%/Stamina/session.json (или ~/.stamina)
- SessionState: text, index, typed, errors, elapsed
- save_session / load_session / clear_session
- атомарная запись через *.tmp + replace
- при старте, если сессия незавершена — спросить «Продолжить?»

stamina/storage.py:
- settings.json, stats.json, cargo.txt, cargo_original.txt
- Store с загрузкой/сохранением настроек и истории заходов
- НЕ меняй формат session.json (совместимость со старыми данными)

Автосохранение во время набора — не чаще раза в ~3 секунды.
При завершении текста — clear_session().
```

Эталон: [stamina/session_storage.py](stamina/session_storage.py), [stamina/storage.py](stamina/storage.py).

---

## Этап 6 — Свой текст (грузовой отсек)

```text
В stamina/screens.py сделай CargoScreen — подготовку пользовательского текста.

UI:
- большое поле текста (ScrolledText)
- Открыть файл… (utf-8 / cp1251 fallback), Вставить из буфера, Очистить, Экспорт .txt
- три независимых переключателя: убрать заглавные / убрать пунктуацию / один пробел
- кнопка «Применить к тексту в поле»
- живой предпросмотр (process_text + длина + язык)
- «Сохранить на борт» — в cargo + session, без автостарта
- «На борт и старт» — сохранить и перейти на Мостик, начать с начала
- «Продолжить с N%» — если есть сохранённый прогресс
- флажок «Защита от правки» (readonly)

Оригинал текста сохраняй отдельно (cargo_original.txt) — он нужен переводчику позже.
Не ломай прогресс session.json.
```

Эталон: `CargoScreen` в [stamina/screens.py](stamina/screens.py).

---

## Этап 7 — Миссии, звёзды, звания

```text
Реализуй stamina/missions.py и экран MissionsScreen.

- 10 английских + 10 русских миссий: домашний ряд → верхний → нижний → буквы → цифры
- генерация упражнений из словарей WORDS_EN / WORDS_RU по разрешённым клавишам
- звёзды: ★ при accuracy≥92%; ★★ при ≥95% и CPM≥цели; ★★★ при ≥98% и CPM≥цель*1.25
- пройденная миссия открывает следующую
- XP и звания: Кадет → … → Адмирал флота
- «Ремонт систем»: упражнение из слов со слабыми клавишами (по stats.key_errors)

UI: звёздная карта / список миссий, кнопка старта, отчёт после полёта
(Enter — повторить, → — следующая, R — ремонт).
```

Эталон: [stamina/missions.py](stamina/missions.py).

---

## Этап 8 — Бортжурнал

```text
Сделай LogScreen в stamina/screens.py:

- сводка: время в полёте, рекорды CPM/точности, XP, звание
- график последних 30 заходов (скорость + точность) на Canvas
- тепловая карта ошибок по клавишам
- список слабых клавиш

Данные бери из Store/stats.json. Не блокируй UI тяжёлыми вычислениями.
```

---

## Этап 9 — Звук

```text
Реализуй stamina/sounds.py:

- синтезируй WAV в stamina/sounds/ (click1..3, error, bell, start) × 4 версии громкости
- SoundBoard: play_ok / play_error / play_done / play_start
- воспроизведение: winsound.PlaySound(..., SND_FILENAME|SND_ASYNC) на Windows
- громкость 0–3, mute, F9 переключает
- верная клавиша → щелчок (ротация вариантов), ошибка → «бззт», конец → колокольчик

Звук включён по умолчанию. Без внешних аудиофайлов из интернета.
```

Эталон: [stamina/sounds.py](stamina/sounds.py).

---

## Этап 10 — Переводчик UPLINK

```text
Реализуй stamina/translator.py:

- разбиение на предложения по ОРИГИНАЛУ (с пунктуацией); если оригинала нет — куски ~14 слов
- фоновый поток + queue: UI никогда не ждёт сеть
- провайдеры: Google translate_a/single?client=gtx, fallback MyMemory
- кэш cache/translations.json (рядом с программой)
- состояние «НЕТ СВЯЗИ», повтор раз в ~20 с
- EN→RU для английского текста, RU→EN для русского
- предзагрузка следующего предложения

На Мостике панель «UPLINK // ПЕРЕВОДЧИК» показывает перевод текущего предложения
только для режима «свой текст». В настройках — выключатель.
```

Эталон: [stamina/translator.py](stamina/translator.py).

---

## Этап 11 — Полный пульт (Cockpit)

```text
Собери stamina/cockpit.py — главное окно:

Разделы (Ctrl+1…5):
1 МОСТИК (Bridge)
2 МИССИИ
3 СВОЙ ТЕКСТ
4 БОРТЖУРНАЛ
5 НАСТРОЙКИ
+ справка F1 (HelpScreen с текстом из ИНСТРУКЦИЯ.md)

Верхняя панель: логотип, навигация HudButton, ранг, звук, часы, F1.
Нижний статус: «ВСЕ СИСТЕМЫ В НОРМЕ» + подсказки клавиш.

Поведение:
- F5 — перезапуск текущего упражнения
- F9 — звук
- Esc — пауза на мостике
- FocusOut / уход в другой раздел → автопауза
- geometry сохраняется в settings
- при старте: resume session или открыть грузовой отсек

Не ломай DPI, иконку на панели задач, имена main.py / stamina /.
```

Эталон: [stamina/cockpit.py](stamina/cockpit.py).

---

## Этап 12 — Полировка UX и ярлык

```text
Доведи продукт до «можно раздавать»:

1) Приборы на мостике: спидометр (дуга + стрелка + цель миссии), кольцо точности,
   шкала ритма, телеметрия (время/ошибки/серия/осталось), звёзды в иллюминаторе
   (~30 fps, скорость от instant_cpm, можно выключить).
2) Подсказка пальца под иллюминатором; тепловая карта на клавиатуре.
3) Stamina.bat — запуск через pythonw без консоли.
4) create_shortcut.ps1 — ярлык «Star Typing» на рабочем столе с иконкой
   stamina/assets/star_typing.ico.
5) README со скриншотами и ИНСТРУКЦИЯ.md для F1.
6) Все тесты зелёные: python -m unittest discover -s tests -v

Не переименовывай репозиторий / AppData-папку Stamina.
```

---

## Промпты на исправление типичных багов

### CPM завышен

```text
В TypingEngine / UI CPM считается неправильно: растёт от ошибок.
Исправь: CPM = (число правильно набранных символов / elapsed_seconds) * 60.
Ошибочные нажатия увеличивают только errors и typed, но не числитель CPM.
Добавь/обнови тест. Эталон: stamina/engine.py → cpm().
```

### Текст «прыгает», граница не в центре

```text
В иллюминаторе граница «набрано/осталось» должна быть ФИКСИРОВАНА в центре Canvas.
Текст смещается так, чтобы text[index] всегда стоял у центральной линии.
Не рисуй подчёркивание под буквой. Используй моноширинный шрифт.
```

### Печать «ничего не делает»

```text
После сохранения текста тренировка не стартует / окно не в фокусе / Key не доходит.
Исправь UX: кнопка «Старт» должна закрыть редактор, передать текст на Мостик,
вызвать start_session, focus_force на главное окно. Покажи подсветку первой клавиши.
```

### Таймер тикает, когда отошёл

```text
Время должно игнорировать простои > 4 секунд (IDLE_CAP) и полностью останавливаться
на паузе Esc / FocusOut. Проверь TypingEngine.elapsed и pause/resume.
```

### Переводчик тормозит печать

```text
UPLINK не должен блокировать UI. Все HTTP-запросы — только в фоновом threading,
результат через queue в after()-тике. Печать продолжается при «НЕТ СВЯЗИ».
```

---

## Промпт «добавь фичу» (шаблон)

```text
Контекст: Star Typing, пакет stamina/, stdlib only. См. README.md и CURSOR_TASK.md.

Задача: <опиши фичу одним абзацем>.

Где менять (предположительно):
- логика без UI → stamina/engine.py или missions.py
- экраны → stamina/screens.py / bridge.py
- виджеты → stamina/hud.py
- данные → storage.py / session_storage.py

Критерии готово:
1) ручная проверка в python main.py
2) python -m unittest discover -s tests -v — зелёный
3) не сломан прогресс session.json и ярлык main.py

Сначала минимальный дифф, без большого рефакторинга.
```

---

## Промпт «объясни код» (для изучения)

```text
Объясни архитектуру Star Typing как учебный гайд:
- диаграмма потока: main → app → Cockpit → Bridge → TypingEngine
- роль каждого файла в stamina/
- как считается честное время и CPM
- как свой текст проходит путь: CargoScreen → process_text → session → Bridge → UPLINK

В ответе дай относительные markdown-ссылки на файлы репозитория
(например stamina/engine.py) и на конкретные функции.
Не переписывай код без нужды — сначала карта, потом детали.
```

---

## Чеклист «вайбкодинг закончен»

- [ ] `python main.py` открывает пульт, разделы Ctrl+1…5 работают
- [ ] свой текст: загрузка → адаптация → старт → подсветка клавиши
- [ ] Esc пауза, F5 заново, F9 звук, F1 справка
- [ ] после закрытия — диалог продолжения сессии
- [ ] миссии открываются по звёздам, XP растёт
- [ ] UPLINK переводит не блокируя печать (или корректно показывает «НЕТ СВЯЗИ»)
- [ ] `python -m unittest discover -s tests -v` — все тесты OK
- [ ] ярлык / `Stamina.bat` запускают без консоли

---

## Короткие «ванильные» промпты (если спешите)

**A. Только классический Stamina (без космоса)**  
```text
Сделай тренажёр печати на tkinter: окно с текстом пользователя, адаптация
(пробелы/пунктуация/нижний регистр), виртуальная QWERTY, красная подсветка
текущей клавиши, двухцветная полоса с границей по центру, CPM по правильным
символам, Esc-пауза, сохранение session.json. Без миссий и переводчика.
```

**B. Доведи мой MVP до Star Typing**  
```text
У меня уже есть набор текста на tkinter. Преврати UI в «пульт космического корабля»
по CURSOR_TASK.md: тёмная тема, приборы, миссии EN/RU, свой текст, бортжурнал,
звук winsound, переводчик UPLINK в фоне. Не меняй main.py и %APPDATA%\Stamina.
```

**C. Только тесты**  
```text
Покрой unittest'ами stamina/text_processing.py и stamina/engine.py:
адаптация EN/RU, idle cap, пауза, CPM без ошибок, segment(). Запусти discover -v.
```

---

*Документ рассчитан на воссоздание или эволюцию проекта [Teslyar75/My_Stamina](https://github.com/Teslyar75/My_Stamina).  
Промпты можно копировать целиком в Cursor Agent.*
