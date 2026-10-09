#!/usr/bin/env bash
# Star Typing — установка в одну команду для Linux:   bash install.sh
# Делает всё сам: системные пакеты (python3, tkinter, venv; espeak-ng для озвучки) → .venv → пакеты pip →
# (по желанию) проверка произношения → ярлык в меню и на рабочем столе → запуск.
# Без вопросов ставит и проверку произношения (vosk + модель ~40 МБ); флаги: --no-voice, --no-launch,
# --no-system (без sudo). Одной строкой без скачивания ZIP:
#   curl -fsSL https://raw.githubusercontent.com/Teslyar75/My_Stamina/master/install.sh | bash
set -u
REPO_ZIP="https://github.com/Teslyar75/My_Stamina/archive/refs/heads/master.zip"
SELF="${BASH_SOURCE[0]:-}"
if [ -n "$SELF" ] && [ -f "$SELF" ] && [ -f "$(dirname "$(readlink -f "$SELF")")/main.py" ]; then
  cd "$(dirname "$(readlink -f "$SELF")")"
else   # запущен через curl | bash — сначала скачать программу в ~/StarTyping
  DEST="${STAR_TYPING_DIR:-$HOME/StarTyping}"
  echo "Скачиваю Star Typing в $DEST ..."
  if [ ! -f "$DEST/main.py" ]; then
    command -v curl >/dev/null 2>&1 || { sudo apt-get install -y curl unzip 2>/dev/null || true; }
    TMPZ="$(mktemp -d)"
    curl -fsSL "$REPO_ZIP" -o "$TMPZ/st.zip" && (cd "$TMPZ" && python3 -m zipfile -e st.zip . 2>/dev/null || unzip -q st.zip) \
      && mkdir -p "$DEST" && cp -r "$TMPZ"/My_Stamina-master/. "$DEST"/ || { echo "Не удалось скачать $REPO_ZIP"; exit 1; }
  fi
  exec bash "$DEST/install.sh" "$@"
fi
ROOT="$PWD"
VOICE=yes; LAUNCH=1; SYSTEM=1
for a in "$@"; do
  case "$a" in
    --voice) VOICE=yes ;; --no-voice) VOICE=no ;; --no-launch) LAUNCH=0 ;; --no-system) SYSTEM=0 ;;
  esac
done
say()  { printf '\n\033[1;36m%s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[!] %s\033[0m\n' "$*"; }

echo "===================  STAR TYPING — УСТАНОВКА (Linux)  ==================="

# --- менеджер пакетов
PM=""; for p in apt-get dnf pacman zypper; do command -v "$p" >/dev/null 2>&1 && { PM="$p"; break; }; done
case "$PM" in
  apt-get) BASE="python3 python3-tk python3-venv python3-pip espeak-ng alsa-utils"; PA="libportaudio2"; INSTALL="apt-get install -y" ;;
  dnf)     BASE="python3 python3-tkinter python3-pip espeak-ng"; PA="portaudio"; INSTALL="dnf install -y" ;;
  pacman)  BASE="python tk python-pip espeak-ng"; PA="portaudio"; INSTALL="pacman -S --needed --noconfirm" ;;
  zypper)  BASE="python3 python3-tk python3-pip espeak-ng"; PA="portaudio"; INSTALL="zypper --non-interactive install" ;;
  *)       BASE=""; PA=""; INSTALL="" ;;
esac
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

need_sys() {   # есть ли что ставить из системных пакетов
  command -v python3 >/dev/null 2>&1 || return 0
  python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null || return 0
  python3 -c 'import tkinter' 2>/dev/null || return 0
  python3 -c 'import venv, ensurepip' 2>/dev/null || return 0
  command -v espeak-ng >/dev/null 2>&1 || command -v espeak >/dev/null 2>&1 || command -v spd-say >/dev/null 2>&1 || return 0
  command -v aplay >/dev/null 2>&1 || command -v paplay >/dev/null 2>&1 || return 0
  [ "$VOICE" = yes ] && ! ldconfig -p 2>/dev/null | grep -q libportaudio && return 0
  return 1
}

say "[1/5] Системные пакеты"
PKGS="$BASE"; [ "$VOICE" = yes ] && PKGS="$PKGS $PA"
if [ "$SYSTEM" = 1 ] && [ -n "$INSTALL" ] && need_sys; then
  echo "$SUDO $INSTALL $PKGS"
  [ "$PM" = apt-get ] && $SUDO apt-get update -qq
  $SUDO $INSTALL $PKGS || warn "Не все системные пакеты встали. Команда для ручной установки: sudo $INSTALL $PKGS"
elif [ -z "$INSTALL" ]; then
  warn "Менеджер пакетов не опознан. Поставьте сами: Python 3.10+, tkinter, venv, pip, espeak-ng."
else
  echo "всё на месте"
fi

command -v python3 >/dev/null 2>&1 || { warn "python3 не найден — установка остановлена."; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || { warn "Нужен Python 3.10+, а стоит $(python3 --version)."; exit 1; }
python3 -c 'import tkinter' 2>/dev/null || { warn "Нет tkinter (пакет python3-tk) — без него окно не откроется."; exit 1; }

say "[2/5] Папка программы .venv"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv || { warn "venv не создался (нужен пакет python3-venv)."; exit 1; }
fi
PY="$ROOT/.venv/bin/python"
"$PY" -m pip install --disable-pip-version-check -q --upgrade pip >/dev/null 2>&1

say "[3/5] Пакеты pip: Pillow, pypdf"
"$PY" -m pip install --disable-pip-version-check -q -r requirements.txt || warn "pip не смог поставить пакеты — программа запустится и без них."

if [ "$VOICE" = yes ]; then
  say "[4/5] Проверка произношения: vosk, sounddevice, модель"
  "$PY" -m pip install --disable-pip-version-check -q vosk sounddevice || warn "vosk/sounddevice не встали."
  "$PY" scripts/download_vosk_model.py || warn "Модель не скачалась — повторите: $PY scripts/download_vosk_model.py"
else
  say "[4/5] Проверка произношения — пропущено (--no-voice; можно позже: bash install.sh)"
fi

say "[5/5] Ярлык"
chmod +x run.sh
ICON="$ROOT/stamina/assets/star_typing_64.png"
DESK="[Desktop Entry]
Type=Application
Name=Star Typing
Comment=Тренажёр слепой печати, английского и скорочтения
Exec=\"$ROOT/run.sh\"
Path=$ROOT
Icon=$ICON
Terminal=false
Categories=Education;"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APPS" && printf '%s\n' "$DESK" > "$APPS/star-typing.desktop" && chmod +x "$APPS/star-typing.desktop"
echo "меню приложений: $APPS/star-typing.desktop"
DESKTOP_DIR="$(command -v xdg-user-dir >/dev/null 2>&1 && xdg-user-dir DESKTOP || echo "$HOME/Desktop")"
if [ -d "$DESKTOP_DIR" ]; then
  printf '%s\n' "$DESK" > "$DESKTOP_DIR/star-typing.desktop" && chmod +x "$DESKTOP_DIR/star-typing.desktop"
  command -v gio >/dev/null 2>&1 && gio set "$DESKTOP_DIR/star-typing.desktop" metadata::trusted true 2>/dev/null
  echo "рабочий стол: $DESKTOP_DIR/star-typing.desktop"
fi
touch .first_run_done

say "Готово! Запуск: ярлык «Star Typing» или ./run.sh"
if [ "$LAUNCH" = 1 ] && { [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; }; then
  nohup ./run.sh >/dev/null 2>&1 &
fi
