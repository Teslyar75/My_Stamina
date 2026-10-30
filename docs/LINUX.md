# Star Typing на Linux

Программа написана на Python + Tkinter и работает на Linux с рабочим столом (X11 или Wayland с XWayland).
Ниже — установка, запуск, тесты и что на Linux работает иначе, чем в Windows.

> **Что проверено (30.10.2026).** Debian 13 «trixie», Python 3.12 с Tk 9.0, виртуальный экран Xvfb 1280×720.
> Скрипт `run_linux.sh` (первый запуск, повторный запуск, `--desktop`, `--autostart`, отказ от sudo),
> старт программы до экрана выбора пилота и полный набор тестов `pytest`. Озвучку (espeak-ng) и микрофон
> на этой машине живьём не проверяли: там нет звуковой карты. Эти ветки кода закрыты модульными
> тестами (`tests/test_linux_compat.py`). На Ubuntu 22.04/24.04 раньше проверяли `install.sh`.

## 1. Быстрый старт

```bash
git clone https://github.com/Teslyar75/My_Stamina.git
cd My_Stamina
./run_linux.sh
```

Что делает `run_linux.sh` при **первом** запуске:

1. Проверяет, есть ли у `python3` модули `tkinter` и `venv`. Если нет, находит менеджер пакетов
   (`apt-get` / `dnf` / `pacman` / `zypper`), показывает список пакетов и **спрашивает**, ставить ли их через
   `sudo`. Ответили «нет» — системные пакеты не трогаются.
2. Создаёт папку `.venv` рядом с программой и ставит в неё `requirements.txt` (Pillow, pypdf, fpdf2)
   и `keyring`. Системный Python при этом не меняется.
3. Запускает программу.

При **следующих** запусках скрипт сразу запускает программу (метка готовности: `.venv/.star_typing_ready`).

| Флаг | Что делает |
| --- | --- |
| `--desktop` | значок в меню приложений: `~/.local/share/applications/star-typing.desktop` |
| `--autostart` | запуск при входе в систему: `~/.config/autostart/star-typing.desktop` |
| `--voice` | распознавание речи: `vosk` + `sounddevice` и модель (≈45 МБ) |
| `--yes` | не спрашивать перед `sudo` (для скриптов) |
| `--no-system` | не проверять и не ставить системные пакеты |
| `--no-launch` | только подготовить, не запускать |
| `--reinstall` | пересоздать `.venv` (например, после обновления Python) |

Другой интерпретатор: `PYTHON=python3.12 ./run_linux.sh`. Остальные аргументы передаются в `main.py`.
Флаги можно сочетать: `./run_linux.sh --desktop --autostart --voice`.

Есть и старый установщик `bash install.sh`: он ставит всё сразу (пакеты, `.venv`, vosk, модель, ярлыки).
Запуск после него — `./run.sh`. Проверка среды — `./run.sh --check`.

## 2. Системные пакеты

| Назначение | Ubuntu / Debian (`apt`) | Fedora (`dnf`) | Arch (`pacman`) |
| --- | --- | --- | --- |
| Python, Tk, venv, pip | `python3 python3-tk python3-venv python3-pip` | `python3 python3-tkinter python3-pip` | `python tk python-pip` |
| Шрифты с кириллицей | `fonts-dejavu` | `dejavu-sans-fonts` | `ttf-dejavu` |
| Озвучка | `espeak-ng speech-dispatcher` (+ `alsa-utils` для `aplay`) | `espeak-ng speech-dispatcher` | `espeak-ng speech-dispatcher` |
| Микрофон (sounddevice) | `libportaudio2` | `portaudio` | `portaudio` |
| Хранилище ключей агентов | `gnome-keyring libsecret-1-0` | `gnome-keyring libsecret` | `gnome-keyring libsecret` |
| Буфер обмена (по желанию) | `xclip` | `xclip` | `xclip` |

Одной командой для Ubuntu/Debian:

```bash
sudo apt install python3 python3-tk python3-venv python3-pip fonts-dejavu espeak-ng speech-dispatcher \
     alsa-utils libportaudio2 gnome-keyring libsecret-1-0 xclip
```

Нужен Python **3.10 или новее** со встроенным tkinter. Проверка: `python3 -c "import tkinter; tkinter._test()"`.

## 3. Ручная установка (без скрипта)

```bash
cd My_Stamina
python3 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -r requirements.txt keyring
.venv/bin/python main.py
```

### Модель распознавания речи (Vosk)

Нужна для проверки произношения в «АНГЛИЙСКОМ» и для голосового вызова Ориона.

```bash
.venv/bin/python -m pip install vosk sounddevice
.venv/bin/python scripts/download_vosk_model.py
```

