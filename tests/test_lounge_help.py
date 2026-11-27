# -*- coding: utf-8 -*-
"""Каркас справки Lounge / Орион: JSON, загрузчик, хуки F1/«?»."""
from __future__ import annotations

import inspect

from stamina.lounge.help_texts import (
    FILE_BY_GAME,
    load_help,
    load_overview,
    load_pack,
    level_ids,
)
from stamina.lounge.help_overlay import format_help_block, format_help_body


REQUIRED_LEVELS = {
    "docker_trainer": [
        "mission_1", "mission_2", "mission_3", "mission_4",
        "mission_5", "mission_6", "mission_7", "mission_8",
        "mission_9", "mission_10", "mission_11", "mission_12",
        "mission_13", "sandbox",
    ],
    "linux_trainer": [
        "mission_1", "mission_2", "mission_3", "mission_4",
        "mission_5", "mission_6", "mission_7", "mission_8",
        "mission_9", "mission_10", "mission_11", "mission_12", "sandbox",
    ],
    "powershell_trainer": [
        "mission_1", "mission_2", "mission_3", "mission_4",
        "mission_5", "mission_6", "mission_7", "mission_8",
        "mission_9", "mission_10", "mission_11", "mission_12",
        "mission_13", "sandbox",
    ],
    "vim_trainer": [
        "motion_basic", "motion_word", "motion_line",
        "delete_char", "delete_word", "delete_line",
        "change_mode", "change_operator", "visual_mode",
        "search_replace", "undo_redo", "repeat_count",
    ],
    "terraformer": [
        "stage_0", "stage_1", "stage_2", "stage_3",
        "stage_4", "stage_5", "stage_6", "stage_7",
    ],
    "orion": [
        "ru-01", "ru-02", "ru-03", "ru-04", "ru-05",
        "ru-06", "ru-07", "ru-08", "ru-09", "ru-10",
        "en-01", "en-02", "en-03", "en-04", "en-05",
        "en-06", "en-07", "en-08", "en-09", "en-10",
    ],
}

SIMPLE_GAMES = ("snake", "tetris", "breakout")
SECTION_KEYS = ("goal", "purpose", "interface")


def _assert_entry(entry: dict, where: str) -> None:
    assert isinstance(entry, dict), where
    for key in SECTION_KEYS:
        val = str(entry.get(key) or "").strip()
        assert val, f"{where}: пустое поле {key}"
    steps = entry.get("steps")
    assert isinstance(steps, list) and steps, f"{where}: steps должен быть непустым списком"
    assert str(steps[0]).strip(), f"{where}: пустой steps[0]"


def test_required_packs_parse_and_ids():
    for game, ids in REQUIRED_LEVELS.items():
        pack = load_pack(game)
        assert pack, f"нет пакета {game}"
        assert pack.get("game") == game
        ov = pack.get("overview")
        _assert_entry(ov, f"{game}.overview")
        assert ov.get("id") == "overview"
        got = level_ids(game)
        assert got == ids, f"{game}: ожидались {ids}, получено {got}"
        seen = set()
        for item in pack["levels"]:
            lid = item["id"]
            assert lid not in seen, f"{game}: повторяется id {lid}"
            seen.add(lid)
            _assert_entry(item, f"{game}.{lid}")
            assert str(item.get("title") or "").strip(), f"{game}.{lid}: пустой title"


def test_section_placeholders_unique_within_pack():
    """Пока тексты-заглушки, но уже уникальны — удобно подставлять и ловить копии."""
    for game in REQUIRED_LEVELS:
        pack = load_pack(game)
        blobs = []
        for item in [pack["overview"], *pack["levels"]]:
            blob = (item["goal"], item["purpose"], item["interface"], tuple(item["steps"]))
            assert blob not in blobs, f"{game}: одинаковые тексты у {item.get('id')}"
            blobs.append(blob)


def test_loader_current_level_and_fallback():
    data = load_help("docker_trainer", "mission_1")
    assert data["id"] == "mission_1"
    assert load_help("docker_trainer", "sandbox")["id"] == "sandbox"
    missing = load_help("docker_trainer", "no_such_mission")
    assert missing["id"] == "overview"
    none = load_help("docker_trainer", None)
    assert none["id"] == "overview"
    assert load_help("trainer", "stage_2")["id"] == "stage_2"
    assert load_help("terraformer", "stage_7")["id"] == "stage_7"
    assert load_help("orion", "ru-01")["id"] == "ru-01"
    assert load_help("orion", "en-10")["id"] == "en-10"
    assert load_overview("vim_trainer")["id"] == "overview"


