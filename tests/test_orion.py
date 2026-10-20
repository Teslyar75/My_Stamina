"""ОРИОН: слой данных (stamina/orion.py) и экран раздела.

Данные проверяются без Tk; экран — на настоящем Tk во временной папке данных
(без дисплея тесты экрана пропускаются). Вызов агента проверяется на подставном
CLI: подменяем переменной окружения, поэтому живой OpenCode и сеть не нужны.
"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from stamina import i18n, orion, owner_key, pilots


def _events(*lines) -> str:
    return "\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n"


class OrionDataTest(unittest.TestCase):
    """Реестр пассажиров, история, документ заданий, понимание речи."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        pilots.reset_root(Path(self._tmp))

    def tearDown(self):
        pilots.reset_root()

    # -- реестр ------------------------------------------------------------
    def test_orion_is_always_aboard(self):
        reg = orion.registry()
        self.assertEqual([a["id"] for a in reg["agents"]], ["orion"])
        self.assertEqual(reg["active"], "orion")
        self.assertEqual(orion.active()["name"], "Орион")
        self.assertEqual(orion.active()["access"], "commander")
        self.assertFalse(orion.agents_path().exists())     # до заселения файла нет

    def test_upsert_and_make_active(self):
        rec = orion.upsert({"name": "Сова", "access": "crew", "note": "советчик"})
        self.assertEqual(rec["id"], "сова")               # id делается из имени
        self.assertEqual([a["id"] for a in orion.agents()], ["orion", "сова"])
        self.assertEqual(rec["access"], "crew")
        self.assertTrue(orion.set_active("сова"))
        self.assertEqual(orion.active()["id"], "сова")
        self.assertFalse(orion.set_active("нет-такого"))
        self.assertEqual(orion.active()["id"], "сова")     # отказ ничего не сломал

    def test_upsert_gives_unique_id(self):
        first = orion.upsert({"name": "Сова"})
        second = orion.upsert({"name": "Сова"})
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(len(orion.agents()), 3)

    # -- привязка агента -------------------------------------------------------
    def test_save_and_read_binding(self):
        orion.upsert({"name": "Сова", "access": "commander"})
        orion.save_binding("сова", opencode_token="oc_token_123",
                           github_token="gh_token_456")
        data = orion.read_binding("сова")
        self.assertEqual(data.get("opencode_token"), "oc_token_123")
        self.assertEqual(data.get("github_token"), "gh_token_456")
        self.assertTrue(data.get("updated", 0) > 0)

    def test_clear_binding(self):
        orion.upsert({"name": "Сова", "access": "crew"})
        orion.save_binding("сова", opencode_token="oc_token")
        orion.clear_binding("сова")
        self.assertEqual(orion.read_binding("сова"), {})
        self.assertFalse(orion.binding_path("сова").exists())

    def test_binding_status_crew(self):
        """Экипажу нужен только OpenCode токен — GitHub не проверяем."""
        orion.upsert({"name": "Сова", "access": "crew"})
        status = orion.binding_status("сова")
        self.assertFalse(status["linked"])
        self.assertFalse(status["access_ok"])
        orion.save_binding("сова", opencode_token="oc_token")
        status = orion.binding_status("сова")
        self.assertTrue(status["linked"])
        self.assertTrue(status["opencode"])
        self.assertFalse(status["github"])
        self.assertTrue(status["access_ok"])

    def test_binding_status_commander(self):
        """Командиру нужны и OpenCode, и GitHub токены."""
        orion.upsert({"name": "Сова", "access": "commander"})
        orion.save_binding("сова", opencode_token="oc_token")
        status = orion.binding_status("сова")
        self.assertTrue(status["linked"])
        self.assertFalse(status["access_ok"])
        orion.save_binding("сова", opencode_token="oc_token",
                           github_token="gh_token")
        status = orion.binding_status("сова")
        self.assertTrue(status["access_ok"])
        self.assertTrue(status["github"])

    def test_make_boarding_code(self):
        code = orion.make_boarding_code()
        self.assertEqual(len(code), 8)
        self.assertTrue(code.isupper())
        self.assertNotEqual(code, orion.make_boarding_code())

    # -- радио и библиотека ---------------------------------------------------
    def test_radio_functions(self):
        """Орион имеет доступ к радиорубке."""
        stations = orion.radio_stations()
        self.assertIsInstance(stations, list)
        current = orion.radio_current()
        self.assertIn("station", current)
        self.assertIn("playing", current)

    def test_library_functions(self):
        """Орион имеет доступ к библиотеке."""
        books = orion.library_books()
        self.assertIsInstance(books, list)
        words = orion.english_words()
        self.assertIsInstance(words, list)

    def test_save_binding_trims_and_limits(self):
        orion.upsert({"name": "Сова", "access": "crew"})
        long_token = "x" * 300
        orion.save_binding("сова", opencode_token=long_token)
        data = orion.read_binding("сова")
        self.assertEqual(len(data["opencode_token"]), 200)

    # -- эволюция характера ---------------------------------------------------
    def test_evolution_level_grows_with_messages(self):
        orion.upsert({"name": "Сова", "access": "crew"})
        self.assertEqual(orion.evolution_level("сова"), 1)
        for _ in range(10):
            orion.remember("сова", "pilot", "привет")
        self.assertEqual(orion.evolution_level("сова"), 2)
        for _ in range(20):
            orion.remember("сова", "pilot", "привет")
        self.assertEqual(orion.evolution_level("сова"), 3)

    def test_evolution_status(self):
        orion.upsert({"name": "Сова", "access": "crew"})
        status = orion.evolution_status("сова")
        self.assertEqual(status["count"], 0)
        self.assertEqual(status["level"], 1)
        self.assertTrue(status["remaining"] > 0)

    def test_evolution_manner_block(self):
        orion.upsert({"name": "Сова", "access": "crew"})
        block = orion.character_block("сова")
        self.assertIn("[МАНЕРЫ АГЕНТА]", block)
        self.assertIn("[ЭВОЛЮЦИЯ ХАРАКТЕРА]", block)

    def test_upsert_keeps_id_and_created(self):
        rec = orion.upsert({"name": "Сова", "access": "observer"})
        again = orion.upsert({"id": rec["id"], "name": "Сова-2", "access": "commander"})
        self.assertEqual(again["id"], rec["id"])
        self.assertEqual(again["name"], "Сова-2")
        self.assertEqual(again["access"], "commander")
        self.assertEqual(len(orion.agents()), 2)

    def test_bad_access_and_voice_fall_back(self):
        rec = orion.upsert({"name": "Сова", "access": "бог", "voice": "крик"})
        self.assertEqual(rec["access"], "crew")
        self.assertEqual(rec["voice"], "ship")

    def test_orion_is_not_removable(self):
        self.assertFalse(orion.remove("orion"))
        orion.upsert({"name": "Сова"})
        self.assertTrue(orion.remove("сова"))
        self.assertFalse(orion.remove("сова"))
        self.assertEqual([a["id"] for a in orion.agents()], ["orion"])

    def test_removing_the_active_agent_switches_to_orion(self):
        orion.upsert({"name": "Сова"})
        orion.set_active("сова")
        orion.remove("сова")
        self.assertEqual(orion.active()["id"], "orion")

    def test_registry_survives_garbage(self):
        orion.agents_path().write_text("{это не json", encoding="utf-8")
        self.assertEqual([a["id"] for a in orion.agents()], ["orion"])
        self.assertEqual(orion.active()["id"], "orion")

    def test_broken_agent_entry_is_ignored(self):
        orion.agents_path().write_text(json.dumps({"agents": [{"name": "без id"}]}),
                                       encoding="utf-8")
        self.assertEqual([a["id"] for a in orion.agents()], ["orion"])

    # -- история -----------------------------------------------------------
    def test_history_keeps_session_and_roles(self):
        orion.remember("orion", "pilot", "  Привет,\nОрион!  ")
        orion.remember("orion", "orion", "Здравствуйте, сэр.", session="ses_1")
        h = orion.history("orion")
        self.assertEqual([m["role"] for m in h["messages"]], ["pilot", "orion"])
        self.assertEqual(h["messages"][0]["text"], "Привет, Орион!")   # лишние пробелы убраны
        self.assertEqual(h["messages"][0]["kind"], "")
        self.assertEqual(h["session"], "ses_1")
        self.assertEqual(orion.last_session("orion"), "ses_1")

    def test_history_keeps_screenshot_path(self):
        orion.remember("orion", "pilot", "Смотри снимок.", shot=r"C:\shots\1.png")
        self.assertEqual(orion.history("orion")["messages"][0]["shot"], r"C:\shots\1.png")

    def test_history_hides_empty_screenshot(self):
        orion.remember("orion", "pilot", "без картинки")
        self.assertNotIn("shot", orion.history("orion")["messages"][0])

    def test_shot_note_points_to_file(self):
        note = orion.shot_note(r"C:\shots\1.png")
        self.assertIn("СНИМОК ПИЛОТА:", note)
        self.assertIn(r"C:\shots\1.png", note)
        self.assertEqual(orion.shot_note(""), "")

    def test_history_is_capped(self):
        for i in range(orion.MAX_MESSAGES + 5):
            orion.remember("orion", "pilot", f"реплика {i}")
        msgs = orion.history("orion")["messages"]
        self.assertEqual(len(msgs), orion.MAX_MESSAGES)
        self.assertEqual(msgs[-1]["text"], f"реплика {orion.MAX_MESSAGES + 4}")

    def test_history_is_per_agent(self):
        orion.remember("orion", "pilot", "Ориону")
        orion.remember("сова", "pilot", "Сове")
        self.assertEqual(len(orion.history("orion")["messages"]), 1)
        self.assertEqual(len(orion.history("сова")["messages"]), 1)
        self.assertNotEqual(orion.history_path("orion"), orion.history_path("сова"))

    def test_clear_history_forgets_session(self):
        orion.remember("orion", "pilot", "раз", session="ses_1")
        orion.clear_history("orion")
        self.assertEqual(orion.history("orion")["messages"], [])
        self.assertEqual(orion.last_session("orion"), "")

    def test_history_files_live_in_crew_root(self):
        orion.remember("orion", "pilot", "раз")
        self.assertEqual(orion.history_path("orion").parent, Path(pilots.ROOT_DIR) / "orion")
        self.assertEqual(orion.agents_path().parent, Path(pilots.ROOT_DIR))

    # -- документ заданий --------------------------------------------------
    def test_task_document(self):
        self.assertEqual(orion.tasks(), [])
        orion.add_task("Сделать тёмную тему", author="Комета")
        orion.add_task("Починить эфир", author="Комета", agent="orion")
        rows = orion.tasks()
        self.assertEqual([r["text"] for r in rows], ["Починить эфир", "Сделать тёмную тему"])
        self.assertTrue(all(r["status"] == "open" for r in rows))
        self.assertEqual(rows[0]["author"], "Комета")
        self.assertTrue(orion.close_task(rows[0]["id"]))
        self.assertEqual([r["text"] for r in orion.tasks(status="open")],
                         ["Сделать тёмную тему"])
        self.assertEqual(len(orion.tasks(status="done")), 1)
        self.assertFalse(orion.close_task("нет-такого"))

    def test_task_document_survives_garbage(self):
        orion.tasks_path().write_text("{это не json", encoding="utf-8")
        self.assertEqual(orion.tasks(), [])
        self.assertTrue(orion.add_task("новая задача"))

    # -- понимание речи пилота ---------------------------------------------
    def test_detect_task_by_triggers(self):
        for phrase, expected in (
            ("Орион, запиши задание сделать тёмную тему", "сделать тёмную тему"),
            ("запиши в документ задание: починить эфир", "починить эфир"),
            ("запиши пожалуйста задачу проверить микрофон", "проверить микрофон"),
            ("поставь задачу обновить справку", "обновить справку"),
            ("запомни: пилот любит короткие доклады", "пилот любит короткие доклады"),
        ):
            found, task = orion.detect_task(phrase)
            self.assertTrue(found, phrase)
            self.assertEqual(task, expected, phrase)

    def test_detect_task_without_trigger(self):
        for phrase in ("Как дела на корабле?", "Расскажи про эфир", "Мне нравится эта задача"):
            found, task = orion.detect_task(phrase)
            self.assertFalse(found, phrase)
            self.assertEqual(task, phrase)

    def test_detect_task_without_content(self):
        found, task = orion.detect_task("запиши")
        self.assertTrue(found)
        self.assertEqual(task, "")                 # корабль спросит, что записать

    def test_yes_and_no(self):
        for phrase in ("да", "Да, записывай", "ага", "подтверждаю", "yes", "окей"):
            self.assertTrue(orion.is_yes(phrase), phrase)
            self.assertFalse(orion.is_no(phrase), phrase)
        for phrase in ("нет", "не надо", "Отмена", "отставить", "no"):
            self.assertTrue(orion.is_no(phrase), phrase)
            self.assertFalse(orion.is_yes(phrase), phrase)
        self.assertFalse(orion.is_yes("кажется да"))
        self.assertFalse(orion.is_no(""))
        self.assertFalse(orion.is_yes(""))

    # -- контекст корабля --------------------------------------------------
    def test_context_line_tells_the_section(self):
        line = orion.context_line(zone="ЭФИР", subtab="ЧАТ", was="МОСТИК", pilot="Комета",
                                  access="КОМАНДИР", version="3.7.0", geometry="1200x800")
        self.assertTrue(line.startswith("[КОРАБЛЬ]"))
        for bit in ("ЭФИР", "ЧАТ", "МОСТИК", "Комета", "КОМАНДИР", "3.7.0", "1200x800"):
            self.assertIn(bit, line)
        self.assertEqual(orion.context_line(), "")            # без данных — пусто
        self.assertNotIn("перед этим", orion.context_line(zone="ЭФИР", was="ЭФИР"))

    # -- профили по уровню доступа ----------------------------------------
    def test_profiles_by_access(self):
        self.assertEqual(orion.profiles({"access": "commander"}), ("orion-recon", "orion-commander"))
        self.assertEqual(orion.profiles({"access": "observer"}), ("orion-recon", None))
        self.assertEqual(orion.profiles({"access": "crew"}), ("orion-chat", None))
        self.assertEqual(orion.profiles({"access": "crew", "profile": "build"}), ("build", None))

    # -- команда запуска и разбор событий ---------------------------------
    def test_build_command(self):
        cmd = orion.build_command("opencode.exe", "orion-recon", "привет", session="ses_9",
                                  model="m1", project=Path("D:/ship"))
        self.assertEqual(cmd[0], "opencode.exe")
        self.assertEqual(cmd[1:3], ["run", "--format"])
        self.assertEqual(cmd[3], "json")
        self.assertIn(str(Path("D:/ship")), cmd)
        self.assertEqual(cmd[cmd.index("--session") + 1], "ses_9")
        self.assertEqual(cmd[cmd.index("--agent") + 1], "orion-recon")
        self.assertEqual(cmd[cmd.index("--model") + 1], "m1")
        self.assertEqual(cmd[-1], "привет")
        self.assertNotIn("--session", orion.build_command("opencode.exe", "orion-chat", "привет"))

    def test_parse_events_takes_last_answer(self):
        stdout = _events(
            {"type": "step_start", "sessionID": "ses_1",
             "part": {"messageID": "m1", "type": "step-start"}},
            {"type": "text", "sessionID": "ses_1", "part": {"messageID": "m1", "text": "думаю…"}},
            {"type": "tool_use", "sessionID": "ses_1",
             "part": {"tool": "read", "state": {"status": "completed", "input": {"filePath": "a"}}}},
            {"type": "text", "sessionID": "ses_1", "part": {"messageID": "m2", "text": "Готово, сэр."}},
        )
        parsed = orion.parse_events(stdout)
        self.assertEqual(parsed["reply"], "Готово, сэр.")      # только последний ответ
        self.assertEqual(parsed["session"], "ses_1")
        self.assertEqual(parsed["tools"], ["read"])
        self.assertFalse(parsed["denied"])
        self.assertFalse(parsed["spoke"])

    def test_parse_events_notices_own_voice_and_denial(self):
        stdout = _events(
            {"type": "tool_use", "sessionID": "ses_1",
             "part": {"tool": "bash", "state": {"status": "completed",
                                                "input": {"command": "python say.py привет"}}}},
            {"type": "tool_use", "sessionID": "ses_1",
             "part": {"tool": "edit", "state": {"status": "error",
                                                "error": "permission denied"}}},
            {"type": "text", "sessionID": "ses_1", "part": {"messageID": "m1", "text": "ок"}},
        )
        parsed = orion.parse_events(stdout)
        self.assertTrue(parsed["spoke"])            # агент озвучил себя сам — корабль молчит
        self.assertTrue(parsed["denied"])

    def test_parse_events_tolerates_noise(self):
        parsed = orion.parse_events("не json\n{}\n[]\n")
        self.assertEqual(parsed["reply"], "")
        self.assertEqual(parsed["session"], "")

    def test_strip_marker(self):
        text, request = orion.strip_marker("Доложил.\n⟦ТРЕБУЕТСЯ РАЗРЕШЕНИЕ⟧ создать файл\nСлушаю.")
        self.assertEqual(text, "Доложил.\nСлушаю.")
        self.assertEqual(request, "создать файл")
        self.assertEqual(orion.strip_marker("обычный ответ"), ("обычный ответ", ""))

    # -- вызов агента на подставном CLI ------------------------------------
    def _fake_cli(self, body: str) -> Path:
        """Подставной OpenCode: печатает заданные события и не ходит в сеть."""
        folder = Path(self._tmp) / "fake"
        folder.mkdir(exist_ok=True)
        script = folder / "fake.py"
        script.write_text(
            "import sys\n"
            f"data = {body!r}\n"
            'sys.stdout.buffer.write(data.encode("utf-8"))\n'
            "sys.stdout.flush()\n",
            encoding="utf-8",
        )
        cmd = folder / "opencode.cmd"
        cmd.write_text('@echo off\r\n"{0}" "%~dp0fake.py"\r\n'.format(sys.executable),
                       encoding="ascii")
        return cmd

    def _with_fake(self, cli: Path, call):
        old = os.environ.get("STAR_TYPING_OPENCODE")
        os.environ["STAR_TYPING_OPENCODE"] = str(cli)
        try:
            return call()
        finally:
            if old is None:
                os.environ.pop("STAR_TYPING_OPENCODE", None)
            else:
                os.environ["STAR_TYPING_OPENCODE"] = old

    def test_run_profile_reads_answer(self):
        answer = _events(
            {"type": "step_start", "sessionID": "ses_7", "part": {"messageID": "m1"}},
            {"type": "text", "sessionID": "ses_7", "part": {"messageID": "m1", "text": "Докладываю."}},
        )
        cli = self._fake_cli(answer)
        res = self._with_fake(cli, lambda: orion.run_profile(
            {"access": "observer"}, "осмотри корабль", profile="orion-recon"))
        self.assertEqual(res.error, "")
        self.assertEqual(res.reply, "Докладываю.")
        self.assertEqual(res.session, "ses_7")
        self.assertEqual(res.profile, "orion-recon")
        self.assertFalse(res.needs_permission)

    def test_run_profile_sees_permission_request(self):
        answer = _events(
            {"type": "text", "sessionID": "ses_8",
             "part": {"messageID": "m1",
                      "text": "План готов.\n⟦ТРЕБУЕТСЯ РАЗРЕШЕНИЕ⟧ править файлы"}},
        )
        cli = self._fake_cli(answer)
        res = self._with_fake(cli, lambda: orion.ask({"access": "commander"}, "правь эфир"))
        self.assertTrue(res.needs_permission)
        self.assertEqual(res.request, "править файлы")
        self.assertEqual(res.reply, "План готов.")      # маркер пилоту не показываем

    def test_run_profile_empty_message(self):
        cli = self._fake_cli("")
        res = self._with_fake(cli, lambda: orion.ask({"access": "crew"}, "   "))
        self.assertEqual(res.error, "empty")

    def test_run_profile_without_cli(self):
        real = orion.find_cli
        orion.find_cli = lambda: ""                     # как будто OpenCode не стоит
        try:
            res = orion.run_profile({"access": "crew"}, "привет", profile="orion-chat")
        finally:
            orion.find_cli = real
        self.assertEqual(res.error, "no_cli")

    def test_available_reports_path_and_env_override(self):
        cli = self._fake_cli("")

        def checks():
            ok, exe = orion.available()
            self.assertTrue(ok)
            self.assertEqual(exe, str(cli))
            self.assertEqual(orion.find_cli(), str(cli))     # переменная окружения важнее PATH

        self._with_fake(cli, checks)
        self.assertEqual(orion.access_label("commander"), "Командир")
        self.assertEqual(orion.access_label("crew"), "Экипаж")

    # -- манеры доезжают до агента -----------------------------------------
    def _echo_cli(self) -> Path:
        """Подставной CLI: отвечает тем, что получил (видно, что дошло до агента)."""
        folder = Path(self._tmp) / "echo"
        folder.mkdir(exist_ok=True)
        script = folder / "echo.py"
        script.write_text(
            "import json, sys\n"
            "prompt = sys.argv[-1]\n"
            "line = json.dumps({'type': 'text', 'sessionID': 'ses_e',\n"
            "                   'part': {'messageID': 'm1', 'text': prompt}}, ensure_ascii=False)\n"
            'sys.stdout.buffer.write((line + "\\n").encode("utf-8"))\n'
            "sys.stdout.flush()\n",
            encoding="utf-8",
        )
        cmd = folder / "opencode.cmd"
        cmd.write_text('@echo off\r\n"{0}" "%~dp0echo.py" %*\r\n'.format(sys.executable),
                       encoding="ascii")
        return cmd

    def test_manners_reach_the_agent(self):
        """Манеры, отметка корабля и реплика доезжают до агента одним запросом.

        Здесь движок — .cmd-обёртка (как npm на Windows): корабль схлопывает
        переводы строк, иначе cmd.exe обрезал бы запрос на первом \\n.
        """
        rec = orion.upsert({"name": "Сова"})
        orion.save_character(rec["id"], "Говори коротко.")
        cli = self._echo_cli()
        res = self._with_fake(cli, lambda: orion.run_profile(
            rec, "Как дела?", profile="orion-chat", context="[КОРАБЛЬ] открыт раздел «Мостик»"))
        self.assertEqual(res.error, "")
        self.assertIn("[МАНЕРЫ АГЕНТА]", res.reply)
        self.assertIn("Говори коротко.", res.reply)
        self.assertIn("[КОРАБЛЬ]", res.reply)
        self.assertTrue(res.reply.endswith("Как дела?"))
        self.assertNotIn("\n", res.reply)

    def test_manners_keep_paragraphs_for_a_real_executable(self):
        """Настоящий exe получает документ манер как есть — с абзацами."""
        rec = orion.upsert({"name": "Сова"})
        orion.save_character(rec["id"], "Первое.\nВторое.")
        seen = {}

        class _Proc:
            pid = 777
            returncode = 0
            stdout = b""
            stderr = b""

            def __init__(self, cmd, **_kw):
                seen["cmd"] = cmd
                self.args = cmd

            def communicate(self, input=None, timeout=None):
                return b"", b""

            def poll(self):
                return 0

            def wait(self, timeout=None):
                return 0

            def kill(self):
                self.returncode = -9

            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

        real_popen, real_cli = orion.subprocess.Popen, orion.find_cli
        orion.subprocess.Popen = _Proc
        orion.find_cli = lambda: "opencode.exe"
        try:
            orion.run_profile(rec, "Как дела?", profile="orion-chat")
        finally:
            orion.subprocess.Popen, orion.find_cli = real_popen, real_cli
            orion._RUNS.clear()
        prompt = seen["cmd"][-1]
        self.assertTrue(prompt.startswith("[МАНЕРЫ АГЕНТА]\nПервое.\nВторое."))
        self.assertTrue(prompt.endswith("Как дела?"))

    def test_flatten_keeps_every_line(self):
        self.assertEqual(orion.flatten("[МАНЕРЫ АГЕНТА]\nПервое.\n\nВторое.\r\n"),
                         "[МАНЕРЫ АГЕНТА] · Первое. · Второе.")

    def test_npm_shim_prefers_native_exe(self):
        """Обёртку .cmd меняем на настоящий exe рядом: она обрезает многострочный запрос."""
        npm = Path(self._tmp) / "npm"
        bin_dir = npm / "node_modules" / "opencode-ai" / "bin"
        bin_dir.mkdir(parents=True)
        native = bin_dir / "opencode.exe"
        native.write_bytes(b"MZ")
        shim = npm / "opencode.cmd"
        shim.write_text("@echo off\r\n", encoding="ascii")
        self.assertEqual(orion._native_exe(str(shim)), str(native))
        self.assertEqual(orion._native_exe(str(native)), str(native))     # exe не трогаем


