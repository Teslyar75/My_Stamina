"""Regression test: requirements.txt должен декодироваться в cp1252."""
import unittest
from pathlib import Path


class RequirementsEncodingTest(unittest.TestCase):
    """Проверка, что requirements.txt устойчив к cp1252 (Windows pip без PYTHONUTF8)."""

    def test_requirements_txt_decodes_in_cp1252(self):
        """requirements.txt декодируется в cp1252 без ошибок.
        
        Предотвращает регрессию: кириллические комментарии в requirements.txt
        падали pip на Windows с cp1252 локалью, пока не был задан PYTHONUTF8=1.
        Содержимое должно быть ASCII-safe для максимальной совместимости.
        """
        req_path = Path(__file__).parent.parent / "requirements.txt"
        with open(req_path, "rb") as f:
            content = f.read()
        
        # Должно декодироваться в cp1252 без UnicodeDecodeError
        try:
            decoded = content.decode("cp1252")
            self.assertTrue(decoded, "decoded content should not be empty")
        except UnicodeDecodeError as e:
            self.fail(f"requirements.txt cannot decode in cp1252: {e}")

    def test_requirements_txt_has_coding_cookie(self):
        """requirements.txt сохраняет coding cookie для документирования."""
        req_path = Path(__file__).parent.parent / "requirements.txt"
        with open(req_path, "r", encoding="utf-8") as f:
            first_line = f.readline()
        
        self.assertIn("coding", first_line.lower(), 
                     "first line should declare encoding via coding cookie")

    def test_requirements_content_unchanged(self):
        """Зависимости остались теми же (Pillow, pypdf, fpdf2)."""
        req_path = Path(__file__).parent.parent / "requirements.txt"
        with open(req_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]
        
        # Проверяем наличие ожидаемых зависимостей
        deps = [l.split(">=")[0].strip() for l in lines]
        self.assertIn("Pillow", deps, "Pillow should be in requirements")
        self.assertIn("pypdf", deps, "pypdf should be in requirements")
        self.assertIn("fpdf2", deps, "fpdf2 should be in requirements")
        self.assertEqual(len(deps), 3, "should have exactly 3 dependencies")


if __name__ == "__main__":
    unittest.main()