def test_simple_games_have_overview_only():
    for game in SIMPLE_GAMES:
        pack = load_pack(game)
        assert pack.get("game") == game
        _assert_entry(pack["overview"], f"{game}.overview")
        assert pack.get("levels") == []
        assert load_help(game, None)["id"] == "overview"


def test_format_help_body_has_three_sections():
    data = load_help("docker_trainer", "mission_3")
    body = format_help_body(data)
    assert "Что нужно сделать" in body
    assert "Зачем эта игра" in body
    assert "Интерфейс" in body
    assert "1. " in body
    block = format_help_block(data, heading="Текущая миссия")
    assert "Текущая миссия" in block
    assert data["title"] in block


def test_gameshell_exposes_help_hooks():
    from stamina.lounge.base import GameShell
    assert callable(GameShell.on_help)
    assert callable(GameShell.handle_help_keys)
    assert callable(GameShell.help_level_id)
    assert callable(GameShell.help_game_id)
    init = inspect.getsource(GameShell.__init__)
    assert "btn_help" in init
    assert "HelpOverlay" in init
    assert "handle_help_keys" in inspect.getsource(GameShell.on_key)
    # не снимаем глобальный Escape
    from stamina.lounge import help_overlay as ho
    src = inspect.getsource(ho)
    assert "unbind_all(" not in src
    assert ".bind_all(" not in src


def test_game_classes_expose_on_help_and_level_ids():
    from stamina.lounge.base import GameShell
    from stamina.lounge.docker_trainer import DockerTrainerGame
    from stamina.lounge.vim_trainer import VimTrainerGame
    from stamina.lounge.trainer import TrainerGame
    from stamina.lounge.snake import SnakeGame
    from stamina.lounge.tetris import TetrisGame
    from stamina.lounge.breakout import BreakoutGame

    for cls in (DockerTrainerGame, VimTrainerGame, TrainerGame, SnakeGame, TetrisGame, BreakoutGame):
        assert issubclass(cls, GameShell)
        assert callable(getattr(cls, "on_help"))

    assert "help_level_id" in DockerTrainerGame.__dict__
    assert "help_level_id" in VimTrainerGame.__dict__
    assert "help_level_id" in TrainerGame.__dict__
    assert "help_game_id" in TrainerGame.__dict__
    src = inspect.getsource(TrainerGame.help_game_id)
    assert "terraformer" in src
    assert "handle_help_keys" in inspect.getsource(DockerTrainerGame.on_key)
    assert "handle_help_keys" in inspect.getsource(VimTrainerGame.on_key)
    assert "handle_help_keys" in inspect.getsource(TrainerGame.on_key)


def test_page_help_reuses_dialog_and_injects_orion():
    from stamina import page_help

    sig = inspect.signature(page_help.content_for)
    assert "app" in sig.parameters
    title, body = page_help.content_for("bridge")
    assert title and body
    # без app не подмешиваем заглушки миссии
    assert "TODO orion" not in body

    class _Bridge:
        meta = {"mode": "mission", "mission": {"id": "ru-01", "title": "Стыковка"}}

    class _App:
        screens = {"bridge": _Bridge()}
        current = "bridge"

    title2, body2 = page_help.content_for("bridge", app=_App())
    assert title2 == title
    assert "Обзор" in body2
    assert "Текущая миссия" in body2
    assert "Стыковка" in body2
    assert "а и о" in body2 and "50 знаков" in body2
    # не второй тип модалки
    assert "HelpOverlay" not in inspect.getsource(page_help.open_page_help)
    # cargo/другие ключи не получают вставку
    _, cargo = page_help.content_for("cargo", app=_App())
    assert "TODO orion ru-01" not in cargo


def test_file_map_covers_shell_ids():
    for gid in ("docker_trainer", "linux_trainer", "powershell_trainer",
                "vim_trainer", "trainer", "terraformer",
                "orion", "bridge", "snake", "tetris", "breakout"):
        assert gid in FILE_BY_GAME, gid