Модели (с https://alphacephei.com/vosk/models/): `vosk-model-small-ru-0.22` (≈45 МБ),
`vosk-model-small-uk-v3-nano`, `vosk-model-small-en-us-0.15`. Их можно скачать и вручную:
распакуйте архив в папку моделей программы (её показывает `./run.sh --check`).

### OpenCode (агент по умолчанию для Ориона)

Орион вызывает консольную программу `opencode`. Она должна находиться в `PATH`:

```bash
curl -fsSL https://opencode.ai/install | bash     # или: npm i -g opencode-ai
opencode --version
```

Без OpenCode можно подключить агента вида «OpenAI-совместимый» (OpenAI, DeepSeek, OpenRouter, Groq,
локальная Ollama) или «Мост GitHub». Это делается клавишей **F4** на экране выбора пилота.

## 4. Запуск и тесты

* Запуск: `./run_linux.sh`, `./run.sh` или `.venv/bin/python main.py`.
* Данные пилотов: `~/.local/share/StarTyping` (в Windows это `%APPDATA%\Stamina`).
* Тесты:

```bash
.venv/bin/python -m pip install pytest
.venv/bin/python -m pytest -q                      # нужен экран (DISPLAY)
xvfb-run -a -s "-screen 0 1280x720x24" .venv/bin/python -m pytest -q   # без экрана (пакет xvfb)
```

Во время тестов озвучка выключена (`STAR_TYPING_NO_LINUX_TTS=1`), и сторож замираний тоже
(`STAR_TYPING_NO_STALL_WATCH=1`). Обе переменные задаёт `tests/conftest.py`.

## 5. Что на Linux работает иначе и почему

| Функция | Windows | Linux |
| --- | --- | --- |
| Ключи API агентов | Диспетчер учётных данных Windows | `keyring` → Secret Service (gnome-keyring / KWallet). Если хранилища нет, ключ **не сохраняется**: окно подключения так и пишет («Нет защищённого хранилища ключей…»). В файл открытым текстом ключ не пишется никогда. Агенты без ключа (OpenCode, Ollama) работают |
| Озвучка Ориона и фраз | SAPI (`say.ps1`), выбор голоса Windows | `espeak-ng` / `espeak` / `spd-say`. Звук фраз-заглушек: WAV из `espeak-ng -w`, играет `pw-play` / `paplay` / `aplay`. Если ничего этого нет, программа молчит, а остальное работает. Поле «голос Windows» на Linux не используется |
| Звуки интерфейса | `winsound` | `paplay` (PulseAudio/PipeWire) или `aplay` (ALSA), если есть; иначе тихо |
| Буфер обмена (геолокация, копирование) | Win32 API | буфер обмена Tk (в части окружений после закрытия окна содержимое пропадает, `xclip` помогает) |
| Отправка письма | MAPI (почтовая программа Windows) | `mailto:` (тема и текст) через почтовую программу по умолчанию (`webbrowser` → `xdg-open`) и папка с файлом — вложение прикрепляете сами |
| Шрифты | Segoe UI / Bahnschrift / Consolas | берутся только семейства **с кириллицей** по `fc-list :lang=ru`: DejaVu Sans, Noto Sans, Ubuntu, Liberation… |
| Сборка мусора | обычная | автоматическая сборка выключена, мусор собирается по таймеру в главном потоке (`stamina/tk_gc.py`). Иначе фоновый поток может удалить объекты Tk, и Tcl падает с `Illegal instruction`. Эту ошибку поймали тесты на Linux |
| Голос Ориона «ОРИОН»/Home | Vosk + SAPI | Vosk + espeak-ng; без микрофона вызов сообщит об этом |

## 6. Если что-то не так

| Признак | Что сделать |
| --- | --- |
| `No module named tkinter` / `_tkinter` | `sudo apt install python3-tk` (Fedora: `python3-tkinter`, Arch: `tk`). Затем `./run_linux.sh --reinstall` |
| `TclError: no display name and no $DISPLAY` | нет графического сеанса (SSH, cron). Запускайте из рабочего стола, `ssh -X` или `xvfb-run` |
| Окно не открывается под Wayland | поставьте `xwayland` или войдите в сессию «Xorg» |
| **Вместо русских букв пустые клетки** | Tk собран без Xft, или нет шрифтов с кириллицей. Поставьте `fonts-dejavu` и берите Python из пакетов дистрибутива (`python3-tk`). Сборки Python «standalone» (uv, pyenv без `libxft-dev`) видят только старые X-шрифты: проверка `python3 -c "import tkinter as t,tkinter.font as f;r=t.Tk();print(len(f.families()))"`. Если вывело меньше ~50 семейств, Xft нет |
| Всё мелкое на 4K/HiDPI | НАСТРОЙКИ → размер интерфейса **L** или **XL**. Tk не смотрит на `GDK_SCALE`: масштаб шрифтов задаёт `Xft.dpi: 192` в `~/.Xresources` (`xrdb -merge ~/.Xresources`, затем перезапуск) |
| Нет звука / озвучки | `espeak-ng "привет"`: если тишина, проблема в системе (PipeWire/PulseAudio). `sudo apt install espeak-ng alsa-utils`; проверьте `aplay -l` |
| Микрофон не слышит | `sudo apt install libportaudio2`, `.venv/bin/python -m pip install sounddevice vosk`; выберите вход в настройках звука; `python -m sounddevice` покажет устройства |
| «Нет защищённого хранилища ключей» | `sudo apt install gnome-keyring libsecret-1-0`, войдите в сеанс заново (связка ключей должна быть разблокирована). В KDE работает KWallet. Проверка: `.venv/bin/python -c "import keyring;print(keyring.get_keyring())"` |
| `externally-managed-environment` при pip | ставьте только в `.venv` (это делает `run_linux.sh`) |
| `.venv` от старого Python | `./run_linux.sh --reinstall` |
| Ничего не происходит при запуске ярлыка | запустите `./run_linux.sh` в терминале. Журнал запуска: `~/.local/share/StarTyping/launch.log` |
