# Ленивая загрузка отсеков — замер и план

Дата замера: 2026-11-12.  
Среда: Linux (Xvfb), Python 3.12.3, пустая библиотека пилота, репозиторий My_Stamina + клон Wed_Star_Typing_Version (`ff6f694`).  
Код продукта не менялся — только измерения.

Цель: понять, какие отсеки тяжёлые, и спланировать загрузку **только при открытии**.

---

## 1. Desktop (Tk)

### Как устроено сейчас

| Момент | Что происходит |
|--------|----------------|
| Импорт `stamina.cockpit` | Тянет bridge, screens, hud, theme (~100 ms cum. по `-X importtime`) |
| `Cockpit.__init__` | Для каждого тяжёлого отсека вызывается `*_hook.load_class()` → **полный import модуля** (english, speedread, …) уже на старте |
| Сборка виджетов | Eager: `bridge`, `missions`, `cargo`, `log`, `settings`, `bridge_settings`, `help`, `honor`. Lazy-фабрики: `english`, `speedread`, `lounge`, `radio`, `comm`, `docs`, `orion` |
| Фон после 120 ms | `_build_pending` собирает все lazy-отсеки по одному (в `--safe` / `STAR_TYPING_SAFE=1` фон отключён) |
| English | Каркас сразу; полный UI после асинхронной загрузки `vocab.json` (~20k слов) |

### Старт приложения (safe mode, первый кадр)

Среднее по 3 прогонам:

| Метрика | Значение |
|---------|----------|
| Время до первого кадра | **~540 ms** |
| RSS после первого кадра | **~84 MB** |
| Экраны на старте | bridge, missions, cargo, log, settings, bridge_settings, help, honor |
| Фабрики в ожидании | english, speedread, lounge, radio, comm, docs, orion |

`load_class()` на старте (import без сборки виджетов), один процесс по порядку:

| Отсек | load_class, ms | Δ RSS, MB |
|-------|----------------|-----------|
| english | 20 | 7.2 |
| speedread | 8 | 1.6 |
| lounge | 1 | 0.1 |
| radio | 13 | 3.0 |
| comm | 4 | 0.7 |
| docs | 13 | 2.3 |
| orion | 4 | 0.9 |

Итого import всех «ленивых» отсеков на старте: порядка **~65 ms** и **~16 MB**, хотя виджеты ещё не построены.

### Таблица по отсекам (изолированный процесс, stub-приложение)

Import — холодный `__import__` пакета. Build — создание экрана (`update` Tk). Для english — ожидание `vocab.ready` и полной сборки страниц.

| Отсек | Import, ms | Build, ms | Δ MB (build) | На старте? | Примечание |
|-------|------------|-----------|--------------|------------|------------|
| bridge | 4 | 19 | 2.7 | виджет eager | мостик |
| missions | 8 | 16 | 2.2 | виджет eager | подменю мостика |
| cargo | 7 | 33 | 3.9 | виджет eager | |
| log | 7 | 46 | 7.2 | виджет eager | |
| settings | 7 | 78 | 9.6 | виджет eager | |
| bridge_settings | 2 | 40 | 4.0 | виджет eager | |
| help | 8 | 13 | 2.6 | виджет eager | |
| **english** | **5** | **880** | **~159** | import через load_class; виджет lazy | словарь 20 579 слов |
| speedread | 8 | 76 | 7.3 | import через load_class; виджет lazy | пустая библиотека |
| lounge | 2 | 22 | 3.3 | import через load_class; виджет lazy | |
| radio | 15 | 24 | 3.7 | import через load_class; виджет lazy | |
| comm | 6 | 15 | 2.4 | import через load_class; виджет lazy | |
| docs | 33 | 45 | 4.8 | import через load_class; виджет lazy | |
| orion | 27 | 122 | 8.9 | import через load_class; виджет lazy | |

`-X importtime` (cum., отдельный процесс): docs ≈ 145 ms, cockpit ≈ 103 ms, orion ≈ 97 ms, speedread ≈ 96 ms, english ≈ 59 ms, radio ≈ 53 ms, comm ≈ 49 ms, lounge ≈ 34 ms, bridge ≈ 33 ms.

### Тяжёлые данные (диск → RAM)

| Данные | На диске | Когда грузится | Заметка |
|--------|----------|----------------|---------|
| `english/data/vocab.json` | **28 MB** | при открытии English (async), затем полный UI | parse одного файла ≈ **300 ms**, **+101 MB** RSS; с построением страниц ≈ **+159 MB** |
| CEFR sets | 11 MB | при работе с наборами/уровнями | в коде есть комментарий про ~1.4 s cold parse уровней |
| verbs | 1.6 MB | вкладка глаголов | |
| alt_wallpapers | **52 MB** | смена отсека/кадра слайдшоу (Pillow) | не все сразу, но файлы крупные |
| sounds | 23 MB | SoundBoard / воспроизведение | на старте создаётся SoundBoard |
| lexicon `*.txt.gz` | 3 MB | glue_fix / правка текста по требованию | |
| guide_content | 36 KB | гид | лёгкий |

