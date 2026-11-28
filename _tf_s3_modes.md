ПРАВИЛО ПРО ТЕСТЫ (прочитай первым):
- pytest запускай НЕ БОЛЬШЕ ОДНОГО раза (если упал — один фикс и тот же запуск ещё раз, потом СТОП, даже если снова красное).
- Обязателен уникальный --basetemp. НИКОГДА не используй папку pytest-of-mi. Не используй head. Не пиши test_out*.txt.
    $env:STAR_TYPING_SILENT=1
    Set-Location D:\tmp\st-s3-holds
    $base = Join-Path $env:TEMP ('pytest-s3-modes-' + [guid]::NewGuid().ToString('N'))
    D:\Star_Typing\.venv\Scripts\python.exe -m pytest tests/test_terraformer_s3_modes.py -q --basetemp=$base --tb=line
- Не гоняй полный набор и не гоняй tests/test_terraformer_trainer.py.
- Не трогай stamina/i18n/ и key_hint(). Не коммить и не пушь. Не делай git reset --hard / clean / checkout -- / stash drop. Игру не запускай. CRLF сохрани. Не трогай %APPDATA%\Stamina, _orion/, graphify-out/. Ключи ВЫБРАТЬ / WÄHLEN / PICK / ВИБРАТИ и '{0} out of {1}' не меняй. Этот файл удали, когда закончишь.

Ты в D:\tmp\st-s3-holds, ветка agent/orion/terraformer-s3-holds, коммит 7e435c6 (уже есть отдельные holds у юнитов и действия у выбранного). Не ломай: per-unit holds, active_unit, dig/try_place_block/unload у выбранного юнита, _hold_cap(), redraw_cell, синхронизацию robot с main_unit, deposit_is_visible.

Справка (не редактируй те деревья): частичная работа есть в D:\tmp\st-s3-modes и D:\tmp\st-s3-modes3 — можно прочитать и аккуратно перенести сюда.

ЭТОТ ПРОХОД ТОЛЬКО — режимы работы, чекбоксы, переключение V, отчёт о действии. Не делай: несколько терраформеров «по одному на язык», червя, туман-разведку, склад как отдельную фичу, энергию, F1, галерею.

Сделай:

1) Режимы у юнита (Unit.mode, по умолчанию "manual"):
   - manual: игрок сам управляет выбранным мышью и стрелками/WASD; без автоприказов и автоподсказок.
   - autonomous / auto: без прямого приказа юнит сам работает по плану (pathfind/issue_move, существующий набор blocked). Полный отсек — едет разгружаться (уже заложено), пустой — копает.
   - semi-autonomous / semi-auto: выполняет назначенное задание и затем ЖДЁТ, не берёт новое авто-задание сам. Хелпер может показать ждущий юнит, куда дальше и ближайшую постройку улучшить/расчистить.
   Смешанный режим: один юнит в auto/semi-auto, другой выбран и в manual — одновременно.

2) apply_control_preset('one'|'two'|'all'|'semi') и компактные чекбоксы в HUD (плоский и iso), клики вызывают API:
   - one: выбранный (или главный) manual, остальные autonomous;
   - two: первые два manual, остальные autonomous;
   - all: все manual;
   - semi: все semi_autonomous.
   Тесты вызывают API без холста.

3) Клавиша V (keysym v и keycode 86) переключает у выбранного юнита manual <-> autonomous в любой момент. Переход в manual сбрасывает автоприказы (order/path от авто). Текущий режим виден в HUD. Текст key_hint() не меняй.

4) unit_action_report(unit) -> dict или tuple: action, target, status (idle / moving / collecting / going to extract / placing / waiting / unloading). Короткий отчёт на экране для выбранного юнита (плоский и iso).

Тесты в tests/test_terraformer_s3_modes.py: режим по умолчанию manual; V/toggle сбрасывает автоприказы; autonomous начинает работу; mixed (один auto, другой manual); пресеты one/two/all/semi; semi-auto после задания ждёт; unit_action_report возвращает action/target/status.

Запусти указанную команду pytest ОДИН раз, затем ruff по изменённым файлам. Если красное — один фикс, та же команда ещё раз, потом стоп.

Напечатай: клавиша переключения — V, и резюме на 3 строки. Затем остановись.
