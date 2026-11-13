"""Тренажёр терраформера A1: логика поля, камера, чертёж и Tk-дым."""
from __future__ import annotations

import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from stamina import pilots, theme
from stamina.terraformer_trainer import (
    BASE_CELL,
    HOLD_CAP,
    LAYERS,
    SITE,
    ZOOM_MAX,
    ZOOM_MIN,
    Camera,
    TrainerModel,
    load_blueprint,
    save_blueprint,
)


def _dig_until_soil_full(model: TrainerModel) -> None:
    for y in range(model.h):
        for x in range(model.w):
            if model.holds["soil"] >= HOLD_CAP:
                return
            if model.on_site(x, y) or model.dug[y][x]:
                continue
            model.robot = [x, y]
            if model.dig() != "ok":
                raise AssertionError("не удалось набрать грунт")


class TrainerModelTest(unittest.TestCase):
    def test_move_clamps_at_edges(self) -> None:
        m = TrainerModel()
        m.robot = [0, 0]
        self.assertFalse(m.move(-1, 0))
        self.assertEqual(m.robot, [0, 0])
        self.assertEqual(m.facing, (-1, 0))
        m.robot = [m.w - 1, m.h - 1]
        self.assertFalse(m.move(1, 1))
        self.assertEqual(m.robot, [m.w - 1, m.h - 1])
        m.robot = [5, 5]
        self.assertTrue(m.move(1, 0))
        self.assertEqual(m.robot, [6, 5])

    def test_dig_takes_soil_then_depth_blocks(self) -> None:
        m = TrainerModel(depth=1)
        m.finds = {}
        m.robot = [10, 10]
        self.assertEqual(m.dig(), "ok")
        self.assertEqual(m.holds["soil"], 1)
        self.assertEqual(m.dug[10][10], 1)
        self.assertEqual(m.dig(), "too_deep")

    def test_depth_two_takes_clay(self) -> None:
        m = TrainerModel(depth=2)
        m.finds = {}
        m.robot = [10, 10]
        self.assertEqual(m.dig(), "ok")
        self.assertEqual(m.dig(), "ok")
        self.assertEqual(m.holds["soil"], 1)
        self.assertEqual(m.holds["clay"], 1)
        self.assertEqual(m.dug[10][10], 2)
        self.assertEqual(m.dig(), "too_deep")

    def test_site_is_not_diggable(self) -> None:
        m = TrainerModel()
        sx, sy = SITE[0], SITE[1]
        m.robot = [sx, sy]
        self.assertTrue(m.on_site(sx, sy))
        self.assertEqual(m.dig(), "site")
        self.assertEqual(m.holds["soil"], 0)

    def test_hold_full_and_robot_still_moves(self) -> None:
        m = TrainerModel()
        _dig_until_soil_full(m)
        self.assertTrue(m.hold_full("soil"))
        x, y = 0, 0
        while m.on_site(x, y) or m.dug[y][x]:
            x += 1
        m.robot = [x, y]
        self.assertEqual(m.dig(), "hold_full")
        self.assertEqual(m.holds["soil"], HOLD_CAP)
        before = list(m.robot)
        m.move(1, 0)
        self.assertNotEqual(m.robot, before)

    def test_unload_needs_full_hold_then_places_block(self) -> None:
        m = TrainerModel()
        self.assertEqual(m.unload(), "not_full")
        _dig_until_soil_full(m)
        self.assertEqual(m.unload(), "ok")
        self.assertEqual(m.progress(), (1, len(m.site_cells())))
        self.assertEqual(m.holds["soil"], 0)
        self.assertEqual(m.blocks, [m.site_cells()[0]])

    def test_twelve_unloads_complete_foundation(self) -> None:
        m = TrainerModel()
        for i in range(12):
            _dig_until_soil_full(m)
            result = m.unload()
            if i < 11:
                self.assertEqual(result, "ok")
            else:
                self.assertEqual(result, "complete")
        self.assertTrue(m.walls_open)
        self.assertEqual(m.progress(), (12, 12))
        _dig_until_soil_full(m)
        self.assertEqual(m.unload(), "done")

    def test_switch_hold_cycles(self) -> None:
        m = TrainerModel()
        self.assertEqual(m.active_hold, LAYERS[0])
        self.assertEqual(m.switch_hold(), LAYERS[1])
        self.assertEqual(m.switch_hold(), LAYERS[2])
        self.assertEqual(m.switch_hold(), LAYERS[0])

    def test_layer_left(self) -> None:
        m = TrainerModel(depth=2)
        m.finds = {}
        self.assertEqual(m.layer_left(10, 10), 2)
        m.robot = [10, 10]
        m.dig()
        self.assertEqual(m.layer_left(10, 10), 1)
        m.dig()
        self.assertEqual(m.layer_left(10, 10), 0)


