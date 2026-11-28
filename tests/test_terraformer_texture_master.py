"""Текстуры изометрии должны жить в интерпретаторе своего окна.

Без явного ``master`` ImageTk.PhotoImage берёт ``tk._default_root`` — первый
когда-либо созданный в процессе Tk. Если тест открыл второй root, картинка
оказывается в чужом интерпретаторе и Canvas падает с
``TclError: image "pyimageNN" does not exist``. В длинном прогоне это ловили
`test_terraformer_s3_map` и `test_terraformer_s3_path`, а поодиночке они зелёные.
"""
from __future__ import annotations

import tkinter as tk
import unittest

from stamina.lounge.trainer import TrainerGame


class _Event:
    def __init__(self, keysym: str = "", keycode: int = 0, state: int = 0) -> None:
        self.keysym = keysym
        self.keycode = keycode
        self.state = state
        self.x = 0
        self.y = 0


class TextureMasterTest(unittest.TestCase):
    def test_textures_use_game_root_not_default_root(self) -> None:
        try:
            first = tk.Tk()
            first.withdraw()
        except tk.TclError:
            self.skipTest("нет дисплея")
        try:
            game_root = tk.Tk()
            game_root.withdraw()
            try:
                from stamina import theme
                theme.init(game_root)
                game = TrainerGame(game_root, on_back=lambda: None, app=None)
                game.pack(fill=tk.BOTH, expand=True)
                game_root.update()

                game.on_key(_Event("i", 73))   # i — изометрия
                game_root.update()

                self.assertTrue(game.iso_view)
                self.assertTrue(game._texture_photos)
                for name, photo in game._texture_photos.items():
                    self.assertIs(photo.tk, game_root.tk, name)

                game.stop()
                game.destroy()
            finally:
                game_root.destroy()
        finally:
            first.destroy()
