# Правила работы агентов на корабле

> Короткий устав. Написан после ночи, когда два агента работали в одной папке
> и `git reset --hard` снёс готовые коммиты. Пилот — Командир; он может разрешить
> отступление, но по умолчанию правила такие.

## Ветки

- Работа — в своей ветке: `agent/<имя>/<тема>`, например `agent/orion/marks-cursor`.
- В `master` только через слияние, после зелёных тестов по затронутым файлам.
- Одна тема — одна ветка. Не мешаем чужим правкам в общем рабочем дереве.

## Запреты

- `git reset --hard` — **только** по прямой команде пилота.
- `git push --force` — **только** по прямой команде пилота.
- `git checkout -- .`, `git clean -fd` — то же самое: это стирает чужую работу.
- Не трогать данные пилота в `%APPDATA%\Stamina` (кроме явно указанного в задании).

## Перед рискованной правкой

```powershell
powershell -ExecutionPolicy Bypass -File tools\snapshot.ps1
```

Скрипт ставит тег `snap-YYYYMMDD-HHMM` и печатает строку откатa. Если что-то
пошло не так — `git checkout <тег>`, и корабль снова дышит.

## Проверка перед слиянием

```powershell
python tools/ci_gate.py --only contrast --only i18n --only dep   # быстрые аудиты, секунды
python -m pytest tests/ -q                                       # тесты (нужен дисплей для GUI-частей)
```

Гейт собирает в один отчёт то, что уже написано в `tools/`: контраст по скинам,
переводы интерфейса, заявленные зависимости, паритет альт-вида (`--full`), и
печатает код возврата для CI. В CI это же исполняет
`.github/workflows/quality-gate.yml` — на Windows и Linux.

Зависимости для разработки (pytest, ruff) лежат в `requirements-dev.txt` и в
`install.bat` не ставятся: пилоту они не нужны, а агенту без них нечем проверить
свою правку.

## Кто чем занят

Общий список — `.opencode/agents/ACTIVE.md`. Перед правкой допиши строку
(кто, что, какие файлы), после — убери. Так второй агент видит, где идёт работа.

## Коммиты

- Сообщение по-русски, коротко, в стиле репозитория: `fix: …`, `feat: …`, `docs: …`.
- Один коммит — одна мысль. Секреты и личные файлы не коммитим.

## Отчёт пилоту

После каждой законченной части — короткая строка в чат: что сделано, какие
проверки прошли, что осталось. Долгие поручения — через доклад о работе
(`python -m stamina.task_progress plan|step|finish <id>` → `_orion/tasks/<id>.json`,
строка на пульте Ориона; запасной путь — legacy `_orion/progress.json` v1).
Новые варианты скинов — по `docs/skins/ALT_SKIN_GUIDE.md`.

## Cursor Cloud specific instructions

Среда агента — Ubuntu с рабочим столом. `install` ставит `python3-tk`, `python3-venv`, `fonts-dejavu`, `xvfb`, `espeak-ng`, `xclip`, `libportaudio2` и создаёт `.venv` из `requirements.txt`, `requirements-dev.txt` и `keyring`. Долгоживущего сервера нет: окно поднимают сами.

- Запуск: `.venv/bin/python main.py` (на столе агента уже есть `DISPLAY`). Данные пилота: `~/.local/share/StarTyping`.
- Быстрый гейт: `.venv/bin/python tools/ci_gate.py --only contrast --only i18n --only dep`
- Тесты без своего экрана: `xvfb-run -a -s "-screen 0 1600x1000x24" .venv/bin/python -m pytest tests/ -q`
- `ruff check stamina tools tests main.py` в CI не блокирует слияние.
- Vosk, модель речи и OpenCode в среду не входят. Озвучка — `espeak-ng`. Без микрофона программа работает.