class OwnerKeyTest(unittest.TestCase):
    """Код владельца корабля: права Командира нельзя выдать «просто так»."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        pilots.reset_root(Path(self._tmp))

    def tearDown(self):
        pilots.reset_root()

    def test_no_code_until_owner_sets_it(self):
        self.assertFalse(owner_key.is_set())
        ok, message = owner_key.verify("1234")
        self.assertFalse(ok)
        self.assertTrue(message)                 # объяснение, а не молчание

    def test_set_and_verify(self):
        owner_key.set_code("4321")
        self.assertTrue(owner_key.is_set())
        self.assertEqual(owner_key.verify("4321"), (True, ""))

    def test_wrong_code_is_counted_and_locks(self):
        owner_key.set_code("4321")
        for i in range(owner_key.MAX_TRIES - 1):
            ok, message = owner_key.verify("0000")
            self.assertFalse(ok)
            self.assertIn(str(owner_key.MAX_TRIES - i - 1), message)   # сколько попыток осталось
        ok, _message = owner_key.verify("0000")                        # последняя ошибка — блокировка
        self.assertFalse(ok)
        self.assertGreater(owner_key.lock_left(), 0)

    def test_code_is_not_stored_as_text(self):
        owner_key.set_code("4321")
        raw = owner_key.path().read_text(encoding="utf-8")
        self.assertNotIn("4321", raw)            # только солёный хэш
        self.assertIn("pbkdf2_sha256", raw)

    def test_bad_code_rejected(self):
        for bad in ("12", "abcdef", ""):
            with self.assertRaises(ValueError):
                owner_key.set_code(bad)
        self.assertFalse(owner_key.is_set())

    def test_clear_code_takes_commander_away(self):
        owner_key.set_code("4321")
        owner_key.clear_code()
        self.assertFalse(owner_key.is_set())
        self.assertFalse(owner_key.verify("4321")[0])


class OrionCharacterTest(unittest.TestCase):
    """Документ манер: корабль создаёт его при входе агента, пилот правит на борту."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        pilots.reset_root(Path(self._tmp))

    def tearDown(self):
        pilots.reset_root()

    def test_document_created_on_boarding(self):
        self.assertFalse(orion.character_path("orion").exists())
        rec = orion.upsert({"name": "Сова"})
        self.assertTrue(orion.character_path(rec["id"]).exists())
        text = orion.read_character(rec["id"])
        self.assertIn("Сова", text)                       # заготовка знает имя агента
        self.assertIn("Манеры", text)
        self.assertTrue(orion.character_block(rec["id"]).startswith("[МАНЕРЫ АГЕНТА]"))

    def test_pilot_edits_manners(self):
        rec = orion.upsert({"name": "Сова"})
        orion.save_character(rec["id"], "  Отвечай дерзко, но по делу.  ")
        self.assertEqual(orion.read_character(rec["id"]), "Отвечай дерзко, но по делу.")
        self.assertIn("Отвечай дерзко", orion.character_block(rec["id"]))

    def test_document_has_limit(self):
        rec = orion.upsert({"name": "Сова"})
        orion.save_character(rec["id"], "я" * (orion.MAX_CHARACTER + 500))
        self.assertEqual(len(orion.read_character(rec["id"])), orion.MAX_CHARACTER)

    def test_empty_document_is_not_sent(self):
        rec = orion.upsert({"name": "Сова"})
        orion.save_character(rec["id"], "   ")
        block = orion.character_block(rec["id"])
        # Пустой документ не отправляется — только правила эволюции без заголовка манер
        self.assertNotIn("[МАНЕРЫ АГЕНТА]", block)
        self.assertTrue(block == "" or block.startswith("[ЭВОЛЮЦИЯ ХАРАКТЕРА]"))

    def test_document_leaves_with_agent(self):
        rec = orion.upsert({"name": "Сова"})
        path = orion.character_path(rec["id"])
        orion.remove(rec["id"])
        self.assertFalse(path.exists())