Без safe mode фоновая `_build_pending` со временем поднимает RSS к **~240+ MB**, если открыть/собрать English (словарь) и остальные отсеки.

---

## 2. Web (Wed_Star_Typing_Version)

Сборка: `frontend` Vite 6, `npm run build`.

### Уже lazy

В `App.tsx` почти все отсеки через `React.lazy`: english, speedread, missions, settings, cargo, flightlog, bridgeSettings, lounge, radio, docs, comm, orion, CockpitEntry.  
**Eager в main:** `BridgeScreen`, shell, guide, i18n, тема, FX.  
Vosk — отдельный динамический import из english/asr.  
Library внутри speedread — тоже `lazy`.

### Размеры чанков (raw KB)

| Отсек / кусок | Chunk KB | Lazy? |
|---------------|----------|-------|
| **main `index-*.js`** | **804** | нет (первый экран) |
| main `index-*.css` | 202 | нет |
| english | 83 | да |
| speedread | 66 (+9 CSS) | да |
| library (из speedread) | 33 | да |
| orion | 35 (+10 CSS) | да |
| docs | 22 (+4 CSS) | да |
| lounge | 19 | да |
| settings | 16 | да |
| radio | 13 | да |
| comm | 10 (+2 CSS) | да |
| flightlog (бортжурнал) | 9 | да |
| bridge_settings | 6 | да |
| cargo | 6 | да |
| missions | 5 | да |
| CockpitEntry (экипаж) | 68 (+14 CSS) | да |
| **vosk-browser** | **5651** | да (только ASR) |

Первая загрузка (то, что тянет `index.html`): **~804 KB JS + ~202 KB CSS**  
(gzip ≈ **271 KB JS + 37 KB CSS** ≈ **308 KB** сжатых).

Главный JS раздут в первую очередь монолитным `src/i18n/setup.ts` (~246 KB исходника со всеми языками) плюс shell/bridge/guide/FX.

### Backend

| Шаг | ms | Δ RSS, MB |
|-----|-----|-----------|
| import `app.main` | ~835 | +69 |
| `english_vocab.load_raw_words` (по запросу) | ~278 | +22 |
| CEFR all levels (по запросу) | ~36 | +15 |
| TestClient lifespan (init_db + workers + warmup) | ~1240 | +148 → **~267 MB** пик в этом прогоне |

В `lifespan` при старте: `init_db`, translate worker, english seed worker, фоновый **`english_packs.warmup()`** (все CEFR-уровни).  
Данные в `backend/app/data`: **~45 MB** (в основном `vocab.json` ~28 MB + CEFR + lexicon).

---

## 3. Что самое тяжёлое (итог)

1. **Desktop English / `vocab.json`** — десятки–сотни MB RAM и ~0.3–1 s при первом открытии.  
2. **Desktop: import всех отсеков через `load_class` на старте** + фоновая `_build_pending` (не safe).  
3. **Web: main bundle ~800 KB JS** (i18n и оболочка), при том что отсеки уже в lazy-чанках.  
4. **Web backend: warmup CEFR + seed** на старте процесса.  
5. **Vosk ~5.5 MB** — уже lazy, оставлять так.  
6. Обои ALT и звуки — крупные на диске; критичны при смене зоны / воспроизведении, не при «голом» импорте модуля.

---

## 4. Приоритетный план

