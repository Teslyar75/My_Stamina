#!/usr/bin/env bash
# Star Typing — запуск на Linux одной командой:   ./run_linux.sh
# Первый запуск: проверяет системные пакеты (apt / dnf / pacman; sudo — только с вашего согласия),
# создаёт .venv, ставит пакеты из requirements.txt и запускает программу. Дальше — просто запускает.
# Флаги:
#   --desktop     значок в меню приложений (~/.local/share/applications/star-typing.desktop)
#   --autostart   запуск при входе в систему (~/.config/autostart/star-typing.desktop)
#   --voice       ещё и распознавание речи: vosk + sounddevice + модель (~45 МБ)
#   --yes         не спрашивать перед sudo (для скриптов)
#   --no-system   не трогать системные пакеты
#   --no-launch   только подготовить, не запускать
#   --reinstall   пересоздать .venv
# Подробно: docs/LINUX.md
set -u
ROOT="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$ROOT" || exit 1
DESKTOP=0; AUTOSTART=0; VOICE=0; YES=0; SYSTEM=1; LAUNCH=1; REINSTALL=0; PASS=()
for a in "$@"; do
  case "$a" in
    --desktop) DESKTOP=1 ;; --autostart) AUTOSTART=1 ;; --voice) VOICE=1 ;; --yes|-y) YES=1 ;;
    --no-system) SYSTEM=0 ;; --no-launch) LAUNCH=0 ;; --reinstall) REINSTALL=1 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) PASS+=("$a") ;;
  esac
done
STAMP=".venv/.star_typing_ready"
PY="${PYTHON:-python3}"

say() { printf '\033[36m[Star Typing]\033[0m %s\n' "$*"; }

pkg_manager() {
  for m in apt-get dnf pacman zypper; do command -v "$m" >/dev/null 2>&1 && { echo "$m"; return; }; done
  echo ""
}

# Пакеты по менеджерам: Python+Tk+venv, шрифты, озвучка, микрофон (portaudio), хранилище ключей.
packages() {
  case "$1" in
    apt-get) echo "python3 python3-tk python3-venv python3-pip fonts-dejavu espeak-ng speech-dispatcher libportaudio2 gnome-keyring libsecret-1-0 xclip" ;;
    dnf)     echo "python3 python3-tkinter python3-pip dejavu-sans-fonts espeak-ng speech-dispatcher portaudio gnome-keyring libsecret xclip" ;;
    pacman)  echo "python tk python-pip ttf-dejavu espeak-ng speech-dispatcher portaudio gnome-keyring libsecret xclip" ;;
    zypper)  echo "python3 python3-tk python3-pip dejavu-fonts espeak-ng speech-dispatcher portaudio gnome-keyring libsecret-1-0 xclip" ;;
  esac
}

need_system() {
  "$PY" -c 'import tkinter, venv, ensurepip' >/dev/null 2>&1 || return 0
  return 1
}

install_system() {
  local pm; pm="$(pkg_manager)"
  if [ -z "$pm" ]; then
    say "Менеджер пакетов не найден — поставьте вручную: Python 3.10+, tkinter, venv (docs/LINUX.md)."
    return 1
  fi
  local pk; pk="$(packages "$pm")"
  say "Нужны системные пакеты ($pm): $pk"
  if [ "$YES" -ne 1 ]; then
    read -r -p "Установить через sudo? [y/N] " ans
    case "$ans" in y|Y|д|Д|yes|да) ;; *) say "Пропускаю. Без python3-tk окно не откроется."; return 1 ;; esac
  fi
  case "$pm" in
    apt-get) sudo apt-get update && sudo apt-get install -y $pk ;;
    dnf)     sudo dnf install -y $pk ;;
    pacman)  sudo pacman -S --needed --noconfirm $pk ;;
    zypper)  sudo zypper install -y $pk ;;
  esac
}

write_entry() {   # $1 — путь .desktop
  mkdir -p "$(dirname "$1")"
  cat > "$1" <<DESK
[Desktop Entry]
Type=Application
Name=Star Typing
Comment=Клавиатурный тренажёр «Пульт пилота»
Exec="$ROOT/run_linux.sh" --no-system
Path=$ROOT
Icon=$ROOT/stamina/assets/star_typing_64.png
Terminal=false
Categories=Education;
DESK
  chmod +x "$1" 2>/dev/null
  say "Ярлык: $1"
}

if [ "$REINSTALL" -eq 1 ]; then rm -rf .venv; fi
if [ ! -f "$STAMP" ]; then
  if [ "$SYSTEM" -eq 1 ] && need_system; then install_system || true; fi
  if ! "$PY" -c 'import tkinter' >/dev/null 2>&1; then
    say "Нет tkinter у $PY. Ubuntu/Debian: sudo apt install python3-tk · Fedora: python3-tkinter · Arch: tk"
    exit 1
  fi
  say "Создаю .venv и ставлю пакеты (один раз)…"
  "$PY" -m venv .venv || { say "Не создался .venv — нужен пакет python3-venv"; exit 1; }
  .venv/bin/python -m pip install -q --upgrade pip >/dev/null 2>&1
  .venv/bin/python -m pip install -q -r requirements.txt keyring || { say "pip не смог поставить пакеты"; exit 1; }
  date > "$STAMP"
  say "Готово."
fi
if [ "$VOICE" -eq 1 ]; then
  say "Ставлю vosk + sounddevice и модель речи…"
  .venv/bin/python -m pip install -q vosk sounddevice && .venv/bin/python scripts/download_vosk_model.py \
    || say "Распознавание речи не поставилось — программа работает и без него."
fi
[ "$DESKTOP" -eq 1 ] && write_entry "$HOME/.local/share/applications/star-typing.desktop"
[ "$AUTOSTART" -eq 1 ] && write_entry "$HOME/.config/autostart/star-typing.desktop"
[ "$LAUNCH" -eq 1 ] || exit 0
exec .venv/bin/python main.py "${PASS[@]}"
