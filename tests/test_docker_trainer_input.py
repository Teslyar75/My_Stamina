"""Docker-тренажёр: набираются пробел и знаки, Backspace стирает, есть учебник.

Раньше символ брался из ``event.keysym``, а у пробела и у «-», «/», «:» он
многословный («space», «minus», «slash», «colon») — ввод команд был невозможен.
Backspace глобальная навигация забирала себе и уводила из игры в лобби.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from stamina import pilots
from stamina.lounge import docker_reference as ref
from stamina.lounge import store
from stamina.lounge.docker_trainer import MISSIONS, typed_char
from stamina.lounge.screen import LoungeScreen
from stamina.nav_back import backspace_edits_text, screen_edits_text


def _key(sym: str, char: str = "", state: int = 0, widget=None):
    return SimpleNamespace(keysym=sym, char=char, state=state, widget=widget)


class TestTypedChar:
    """Символ для командной строки берётся из event.char."""

    @pytest.mark.parametrize("sym,char,want", [
        ("space", " ", " "),
        ("minus", "-", "-"),
        ("slash", "/", "/"),
        ("colon", ":", ":"),
        ("period", ".", "."),
        ("underscore", "_", "_"),
        ("d", "d", "d"),
        ("D", "D", "D"),
        ("4", "4", "4"),
        ("Cyrillic_ef", "ф", "ф"),
    ])
    def test_printable_keys(self, sym, char, want):
        assert typed_char(_key(sym, char)) == want

    @pytest.mark.parametrize("sym,char", [
        ("Return", "\r"),
        ("KP_Enter", "\r"),
        ("Tab", "\t"),
        ("BackSpace", "\x08"),
        ("Escape", "\x1b"),
        ("Up", ""),
        ("Control_L", ""),
        ("F1", ""),
    ])
    def test_service_keys_give_nothing(self, sym, char):
        assert typed_char(_key(sym, char)) == ""

    def test_no_char_attribute(self):
        assert typed_char(SimpleNamespace(keysym="a")) == ""


class _Screen:
    def __init__(self, edits: bool) -> None:
        self.edits = edits

    def backspace_edits(self) -> bool:
        return self.edits


class TestScreenEditsText:
    """Экран может сам попросить Backspace для правки текста."""

    def test_screen_asks_for_backspace(self):
        app = SimpleNamespace(current="lounge", screens={"lounge": _Screen(True)})
        assert screen_edits_text(app)
        assert backspace_edits_text(app, _key("BackSpace", "\x08"))

    def test_screen_without_hook_does_not(self):
        app = SimpleNamespace(current="lounge", screens={"lounge": SimpleNamespace()})
        assert not screen_edits_text(app)
        assert not backspace_edits_text(app, _key("BackSpace", "\x08"))

    def test_screen_off_keeps_global_backspace(self):
        app = SimpleNamespace(current="lounge", screens={"lounge": _Screen(False)})
        assert not screen_edits_text(app)
        assert not backspace_edits_text(app, _key("BackSpace", "\x08"))

    def test_flag_instead_of_method(self):
        app = SimpleNamespace(current="lounge",
                              screens={"lounge": SimpleNamespace(backspace_edits=True)})
        assert screen_edits_text(app)

    def test_broken_hook_is_not_fatal(self):
        class Bad:
            def backspace_edits(self):
                raise RuntimeError("экран сломан")

        app = SimpleNamespace(current="lounge", screens={"lounge": Bad()})
        assert not screen_edits_text(app)

    def test_no_screens(self):
        assert not screen_edits_text(SimpleNamespace(current="lounge", screens=None))

    def test_other_screens_are_untouched(self):
        """Вне игры Backspace выходит из отсека, как и раньше."""
        app = SimpleNamespace(current="english", screens={"english": _Screen(False)})
        assert not backspace_edits_text(app, _key("BackSpace", "\x08"))


class TestLoungeBackspace:
    """Экран «Отдых» отдаёт Backspace игре только по её просьбе."""

    def test_in_game_with_tick(self):
        fake = SimpleNamespace(game=SimpleNamespace(backspace_edits=True))
        assert LoungeScreen.backspace_edits(fake) is True

    def test_in_game_without_tick(self):
        fake = SimpleNamespace(game=SimpleNamespace(backspace_edits=False))
        assert LoungeScreen.backspace_edits(fake) is False

    def test_lobby(self):
        assert LoungeScreen.backspace_edits(SimpleNamespace(game=None)) is False


class TestStoreSetting:
    def setup_method(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._root = Path(self._tmp.name) / "Stamina"
        self._root.mkdir()
        pilots.reset_root(self._root)

    def teardown_method(self):
        pilots.reset_root()
        self._tmp.cleanup()

    def test_default_is_on(self):
        assert store.setting("backspace_edits", True) is True

    def test_roundtrip(self):
        store.set_setting("backspace_edits", False)
        assert store.setting("backspace_edits", True) is False
        assert store.load()["settings"]["backspace_edits"] is False
        store.set_setting("backspace_edits", True)
        assert store.setting("backspace_edits", True) is True

    def test_broken_settings_do_not_crash(self):
        (self._root / "lounge.json").write_text('{"settings": "чепуха"}', encoding="utf-8")
        assert store.setting("backspace_edits", True) is True


class TestMissions:
    """Каждая миссия засчитывается своими же командами — иначе тренажёр не пройти."""

    def test_every_mission_is_completable(self):
        from stamina.lounge.docker_sim import DockerSimulator

        sim = DockerSimulator()
        for idx, mission in enumerate(MISSIONS, 1):
            out = ""
            for cmd in mission["expected"]:
                out, code = sim.execute(cmd)
                assert code == 0, (idx, cmd, out)
            assert mission["check"](sim, out), f"миссия {idx} не засчитывается: {mission['title']}"

    def test_mission_one_tick_matches_generated_name(self):
        from stamina.lounge.docker_sim import DockerSimulator

        sim = DockerSimulator()
        out, _code = sim.execute("docker run -d ship/radio")
        assert MISSIONS[0]["check"](sim, out)


HANDLERS = (
    "run", "ps", "logs", "stop", "rm", "images", "pull", "build", "port",
    "volume", "network", "compose", "system", "image", "container",
)


class TestReference:
    """Учебник: данные полные, а отметка «выполняется» не врёт."""

    def test_topics_are_present(self):
        topics = ref.topics()
        assert len(topics) >= 8, "тем должно быть не меньше восьми"
        ids = [t["id"] for t in topics]
        assert len(ids) == len(set(ids)), "id тем повторяются"
        for topic in topics:
            assert topic["title"] and topic["blurb"], topic["id"]
            assert topic["commands"], f"в теме {topic['id']} нет команд"

    def test_commands_have_all_fields(self):
        assert ref.total() >= 80, "учебник должен быть основательным"
        seen = set()
        for item in ref.commands():
            assert item["cmd"] and item["desc"] and item["example"], item["cmd"]
            assert isinstance(item["sim"], bool), item["cmd"]
            assert item["cmd"] not in seen, f"дубль команды: {item['cmd']}"
            seen.add(item["cmd"])

    def test_sim_commands_map_to_simulator_handlers(self):
        from stamina.lounge.docker_sim import DockerSimulator

        items = [c for c in ref.commands() if c["sim"]]
        assert items, "ничего не отмечено как исполняемое в тренажёре"
        for item in items:
            words = item["cmd"].split()
            group = words[1] if len(words) > 1 else words[0]
            assert group in HANDLERS, f"не тот учебник для тренажёра: {item['cmd']}"
            if group == "compose":
                assert hasattr(DockerSimulator, "cmd_compose_" + words[2])
            elif group in ("volume", "network", "system", "image", "container"):
                assert hasattr(DockerSimulator, f"cmd_{group}_{words[2]}")
            elif group != "docker":
                assert hasattr(DockerSimulator, "cmd_" + group), item["cmd"]

    def test_commands_are_docker_commands(self):
        for item in ref.commands():
            head = item["cmd"].split()[0]
            assert head == "docker" or head.upper() in (
                "FROM", "WORKDIR", "COPY", "ADD", "RUN", "CMD", "ENTRYPOINT",
                "EXPOSE", "ENV", "ARG", "VOLUME", "USER", "HEALTHCHECK", "LABEL",
            ), item["cmd"]

    def test_search_filters_everything(self):
        found = ref.search("volume")
        assert found and all("volume" in (c["cmd"] + c["desc"]).lower() for c in found)
        assert ref.search("") == ref.commands()
        assert not ref.search("нет-такой-команды-никогда")

    def test_search_stays_inside_topic(self):
        found = ref.search("run", topic_id="containers")
        assert found and all("run" in (c["cmd"] + c["desc"]).lower() for c in found)

    def test_completions_come_from_textbook(self):
        heads = ref.completions()
        assert "docker run" in heads and "docker compose" in heads
        assert len(heads) == len(set(heads))


@pytest.fixture
def game():
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    root.geometry("900x360")
    root.update()
    tmp = tempfile.TemporaryDirectory()
    pilots.reset_root(Path(tmp.name) / "Stamina")
    from stamina.lounge.docker_trainer import DockerTrainerGame

    try:
        g = DockerTrainerGame(root, on_back=lambda: None, app=None)
        g.pack(fill=tk.BOTH, expand=True)
        g.start()
        root.update()
        yield g
        g.stop()
    finally:
        pilots.reset_root()
        tmp.cleanup()
        root.destroy()


def _type(game, text: str) -> None:
    for ch in text:
        sym = {" ": "space", "-": "minus", "/": "slash", ":": "colon",
               ".": "period", "_": "underscore"}.get(ch, ch)
        game.on_key(_key(sym, ch))


class TestGameInput:
    """Живая игра: команда набирается целиком, Backspace стирает по символу."""

    def test_mission_command_is_typed(self, game):
        _type(game, "docker run -d ship/radio")
        assert game.command_buffer == "docker run -d ship/radio"

    def test_ports_and_name(self, game):
        _type(game, "docker run -d -p 9000:9000 --name my_orion ship/orion")
        assert game.command_buffer == "docker run -d -p 9000:9000 --name my_orion ship/orion"

    def test_backspace_erases_one_char(self, game):
        _type(game, "docker ru")
        game.on_key(_key("BackSpace", "\x08"))
        assert game.command_buffer == "docker r"
        game.on_key(_key("BackSpace", "\x08"))
        game.on_key(_key("BackSpace", "\x08"))
        assert game.command_buffer == "docker"

    def test_backspace_on_empty_is_harmless(self, game):
        game.on_key(_key("BackSpace", "\x08"))
        assert game.command_buffer == ""

    def test_game_asks_backspace_for_itself(self, game):
        assert game.text_input is True
        assert game.backspace_edits is True
        assert LoungeScreen.backspace_edits(SimpleNamespace(game=game)) is True

    def test_checkbox_off_returns_backspace_to_navigation(self, game):
        assert game.var_backspace is not None
        game.var_backspace.set(False)
        game._on_backspace_toggle()
        assert game.backspace_edits is False
        assert LoungeScreen.backspace_edits(SimpleNamespace(game=game)) is False
        assert store.setting("backspace_edits", True) is False

    def test_enter_runs_command_and_clears_line(self, game):
        _type(game, "docker images")
        game.on_key(_key("Return", "\r"))
        assert game.command_buffer == ""
        assert any("$ docker images" in text for text, _color in game.output_lines)

    def test_input_box_is_three_lines(self, game):
        in_top, in_bot, term_h = game._input_box(360)
        assert in_bot - in_top >= 58, "строка ввода должна быть выше прежней"
        assert term_h > 100, "терминалу должно остаться место"


class TestReferencePanel:
    """Учебник внутри игры: открывается, фильтрует, кладёт команду в строку."""

    def test_f2_opens_and_closes(self, game):
        assert not game.reference_open()
        game.on_key(_key("F2"))
        game.winfo_toplevel().update()
        assert game.reference_open()
        assert game.ref_panel is not None
        game.on_key(_key("F2"))
        game.winfo_toplevel().update()
        assert not game.reference_open()

    def test_topics_and_commands_are_listed(self, game):
        game.toggle_reference()
        panel = game.ref_panel
        assert panel.topics.keys() == [t["id"] for t in ref.topics()]
        assert len(panel.visible_commands()) >= 5

    def test_search_filters_commands(self, game):
        game.toggle_reference()
        panel = game.ref_panel
        panel.set_query("volume")
        assert panel.visible_commands()
        assert all("volume" in cmd.lower() for cmd in panel.visible_commands())
        panel.set_query("нет-такой-команды")
        assert panel.visible_commands() == []

    def test_topic_switch_resets_query(self, game):
        game.toggle_reference()
        panel = game.ref_panel
        panel.set_query("compose")
        panel.select_topic("networks")
        assert panel.var_query.get() == ""
        assert panel.visible_commands()

    def test_insert_puts_command_into_line(self, game):
        game.toggle_reference()
        panel = game.ref_panel
        panel.select_topic("containers")
        panel.select_command("docker run -d ship/radio")
        panel.insert_selected()
        assert game.command_buffer == "docker run -d ship/radio"
        assert not game.reference_open()

    def test_run_executes_command(self, game):
        game.toggle_reference()
        panel = game.ref_panel
        panel.select_command("docker images")
        panel.run_selected()
        assert not game.reference_open()
        assert any("$ docker images" in text for text, _color in game.output_lines)

    def test_typing_is_ignored_while_open(self, game):
        game.toggle_reference()
        game.winfo_toplevel().update()
        game.command_buffer = ""
        _type(game, "docker ps")
        assert game.command_buffer == ""
        game.on_key(_key("Escape", "\x1b"))
        game.winfo_toplevel().update()
        assert not game.reference_open()


class TestSandboxMode:
    def test_checkbox_switches_free_mode(self, game):
        assert game.var_sandbox is not None
        game.var_sandbox.set(True)
        game._on_sandbox_toggle()
        assert game.sandbox_mode is True
        # в свободном режиме миссии не засчитываются, но симулятор работает
        _type(game, "docker run -d ship/radio")
        game.on_key(_key("Return", "\r"))
        assert 0 not in game.completed_missions
        game.var_sandbox.set(False)
        game._on_sandbox_toggle()
        assert game.sandbox_mode is False

    def test_free_mode_survives_reopen(self, game):
        game.var_sandbox.set(True)
        game._on_sandbox_toggle()
        game.save_progress()
        from stamina.lounge.docker_trainer import DockerTrainerGame

        root = game.winfo_toplevel()
        second = DockerTrainerGame(root, on_back=lambda: None, app=None)
        try:
            assert second.var_sandbox.get() is True
        finally:
            second.destroy()
