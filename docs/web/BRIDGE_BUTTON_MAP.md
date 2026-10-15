# Мостик: кнопка → десктоп → веб

Эталон-скрин: [`screenshots/overview/01_bridge_own_text.png`](../../screenshots/overview/01_bridge_own_text.png)  
Десктоп: `stamina/cockpit.py`, `stamina/bridge.py`, `stamina/translator.py`

| UI (скрин) | Десктоп | Веб (цель) |
| --- | --- | --- |
| Нав: МОСТИК…НАСТРОЙКИ | `Cockpit.SCREENS` → `show(name)` | `App` tabs → `setTab` |
| ★ пилот / ранг / XP | `update_rank`, `pilot_menu` | `GET /api/pilots/me` (+ dossier) |
| ? F1 | `open_help` | `HelpDrawer` |
| ♪ звук | `toggle_sound` / F9 | `soundsMuted` / `setSoundsMuted` |
| Часы | `_clock_tick` | local `Date` |
| Прогресс маршрута | `HeaderBar` progress | `engine.index / length` |
| Набор в канале | `BridgeScreen.on_key` → `TypingEngine` | `TypingEngine.press` + ghost input |
| Esc пауза | `toggle_pause` | `engine.pause` / `resume` |
| F5 / ЗАНОВО | `restart_current` → `_last_action` | `reloadEngine` (+ confirm later) |
| ТЕПЛОВАЯ КАРТА | `toggle_heat` | `Heatmap` show/hide + `GET /api/missions/key-errors` |
| UPLINK слово/фраза | `translator.Translator` + `_update_uplink` | `GET/POST` translate API или stub → wire |
| Сессия на финише | persist / sessions | `POST /api/sessions` |
| Миссии / ремонт | `start_mission` / `start_repair` | `POST /api/missions/drills/…`, `/repair/start` |
| Клавиша под прицелом | `HudKeyboard.highlighted` = цель | `.key.active` янтарём на **целевой** клавише (`engine.current`) |

Правило: сначала копия UI, потом каждая строка таблицы — живой handler.

**Клавиатура:** жёлтый/янтарь = «нажми эту», не вспышка после верного нажатия.
