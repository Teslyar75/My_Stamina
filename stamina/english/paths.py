"""Где лежат данные модуля «Английский».

Пакет stamina/english входит в Star Typing. Словарь лежит рядом с кодом: data/vocab.json
(или data/vocab.json.gz). Модель Vosk не хранится в репозитории: её скачивает
scripts/download_vosk_model.ps1 в папку models/ в корне проекта.
Прогресс хранится рядом с данными Star Typing: %APPDATA%\\Stamina\\english.json.
"""
from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent.parent          # корень Star Typing (там main.py)
DATA_DIR = PACKAGE_DIR / "data"
VOCAB_PATH = DATA_DIR / "vocab.json"
VOCAB_GZ_PATH = DATA_DIR / "vocab.json.gz"
SAMPLE_PATH = PACKAGE_DIR / "sample_vocab.json"
MODELS_DIR = Path(os.environ.get("STAR_TYPING_MODELS") or (PROJECT_DIR / "models"))


def vocab_file() -> Path:
    for p in (VOCAB_PATH, VOCAB_GZ_PATH):
        if p.exists():
            return p
    return SAMPLE_PATH


def stamina_data_dir() -> Path:
    try:
        from stamina.storage import DATA_DIR as ST_DIR  # тот же каталог, что у Star Typing
        return Path(ST_DIR)
    except Exception:
        from stamina.pilots import default_root
        return default_root()


PROGRESS_PATH = stamina_data_dir() / "english.json"


def vosk_model_dir() -> Path | None:
    if not MODELS_DIR.exists():
        return None
    for p in sorted(MODELS_DIR.iterdir()):
        if p.is_dir() and p.name.startswith("vosk-model") and (p / "am").exists():
            return p
    return None
