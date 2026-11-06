"""Тесты encoding-устойчивости ci_gate: кириллица в cp1252 не роняет print."""
import io
import sys
import unittest
from unittest import mock

from tools import ci_gate


class CiGateEncodingTest(unittest.TestCase):
    """Проверка, что ci_gate печатает заголовки шагов при любой кодировке консоли."""

    def test_cyrillic_step_names_survive_cp1252_stdout(self):
        """Кириллица в названии шага не роняет print на cp1252-консоли."""
        class Cp1252Stream:
            """Поток с кодировкой cp1252, симулирующий Windows cmd."""
            encoding = "cp1252"
            
            def __init__(self):
                self.text = ""
                self.errors = "strict"
            
            def write(self, s):
                # cp1252 не содержит кириллицу — strict режим бросил бы UnicodeEncodeError
                self.text += s.encode(self.encoding, self.errors).decode(self.encoding)
                return len(s)
            
            def flush(self):
                pass
            
            def reconfigure(self, **kw):
                self.errors = kw.get("errors", self.errors)

        stream = Cp1252Stream()
        with mock.patch.object(sys, "stdout", stream), \
             mock.patch.object(sys, "argv", ["ci_gate.py", "--only", "тест", "--repo", "."]), \
             mock.patch.object(ci_gate, "build_steps", return_value=[
                 {"name": "тест (кириллица)", "cmd": ["echo", "ok"], "tier": "block",
                  "needs_display": False, "full_only": False, "why": "причина"}
             ]), \
             mock.patch.object(ci_gate, "run_step", return_value={
                 "exit": 0, "seconds": 0.1, "output_tail": [], "tier": "block"}):
            # Запуск main с --only для минимального прогона
            exit_code = ci_gate.main()
        
        # Проверяем, что print не упал и текст напечатан (символы заменены на ?)
        self.assertEqual(exit_code, 0, "main должен вернуть 0 при успехе")
        self.assertTrue(stream.text.strip(), "stdout не должен быть пустым")
        # Кириллица заменена на '?', но структура сохранена
        self.assertIn("?", stream.text, "кириллица должна быть заменена")

    def test_main_calls_reconfigure_on_stdout(self):
        """main() вызывает sys.stdout.reconfigure(errors='replace')."""
        original_stdout = sys.stdout
        mock_stdout = mock.MagicMock()
        mock_stdout.reconfigure = mock.MagicMock()
        
        with mock.patch.object(sys, "stdout", mock_stdout), \
             mock.patch.object(sys, "argv", ["ci_gate.py", "--list"]), \
             mock.patch.object(ci_gate, "build_steps", return_value=[]):
            try:
                ci_gate.main()
            except SystemExit:
                pass
        
        # Проверяем, что reconfigure был вызван
        mock_stdout.reconfigure.assert_called_once_with(errors="replace")


if __name__ == "__main__":
    unittest.main()