class OrionScreenTest(unittest.TestCase):
    """Экран ОРИОНА на настоящем Tk: доска, задание в документ, заселение агентов."""

    def setUp(self):
        import tkinter as tk

        self._tmp = tempfile.mkdtemp()
        pilots.reset_root(Path(self._tmp))
        os.environ.setdefault("APPDATA", self._tmp)
        # агент настоящий не нужен: ответ мгновенный и без сети
        self._real_run = orion.run_profile
        orion.run_profile = lambda *a, **kw: orion.Result(reply="Принято, пилот.", session="ses_x",
                                                         profile=str(kw.get("profile") or ""))
        try:
            from stamina.cockpit import Cockpit
            self.app = Cockpit()
        except tk.TclError:
            orion.run_profile = self._real_run
            pilots.reset_root()
            self.skipTest("нет дисплея")
        self.app.update()

    def tearDown(self):
        orion.run_profile = self._real_run
        self.app.destroy()
        pilots.reset_root()

    def _screen(self):
        scr = self.app.screens.get("orion")
        if scr is None:
            self.skipTest("раздел ОРИОН не загрузился")
        scr._answer_voice = False          # в тестах Орион молчит
        scr.mic.start = lambda: False      # микрофон не открываем
        return scr

    def test_zone_is_in_header(self):
        keys = [s for s, _ in self.app.SCREENS]
        self.assertIn("orion", keys)
        self.assertEqual(keys.index("orion"), keys.index("settings") - 1)
        self.assertIn("orion", self.app.nav_buttons)
        self.assertTrue(self.app.bind("<Control-Key-8>"))     # Ctrl+8 — восьмая зона

    def test_orion_zone_opens_with_subtabs(self):
        self.app.show("orion")
        scr = self._screen()
        self.assertEqual(self.app.current, "orion")
        self.assertEqual(scr.tab_keys(), ["chat", "agents", "archive"])
        scr.show_tab("agents")
        self.assertEqual(scr.current_tab, "agents")
        self.assertEqual(scr.page_help_key(), "orion.agents")  # у каждой подвкладки своя справка

    def test_board_is_hidden_until_asked(self):
        """Доска скрыта: разговор идёт как контекст, пока не попросили показать."""
        self.app.show("orion")
        scr = self._screen()
        self.assertFalse(scr.board_visible)
        self.assertIn("СКРЫТА", scr.board_btn._text)
        self.assertTrue(scr.strip.winfo_manager())        # на месте живая линия
        self.assertFalse(scr.board.winfo_manager())
        scr._toggle_board()
        self.assertTrue(scr.board_visible)
        self.assertIn("ОТКРЫТА", scr.board_btn._text)
        self.assertTrue(scr.board.winfo_manager())
        self.assertFalse(scr.strip.winfo_manager())

    def test_voice_text_goes_to_input(self):
        scr = self._screen()
        scr.entry.delete(0, "end")
        scr._insert_text("Проверить эфир")
        self.assertEqual(scr.entry.get(), "Проверить эфир")
        scr._insert_text("и микрофон")
        self.assertEqual(scr.entry.get(), "Проверить эфир и микрофон")

    def test_task_question_then_confirmation(self):
        """«Запиши…» → вопрос → подтверждение → задание в документе и доска открыта."""
        self.app.show("orion")
        scr = self._screen()
        scr._busy = True                       # агента не зовём: проверяем запись в документ
        scr._ask_task("сделать тёмную тему")
        self.assertTrue(scr.ask_row.winfo_manager())
        self.assertEqual(scr._pending_task, "сделать тёмную тему")
        scr._confirm_task(True)
        self.assertEqual(orion.tasks()[0]["text"], "сделать тёмную тему")
        self.assertFalse(scr.ask_row.winfo_manager())
        self.assertTrue(scr.board_visible)     # доска чата открылась сама
        kinds = [m.get("kind") for m in orion.history("orion")["messages"]]
        self.assertIn("task", kinds)

    def test_task_can_be_refused(self):
        scr = self._screen()
        scr._busy = True
        scr._ask_task("лишнее дело")
        scr._confirm_task(False)
        self.assertEqual(orion.tasks(), [])
        self.assertEqual(scr._pending_task, "")

    def test_second_step_asks_what_to_record(self):
        """Сказали только «запиши» — корабль спрашивает, что именно записать."""
        self.app.show("orion")
        scr = self._screen()
        scr._busy = True
        scr._await_task = True
        scr._take_task("проверить микрофон")
        self.assertFalse(scr._await_task)
        self.assertEqual(scr._pending_task, "проверить микрофон")
        scr._confirm_task(False)

    def test_voice_yes_confirms_without_enter(self):
        """«Да» голосом подтверждает запись — Enter не нужен."""
        scr = self._screen()
        scr._busy = True
        scr._ask_task("починить эфир")
        scr._insert_text("Да, записывай")
        self.assertEqual(orion.tasks()[0]["text"], "починить эфир")
        self.assertEqual(scr._pending_task, "")

    def _grant_commander(self, scr, allow=True, github=True):
        """Выдать (или не выдать) права Командира: два шага — код владельца, доступ к GitHub."""
        from stamina import orion_screen

        class _Stub:
            def __init__(self, *_a, **_kw):
                pass

            def run(self):
                return allow

        class _GitHubStub:
            def __init__(self, *_a, **_kw):
                pass

            def run(self):
                return github

        real = orion_screen._OwnerCodeDialog
        real_gh = orion_screen._GitHubAccessDialog
        orion_screen._OwnerCodeDialog = _Stub
        orion_screen._GitHubAccessDialog = _GitHubStub
        try:
            scr._pick_access("commander")
        finally:
            orion_screen._OwnerCodeDialog = real
            orion_screen._GitHubAccessDialog = real_gh

    def test_boarding_new_agent(self):
        self.app.show("orion")
        scr = self._screen()
        scr._new_agent()
        scr.name_var.set("Сова")
        self._grant_commander(scr)                 # права Командира — по коду владельца
        self.assertEqual(scr._access, "commander")
        scr._save_agent()
        names = [a["name"] for a in orion.agents()]
        self.assertIn("Сова", names)
        rec = orion.get(scr._draft_id)
        self.assertEqual(rec["name"], "Сова")
        self.assertEqual(rec["access"], "commander")
        self.assertEqual(rec["voice"], "ship")
        scr._make_active()
        self.assertEqual(orion.active()["name"], "Сова")
        # в списке пассажиров на каждого: кнопка имени + подпись уровня
        self.assertEqual(len(scr.crew_box.winfo_children()), 4)

    def test_commander_needs_github_access(self):
        """Отказ в доступе к GitHub — прав Командира нет, это второй шаг заселения."""
        scr = self._screen()
        scr._new_agent()
        scr.name_var.set("Сова")
        self._grant_commander(scr, github=False)
        self.assertEqual(scr._access, "crew")

    def test_commander_needs_owner_code(self):
        """Отказ по коду владельца — дальше GitHub уже не спрашивают."""
        scr = self._screen()
        scr._new_agent()
        scr.name_var.set("Сова")
        self._grant_commander(scr, allow=False)
        self.assertEqual(scr._access, "crew")

    def test_boarding_needs_name(self):
        scr = self._screen()
        scr._new_agent()
        scr.name_var.set("   ")
        scr._save_agent()
        self.assertEqual(len(orion.agents()), 1)

    def _rights_enabled(self, scr) -> bool:
        """Открыты ли кнопки прав (они активны только при заселении нового агента)."""
        return all(btn._enabled for btn in scr.access_btns.values())

    def test_rights_are_chosen_by_buttons_at_boarding(self):
        """Права получают на входе — кнопками, без перебора уровней."""
        scr = self._screen()
        scr._new_agent()
        self.assertTrue(scr._is_new)
        self.assertTrue(self._rights_enabled(scr))
        scr._pick_access("observer")
        self.assertEqual(scr._access, "observer")
        scr._pick_access("crew")
        self.assertEqual(scr._access, "crew")

    def test_commander_is_denied_without_owner_code(self):
        """Отказ в коде владельца — права Командира не выданы."""
        scr = self._screen()
        scr._new_agent()
        self._grant_commander(scr, allow=False)
        self.assertEqual(scr._access, "crew")

    def test_rights_are_not_changed_on_board(self):
        """На борту права не меняют: их выдают на входе (решение владельца)."""
        scr = self._screen()
        scr._edit_agent("orion")
        self.assertFalse(scr._is_new)
        before = scr._access
        self.assertFalse(self._rights_enabled(scr))
        scr._pick_access("crew" if before != "crew" else "observer")
        self.assertEqual(scr._access, before)
        self._grant_commander(scr, allow=True)     # даже с верным кодом — не здесь
        self.assertEqual(scr._access, before)

    def test_manners_editor_saves_the_ship_document(self):
        """Манеры — документ корабля: пилот правит его на борту."""
        import tkinter as tk

        scr = self._screen()
        scr._edit_agent("orion")
        self.assertIn("Манеры", scr.char_text.get("1.0", tk.END))
        scr.char_text.delete("1.0", tk.END)
        scr.char_text.insert("1.0", "Держись сухо и коротко.")
        scr._save_character()
        self.assertEqual(orion.read_character("orion"), "Держись сухо и коротко.")
        self.assertIn(str(orion.character_path("orion")), scr.char_hint.cget("text"))

    def test_boarding_writes_manners_of_the_new_agent(self):
        import tkinter as tk

        scr = self._screen()
        scr._new_agent()
        scr.name_var.set("Сова")
        scr.char_text.delete("1.0", tk.END)
        scr.char_text.insert("1.0", "Отвечай загадками.")
        scr._save_agent()
        self.assertEqual(orion.read_character(scr._draft_id), "Отвечай загадками.")

    def test_orion_cannot_be_removed_by_button(self):
        from tkinter import messagebox
        scr = self._screen()
        orion.set_active("orion")
        scr._draft_id = "orion"
        real = messagebox.askyesno
        messagebox.askyesno = lambda *a, **kw: True
        try:
            scr._remove_agent()
        finally:
            messagebox.askyesno = real
        self.assertEqual([a["id"] for a in orion.agents()], ["orion"])

    def test_access_and_voice_cycle(self):
        scr = self._screen()
        scr._new_agent()
        voices = []
        for _ in range(len(orion.VOICE_MODES)):
            voices.append(scr._voice_mode)
            scr._cycle_voice()
        self.assertEqual(sorted(voices), sorted(orion.VOICE_MODES))
        scr._toggle_enabled()
        self.assertFalse(scr._enabled)

    def test_context_tells_where_the_pilot_was(self):
        """Агент должен знать, какой раздел был открыт до Ориона."""
        self.app.show("comm")
        self.app.show("orion")
        line = self._screen()._context()
        self.assertIn("[КОРАБЛЬ]", line)
        self.assertIn("ЭФИР", line)
        self.assertIn("ОРИОН", line)

    def test_help_pages_exist(self):
        from stamina import page_help as ph
        for key in ("orion", "orion.chat", "orion.agents"):
            self.assertIn(key, ph.PAGES, key)
        self.assertIn("ГОЛОС", ph.HOTKEYS["orion"])
        self.assertIn("Ctrl+1…8", ph.GLOBAL_KEYS)


