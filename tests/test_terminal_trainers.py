# -*- coding: utf-8 -*-
"""Тренажёры Linux и PowerShell: миссии проходятся, учебник несёт теорию.

Проверяем то, что легко сломать при правке данных: у каждой миссии есть
команды, которые симулятор действительно понимает; каждая тема учебника
объясняет себя (тезисы теории + вступление); панель F2 показывает теорию
той темы, которую выбрал игрок, а не первую попавшуюся.
"""
from __future__ import annotations

import pytest

from stamina.lounge import docker_reference, linux_reference, powershell_reference
from stamina.lounge.docker_trainer import MISSIONS as DOCKER_MISSIONS
from stamina.lounge.linux_trainer import LINUX_MISSIONS
from stamina.lounge.powershell_trainer import POWERSHELL_MISSIONS
from stamina.lounge.terminal_sim import FakeTerminalSimulator

#: (название, миссии, учебник) — одна таблица на оба терминальных тренажёра.
TRAINERS = (
    ("linux", LINUX_MISSIONS, linux_reference),
    ("powershell", POWERSHELL_MISSIONS, powershell_reference),
)


def _fallback(sim: FakeTerminalSimulator, cmd: str) -> bool:
    """Симулятор отвечает заглушкой «Запрос принят» — значит команду он не знает."""
    out, _code = sim.execute(cmd)
    return out.startswith("Запрос принят")


@pytest.mark.parametrize("name,missions,reference", TRAINERS)
class TestMissions:
    def test_missions_are_well_formed(self, name, missions, reference):
        ids = [m["id"] for m in missions]
        assert len(ids) == len(set(ids)), f"{name}: повторяются id миссий"
        for mission in missions:
            assert mission["title"].strip(), f"{name}: пустой title"
            assert mission["hint"].strip(), f"{name}.{mission['id']}: пустая подсказка"
            assert mission["desc"].strip(), f"{name}.{mission['id']}: пустое описание"
            assert isinstance(mission["xp"], int) and mission["xp"] > 0
            assert isinstance(mission["expected"], list)
            assert callable(mission["check"])

    def test_every_mission_is_completable(self, name, missions, reference):
        sim = FakeTerminalSimulator()
        for idx, mission in enumerate(missions, 1):
            out = ""
            for cmd in mission["expected"]:
                out, code = sim.execute(cmd)
                assert code == 0, (name, idx, cmd, out)
            assert mission["check"](sim, out), \
                f"{name}: миссия {idx} не засчитывается: {mission['title']}"

    def test_mission_commands_are_understood(self, name, missions, reference):
        """Подсказка миссии должна работать на учебном стенде, а не «в реальном». """
        sim = FakeTerminalSimulator()
        for mission in missions:
            for cmd in mission["expected"]:
                assert not _fallback(sim, cmd), \
                    f"{name}.{mission['id']}: симулятор не знает «{cmd}»"

    def test_sandbox_is_last_and_free(self, name, missions, reference):
        last = missions[-1]
        assert last["id"] == "sandbox"
        assert last["expected"] == []
        assert last["check"](FakeTerminalSimulator(), "")

    def test_missions_are_numbered_in_order(self, name, missions, reference):
        numbered = [m for m in missions if m["id"] != "sandbox"]
        for idx, mission in enumerate(numbered, 1):
            assert mission["id"] == f"mission_{idx}", mission["id"]
            assert mission["title"].startswith(f"Миссия {idx}:"), mission["title"]


@pytest.mark.parametrize("name,missions,reference", TRAINERS)
class TestReference:
    def test_topics_have_theory(self, name, missions, reference):
        topics = reference.topics()
        assert len(topics) >= 8, f"{name}: слишком мало тем"
        for topic in topics:
            assert topic["title"].strip(), topic["id"]
            assert topic["blurb"].strip(), topic["id"]
            theory = topic.get("theory") or []
            assert len(theory) >= 2, f"{name}.{topic['id']}: теории меньше двух тезисов"
            for line in theory:
                assert str(line).strip(), topic["id"]

    def test_commands_have_all_fields(self, name, missions, reference):
        seen = set()
        for item in reference.commands():
            assert item["cmd"].strip() and item["desc"].strip() and item["example"].strip()
            assert isinstance(item["sim"], bool)
            assert item["cmd"] not in seen, f"{name}: дубль команды {item['cmd']}"
            seen.add(item["cmd"])

    def test_sim_commands_are_understood(self, name, missions, reference):
        sim = FakeTerminalSimulator()
        for item in reference.supported():
            assert not _fallback(sim, item["cmd"]), \
                f"{name}: отмечена исполняемой, но не работает: {item['cmd']}"

    def test_completions_are_unique_and_nonempty(self, name, missions, reference):
        heads = reference.completions()
        assert heads
        assert len(heads) == len(set(heads))

    def test_search_finds_by_text(self, name, missions, reference):
        assert reference.search("") == reference.commands()
        assert not reference.search("нет-такой-команды-никогда")

    def test_panel_title_names_the_shell(self, name, missions, reference):
        title = reference.PANEL_TITLE.upper()
        assert name.upper() in title
        assert reference.SIM_HINT.strip()
        assert reference.REAL_HINT.strip()


