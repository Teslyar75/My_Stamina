# Скачать модель Vosk для вкладки «АНГЛИЙСКИЙ» и поставить библиотеки распознавания речи.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
python -m pip install --user vosk sounddevice
python (Join-Path $root "scripts\download_vosk_model.py")
