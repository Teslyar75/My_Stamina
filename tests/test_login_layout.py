"""Окно входа: выбор вида интерфейса (классика / Пульт-кабина) — тот же ключ ui_layout,
что и в Настройках, хранится в settings.json пилота (как скин)."""
from pathlib import Path

from stamina import alt_ui, pilots
from stamina.pilot_screens import LoginScreen


class _Fake:
    _pilot_settings = LoginScreen._pilot_settings
    _save_pilot_layout = LoginScreen._save_pilot_layout
    _load_layout = LoginScreen._load_layout


def test_layout_saved_per_pilot(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(pilots, "pilot_dir", lambda pid: tmp_path / pid)
    (tmp_path / "p1").mkdir()
    pilots.write_json(tmp_path / "p1" / "settings.json", {"skin": "steampunk"})
    f = _Fake()
    f._load_layout("p1")
    assert f._layout_id == "classic"
    f._save_pilot_layout("p1", "alt")
    data = pilots.read_json(tmp_path / "p1" / "settings.json")
    assert data == {"skin": "steampunk", "ui_layout": "alt"}
    f._load_layout("p1")
    assert f._layout_id == "alt" == alt_ui.layout_of(data)


def test_login_has_layout_toggle():
    src = Path(__file__).resolve().parents[1].joinpath("stamina", "pilot_screens.py").read_text(encoding="utf-8")
    assert "_layout_btns" in src and '"ui_layout"' in src
