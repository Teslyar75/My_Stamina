"""Своя история правок (Ctrl+Z / Ctrl+Y) для редактора документов.

Встроенная отмена tk.Text не записывает вставку и удаление картинок
(image create): после «вставили снимок → Ctrl+Z» Tk откатывал предыдущий
текст, а снимок оставался, и наоборот — удалённый снимок не возвращался.

Здесь команда виджета подменяется прокси (как idlelib.redirector):
все insert / delete / replace / image create, откуда бы они ни пришли
(классовые привязки Tk, вставка из буфера, код редактора), записываются
в стек. Удаление запоминает и текст, и картинки с их шириной, поэтому
отмена возвращает документ точно в прежнее состояние. Изменение размера
картинки пишется отдельным шагом через record_resize().

Правки группируются «как в Tk»: набор подряд — одна группа до пробела
после слова, смены вставки на удаление, прыжка курсора или явного
edit separator.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable

MAX_GROUPS = 500


class DocUndo:
    """Подменяет команду text-виджета и ведёт стек отмены.

    image_width(name) -> int | None — логическая ширина картинки (для удаления);
    restore_image(index, name, width) — вставить картинку обратно;
    set_width(name, width) — поменять ширину картинки (шаг «размер»).
    on_cursor() — зовётся после любой правки или перемещения курсора.
    """

    def __init__(self, text: tk.Text, *, image_width: Callable[[str], int | None],
                 restore_image: Callable[[str, str, int | None], None],
                 set_width: Callable[[str, int], None],
                 on_cursor: Callable[[], None] | None = None) -> None:
        self.text = text
        self.image_width = image_width
        self.restore_image = restore_image
        self.set_width = set_width
        self.on_cursor = on_cursor
        self.undo_stack: list[list[tuple]] = []
        self.redo_stack: list[list[tuple]] = []
        self._open = False           # последняя группа ещё принимает правки
        self._last: tuple | None = None
        self.replaying = False
        text.configure(undo=False)
        w = text._w
        self._orig = w + "_docundo_orig"
        text.tk.call("rename", w, self._orig)
        text.tk.createcommand(w, self._dispatch)
        text.bind("<Destroy>", self._on_destroy, add="+")

    # -- прокси -----------------------------------------------------------------------
    def _on_destroy(self, e) -> None:
        if e.widget is not self.text:
            return
        try:
            self.text.tk.deletecommand(self.text._w)
        except tk.TclError:
            pass

    def raw(self, *args):
        """Команда виджета мимо истории."""
        return self.text.tk.call(self._orig, *args)

    def _dispatch(self, *args):
        cmd = args[0] if args else ""
        if cmd == "edit" and len(args) > 1:
            sub = args[1]
            if sub == "undo":
                return self.undo()
            if sub == "redo":
                return self.redo()
            if sub == "separator":
                self.separator()
                return ""
            if sub == "reset":
                self.reset()
                return ""
            if sub == "canundo":
                return int(bool(self.undo_stack))
            if sub == "canredo":
                return int(bool(self.redo_stack))
            return self.raw(*args)
        if self.replaying:
            return self.raw(*args)
        if cmd == "insert" and len(args) >= 3:
            return self._insert(args[1], args[2:])
        if cmd == "delete" and len(args) >= 2:
            return self._delete(args[1:])
        if cmd == "replace" and len(args) >= 4:
            a, b = self.raw("index", args[1]), self.raw("index", args[2])
            self._delete((a, b), kind_break=False)
            return self._insert(a, args[3:], kind_break=False)
        if cmd == "image" and len(args) >= 3 and args[1] == "create":
            return self._image_create(args[2:])
        res = self.raw(*args)
        if cmd == "mark" and len(args) >= 3 and args[1] == "set" and args[2] == "insert":
            self._cursor()
        return res

    def _cursor(self) -> None:
        if self.on_cursor is not None:
            try:
                self.on_cursor()
            except Exception:  # noqa: BLE001 — колбэк не должен ломать набор
                pass

    def _idx(self, index) -> str:
        i = self.raw("index", index)
        if self.raw("compare", i, "==", "end"):
            i = self.raw("index", "end-1c")
        return str(i)

    # -- запись -----------------------------------------------------------------------
    def _push(self, op: tuple, kind_break: bool = True) -> None:
        self.redo_stack.clear()
        last = self._last
        new_group = not self._open or not self.undo_stack
        if not new_group and kind_break and last is not None:
            if last[0] == "img" and op[0] == "ins" and op[1] == last[3] and op[2] == ["\n"]:
                pass                    # перевод строки за картинкой — одна правка с ней
            elif op[0] != last[0] or op[0] == "img" or last[0] == "img":
                new_group = True
            elif op[0] == "ins":
                # продолжение набора — ровно с конца прошлой вставки; пробел после слова — новая группа
                if op[1] != last[3]:
                    new_group = True
                else:
                    prev_txt = "".join(p for p in last[2] if isinstance(p, str))
                    cur_txt = "".join(p for p in op[2] if isinstance(p, str))
                    if prev_txt and cur_txt and cur_txt[:1].isspace() and not prev_txt[-1:].isspace():
                        new_group = True
            elif op[0] == "del":
                # Backspace подряд: конец новой = начало прошлой; Delete подряд: то же начало
                if op[2] != last[1] and op[1] != last[1]:
                    new_group = True
        if new_group:
            self.undo_stack.append([])
            if len(self.undo_stack) > MAX_GROUPS:
                del self.undo_stack[0]
        self.undo_stack[-1].append(op)
        self._open = True
        self._last = op

    def _insert(self, index, rest, kind_break: bool = True):
        start = self._idx(index)
        res = self.raw("insert", start, *rest)
        chars = "".join(str(rest[k]) for k in range(0, len(rest), 2))
        if chars:
            end = str(self.raw("index", f"{start}+{len(chars)}c"))
            self._push(("ins", start, [chars], end), kind_break)
        self._cursor()
        return res

    def _image_create(self, rest):
        start = self._idx(rest[0])
        name = self.raw("image", "create", start, *rest[1:])
        end = str(self.raw("index", f"{start}+1c"))
        self._push(("img", start, [("img", str(name))], end))
        self._cursor()
        return name

    def _dump(self, a: str, b: str) -> list[tuple[str, str, str]]:
        flat = self.text.tk.splitlist(self.raw("dump", "-text", "-image", a, b))
        return [(str(flat[k]), str(flat[k + 1]), str(flat[k + 2])) for k in range(0, len(flat) - 2, 3)]

    def _delete(self, idxs, kind_break: bool = True):
        idxs = list(idxs)
        if len(idxs) == 1:
            idxs.append(f"{idxs[0]}+1c")
        ranges = []
        for k in range(0, len(idxs) - 1, 2):
            a = self._idx(idxs[k])
            b = str(self.raw("index", idxs[k + 1]))
            last = str(self.raw("index", "end-1c"))
            if self.raw("compare", b, ">", last):
                b = last
            if self.raw("compare", a, "<", b):
                ranges.append((a, b))
        # с конца, чтобы индексы начал не сдвигались
        ranges.sort(key=lambda r: tuple(int(x) for x in r[0].split(".")), reverse=True)
        for a, b in ranges:
            content = self._content(a, b)
            self.raw("delete", a, b)
            self._push(("del", a, content, b), kind_break)
        self._cursor()
        return ""

    def _content(self, a: str, b: str) -> list:
        out: list = []
        for key, val, _idx in self._dump(a, b):
            if key == "text":
                if out and isinstance(out[-1], str):
                    out[-1] += val
                else:
                    out.append(val)
            elif key == "image":
                out.append(("img", val, self.image_width(val)))
        return out

    def record_resize(self, name: str, old: int, new: int) -> None:
        """Шаг истории «картинка name: ширина old → new» (сам размер меняет вызывающий)."""
        if old == new:
            return
        self._push(("size", name, old, new), kind_break=True)
        self._open = False

    def separator(self) -> None:
        self._open = False

    def reset(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._open = False
        self._last = None

    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    # -- воспроизведение ----------------------------------------------------------------
    def _put(self, index: str, content: list) -> None:
        pos = index
        for part in content:
            if isinstance(part, str):
                self.raw("insert", pos, part)
                pos = str(self.raw("index", f"{pos}+{len(part)}c"))
            else:
                _k, name, width = (tuple(part) + (None,))[:3]
                self.restore_image(pos, name, width if width is not None else self.image_width(name))
                pos = str(self.raw("index", f"{pos}+1c"))

    def _size(self, content: list) -> int:
        return sum(len(p) if isinstance(p, str) else 1 for p in content)

    def _apply(self, op: tuple, inverse: bool) -> str:
        kind = op[0]
        if kind == "size":
            _k, name, old, new = op
            self.set_width(name, old if inverse else new)
            return ""
        _k, start, content, _end = op
        removing = (kind in ("ins", "img")) == inverse
        if removing:
            self.raw("delete", start, f"{start}+{self._size(content)}c")
        else:
            self._put(start, content)
        return start

    def _replay(self, src: list, dst: list, inverse: bool) -> str:
        if not src:
            raise tk.TclError("nothing to " + ("undo" if inverse else "redo"))
        group = src.pop()
        self.replaying = True
        pos = ""
        try:
            for op in (reversed(group) if inverse else group):
                pos = self._apply(op, inverse) or pos
        finally:
            self.replaying = False
        dst.append(group)
        self._open = False
        self._last = None
        if pos:
            if not inverse:
                last = group[-1]
                if last[0] in ("ins", "img"):
                    pos = str(self.raw("index", f"{last[1]}+{self._size(last[2])}c"))
            self.raw("mark", "set", "insert", pos)
            self.raw("see", "insert")
        self.raw("edit", "modified", 1)
        self._cursor()
        return ""

    def undo(self) -> str:
        return self._replay(self.undo_stack, self.redo_stack, inverse=True)

    def redo(self) -> str:
        return self._replay(self.redo_stack, self.undo_stack, inverse=False)