class CameraTest(unittest.TestCase):
    def test_zoom_clamps(self) -> None:
        cam = Camera(40, 24)
        self.assertAlmostEqual(cam.cell_px(), BASE_CELL)
        for _ in range(50):
            cam.zoom_in()
        self.assertEqual(cam.zoom, ZOOM_MAX)
        for _ in range(50):
            cam.zoom_out()
        self.assertEqual(cam.zoom, ZOOM_MIN)

    def test_reset_and_track(self) -> None:
        cam = Camera(40, 24)
        cam.pan(10, 10)
        self.assertFalse(cam.follow)
        cam.reset(5, 6)
        self.assertTrue(cam.follow)
        self.assertEqual(cam.zoom, 1.0)
        self.assertAlmostEqual(cam.cx, 5.5)
        self.assertAlmostEqual(cam.cy, 6.5)
        cam.track(8, 9)
        self.assertAlmostEqual(cam.cx, 8.5)
        self.assertAlmostEqual(cam.cy, 9.5)

    def test_pan_disables_follow_and_clamps(self) -> None:
        cam = Camera(40, 24)
        cam.pan(-1000, -1000)
        self.assertFalse(cam.follow)
        self.assertGreaterEqual(cam.cx, 0)
        self.assertGreaterEqual(cam.cy, 0)
        cam.pan(10000, 10000)
        self.assertLessEqual(cam.cx, 40)
        self.assertLessEqual(cam.cy, 24)

    def test_to_screen_center(self) -> None:
        cam = Camera(40, 24)
        cam.reset(10, 10)
        px, py = cam.to_screen(10, 10, 800, 600)
        self.assertAlmostEqual(px, 400 - BASE_CELL / 2)
        self.assertAlmostEqual(py, 300 - BASE_CELL / 2)


class BlueprintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "Stamina"
        self.root.mkdir()
        pilots.reset_root(self.root)
        self.pilot = pilots.create("Tester")
        pilots.activate(self.pilot["id"])

    def tearDown(self) -> None:
        pilots.reset_root()
        self.tmp.cleanup()

    def test_round_trip(self) -> None:
        m = TrainerModel()
        m.robot = [7, 7]
        m.dig()
        _dig_until_soil_full(m)
        m.unload()
        self.assertTrue(save_blueprint(m))
        loaded = load_blueprint()
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.to_blueprint(), m.to_blueprint())

    def test_garbage_from_blueprint_is_fresh(self) -> None:
        fresh = TrainerModel.from_blueprint({"kind": "wrong"})
        self.assertEqual(fresh.w, TrainerModel().w)
        self.assertEqual(fresh.h, TrainerModel().h)
        fresh = TrainerModel.from_blueprint({"kind": "terraformer_trainer", "w": "x"})
        self.assertEqual(fresh.dug, [[0] * fresh.w for _ in range(fresh.h)])
        fresh = TrainerModel.from_blueprint("garbage")  # type: ignore[arg-type]
        self.assertEqual(fresh.w, TrainerModel().w)

    def test_load_missing_and_garbage(self) -> None:
        self.assertIsNone(load_blueprint())
        path = Path(self.tmp.name) / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        self.assertIsNone(load_blueprint(path))
        path.write_text(json.dumps({"kind": "other"}), encoding="utf-8")
        self.assertIsNone(load_blueprint(path))


class TrainerTkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.root = tk.Tk()
        except tk.TclError:
            cls.root = None
            return
        theme.init(cls.root)
        cls.root.geometry("1024x600")

    @classmethod
    def tearDownClass(cls) -> None:
        if getattr(cls, "root", None) is not None:
            try:
                cls.root.destroy()
            except tk.TclError:
                pass

    def setUp(self) -> None:
        if getattr(self, "root", None) is None:
            self.skipTest("нет дисплея")
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name) / "Stamina"
        self.data.mkdir()
        pilots.reset_root(self.data)
        p = pilots.create("Tester")
        pilots.activate(p["id"])

        from stamina.lounge.screen import GAMES
        from stamina.lounge.trainer import TrainerGame

        self.assertIn("trainer", [g["id"] for g in GAMES])
        self.game = TrainerGame(self.root, on_back=lambda: None, app=None)
        self.game.pack(fill=tk.BOTH, expand=True)
        self.root.update()

    def tearDown(self) -> None:
        try:
            self.game.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.game.destroy()
        except tk.TclError:
            pass
        self.root.update()
        pilots.reset_root()
        self.tmp.cleanup()

    class _Event:
        def __init__(self, keysym: str, keycode: int = 0, state: int = 0) -> None:
            self.keysym = keysym
            self.keycode = keycode
            self.state = state

    def _canvas_texts(self) -> list[str]:
        c = self.game.canvas
        return [c.itemcget(i, "text") for i in c.find_all() if c.type(i) == "text"]

    def test_handlers_move_dig_and_keys(self) -> None:
        before = list(self.game.model.robot)
        self.game.do_move(-1, 0)
        self.root.update()
        self.assertNotEqual(self.game.model.robot, before)

        self.game.model.robot = [10, 10]
        self.assertEqual(self.game.do_dig(), "ok")
        self.assertEqual(self.game.model.holds["soil"], 1)

        self.assertEqual(self.game.do_unload(), "not_full")

        self.assertIn("Учебная смена", "\n".join(self._canvas_texts()))

    def test_on_key_and_wheel(self) -> None:
        before = list(self.game.model.robot)
        self.game.on_key(self._Event("d", 68))
        self.root.update()
        self.assertEqual(self.game.model.robot[0], before[0] + 1)

        # русская раскладка: неизвестный keysym, знакомый keycode
        before = list(self.game.model.robot)
        self.game.on_key(self._Event("в", 65))
        self.root.update()
        self.assertEqual(self.game.model.robot[0], before[0] - 1)

        zoom = self.game.camera.zoom
        self.game.on_wheel(-1, True, False)
        self.assertGreater(self.game.camera.zoom, zoom)
        self.game.on_wheel(1, True, False)
        self.assertAlmostEqual(self.game.camera.zoom, zoom)


class ArchiveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "Stamina"
        self.root.mkdir()
        pilots.reset_root(self.root)
        pilots.activate(pilots.create("Tester")["id"])

    def tearDown(self) -> None:
        pilots.reset_root()
        self.tmp.cleanup()

    def test_archive_copies_and_keeps_latest(self) -> None:
        from stamina.terraformer_trainer import ARCHIVE_DIR, archive_blueprint, blueprint_path
        self.assertIsNone(archive_blueprint())          # нет чертежа — нечего архивировать
        m = TrainerModel()
        m.robot = [7, 7]
        m.dig()
        self.assertTrue(save_blueprint(m))
        folder = blueprint_path().parent / ARCHIVE_DIR
        other = folder.parent / "keep_me.json"
        other.write_text("{}", encoding="utf-8")        # чужие файлы пилота не трогаем
        first = archive_blueprint(stamp="20260101-000000")
        self.assertIsNotNone(first)
        self.assertEqual(json.loads(first.read_text(encoding="utf-8")), m.to_blueprint())
        for i in range(25):
            archive_blueprint(keep=20, stamp=f"20260101-0001{i:02d}")
        files = sorted(folder.glob("*.json"))
        self.assertEqual(len(files), 20)
        self.assertTrue(other.is_file())
        self.assertTrue(blueprint_path().is_file())

    def test_restart_archives_previous_site(self) -> None:
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("нет дисплея")
        try:
            theme.init(root)
            from stamina.lounge.trainer import TrainerGame
            from stamina.terraformer_trainer import ARCHIVE_DIR, blueprint_path
            game = TrainerGame(root, on_back=lambda: None, app=None)
            game.model.robot = [10, 10]
            game.do_dig()
            game.reset()                                  # то, что делает кнопка ЗАНОВО
            arch = list((blueprint_path().parent / ARCHIVE_DIR).glob("*.json"))
            self.assertEqual(len(arch), 1)
            saved = json.loads(arch[0].read_text(encoding="utf-8"))
            self.assertEqual(saved["dug"][10][10], 1)
            self.assertEqual(game.model.dug[10][10], 0)
            game.stop()
            game.destroy()
        finally:
            root.destroy()