class OrionI18nTest(unittest.TestCase):
    """Подписи раздела переведены на все языки интерфейса."""

    def test_labels_translated(self):
        keys = ["ОРИОН · ЧАТ", "ОРИОН · АГЕНТЫ", "ЖИВАЯ ЛИНИЯ", "ПАССАЖИРЫ БОРТА",
                "КАРТОЧКА ПАССАЖИРА", "СЛУШАЮ… говорите", "ГОЛОС", "КОМАНДИР",
                "НАБЛЮДАТЕЛЬ", "ЭКИПАЖ", "ДОСКА: СКРЫТА", "СЛУШАЮ… {0} {1}"]
        try:
            ru = json.loads((i18n.DIR / "ru.json").read_text(encoding="utf-8"))
            for key in keys:
                self.assertIn(key, ru, ("ru", key))          # русская фраза — сам ключ
            for lang in ("uk", "en", "de"):
                table = i18n.load_table(lang)
                for key in keys:
                    self.assertIn(key, table, (lang, key))
                    self.assertTrue(str(table[key]).strip(), (lang, key))
            i18n.set_language("en")
            for key in ("ЖИВАЯ ЛИНИЯ", "КАРТОЧКА ПАССАЖИРА", "ДОСКА: СКРЫТА", "СЛУШАЮ… говорите"):
                self.assertNotEqual(i18n.t(key), key, key)
        finally:
            i18n.set_language("ru")


