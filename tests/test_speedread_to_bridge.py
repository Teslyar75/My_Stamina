from types import SimpleNamespace

from stamina.speedread.book_reader import BookReaderPage


def test_to_bridge_sends_open_book_to_typing():
    calls = []
    lib_page = SimpleNamespace(type_text=lambda tid: calls.append(("type", tid)))
    fake = SimpleNamespace(
        tid="b1", _fullscreen=True,
        exit_fullscreen=lambda: calls.append("exitfs"),
        speech_stop=lambda: calls.append("stop"),
        save_pos=lambda: calls.append("save"),
        ctx=SimpleNamespace(pages={"library": lib_page}),
    )
    BookReaderPage.to_bridge(fake)
    assert calls == ["exitfs", "stop", "save", ("type", "b1")]


def test_to_bridge_without_book_does_nothing():
    fake = SimpleNamespace(tid=None, ctx=None)
    BookReaderPage.to_bridge(fake)