def _cell_with(model: TrainerModel, res: str, layer: int):
    return next(c for c, f in sorted(model.finds.items()) if f == (res, layer))


class FindsModelTest(unittest.TestCase):
    """Находки: детерминизм по сиду, открытие ровно один раз, отдельный отсек."""

    def test_seed_is_deterministic_and_saved(self) -> None:
        from stamina.terraformer_trainer import RESOURCES
        a, b = TrainerModel(seed=1234), TrainerModel(seed=1234)
        self.assertEqual(a.finds, b.finds)
        self.assertNotEqual(a.finds, TrainerModel(seed=4321).finds)
        again = TrainerModel.from_blueprint(a.to_blueprint())
        self.assertEqual(again.seed, 1234)
        self.assertEqual(again.finds, a.finds)
        cells = a.w * a.h
        self.assertTrue(0.04 * cells <= len(a.finds) <= 0.08 * cells, len(a.finds))
        self.assertEqual({f[0] for f in a.finds.values()}, set(RESOURCES))
        for cell in a.site_cells() + [tuple(a.robot)]:
            self.assertNotIn(cell, a.finds)

    def test_a1_can_find_something(self) -> None:
        for seed in (1, 2, 3, 99):
            top = [f[0] for f in TrainerModel(seed=seed).finds.values() if f[1] == 0]
            self.assertGreaterEqual(top.count("water"), 1)
            self.assertIn("organic", top)
            self.assertIn("quartz", top)

    def test_find_revealed_once_and_spring_blocks(self) -> None:
        m = TrainerModel(seed=7)
        m.robot = list(_cell_with(m, "water", 0))
        self.assertEqual(m.dig(), "ok")
        self.assertEqual(m.last_find["res"], "water")
        self.assertTrue(m.last_find["first"])
        self.assertEqual(m.dig(), "spring")
        self.assertIsNone(m.last_find)
        self.assertEqual(m.finds_count["water"], 1)
        self.assertIn(tuple(m.robot), m.springs)

        m.robot = list(_cell_with(m, "organic", 0))
        self.assertEqual(m.dig(), "ok")
        self.assertEqual(m.last_find["res"], "organic")
        self.assertEqual(m.dig(), "too_deep")
        self.assertIsNone(m.last_find)
        self.assertEqual(m.finds_count["organic"], 1)
        second = [c for c, f in m.finds.items() if f == ("organic", 0) and c != tuple(m.robot)][0]
        m.robot = list(second)
        m.dig()
        self.assertFalse(m.last_find["first"])
        self.assertEqual(m.finds_count["organic"], 2)

    def test_find_goes_to_own_hold_when_soil_full(self) -> None:
        m = TrainerModel(seed=11)
        m.holds["soil"] = HOLD_CAP
        m.robot = list(_cell_with(m, "quartz", 0))
        self.assertEqual(m.dig(), "hold_full")
        self.assertEqual(m.last_find["res"], "quartz")
        self.assertEqual(m.finds_count["quartz"], 1)
        self.assertEqual(m.holds["soil"], HOLD_CAP)
        self.assertEqual(m.dig(), "hold_full")
        self.assertIsNone(m.last_find)                 # второй раз не открывается
        self.assertEqual(m.finds_count["quartz"], 1)

    def test_a1_does_not_reveal_deep_finds(self) -> None:
        m = TrainerModel(seed=5)
        m.robot = list(_cell_with(m, "stone", 1))
        self.assertEqual(m.dig(), "ok")
        self.assertIsNone(m.last_find)
        self.assertEqual(m.dig(), "too_deep")
        self.assertEqual(m.finds_count["stone"], 0)

    def test_old_blueprint_without_finds_loads(self) -> None:
        m = TrainerModel(seed=3)
        old = m.to_blueprint()
        for k in ("seed", "revealed", "finds_count"):
            old.pop(k)
        loaded = TrainerModel.from_blueprint(old)
        self.assertEqual(sum(loaded.finds_count.values()), 0)
        self.assertEqual(loaded.revealed, set())
        self.assertTrue(loaded.finds)
        self.assertEqual(loaded.dug, m.dug)

    def test_new_blueprint_roundtrip_keeps_finds(self) -> None:
        m = TrainerModel(seed=21)
        m.robot = list(_cell_with(m, "organic", 0))
        m.dig()
        loaded = TrainerModel.from_blueprint(json.loads(json.dumps(m.to_blueprint())))
        self.assertEqual(loaded.finds_count, m.finds_count)
        self.assertEqual(loaded.revealed, m.revealed)
        loaded.robot = list(m.robot)
        loaded.dig()
        self.assertIsNone(loaded.last_find)            # уже открытое не открывается снова