class TestDockerMissions:
    """Docker уже покрыт своим тестом — здесь только связь миссий и учебника."""

    def test_missions_are_numbered_and_end_with_sandbox(self):
        ids = [m["id"] for m in DOCKER_MISSIONS]
        assert ids == [f"mission_{i}" for i in range(1, 14)] + ["sandbox"]

    def test_every_mission_is_completable(self):
        from stamina.lounge.docker_sim import DockerSimulator

        sim = DockerSimulator()
        for idx, mission in enumerate(DOCKER_MISSIONS, 1):
            out = ""
            for cmd in mission["expected"]:
                out, code = sim.execute(cmd)
                assert code == 0, (idx, cmd, out)
            assert mission["check"](sim, out), f"миссия {idx}: {mission['title']}"

    def test_every_topic_has_theory(self):
        for topic in docker_reference.topics():
            theory = topic.get("theory") or []
            assert len(theory) >= 2, f"тема {topic['id']} без теории"
            assert topic.get("blurb"), topic["id"]


@pytest.fixture
def tk_root():
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    root.geometry("900x420")
    root.update()
    yield root
    root.destroy()


@pytest.mark.parametrize("name,reference", (
    ("linux", linux_reference),
    ("powershell", powershell_reference),
    ("docker", docker_reference),
))
class TestReferencePanel:
    """Панель F2 показывает теорию выбранной темы, а не первую попавшуюся."""

    def _panel(self, root, reference):
        from stamina.lounge.docker_ref_panel import DockerReferencePanel

        panel = DockerReferencePanel(root, ref_source=reference,
                                     on_insert=lambda _c: None,
                                     on_run=lambda _c: None,
                                     on_close=lambda: None)
        panel.pack(fill="both", expand=True)
        root.update()
        return panel

    def test_theory_matches_selected_topic(self, tk_root, name, reference):
        panel = self._panel(tk_root, reference)
        try:
            first = reference.topics()[0]
            assert first["blurb"] in panel.visible_theory()
            for topic in reference.topics():
                panel.select_topic(topic["id"])
                tk_root.update()
                text = panel.visible_theory()
                assert topic["blurb"] in text, f"{name}.{topic['id']}: нет вступления"
                for line in topic["theory"]:
                    assert line in text, f"{name}.{topic['id']}: нет тезиса «{line}»"
        finally:
            panel.destroy()

    def test_search_keeps_theory_of_open_topic(self, tk_root, name, reference):
        panel = self._panel(tk_root, reference)
        try:
            topic = reference.topics()[-1]
            panel.select_topic(topic["id"])
            panel.var_query.set("zzz-ничего-нет")
            tk_root.update()
            assert topic["blurb"] in panel.visible_theory()
            panel.var_query.set("")
            tk_root.update()
            assert topic["blurb"] in panel.visible_theory()
        finally:
            panel.destroy()


def test_lobby_counts_missions_itself():
    """Подпись в лобби берёт число миссий из класса, а не из захардкоженного текста."""
    from stamina.lounge.screen import GAMES

    by_id = {game["id"]: game for game in GAMES}
    for gid in ("docker_trainer", "linux_trainer", "powershell_trainer"):
        entry = by_id[gid]
        # песочница — режим, а не миссия: в подписи только настоящие задания
        count = len([m for m in entry["cls"].missions if m["id"] != "sandbox"])
        assert str(count) in entry["subtitle"], (gid, entry["subtitle"])
        assert "8 МИССИЙ" not in entry["subtitle"].upper() or count == 8