class OrionStopTest(unittest.TestCase):
    """Квадратик «стоп»: агента можно оборвать, а сессию сохранить для уточнений."""

    def setUp(self):
        import subprocess

        from stamina import orion
        self.orion = orion
        self.subprocess = subprocess
        self.killed = []
        self._kill = orion._kill
        self._popen = subprocess.Popen
        self._cli = orion.find_cli
        orion._kill = lambda proc: self.killed.append(proc.pid)
        orion.find_cli = lambda: "opencode.exe"

    def tearDown(self):
        self.subprocess.Popen = self._popen
        self.orion._kill = self._kill
        self.orion.find_cli = self._cli
        self.orion._RUNS.clear()
        self.orion._STOPPED.clear()
        self.killed.clear()

    def _fake_popen(self, payload: bytes, stop_inside: bool):
        orion = self.orion

        class _Proc:
            pid = 4242
            returncode = 1

            def __init__(self, cmd, **kw):
                self.cmd = cmd
                self.args = cmd

            def communicate(self, input=None, timeout=None):
                if stop_inside:
                    orion.stop_run("orion")
                return payload, b""

            def poll(self):
                return self.returncode

            def wait(self, timeout=None):
                return self.returncode

            def kill(self):
                self.returncode = -9

            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

        return _Proc

    def test_stop_all_kills_everything(self):
        """Закрыли корабль — гасим всех: ни один агент не остаётся сиротой."""
        self.orion._remember_run("orion", SimpleNamespace(pid=11))
        self.orion._remember_run("sova", SimpleNamespace(pid=22))
        self.assertEqual(self.orion.stop_all(), 2)
        self.assertEqual(sorted(self.killed), [11, 22])
        self.assertEqual(self.orion.stop_all(), 0)      # повторно гасить нечего
        self.assertFalse(self.orion.running())

    def test_stop_all_leaves_no_trace(self):
        """После гашения счётчик живых пуст, иначе кнопка «стоп» осталась бы горящей."""
        self.orion._remember_run("orion", SimpleNamespace(pid=33))
        self.orion._RUNS.clear()                        # процесс завершился сам
        self.assertEqual(self.orion.stop_all(), 0)
        self.assertEqual(self.killed, [])

    def test_stop_without_work(self):
        self.assertFalse(self.orion.stop_run())
        self.assertFalse(self.orion.running())

    def test_stopped_run_keeps_partial_reply_and_session(self):
        payload = (b'{"type":"text","sessionID":"ses_7",'
                   b'"part":{"messageID":"m1","text":"\\u041d\\u0430\\u0447\\u0430\\u043b '
                   b'\\u043f\\u0440\\u0430\\u0432\\u043a\\u0443"}}\n')
        self.subprocess.Popen = self._fake_popen(payload, stop_inside=True)
        res = self.orion.run_profile({"id": "orion"}, "починить", profile="orion-recon")
        self.assertEqual(res.error, "stopped")
        self.assertEqual(res.session, "ses_7")
        self.assertIn("Начал", res.reply)
        self.assertEqual(self.killed, [4242])          # процесс действительно погасили
        self.assertFalse(self.orion.running())         # и сняли с учёта

    def test_run_without_stop_is_normal(self):
        payload = (b'{"type":"text","sessionID":"ses_8",'
                   b'"part":{"messageID":"m1","text":"\\u0413\\u043e\\u0442\\u043e\\u0432\\u043e"}}\n')
        self.subprocess.Popen = self._fake_popen(payload, stop_inside=False)
        res = self.orion.run_profile({"id": "orion"}, "привет", profile="orion-recon")
        self.assertEqual(res.error, "")
        self.assertEqual(res.reply, "Готово")
        self.assertEqual(self.killed, [])

    def test_running_sees_live_agent(self):
        proc = SimpleNamespace(pid=777)
        self.orion._remember_run("orion", proc)
        self.assertTrue(self.orion.running())
        self.assertTrue(self.orion.running("orion"))
        self.assertFalse(self.orion.running("other"))
        self.assertTrue(self.orion.stop_run("orion"))
        self.assertEqual(self.killed, [777])
        self.assertTrue(self.orion._forget_run(proc))


