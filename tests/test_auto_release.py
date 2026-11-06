"""Тесты авто-выпуска: без него релиз не появляется, и обновляться нечем.

Главное, что здесь проверяется, — решение «выпускать или молчать». Ошибка в нём
дорого стоит: лишний релиз на каждый пустяк или, наоборот, тишина, из-за которой
у пилота месяцами нет обновлений (так и вышло с 3.7.0).
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import auto_release as ar


class VersionTest(unittest.TestCase):
    def test_parse_with_and_without_v(self):
        self.assertEqual(ar.parse_version("v3.8.1"), (3, 8, 1))
        self.assertEqual(ar.parse_version("3.8.1"), (3, 8, 1))

    def test_parse_rejects_snapshot_tags(self):
        self.assertIsNone(ar.parse_version("snap-20261105-1040"))
        self.assertIsNone(ar.parse_version(""))

    def test_bump_patch(self):
        self.assertEqual(ar.bump_patch("3.7.0"), "3.7.1")
        self.assertEqual(ar.bump_patch("v3.7.9"), "3.7.10")

    def test_released_versions_skips_noise(self):
        tags = ["v3.7.0", "snap-20261022-1942", "v3.8.0", "v3.8.0-beta"]
        self.assertEqual(ar.released_versions(tags), ["3.7.0", "3.8.0"])


class DecideTest(unittest.TestCase):
    def test_first_release_uses_current(self):
        self.assertEqual(ar.decide("3.8.0", [], 0), "3.8.0")

    def test_nothing_to_do_when_version_released_and_no_commits(self):
        # так CI не зацикливается на собственном коммите выпуска
        self.assertIsNone(ar.decide("3.8.0", ["3.8.0"], 0))

    def test_new_commits_after_release_bump_patch(self):
        self.assertEqual(ar.decide("3.8.0", ["3.8.0"], 7), "3.8.1")

    def test_manual_minor_wins(self):
        # в __version__ поставили 3.9.0 руками — выпускаем именно её
        self.assertEqual(ar.decide("3.9.0", ["3.8.0"], 12), "3.9.0")

    def test_older_current_is_not_published(self):
        # откатили версию назад: не выпускаем «новый» старый номер
        self.assertEqual(ar.decide("3.7.0", ["3.8.0"], 5), "3.8.1")

    def test_broken_version_does_not_release(self):
        self.assertIsNone(ar.decide("0.0.0", [], 3))
        self.assertIsNone(ar.decide("не версия", ["3.8.0"], 3))


class ChangelogTest(unittest.TestCase):
    TEXT = (
        "# История изменений\n\n"
        "## Не выпущено\n\n"
        "### Исправлено\n"
        "- Починили запуск.\n\n"
        "## 3.7.0 — 17.10.2026 — автообновления\n\n"
        "### Добавлено\n"
        "- Проверка обновлений.\n"
    )

    def test_renames_section_and_keeps_body(self):
        out = ar.release_changelog(self.TEXT, "3.8.0", "06.11.2026")
        self.assertIn("## 3.8.0 — 06.11.2026", out)
        self.assertIn("- Починили запуск.", out)
        self.assertNotIn("## Не выпущено\n\n### Исправлено", out)

    def test_leaves_fresh_unreleased_section_on_top(self):
        out = ar.release_changelog(self.TEXT, "3.8.0", "06.11.2026")
        self.assertLess(out.index("## Не выпущено"), out.index("## 3.8.0"))

    def test_second_release_uses_the_fresh_section(self):
        once = ar.release_changelog(self.TEXT, "3.8.0", "06.11.2026")
        # в новую секцию кто-то дописал работу
        once = once.replace(ar.EMPTY_SECTION, ar.EMPTY_SECTION + "### Исправлено\n- Ещё фикс.\n\n", 1)
        twice = ar.release_changelog(once, "3.8.1", "07.11.2026")
        self.assertIn("## 3.8.1 — 07.11.2026", twice)
        self.assertIn("- Ещё фикс.", twice.split("## 3.8.1", 1)[1])
        self.assertIn("- Починили запуск.", twice)   # старые записи целы

    def test_missing_unreleased_section_changes_nothing(self):
        text = "# История\n\n## 3.7.0 — 17.10.2026\n\n- что-то\n"
        self.assertEqual(ar.release_changelog(text, "3.8.0", "06.11.2026"), text)


class VersionFileTest(unittest.TestCase):
    def test_read_and_write_keep_comment_and_encoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "stamina").mkdir()
            init = root / "stamina" / "__init__.py"
            init.write_text('"""Пакет."""\n\n__version__ = "3.7.0"\n',
                            encoding="utf-8")
            self.assertEqual(ar.read_version(root), "3.7.0")
            ar.write_version("3.8.0", root)
            self.assertEqual(ar.read_version(root), "3.8.0")
            self.assertIn("Пакет", init.read_text(encoding="utf-8"))

    def test_missing_version_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "stamina").mkdir()
            (root / "stamina" / "__init__.py").write_text("x = 1\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                ar.read_version(root)


class NotesTest(unittest.TestCase):
    def test_notes_from_changelog(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CHANGELOG.md"
            path.write_text(ChangelogTest.TEXT.replace("## Не выпущено", "## 3.8.0"),
                            encoding="utf-8")
            with mock.patch.object(ar, "CHANGELOG", path):
                notes = ar.release_notes("3.8.0")
        self.assertIn("Починили запуск", notes)

    def test_empty_notes_fall_back_to_commits(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CHANGELOG.md"
            path.write_text("# История\n\n## Не выпущено\n", encoding="utf-8")
            with mock.patch.object(ar, "CHANGELOG", path), \
                 mock.patch.object(ar, "commit_subjects",
                                   return_value=["- feat: пульт-кабина", "- fix: запуск"]):
                notes = ar.release_notes("3.8.0")
        self.assertIn("пульт-кабина", notes)
        self.assertIn("2 коммитов", notes)


if __name__ == "__main__":
    unittest.main()