| # | Что сделать | Ожидаемый выигрыш | Риск |
|---|-------------|-------------------|------|
| **P0** | Desktop: не импортировать модули отсеков в `load_class` на старте — только проверка наличия / отложенный import внутри фабрики | −50…80 ms старта, −10…20 MB до первого захода в отсеки; проще держать cold start | средний: вкладка пропадёт только при реальном заходе, если модуль сломан; нужны smoke-тесты навигации |
| **P0** | Desktop: по умолчанию не вызывать `_build_pending` (собирать отсек только в `show` / `_ensure_screen`), safe-поведение как норма | RSS остаётся ~80–90 MB, пока пилот не открыл тяжёлые зоны; уходит фоновая нагрузка CPU | низкий/средний: первая отрисовка отсека чуть дольше (уже есть фабрики) |
| **P0** | Desktop English: не держать весь `vocab.json` в RAM до нужды — индекс slug→offset / чанки / грузить полные карточки по запросу; CEFR и verbs только на своих вкладках | −100…160 MB при открытии English «вскользь»; быстрее первый paint обзора | высокий по данным: ломается поиск/склад, если API словаря не сохранить; нужна совместимость прогресса |
| **P1** | Desktop: миссии / свой текст / бортжурнал / help / honor — тоже через `_lazy`, как english | −50…150 ms и несколько MB на старте (сейчас все виджеты в `screens = {…}`) | низкий: тот же механизм, что у других отсеков |
| **P1** | Web: разрезать i18n по языкам (один язык в main, остальные dynamic import) | main JS заметно меньше 800 KB (ориентир −150…250 KB raw) | средний: вспышка при смене языка; проверить SSR/нет |
| **P1** | Web backend: убрать или отложить `warmup()` CEFR и тяжёлый seed до первого `/api/english…` | быстрее и легче холодный API-процесс | низкий: первый запрос english чуть холоднее |
| **P2** | Web: вынести guide/FX/редко нужное из main; manualChunks для вендоров | ещё −50…150 KB first-load | низкий |
| **P2** | Desktop: обои — декодировать только текущий кадр зоны, сбрасывать PhotoImage предыдущего | меньше пиков RSS при обходе отсеков | низкий |
| **P2** | Не трогать vosk: оставить dynamic import | уже хорошо | — |

### Практичный порядок внедрения

1. Отложить import+сборку отсеков до открытия (P0 desktop) — мало кода, сразу видно в RSS/времени.  
2. Разгрузить словарь English (P0) — главный выигрыш по памяти.  
3. Web i18n split + backend warmup off (P1) — first-load и API.  
4. Дожать eager-экраны мостика и обои (P1–P2).

---

## 5. Метод замера (чтобы повторить)

Desktop:

```bash
# старт + открытие English (safe mode), как в §6
STAR_TYPING_SAFE=1 PYTHONPATH=. python3 tools/measure_lazy_compartments.py

STAR_TYPING_SAFE=1 python3 -X importtime -c "import stamina.english" 2>importtime.txt
```

Web:

```bash
cd frontend && npm ci && npm run build
# смотреть dist/assets/* и gzip size в логе Vite
```

Backend:

```bash
# DATABASE_URL=sqlite:///...  python -c "from app.main import app" + TestClient lifespan
```

Числа зависят от машины, наличия книг в библиотеке и кэша Python; порядок величин и относительный рейтинг отсеков стабильнее абсолютных миллисекунд.

---

## 6. P0 внедрено (desktop) — 2026-11-12

Ветка реализации: `cursor/lazy-compartments-p0-1e65`. Код продукта изменён.

### Что сделано

1. **`load_class()`** в `*_hook.py` только проверяет файлы на диске (маркер `AVAILABLE`); **import экрана — в `create()`** при первом заходе.
2. **Пакетные `__init__.py`** (english / speedread / lounge / radio) отдают экран через `__getattr__`, чтобы мини-бар радио на мостике не тянул `RadioScreen`.
3. **Фоновый `_build_pending`** — no-op: отсеки собираются только в `show` / `_ensure_screen` (как раньше в safe mode). Мостик и eager-экраны без изменений.
4. **Словарь English**: лёгкий индекс + чанки по букве slug в `%APPDATA%/Stamina/vocab_lazy_v1/` (или `~/…`). Исходный `vocab.json` **не удаляется**; миграция автоматическая при первом чтении. Тяжёлые поля (предложения, определения…) подгружаются в `LazyWord` по доступу. Полная загрузка: `STAR_TYPING_VOCAB_FULL=1`.

### Замер до / после (та же машина и метод)

Среда: Linux, Xvfb, Python 3.12, `STAR_TYPING_SAFE=1`, `tools/measure_lazy_compartments.py`.  
После: среднее по 3 прогонам (кэш словаря уже собран). До: один прогон на `master` до правки.

| Метрика | До (master) | После (P0) | Δ |
|---------|-------------|------------|---|
| Время до первого кадра | **741 ms** | **~369 ms** | **−372 ms** |
| RSS после старта | **59.2 MB** | **~47.4 MB** | **−11.8 MB** |
| Модули экранов lazy-отсеков на старте | все 7 загружены через `load_class` | **ни одного** | — |
| Открытие English (до UI ready) | **905 ms** | **~688 ms** | **−217 ms** |
| RSS после English | **235.6 MB** | **~172.4 MB** | **−63.2 MB** |
| Δ RSS старт→English | **+176.4 MB** | **~+125.0 MB** | **−51 MB** |
| Только `Vocab.load()` (отдельный процесс) | full **+95 MB** | lazy-index **+46 MB** | **−49 MB** |

Горячие клавиши, сохранение состояния и API словаря (поиск / наборы / предложения) сохранены; тесты: `tests/test_lazy_compartments.py`, `tests/test_vocab_lazy.py`.