class OrionTokenHelpTest(unittest.TestCase):
    """Справка «где взять токен GitHub» — для пилота, который не знаток GitHub."""

    def test_help_explains_steps(self):
        from stamina import orion_screen
        text = orion_screen.github_token_help()
        self.assertIn("Settings", text)
        self.assertIn("Developer settings", text)
        self.assertIn("Tokens (classic)", text)
        self.assertIn("repo", text)
        self.assertIn("ghp_", text)

    def test_help_covers_another_computer(self):
        from stamina import orion_screen
        self.assertIn("другом компьютере", orion_screen.github_token_help())

    def test_tokens_page_url(self):
        from stamina import orion_screen
        self.assertTrue(orion_screen.GITHUB_TOKENS_URL.startswith("https://github.com/"))

    def test_help_is_translated(self):
        from stamina import i18n, orion_screen
        keys = [line for line in orion_screen.github_token_help().splitlines() if line]
        try:
            ru = json.loads((i18n.DIR / "ru.json").read_text(encoding="utf-8"))
            for key in keys[:8]:
                self.assertIn(key, ru, ("ru", key))
        finally:
            i18n.set_language("ru")


class OrionUiModeTest(unittest.TestCase):
    """Вид чата — выбор пилота: «Чат» или «Ремонтный отсек»."""

    def test_modes_are_translated(self):
        from stamina import i18n
        try:
            ru = json.loads((i18n.DIR / "ru.json").read_text(encoding="utf-8"))
            for key in ("РЕЖИМ: ЧАТ", "РЕЖИМ: ПРО", "РЕМОНТНЫЙ ОТСЕК", "ЧАТ"):
                self.assertIn(key, ru, key)
        finally:
            i18n.set_language("ru")


