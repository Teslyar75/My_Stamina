"""Скачать малую английскую модель Vosk (Apache 2.0, ~40 МБ) в папку models/ проекта.

Запуск:  python scripts/download_vosk_model.py
Модель нужна только для проверки произношения во вкладке «АНГЛИЙСКИЙ».
Без неё вкладка работает, а говорение переходит на самооценку.
"""
from __future__ import annotations

import sys
import urllib.request
import zipfile
from pathlib import Path

NAME = "vosk-model-small-en-us-0.15"
URL = f"https://alphacephei.com/vosk/models/{NAME}.zip"
MODELS = Path(__file__).resolve().parent.parent / "models"


def main() -> int:
    target = MODELS / NAME
    if (target / "am").exists():
        print(f"Модель уже есть: {target}")
        return 0
    MODELS.mkdir(parents=True, exist_ok=True)
    tmp = MODELS / f"{NAME}.zip"
    print(f"Скачиваю {URL} ...")
    urllib.request.urlretrieve(URL, tmp)
    print("Распаковываю ...")
    with zipfile.ZipFile(tmp) as z:
        z.extractall(MODELS)
    tmp.unlink()
    print(f"Готово: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
