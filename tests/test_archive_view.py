from stamina import archive_view as av


def test_hit_spans_case_and_merge():
    assert av.hit_spans("Снимок и СНИМОК", ["снимок"]) == [(0, 6), (9, 15)]
    assert av.hit_spans("abcdef", ["abc", "bcd"]) == [(0, 4)]
    assert av.hit_spans("text", []) == []


def test_snippet_short_text_whole():
    text, spans = av.snippet("привет, орион", ["орион"])
    assert text == "привет, орион"
    assert text[spans[0][0]:spans[0][1]] == "орион"


def test_snippet_centres_on_match():
    long = " ".join(f"слово{i}" for i in range(60)) + " МАЯК " + " ".join(
        f"хвост{i}" for i in range(60))
    text, spans = av.snippet(long, ["маяк"], width=60)
    assert text.startswith("…") and text.endswith("…")
    assert len(text) <= 64
    assert [text[a:b] for a, b in spans] == ["МАЯК"]


def test_snippet_without_match_takes_start():
    text, spans = av.snippet("x " * 200, ["нет"], width=40)
    assert spans == [] and not text.startswith("…") and text.endswith("…")


def test_prepare_and_context():
    rows = [{"text": "раз маяк"}, {"text": "два"}]
    out = av.prepare(rows, ["маяк"])
    assert out[0][1] and out[1][1] == []
    msgs = [{"id": str(i)} for i in range(10)]
    win, pos = av.context(msgs, "0")
    assert [m["id"] for m in win] == ["0", "1", "2"] and pos == 0
    win, pos = av.context(msgs, "5")
    assert len(win) == 5 and win[pos]["id"] == "5"
    assert av.context(msgs, "zz") == ([], -1)