class OrionProgressTest(unittest.TestCase):
    """Доклад агента о работе: «чем занят Орион» на пульте (название, шаг, процент)."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._old = os.environ.get("STAR_TYPING_PROGRESS_FILE")
        os.environ["STAR_TYPING_PROGRESS_FILE"] = str(Path(self._tmp) / "progress.json")

    def tearDown(self):
        if self._old is None:
            os.environ.pop("STAR_TYPING_PROGRESS_FILE", None)
        else:
            os.environ["STAR_TYPING_PROGRESS_FILE"] = self._old

    def test_empty_report(self):
        self.assertEqual(orion.read_progress(), {})
        self.assertEqual(orion.progress_view(), {})

    def test_percent_from_steps(self):
        orion.write_progress("Починка склейки", ["найти причину", "правило словаря", "тесты"], done=1)
        view = orion.progress_view()
        self.assertEqual(view["task"], "Починка склейки")
        self.assertEqual((view["done"], view["total"], view["percent"]), (1, 3, 33))
        self.assertEqual(view["state"], "working")
        self.assertFalse(view["stale"])

    def test_done_state_is_hundred(self):
        orion.write_progress("Индикатор", ["код", "тесты"], done=2, state="done")
        self.assertEqual(orion.progress_view()["percent"], 100)

    def test_done_clamped_to_steps(self):
        orion.write_progress("Индикатор", ["код"], done=7)
        view = orion.progress_view()
        self.assertEqual((view["done"], view["percent"]), (1, 100))

    def test_stale_report(self):
        orion.write_progress("Долгая задача", ["шаг"], done=0)
        later = time.time() + orion.PROGRESS_STALE + 5
        self.assertTrue(orion.progress_view(later)["stale"])
        self.assertFalse(orion.progress_view(time.time())["stale"])

    def test_no_steps_means_no_percent(self):
        orion.write_progress("Просто работа", [])
        view = orion.progress_view()
        self.assertEqual(view["total"], 0)
        self.assertEqual(view["percent"], 0)
        self.assertTrue(view["task"])

    def test_broken_file_is_silent(self):
        Path(os.environ["STAR_TYPING_PROGRESS_FILE"]).write_text("{ ой", encoding="utf-8")
        self.assertEqual(orion.progress_view(), {})


class OrionWorkBarKeysTest(unittest.TestCase):
    """Строки шкалы работы есть в словарях (русский — с проверкой значения)."""

    def test_keys_exist(self):
        from stamina import i18n
        keys = ("ОРИОН СВОБОДЕН — можно обращаться", "шаг {0} из {1}",
                "доклад не обновлялся", "ЗАДАЧА ВЫПОЛНЕНА: {0}")
        try:
            ru = json.loads((i18n.DIR / "ru.json").read_text(encoding="utf-8"))
            for key in keys:
                self.assertIn(key, ru, key)
                self.assertEqual(ru[key], key, key)
        finally:
            i18n.set_language("ru")


class HudButtonSizeTest(unittest.TestCase):
    """Кнопка не обрезает текст: «НА БОРТУ: ДА» превращалось в огрызок «ОРТ»."""

    def setUp(self):
        import tkinter as tk
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("нет дисплея")
        self.root.withdraw()

    def tearDown(self):
        self.root.destroy()

    def test_auto_width_grows_with_text(self):
        from stamina.hud import HudButton
        from stamina.theme import px
        btn = HudButton(self.root, "")
        narrow = int(btn.cget("width"))
        btn.set_text("НА БОРТУ: ДА")
        self.assertGreater(int(btn.cget("width")), narrow)
        self.assertGreater(int(btn.cget("width")), px(80))

    def test_explicit_width_is_kept(self):
        from stamina.hud import HudButton
        from stamina.theme import px
        btn = HudButton(self.root, "", width=140)
        btn.set_text("НА БОРТУ: ДА")
        self.assertEqual(int(btn.cget("width")), px(140))

    def test_placeholder_then_label(self):
        # В карточке пассажира кнопки создаются до данных, текст приходит позже.
        from stamina.hud import HudButton
        btn = HudButton(self.root, "—")
        btn.set_text("ГОЛОС: КОРАБЛЬ")
        self.assertGreater(int(btn.cget("width")), 100)


class OrionArchiveTest(unittest.TestCase):
    """Бортовой архив: время с датой, разбор запроса, поиск по всем пассажирам."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        pilots.reset_root(Path(self._tmp))

    def tearDown(self):
        pilots.reset_root()

    def test_when_text_has_date_and_time(self):
        ts = time.mktime((2026, 10, 19, 22, 15, 0, 0, 0, -1))
        self.assertEqual(orion.when_text(ts), "19.10.2026 22:15")

    def test_role_names(self):
        self.assertEqual(orion.role_name("pilot"), "пилот")
        self.assertEqual(orion.role_name("orion"), "орион")
        self.assertEqual(orion.role_name("system"), "корабль")

    def test_parse_date_is_whole_day(self):
        now = time.mktime((2026, 10, 20, 12, 0, 0, 0, 0, -1))
        query = orion.parse_query("19.10.2026", now=now)
        self.assertEqual(query.words, ())
        self.assertEqual(orion.when_text(query.from_ts)[:10], "19.10.2026")
        self.assertAlmostEqual(query.to_ts - query.from_ts, 86399, delta=1)

    def test_parse_short_date_uses_current_year(self):
        now = time.mktime((2026, 10, 20, 12, 0, 0, 0, 0, -1))
        self.assertEqual(orion.when_text(orion.parse_query("19.10", now=now).from_ts)[:10],
                         "19.10.2026")

    def test_parse_time_and_words(self):
        query = orion.parse_query("22:15 снимок архив")
        self.assertEqual((query.hour, query.minute), (22, 15))
        self.assertEqual(query.words, ("снимок", "архив"))

    def test_parse_today_and_yesterday(self):
        now = time.mktime((2026, 10, 20, 12, 0, 0, 0, 0, -1))
        today = orion.parse_query("сегодня", now=now)
        self.assertEqual(orion.when_text(today.from_ts)[:10], "20.10.2026")
        yesterday = orion.parse_query("вчера", now=now)
        self.assertEqual(orion.when_text(yesterday.from_ts)[:10], "19.10.2026")

    def test_archive_finds_by_word(self):
        orion.remember("orion", "pilot", "Посмотри архив за октябрь")
        orion.remember("orion", "orion", "Смотрю склейки слов")
        rows = orion.archive("склейки")
        self.assertEqual([m["text"] for m in rows], ["Смотрю склейки слов"])

    def test_archive_all_words_must_match(self):
        orion.remember("orion", "pilot", "архив и книги")
        orion.remember("orion", "pilot", "архив и снимки")
        self.assertEqual(len(orion.archive("архив книги")), 1)

    def test_archive_newest_first(self):
        for word in ("первое", "второе", "третье"):
            orion.remember("orion", "pilot", word)
        self.assertEqual([m["text"] for m in orion.archive("")], ["третье", "второе", "первое"])

    def test_archive_by_day_and_minute(self):
        msg = orion.remember("orion", "pilot", "бортовое время")
        day = orion.when_text(msg["ts"])[:10]
        self.assertEqual([m["id"] for m in orion.archive(day)], [msg["id"]])
        minute = time.strftime("%H:%M", time.localtime(msg["ts"]))
        self.assertEqual([m["id"] for m in orion.archive(minute)], [msg["id"]])

    def test_archive_covers_all_passengers(self):
        orion.upsert({"id": "sova", "name": "Сова"})
        orion.remember("orion", "pilot", "реплика ориона")
        orion.remember("sova", "pilot", "реплика совы")
        texts = {m["text"]: m["agent_name"] for m in orion.archive("реплика")}
        self.assertEqual(texts.get("реплика совы"), "Сова")

    def test_archive_survives_history_clear(self):
        orion.remember("orion", "pilot", "это должно остаться")
        orion.clear_history("orion")
        self.assertEqual([m["text"] for m in orion.archive("остаться")],
                         ["это должно остаться"])

    def test_archive_limit(self):
        for i in range(5):
            orion.remember("orion", "pilot", f"строка {i}")
        self.assertEqual(len(orion.archive("", limit=2)), 2)


