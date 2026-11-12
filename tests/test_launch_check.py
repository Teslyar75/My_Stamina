"""Тесты проверки перед стартом: без неё «программа не запускается» выглядит молчанием.

Проверка решает, что показать человеку: нет tkinter, нет окна, нет экрана, нет X11.
Здесь она вызывается с подставленными значениями — на машине сборки нет ни Linux,
ни настоящего экрана, а поведение нужно знать точно.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from stamina import launch_check as lc
from stamina import pilots


class CheckTest(unittest.TestCase):
    def test_ok_when_tkinter_and_display(self):
        self.assertIsNone(lc.check(tk_ok=True, window_ok=True, env={"DISPLAY": ":0"},
                                   platform="linux"))

    def test_ok_on_windows_without_display_variable(self):
        self.assertIsNone(lc.check(tk_ok=True, window_ok=True, env={}, platform="win32"))

    def test_missing_tkinter_names_the_package(self):
        problem = lc.check(tk_ok=False, env={"DISPLAY": ":0"}, platform="linux")
        assert problem is not None
        self.assertIn("tkinter", problem.detail)
        self.assertIn("python3-tk", problem.detail)

    def test_missing_tkinter_on_windows_points_to_installer(self):
        problem = lc.check(tk_ok=False, env={}, platform="win32")
        assert problem is not None
        self.assertIn("python.org", problem.detail)

    def test_import_ok_but_window_broken_names_python_313(self):
        # Python 3.13.0 + .venv: импорт проходит, tkinter.Tk() падает (gh-125235)
        problem = lc.check(tk_ok=True, window_ok=False, env={}, platform="win32")
        assert problem is not None
        self.assertIn("init.tcl", problem.detail)
        self.assertIn("3.13.1", problem.detail)
        self.assertIn("TCL_LIBRARY", problem.detail)

    def test_window_broken_on_linux_points_to_tk_package(self):
        problem = lc.check(tk_ok=True, window_ok=False, env={"DISPLAY": ":0"}, platform="linux")
        assert problem is not None
        self.assertIn("python3-tk", problem.detail)

    def test_linux_without_display(self):
        problem = lc.check(tk_ok=True, window_ok=True, env={}, platform="linux")
        assert problem is not None
        self.assertIn("экрана", problem.title.lower())

    def test_linux_wayland_without_xwayland(self):
        problem = lc.check(tk_ok=True, window_ok=True, env={"WAYLAND_DISPLAY": "wayland-0"},
                           platform="linux")
        assert problem is not None
        self.assertIn("XWayland", problem.title)

    def test_problem_never_raised_by_broken_environment(self):
        # env без словаря — не повод падать: запуск важнее проверки
        with mock.patch.object(lc, "check", side_effect=RuntimeError("бум")):
            self.assertTrue(lc.preflight())


class RepairTclTest(unittest.TestCase):
    """Python 3.13.0 + venv: подставляем TCL_LIBRARY из базовой установки, окно работает."""

    def test_sets_tcl_library_for_venv_on_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "Python313"
            (base / "tcl" / "tcl8.6").mkdir(parents=True)
            (base / "tcl" / "tcl8.6" / "init.tcl").write_text("# tcl\n", encoding="utf-8")
            env: dict[str, str] = {}
            with mock.patch.object(lc.sys, "platform", "win32"), \
                 mock.patch.object(lc.sys, "prefix", str(Path(tmp) / ".venv")), \
                 mock.patch.object(lc.sys, "base_prefix", str(base)), \
                 mock.patch.object(lc.os, "environ", env):
                self.assertEqual(lc.repair_tcl_env(), str(base / "tcl" / "tcl8.6"))
                self.assertEqual(env["TCL_LIBRARY"], str(base / "tcl" / "tcl8.6"))

    def test_does_not_touch_existing_variable(self):
        env = {"TCL_LIBRARY": r"C:\own\tcl"}
        with mock.patch.object(lc.sys, "platform", "win32"), \
             mock.patch.object(lc.os, "environ", env):
            self.assertIsNone(lc.repair_tcl_env())
            self.assertEqual(env["TCL_LIBRARY"], r"C:\own\tcl")

    def test_no_repair_outside_venv(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "Python313"
            (base / "tcl" / "tcl8.6").mkdir(parents=True)
            (base / "tcl" / "tcl8.6" / "init.tcl").write_text("# tcl\n", encoding="utf-8")
            with mock.patch.object(lc.sys, "platform", "win32"), \
                 mock.patch.object(lc.sys, "prefix", str(base)), \
                 mock.patch.object(lc.sys, "base_prefix", str(base)), \
                 mock.patch.object(lc.os, "environ", {}):
                self.assertIsNone(lc.repair_tcl_env())


class ReportTest(unittest.TestCase):
    def test_report_shows_whether_window_opens(self):
        with mock.patch.object(lc, "has_tkinter", return_value=True), \
             mock.patch.object(lc, "has_tk_window", return_value=False):
            text = "\n".join(lc.report())
        self.assertIn("окно: НЕ создаётся", text)

    def test_report_survives_cp1252_console(self):
        """`--check > файл` на cmd с cp1252: отчёт не должен теряться из-за кириллицы."""
        import main as entry

        class Cmd:
            encoding = "cp1252"

            def __init__(self):
                self.text = ""
                self.errors = "strict"

            def write(self, s):
                self.text += s.encode("cp1252", self.errors).decode("cp1252")

            def flush(self):
                pass

            def reconfigure(self, **kw):
                self.errors = kw.get("errors", self.errors)

        stream = Cmd()
        with mock.patch.object(entry.sys, "stdout", stream):
            entry._print("Ошибка: кириллица")
        self.assertTrue(stream.text.strip(), "отчёт не должен пропадать")
        self.assertIn("?", stream.text)          # буквы заменены, но строка напечатана
        self.assertIn(":", stream.text)


class JournalTest(unittest.TestCase):
    def test_log_goes_next_to_pilot_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(pilots, "ROOT_DIR", Path(tmp)):
                lc.write_log("проверка журнала")
                text = (Path(tmp) / lc.LOG_NAME).read_text(encoding="utf-8")
        self.assertIn("проверка журнала", text)

    def test_dialog_failure_does_not_raise(self):
        with mock.patch.object(lc.sys, "platform", "linux"), \
             mock.patch.object(lc.shutil, "which", return_value=None):
            self.assertFalse(lc.show_dialog("заголовок", "текст"))

    def test_report_mentions_python_and_tkinter(self):
        text = "\n".join(lc.report())
        self.assertIn("Python:", text)
        self.assertIn("tkinter:", text)


if __name__ == "__main__":
    unittest.main()
