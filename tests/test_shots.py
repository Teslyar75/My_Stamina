"""Снимки экрана для чата ОРИОНА: сохранить, ужать, почистить, найти в буфере."""

import os
import tempfile
import time
import unittest
from pathlib import Path

from stamina import shots

PIL_OK = shots.available()


@unittest.skipUnless(PIL_OK, "нужен Pillow")
class ShotsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_env = os.environ.get("STAR_TYPING_SHOTS_DIR")
        os.environ["STAR_TYPING_SHOTS_DIR"] = self._tmp.name
        self.folder = Path(self._tmp.name)

    def tearDown(self):
        if self._old_env is None:
            os.environ.pop("STAR_TYPING_SHOTS_DIR", None)
        else:
            os.environ["STAR_TYPING_SHOTS_DIR"] = self._old_env
        self._tmp.cleanup()

    @staticmethod
    def _image(size=(64, 48), color=(10, 20, 30)):
        from PIL import Image
        return Image.new("RGB", size, color)

    def test_folder_follows_env(self):
        """Каталог снимков берётся из окружения — иначе тесты писали бы пилоту в корабль."""
        self.assertEqual(shots.shots_dir(), self.folder)

    def test_save_writes_png(self):
        path = shots.save_image(self._image())
        self.assertTrue(path.is_file())
        self.assertEqual(path.suffix, ".png")
        self.assertEqual(path.parent, self.folder)

    def test_save_does_not_overwrite_same_second(self):
        """Два снимка в одну секунду — два файла, а не один затёртый."""
        first = shots.save_image(self._image())
        second = shots.save_image(self._image())
        self.assertNotEqual(first, second)
        self.assertTrue(first.is_file() and second.is_file())

    def test_save_shrinks_to_limit(self):
        """Тяжёлый снимок ужимается под лимит, а не падает."""
        from PIL import Image
        import random
        rnd = random.Random(7)
        noisy = Image.new("RGB", (600, 400))
        noisy.putdata([(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
                       for _ in range(600 * 400)])
        path = shots.save_image(noisy, limit=200_000)
        self.assertLessEqual(path.stat().st_size, 200_000)

    def test_save_gives_up_loudly(self):
        """Если снимок не влезает даже ужатым — ошибка и никакого мусора на борту."""
        path = self.folder / "нет.png"
        with self.assertRaises(ValueError):
            shots.save_image(self._image((400, 400)), limit=50)
        self.assertFalse(path.exists())
        self.assertEqual(list(self.folder.glob("*.png")), [])

    def test_cleanup_removes_only_old(self):
        old = shots.save_image(self._image())
        fresh = shots.save_image(self._image())
        long_ago = time.time() - 40 * 86400
        os.utime(old, (long_ago, long_ago))
        self.assertEqual(shots.cleanup(days=30), 1)
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())

    def test_cleanup_on_missing_folder(self):
        """Папки ещё нет — чистка молчит и не падает."""
        self.assertEqual(shots.cleanup(folder=self.folder / "пусто"), 0)

    def test_thumbnail_fits_box(self):
        path = shots.save_image(self._image((800, 400)))
        pic = shots.thumbnail(path, size=120)
        self.assertIsNotNone(pic)
        self.assertLessEqual(max(pic.size), 120)
        self.assertGreater(pic.width, pic.height)      # пропорции снимка сохранены

    def test_thumbnail_of_missing_file(self):
        self.assertIsNone(shots.thumbnail(self.folder / "нет-такого.png"))

    def test_open_missing_file(self):
        self.assertFalse(shots.open_file(self.folder / "нет-такого.png"))

    def test_filename_is_timestamp(self):
        name = shots.new_filename(now=time.mktime((2026, 10, 19, 20, 15, 30, 0, 0, -1)))
        self.assertEqual(name, "20261019-201530.png")

    def test_cleanup_never_touches_other_files(self):
        (self.folder / "заметка.txt").write_text("не снимок", encoding="utf-8")
        shots.cleanup(days=0, now=time.time() + 86400)
        self.assertTrue((self.folder / "заметка.txt").exists())

    def test_finds_path_in_text(self):
        """Пилот пишет путь словами — корабль находит его сам, пробелы не мешают."""
        path = shots.save_image(self._image())
        text = f"смотри что тут: {path} — кажется, сломалось"
        self.assertEqual(shots.image_paths_in(text), [path])

    def test_ignores_paths_of_missing_files(self):
        self.assertEqual(shots.image_paths_in(r"C:\нет-такого\снимок.png"), [])

    def test_ignores_text_without_paths(self):
        self.assertEqual(shots.image_paths_in("просто просьба, сэр"), [])

    def test_adopt_copies_file_into_ship(self):
        """Снимок с рабочего стола переезжает внутрь корабля — иначе агент его не прочтёт."""
        with tempfile.TemporaryDirectory() as outside_dir:
            shots.save_image(self._image(), folder=Path(outside_dir))
            outside = next(Path(outside_dir).glob("*.png"))
            taken = shots.adopt([outside])
            self.assertEqual(len(taken), 1)
            self.assertEqual(taken[0].parent, self.folder)
            self.assertEqual(taken[0].name, outside.name)
            self.assertTrue(taken[0].is_file())
            self.assertTrue(outside.is_file())      # оригинал не трогаем

    def test_adopt_keeps_file_already_inside(self):
        inside = shots.save_image(self._image())
        self.assertEqual(shots.adopt([inside]), [inside])

    def test_adopt_survives_lost_file(self):
        self.assertEqual(shots.adopt([self.folder / "испарился.png"]), [])


if __name__ == "__main__":
    unittest.main()