class TrainerHelpTkTest(unittest.TestCase):
    """F1-инструкция, отсек «Находки», уведомления и ширина подсказки (1280)."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.root = tk.Tk()
        except tk.TclError:
            cls.root = None
            return
        theme.init(cls.root)
        cls.root.geometry("1280x720")

    @classmethod
    def tearDownClass(cls) -> None:
        if getattr(cls, "root", None) is not None:
            try:
                cls.root.destroy()
            except tk.TclError:
                pass

    def setUp(self) -> None:
        if getattr(self, "root", None) is None:
            self.skipTest("нет дисплея")
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name) / "Stamina"
        self.data.mkdir()
        pilots.reset_root(self.data)
        pilots.activate(pilots.create("Tester")["id"])
        from stamina.lounge.trainer import TrainerGame
        self.game = TrainerGame(self.root, on_back=lambda: None, app=None)
        self.game.pack(fill=tk.BOTH, expand=True)
        self.root.update()

    def tearDown(self) -> None:
        try:
            self.game.stop()
            self.game.destroy()
        except tk.TclError:
            pass
        self.root.update()
        pilots.reset_root()
        self.tmp.cleanup()

    class _Event:
        def __init__(self, keysym: str, keycode: int = 0, state: int = 0) -> None:
            self.keysym, self.keycode, self.state = keysym, keycode, state

    def _texts(self, tag: str | None = None) -> str:
        c = self.game.canvas
        ids = c.find_withtag(tag) if tag else c.find_all()
        return "\n".join(c.itemcget(i, "text") for i in ids if c.type(i) == "text")

    def test_f1_opens_and_closes_and_blocks_keys(self) -> None:
        g = self.game
        self.assertTrue(g.on_help())
        self.assertEqual(g.overlay, "help")
        self.root.update()
        self.assertIn("Ресурсы и находки", self._texts("help"))
        self.assertTrue(g.help_fits)                   # без прокрутки на 1280×720
        before = list(g.model.robot)
        g.on_key(self._Event("d", 68))
        g.on_key(self._Event("space", 32))
        g.on_wheel(-1, True, False)
        self.assertEqual(g.model.robot, before)
        self.assertEqual(g.model.holds["soil"], 0)
        self.assertEqual(g.camera.zoom, 1.0)
        g.on_key(self._Event("Escape", 27))
        self.assertIsNone(g.overlay)
        self.assertFalse(g.paused)                     # Esc закрыл инструкцию, а не поставил паузу
        g.on_key(self._Event("F1", 112))
        self.assertEqual(g.overlay, "help")
        g.on_key(self._Event("F1", 112))
        self.assertIsNone(g.overlay)

    def test_lounge_delegates_f1_only_in_trainer(self) -> None:
        from stamina.lounge.screen import LoungeScreen

        class _App:
            living = None

            def set_status(self, *_a, **_k):
                pass

            def open_help(self):
                pass
        scr = LoungeScreen(self.root, _App())
        try:
            self.assertFalse(scr.on_help())            # лобби — обычная справка страницы
            scr.launch("trainer")
            self.assertTrue(scr.on_help())
            self.assertEqual(scr.game.overlay, "help")
            scr.show_lobby()
            scr.launch("snake")
            self.assertFalse(scr.on_help())
        finally:
            scr.close()
            scr.destroy()

    def test_finds_panel_and_toast(self) -> None:
        g = self.game
        g.model = TrainerModel(seed=7)
        self.assertEqual(g.toggle_finds(), "finds")
        self.root.update()
        self.assertIn("???", self._texts("finds"))
        before = list(g.model.robot)
        g.on_key(self._Event("d", 68))
        self.assertEqual(g.model.robot, before)        # пока открыт отсек — робот стоит
        g.on_key(self._Event("q", 81))
        self.assertIsNone(g.overlay)

        g.model.robot = list(_cell_with(g.model, "water", 0))
        g.do_dig()
        self.assertIsNotNone(g.toast)
        self.assertIn("источник воды", g.toast[0])
        self.assertTrue(g.toast[1])                    # первая находка типа — ярче
        self.root.update()
        self.assertIn(g.toast[0], self._texts("toast"))
        cells = [c for c, f in sorted(g.model.finds.items()) if f == ("water", 0)]
        g.model.robot = list(cells[1])
        g.do_dig()
        self.assertFalse(g.toast[1])
        g.on_key(self._Event("Escape", 27))            # Esc без оверлея — пауза
        self.assertTrue(g.paused)
        g.on_key(self._Event("Escape", 27))
        g.toggle_finds()
        self.root.update()
        text = self._texts("finds")
        self.assertIn("Источник воды × 2", text)
        self.assertIn("Пригодится на этапе", text)
        from stamina.terraformer_trainer import load_blueprint
        self.assertEqual(load_blueprint().finds_count["water"], 2)   # находка сохранена сразу

    def test_key_hint_fits_1280_in_all_languages(self) -> None:
        import tkinter.font as tkfont
        from stamina import i18n
        from stamina.lounge.trainer import key_hint
        key = key_hint()
        self.assertIn("F1", key)
        self.assertIn("Q", key)
        font = tkfont.Font(root=self.root, font=theme.font(10))
        room = 1280 - theme.px(12) * 2 - theme.px(40)
        for lang in ("ru", "uk", "en", "de"):
            text = key if lang == "ru" else json.loads(
                (i18n.DIR / f"{lang}.json").read_text(encoding="utf-8"))[key]
            self.assertLessEqual(font.measure(text), room, lang)
        self.root.update()
        self.game.redraw()
        self.assertEqual(self.game.hint_font_size, 10)
        self.assertIn("F1", self._texts("keyhint"))


class TrainerI18nTest(unittest.TestCase):
    def test_help_and_resource_keys_in_all_languages(self) -> None:
        from stamina import i18n
        from stamina.lounge import trainer as tr
        from stamina.terraformer_trainer import RESOURCES
        keys = [tr.key_hint(), "ИНСТРУКЦИЯ · ТРЕНАЖЁР ТЕРРАФОРМЕРА", "F1 или Esc — закрыть",
                "ОТСЕК «НАХОДКИ»", "Q или Esc — закрыть", "Отлично, нашёл источник воды!",
                "Нашёл ресурс: {0}"]
        for head, body in tr.help_sections():
            keys += [head, body]
        for res in RESOURCES:
            use, stage = tr.resource_use(res)
            keys += [tr.resource_name(res), use, stage]
        ru = json.loads((i18n.DIR / "ru.json").read_text(encoding="utf-8"))
        for lang in ("uk", "en", "de"):
            table = json.loads((i18n.DIR / f"{lang}.json").read_text(encoding="utf-8"))
            for k in keys:
                self.assertIn(k, ru)
                self.assertTrue(table.get(k), (lang, k))


if __name__ == "__main__":
    unittest.main()
