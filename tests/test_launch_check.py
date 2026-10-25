"""Тесты проверки перед стартом: без неё «программа не запускается» выглядит молчанием.

Проверка решает, что показать человеку: нет tkinter, нет экрана, нет X11.
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
        self.assertIsNone(lc.check(tk_ok=True, env={"DISPLAY": ":0"}, platform="linux"))

    def test_ok_on_windows_without_display_variable(self):
        self.assertIsNone(lc.check(tk_ok=True, env={}, platform="win32"))

    def test_missing_tkinter_names_the_package(self):
        problem = lc.check(tk_ok=False, env={"DISPLAY": ":0"}, platform="linux")
        assert problem is not None
        self.assertIn("tkinter", problem.detail)
        self.assertIn("python3-tk", problem.detail)

    def test_missing_tkinter_on_windows_points_to_installer(self):
        problem = lc.check(tk_ok=False, env={}, platform="win32")
        assert problem is not None
        self.assertIn("python.org", problem.detail)

    def test_linux_without_display(self):
        problem = lc.check(tk_ok=True, env={}, platform="linux")
        assert problem is not None
        self.assertIn("экрана", problem.title.lower())

    def test_linux_wayland_without_xwayland(self):
        problem = lc.check(tk_ok=True, env={"WAYLAND_DISPLAY": "wayland-0"}, platform="linux")
        assert problem is not None
        self.assertIn("XWayland", problem.title)

    def test_problem_never_raised_by_broken_environment(self):
        # env без словаря — не повод падать: запуск важнее проверки
        with mock.patch.object(lc, "check", side_effect=RuntimeError("бум")):
            self.assertTrue(lc.preflight())


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
