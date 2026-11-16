"""Предварительная редакция снимка: обрезка рамкой, поворот, запись на борт."""
from __future__ import annotations

from pathlib import Path

import pytest


def _png(path: Path, size=(120, 80)) -> Path:
    from PIL import Image
    Image.new("RGB", size, (30, 60, 90)).save(path)
    return path


def test_editor_crops_rotates_and_saves(tmp_path, monkeypatch) -> None:
    tk = pytest.importorskip("tkinter")
    pytest.importorskip("PIL")
    monkeypatch.setenv("STAR_TYPING_SHOTS_DIR", str(tmp_path / "shots"))
    src = _png(tmp_path / "src.png")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    root.withdraw()
    from stamina.shot_editor import ShotEditor

    editor = ShotEditor(root, str(src))
    try:
        root.update_idletasks()
        editor._coords = (10, 10, 60, 40)
        editor.crop()
        assert editor.image.size == (50, 30)

        editor.rotate()
        assert editor.image.size == (30, 50)

        results: list = []
        editor.on_done = results.append
        editor.apply()
        assert results and results[0], "редактор должен вернуть путь нового файла"
        assert Path(results[0]).is_file()
        assert not src.exists(), "исходный снимок после «Применить» уходит с борта"
    finally:
        root.destroy()


def test_editor_drop_returns_empty(tmp_path) -> None:
    tk = pytest.importorskip("tkinter")
    pytest.importorskip("PIL")
    src = _png(tmp_path / "src.png")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    root.withdraw()
    from stamina.shot_editor import ShotEditor

    editor = ShotEditor(root, str(src))
    try:
        results: list = []
        editor.on_done = results.append
        editor.drop()
        assert results == [""], "пустой результат = снять снимок с сообщения"
        assert not src.exists()
    finally:
        root.destroy()


def test_crop_needs_selection(tmp_path) -> None:
    tk = pytest.importorskip("tkinter")
    pytest.importorskip("PIL")
    src = _png(tmp_path / "src.png")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    root.withdraw()
    from stamina.shot_editor import ShotEditor

    editor = ShotEditor(root, str(src))
    try:
        before = editor.image.size
        editor.crop()
        assert editor.image.size == before, "без рамки ничего не режем"
    finally:
        root.destroy()