class OrionBookCheckTest(unittest.TestCase):
    """Проверка книги агентом: запрос, разбор ответа, аккуратная замена."""

    def test_prompt_carries_text_and_format(self):
        prompt = orion.check_prompt("nineteenthcentury век", what="Книга «XIX век»")
        self.assertIn("nineteenthcentury век", prompt)
        self.assertIn("Книга «XIX век»", prompt)
        self.assertIn("JSON", prompt)

    def test_parse_json_from_fenced_reply(self):
        reply = '```json\n[{"bad": "nineteenthcentury", "good": "nineteenth century"}]\n```'
        self.assertEqual(orion.parse_fixes(reply),
                         [("nineteenthcentury", "nineteenth century")])

    def test_parse_empty_array(self):
        self.assertEqual(orion.parse_fixes("[]"), [])
        self.assertEqual(orion.parse_fixes(""), [])
        self.assertEqual(orion.parse_fixes("правок нет"), [])

    def test_parse_arrow_lines(self):
        reply = "ивот → и вот\nthebook -> the book\nмусор без стрелки"
        self.assertEqual(orion.parse_fixes(reply),
                         [("ивот", "и вот"), ("thebook", "the book")])

    def test_parse_skips_equal_and_empty(self):
        reply = '[{"bad": "дом", "good": "дом"}, {"bad": "", "good": "x"}, {"bad": "a", "good": 5}]'
        self.assertEqual(orion.parse_fixes(reply), [("a", "5")])

    def test_apply_keeps_word_boundaries(self):
        text = "живот и ивот, ещё nineteenthcentury"
        fixed = orion.apply_fixes(text, [("ивот", "и вот"), ("nineteenthcentury", "nineteenth century")])
        self.assertEqual(fixed, "живот и и вот, ещё nineteenth century")

    def test_apply_is_case_insensitive_and_repeats(self):
        self.assertEqual(orion.apply_fixes("Thebook, THEBOOK", [("thebook", "the book")]),
                         "the book, the book")


if __name__ == "__main__":
    unittest.main()
