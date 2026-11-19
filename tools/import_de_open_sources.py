#!/usr/bin/env python
"""Import CC BY 4.0 German grammar sources into Star Typing as verbatim JSON data.

Sources:
  - Grimm Grammar (COERLL / UT Austin, Zsuzsanna Abrams), CC BY 4.0
    https://www.coerll.utexas.edu/gg/index.html
  - ZUM Deutsch Lernen, Grammatik-Kiste, default CC BY 4.0
    https://deutsch-lernen.zum.de/wiki/Grammatik-Kiste
    API: https://deutsch-lernen.zum.de/api.php

Texts are copied verbatim (navigation/chrome stripped). Nothing is generated.
Pages marked with a licence other than CC BY are skipped.
Raw HTTP responses are cached under %%TEMP%%/star-typing-de-open-sources (outside the repo).
"""

from __future__ import annotations

import argparse
import hashlib
import html as htmlmod
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "stamina" / "languages" / "plugins" / "de" / "grammar" / "sources"
RETRIEVED = "2026-11-19"
USER_AGENT = "Star Typing importer (https://github.com/Teslyar75/My_Stamina)"
REQUEST_INTERVAL = 1.0
GRIMM_BASE = "https://www.coerll.utexas.edu/gg/gr/"
GRIMM_INDEX = GRIMM_BASE + "index.html"
GRIMM_ANSWER_KEY = "https://www.coerll.utexas.edu/gg/pd/answer_key.html"
GRIMM_HOME = "https://www.coerll.utexas.edu/gg/index.html"
ZUM_API = "https://deutsch-lernen.zum.de/api.php"
ZUM_WIKI = "https://deutsch-lernen.zum.de/wiki/"
ZUM_KISTE = ZUM_WIKI + "Grammatik-Kiste"
ZUM_ABOUT = "https://deutsch-lernen.zum.de/wiki/%C3%9Cber_ZUM_Deutsch_Lernen"
LICENSE_CC_BY = "CC BY 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
CEFR_ORDER = ("A1", "A2", "B1", "B2", "C1", "C2")
CEFR_TOKEN = re.compile(r"\b(A1|A2|B1|B2|C1|C2)\b")
# Matches a clearly marked non-CC-BY licence; plain "CC BY 4.0" must not match.
NON_CC_BY_LICENCE = re.compile(
    r"""
    \bCC0\b
    | CC\s*BY0
    | CC[\s-]*BY[\s-]*SA\b
    | CC[\s-]*BY[\s-]*NC(?:[\s-]*SA|[\s-]*ND)?\b
    | CC[\s-]*BY[\s-]*ND\b
    | all\s+rights\s+reserved
    | alle\s+Rechte\s+vorbehalten
    """,
    re.IGNORECASE | re.VERBOSE,
)
AUDIO_CHROME = re.compile(r"Your browser does not support the audio element\.?", re.I)
WHITESPACE = re.compile(r"[ \t\xa0]+")
TOPIC_HREF = re.compile(r"^[a-z]+_\d+\.html$", re.I)
VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
IMPLICIT_CLOSE: dict[str, frozenset[str]] = {
    "p": frozenset({"p", "div", "table", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "form", "hr"}),
    "li": frozenset({"li"}),
    "td": frozenset({"td", "th", "tr"}),
    "th": frozenset({"td", "th", "tr"}),
    "tr": frozenset({"tr"}),
    "dt": frozenset({"dt", "dd"}),
    "dd": frozenset({"dt", "dd"}),
    "option": frozenset({"option"}),
}
BLOCK_TAGS = frozenset(
    {
        "p",
        "div",
        "table",
        "tr",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "ul",
        "ol",
        "li",
        "form",
        "section",
        "article",
        "blockquote",
        "pre",
        "hr",
        "br",
    }
)

_last_request_at = 0.0


def cache_dir() -> Path:
    base = os.environ.get("TEMP") or os.environ.get("TMP") or os.environ.get("TMPDIR") or "/tmp"
    path = Path(base) / "star-typing-de-open-sources"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_path(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return cache_dir() / digest


def fetch(url: str, *, binary: bool = False) -> bytes:
    """GET a URL at most once per second; cache raw bytes outside the repo."""
    global _last_request_at
    path = cache_path(url)
    meta = path.with_suffix(".url")
    if path.exists():
        return path.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    wait = REQUEST_INTERVAL - (time.monotonic() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    last_err: Exception | None = None
    data = b""
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            break
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_err = exc
            time.sleep(2 * (attempt + 1))
    else:
        raise RuntimeError(f"Failed to fetch {url}: {last_err}") from last_err
    _last_request_at = time.monotonic()
    path.write_bytes(data)
    meta.write_text(url + "\n", encoding="utf-8")
    return data


def fetch_text(url: str) -> str:
    raw = fetch(url)
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def fetch_json(url: str) -> Any:
    return json.loads(fetch_text(url))


# ---------------------------------------------------------------------------
# Minimal HTML tree (stdlib only)
# ---------------------------------------------------------------------------


class Node:
    def __init__(self, tag: str, attrs: list[tuple[str, str | None]] | None = None) -> None:
        self.tag = tag
        self.attrs = {k.lower(): (v or "") for k, v in (attrs or [])}
        self.children: list[Node | str] = []
        self.parent: Node | None = None

    def get(self, name: str, default: str = "") -> str:
        return self.attrs.get(name.lower(), default)

    @property
    def id(self) -> str:
        return self.get("id")

    @property
    def classes(self) -> list[str]:
        return [c for c in self.get("class").split() if c]

    def has_class(self, name: str) -> bool:
        return name in self.classes

    def append(self, child: Node | str) -> None:
        if isinstance(child, Node):
            child.parent = self
        self.children.append(child)

    def iter(self, tag: str | None = None) -> Any:
        if tag is None or self.tag == tag:
            yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.iter(tag)

    def find(self, *, tag: str | None = None, id: str | None = None, class_name: str | None = None) -> Node | None:
        for node in self.iter(tag):
            if id is not None and node.id != id:
                continue
            if class_name is not None and not node.has_class(class_name):
                continue
            return node
        return None

    def find_all(self, *, tag: str | None = None, class_name: str | None = None) -> list[Node]:
        out: list[Node] = []
        for node in self.iter(tag):
            if node is self and tag is None:
                continue
            if class_name is not None and not node.has_class(class_name):
                continue
            if tag is not None and node.tag != tag:
                continue
            if node is self:
                continue
            out.append(node)
        # include self if it matches tag/class? usually we search descendants
        return out

    def find_attr(self, name: str, value: str, tag: str | None = None) -> Node | None:
        for node in self.iter(tag):
            if node.get(name) == value:
                return node
        return None


class TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("[document]")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self._implicit_close(tag)
        node = Node(tag, attrs)
        self.stack[-1].append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in VOID_TAGS:
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data: str) -> None:
        if data:
            self.stack[-1].append(data)

    def _implicit_close(self, tag: str) -> None:
        while len(self.stack) > 1:
            current = self.stack[-1].tag
            closers = IMPLICIT_CLOSE.get(current)
            if closers and tag in closers:
                self.stack.pop()
                continue
            break


def parse_html(text: str) -> Node:
    builder = TreeBuilder()
    builder.feed(text)
    builder.close()
    return builder.root


def normalize_text(text: str) -> str:
    text = htmlmod.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = AUDIO_CHROME.sub("", text)
    lines = [WHITESPACE.sub(" ", line).strip() for line in text.split("\n")]
    # collapse >1 blank lines
    out: list[str] = []
    blank = False
    for line in lines:
        if not line:
            if out and not blank:
                out.append("")
            blank = True
        else:
            out.append(line)
            blank = False
    return "\n".join(out).strip()


def get_text(node: Node | str, *, inline: bool = False) -> str:
    if isinstance(node, str):
        return node
    if node.tag in {"script", "style", "noscript"}:
        return ""
    if node.tag == "br":
        return "\n"
    parts: list[str] = []
    for child in node.children:
        parts.append(get_text(child, inline=inline or node.tag in {"td", "th", "span", "a", "b", "i", "em", "strong"}))
    text = "".join(parts)
    if node.tag in {"td", "th"}:
        return WHITESPACE.sub(" ", text).strip()
    if node.tag == "tr":
        cells = [get_text(c) for c in node.children if isinstance(c, Node) and c.tag in {"td", "th"}]
        return " | ".join(c for c in cells if c) + "\n"
    if node.tag in BLOCK_TAGS and not inline:
        return text.strip() + "\n"
    return text


def visible_text(node: Node) -> str:
    return normalize_text(get_text(node))


def replace_inputs_with_gaps(node: Node) -> str:
    """Render a question, turning <input> / answer spans into ___."""

    def walk(n: Node | str) -> str:
        if isinstance(n, str):
            return n
        if n.tag in {"script", "style"}:
            return ""
        if n.tag == "input":
            return "___"
        if n.tag == "span" and (n.has_class("ans_fib") or n.has_class("ans_mc")):
            return "___"
        if n.tag == "table" and any(c in n.classes for c in ("mc_vert", "mc_horiz", "wb")):
            return ""
        if n.tag == "br":
            return "\n"
        return "".join(walk(c) for c in n.children)

    return normalize_text(walk(node))


def table_rows(table: Node) -> list[list[str]]:
    rows: list[list[str]] = []
    for tr in table.find_all(tag="tr"):
        # only direct-ish rows of this table (skip nested)
        parent_table = tr.parent
        while parent_table and parent_table.tag not in {"table", "[document]"}:
            parent_table = parent_table.parent
        if parent_table is not table:
            continue
        cells: list[str] = []
        for child in tr.children:
            if isinstance(child, Node) and child.tag in {"td", "th"}:
                cells.append(visible_text(child))
        if any(cells):
            rows.append(cells)
    return rows


def looks_english(text: str) -> bool:
    if not text:
        return False
    ascii_letters = sum(1 for ch in text if ("A" <= ch <= "Z") or ("a" <= ch <= "z"))
    letters = sum(1 for ch in text if ch.isalpha())
    if letters == 0:
        return False
    return ascii_letters / letters >= 0.85 and re.search(r"[A-Za-z]{3}", text) is not None


def is_heading_class(classes: list[str]) -> bool:
    return any(c.startswith("h_14_") or c.startswith("h_13_") or c.startswith("h_16_") for c in classes)


# ---------------------------------------------------------------------------
# Shared writers
# ---------------------------------------------------------------------------


def slugify(title: str) -> str:
    trans = str.maketrans(
        {
            "ä": "ae",
            "ö": "oe",
            "ü": "ue",
            "Ä": "Ae",
            "Ö": "Oe",
            "Ü": "Ue",
            "ß": "ss",
        }
    )
    s = title.translate(trans)
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    return s or "topic"


def cefr_from_text(*parts: str) -> str | None:
    found: list[str] = []
    for part in parts:
        for token in CEFR_TOKEN.findall(part or ""):
            token = token.upper()
            if token in CEFR_ORDER and token not in found:
                found.append(token)
    if not found:
        return None
    found.sort(key=CEFR_ORDER.index)
    return ", ".join(found)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def unique_path(folder: Path, stem: str) -> Path:
    candidate = folder / f"{stem}.json"
    if not candidate.exists():
        return candidate
    i = 2
    while True:
        candidate = folder / f"{stem}_{i}.json"
        if not candidate.exists():
            return candidate
        i += 1


# ---------------------------------------------------------------------------
# Grimm Grammar
# ---------------------------------------------------------------------------

GRIMM_SKIP_PAGES = frozenset(
    {
        "index.html",
        "about.html",
        "characters.html",
        "credits.html",
        "help.html",
        "answer_key.html",
    }
)


def grimm_toc(index_html: str) -> list[dict[str, str]]:
    tree = parse_html(index_html)
    si = tree.find(id="si") or tree
    topics: list[dict[str, str]] = []
    seen: set[str] = set()
    current_section = ""
    for node in si.iter():
        if node.tag in {"div", "li"} and node.has_class("ti_div") or (node.has_class("ti") and node.tag == "li"):
            title_node = node.find(class_name="ti_div") if node.tag == "li" else node
            if title_node is not None:
                text = visible_text(title_node)
                if text:
                    current_section = text
        if node.tag != "a":
            continue
        href = node.get("href").split("?")[0].split("#")[0]
        if href in GRIMM_SKIP_PAGES or not TOPIC_HREF.match(href):
            continue
        stem = href[:-5]
        if stem in seen:
            continue
        seen.add(stem)
        topics.append(
            {
                "id": stem,
                "href": href,
                "title": visible_text(node) or stem,
                "section": current_section,
                "original_url": urllib.parse.urljoin(GRIMM_BASE, href),
            }
        )
    return topics


def _new_section(heading: str) -> dict[str, str]:
    return {"heading": heading, "text": ""}


def _append_text(section: dict[str, str], text: str) -> None:
    text = normalize_text(text)
    if not text:
        return
    if section["text"]:
        section["text"] = section["text"] + "\n\n" + text
    else:
        section["text"] = text


def _maybe_examples(table: Node, examples: list[dict[str, str]]) -> bool:
    rows = table_rows(table)
    useful = False
    for row in rows:
        if len(row) < 2:
            continue
        left, right = row[0], row[1]
        if not left or not right or left.lower() in {"word bank"}:
            continue
        # two-column lemma/gloss or sentence/translation
        item: dict[str, str] = {"de": left}
        if looks_english(right):
            item["en"] = right
        elif looks_english(left):
            # unexpected column order: keep verbatim labels
            item["de"] = right
            item["en"] = left
        if item not in examples:
            examples.append(item)
            useful = True
    return useful


def parse_grimm_content(content: Node) -> tuple[str, list[dict[str, str]], list[dict[str, str]]]:
    title = ""
    sections: list[dict[str, str]] = []
    examples: list[dict[str, str]] = []
    current = _new_section("")

    def flush() -> None:
        nonlocal current
        if current["heading"] or current["text"]:
            if not current["text"] and current["heading"]:
                current["text"] = current["heading"]
            sections.append(current)
        current = _new_section("")

    def consider(node: Node) -> None:
        nonlocal title, current
        if node.tag in {"script", "style"}:
            return
        # page title
        for span in node.find_all(tag="span"):
            if any(c.startswith("h_16_") for c in span.classes) and not title:
                title = re.sub(r"\s*:\s*", ": ", visible_text(span)).strip()
        heading_text = ""
        for span in node.find_all(tag="span"):
            if any(c.startswith("h_14_") or c.startswith("h_13_") for c in span.classes):
                heading_text = visible_text(span)
                break
        if heading_text and node.tag == "p":
            flush()
            current = _new_section(heading_text)
            return
        if node.tag == "table":
            _maybe_examples(node, examples)
            text = visible_text(node)
            if text:
                _append_text(current, text)
            return
        if node.tag == "div" and node.has_class("indent_wrap_250"):
            for table in node.find_all(tag="table"):
                _maybe_examples(table, examples)
            text = visible_text(node)
            if text:
                _append_text(current, text)
            return
        if node.tag == "p" and any(
            any(c.startswith("h_16_") for c in span.classes) for span in node.find_all(tag="span")
        ):
            # Page-title paragraph is stored separately; do not duplicate it as body text.
            return
        if node.tag in {"p", "div"}:
            text = visible_text(node)
            if text:
                _append_text(current, text)

    for child in content.children:
        if isinstance(child, Node):
            consider(child)
        elif isinstance(child, str) and child.strip():
            _append_text(current, child)
    flush()
    # drop completely empty
    sections = [s for s in sections if s["text"].strip()]
    if not sections and title:
        sections = [{"heading": title, "text": title}]
    return title, sections, examples


def _set_id_from_block(block: Node, fallback: str = "") -> str:
    form = block.find(tag="form")
    if form is not None and form.get("name"):
        return form.get("name")
    for span in block.find_all(tag="span"):
        text = visible_text(span)
        if re.match(r"^[a-z]+_\d+_\d+_(?:fib|mcr|dd)$", text, re.I):
            return text
    # preceding named anchor is a sibling; caller may pass it
    return fallback


def parse_exercise_block(block: Node) -> tuple[str, list[dict[str, Any]]]:
    set_id = _set_id_from_block(block)
    title = ""
    prompt = ""
    word_bank: list[str] = []
    # title / prompt paragraphs
    for p in block.find_all(tag="p"):
        classes = p.classes
        text = visible_text(p)
        if not text:
            continue
        if any(c.startswith("h_16_") or c.startswith("bot_075") for c in classes) or p.find(class_name="h_16_8a97b2"):
            # strip internal set id line
            lines = [ln for ln in text.split("\n") if not re.match(r"^[a-z]+_\d+_\d+_(?:fib|mcr|dd)$", ln, re.I)]
            title = title or " ".join(lines).strip()
        elif "Instructions" in text and text.startswith("Instructions"):
            continue
        elif not prompt:
            prompt = text
    for table in block.find_all(tag="table"):
        if table.has_class("wb"):
            for row in table_rows(table):
                for cell in row:
                    if cell and cell.lower() != "word bank":
                        word_bank.append(cell)
    exercises: list[dict[str, Any]] = []
    kind = "gap"
    if set_id.endswith("_mcr") or block.id.endswith("_mcr"):
        kind = "choice"
    elif set_id.endswith("_dd") or block.id.endswith("_dd"):
        kind = "gap"

    if kind == "choice":
        ex_tables = [t for t in block.find_all(tag="table") if t.has_class("ex")]
        for table in ex_tables:
            for tr in table.find_all(tag="tr"):
                parent_table = tr.parent
                while parent_table and parent_table.tag not in {"table", "[document]"}:
                    parent_table = parent_table.parent
                if parent_table is not table:
                    continue
                # skip rows that are only option rows from a nested table — we process whole outer row
                q_cell = None
                cells = [c for c in tr.children if isinstance(c, Node) and c.tag in {"td", "th"}]
                if len(cells) >= 2:
                    q_cell = cells[1]
                elif len(cells) == 1:
                    q_cell = cells[0]
                if q_cell is None:
                    continue
                mc = q_cell.find(class_name="mc_vert") or q_cell.find(class_name="mc_horiz")
                if mc is None:
                    continue
                q = replace_inputs_with_gaps(q_cell)
                options: list[str] = []
                answer = None
                for td in mc.find_all(tag="td"):
                    # only leaves
                    if td.find(tag="table"):
                        continue
                    text = visible_text(td)
                    if not text:
                        continue
                    options.append(text)
                    if td.find(class_name="ans_mc"):
                        answer = visible_text(td.find(class_name="ans_mc") or td)
                    # selected radio (rare on answer key)
                    for inp in td.find_all(tag="input"):
                        if inp.get("type") == "radio" and inp.get("checked") not in {"", None}:
                            answer = text
                if not q and not options:
                    continue
                item: dict[str, Any] = {"type": "choice", "q": q, "options": options}
                if answer:
                    item["a"] = answer
                if set_id:
                    item["set_id"] = set_id
                if title:
                    item["set_title"] = title
                if prompt:
                    item["prompt"] = prompt
                exercises.append(item)
    else:
        # fill-in / word-bank / ordering
        ul = None
        for candidate in block.find_all(tag="ul"):
            ul = candidate
            break
        if ul is not None and (set_id.endswith("_dd") or block.id.endswith("_dd")):
            sentences = [visible_text(li) for li in ul.find_all(tag="li") if visible_text(li)]
            item = {
                "type": "gap",
                "q": prompt or title or "Put the sentences in the correct order.",
                "a": sentences,
            }
            if set_id:
                item["set_id"] = set_id
            if title:
                item["set_title"] = title
            if prompt:
                item["prompt"] = prompt
            exercises.append(item)
        else:
            ex_tables = [t for t in block.find_all(tag="table") if t.has_class("ex")]
            for table in ex_tables:
                for tr in table.find_all(tag="tr"):
                    parent_table = tr.parent
                    while parent_table and parent_table.tag not in {"table", "[document]"}:
                        parent_table = parent_table.parent
                    if parent_table is not table:
                        continue
                    cells = [c for c in tr.children if isinstance(c, Node) and c.tag in {"td", "th"}]
                    if not cells:
                        continue
                    q_cell = cells[-1] if len(cells) >= 1 else None
                    if q_cell is None:
                        continue
                    q = replace_inputs_with_gaps(q_cell)
                    answers = [visible_text(span) for span in q_cell.find_all(tag="span") if span.has_class("ans_fib")]
                    if not q:
                        continue
                    # Skip section headings and context lines that are not actual gaps.
                    if "___" not in q and not answers:
                        continue
                    item = {"type": "gap", "q": q}
                    if answers:
                        item["a"] = answers[0] if len(answers) == 1 else answers
                    if word_bank:
                        item["options"] = word_bank
                    if set_id:
                        item["set_id"] = set_id
                    if title:
                        item["set_title"] = title
                    if prompt:
                        item["prompt"] = prompt
                    exercises.append(item)
    return set_id, exercises


def parse_all_exercises(tree: Node) -> dict[str, list[dict[str, Any]]]:
    wrap = tree.find(id="ex_wrapper")
    if wrap is None:
        return {}
    by_set: dict[str, list[dict[str, Any]]] = {}
    pending_name = ""
    for child in wrap.children:
        if isinstance(child, Node) and child.tag == "a" and child.get("name"):
            pending_name = child.get("name")
            continue
        if not isinstance(child, Node):
            continue
        if not (child.id.startswith("es_") or child.find(tag="form") or child.find(tag="table", class_name="ex")):
            continue
        set_id, exercises = parse_exercise_block(child)
        set_id = set_id or pending_name
        if set_id and exercises:
            for ex in exercises:
                ex.setdefault("set_id", set_id)
            by_set.setdefault(set_id, []).extend(exercises)
        pending_name = ""
    return by_set


def topic_id_of_set(set_id: str) -> str | None:
    m = re.match(r"^([a-z]+_\d+)_\d+_(?:fib|mcr|dd)$", set_id, re.I)
    return m.group(1).lower() if m else None


def import_grimm(out_dir: Path) -> dict[str, Any]:
    print("Grimm Grammar: fetching index and answer key…")
    index_html = fetch_text(GRIMM_INDEX)
    toc = grimm_toc(index_html)
    if not toc:
        raise RuntimeError("Could not parse Grimm Grammar site index")
    answer_html = fetch_text(GRIMM_ANSWER_KEY)
    answers = parse_all_exercises(parse_html(answer_html))
    print(f"  TOC topics: {len(toc)}; answer-key exercise sets: {len(answers)}")

    topics_out: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    exercise_count = 0
    for i, meta in enumerate(toc, 1):
        url = meta["original_url"]
        print(f"  [{i}/{len(toc)}] {meta['id']}")
        try:
            page_html = fetch_text(url)
        except Exception as exc:  # noqa: BLE001 — record and continue
            skipped.append({"id": meta["id"], "url": url, "reason": f"fetch failed: {exc}"})
            continue
        # licence is site-wide CC BY 4.0; still skip if a page somehow marks otherwise
        if NON_CC_BY_LICENCE.search(page_html):
            skipped.append({"id": meta["id"], "url": url, "reason": "license: non-CC-BY marker found on page"})
            continue
        tree = parse_html(page_html)
        content = tree.find(id="content_wrapper")
        if content is None:
            skipped.append({"id": meta["id"], "url": url, "reason": "no extractable content_wrapper"})
            continue
        title, sections, examples = parse_grimm_content(content)
        title = title or meta["title"]
        page_sets = parse_all_exercises(tree)
        # prefer answer-key copy (includes answers); fall back to the live page
        exercises: list[dict[str, Any]] = []
        used: set[str] = set()
        for set_id, exs in answers.items():
            if topic_id_of_set(set_id) == meta["id"]:
                exercises.extend(exs)
                used.add(set_id)
        for set_id, exs in page_sets.items():
            if set_id not in used:
                exercises.extend(exs)
        if not sections:
            skipped.append({"id": meta["id"], "url": url, "reason": "no extractable sections"})
            continue
        topic = {
            "id": meta["id"],
            "title": title,
            "original_url": url,
            "explanation_lang": "en",
            "section": meta.get("section") or None,
            "cefr": None,
            "sections": sections,
            "examples": examples,
            "exercises": exercises,
        }
        write_json(out_dir / f"{meta['id']}.json", topic)
        topics_out.append(
            {
                "id": meta["id"],
                "title": title,
                "original_url": url,
                "cefr": None,
                "section": meta.get("section") or None,
                "exercise_count": len(exercises),
            }
        )
        exercise_count += len(exercises)

    source = {
        "id": "grimm_grammar",
        "name": "Grimm Grammar",
        "publisher": "Center for Open Educational Resources and Language Learning (COERLL), University of Texas at Austin",
        "author": "Zsuzsanna Abrams",
        "url": GRIMM_HOME,
        "license": LICENSE_CC_BY,
        "license_url": LICENSE_URL,
        "attribution": {
            "ru": "Grimm Grammar © Zsuzsanna Abrams, COERLL, Техасский университет в Остине, лицензия CC BY 4.0.",
            "en": "Grimm Grammar © Zsuzsanna Abrams, COERLL, The University of Texas at Austin, licensed under CC BY 4.0.",
            "de": "Grimm Grammar © Zsuzsanna Abrams, COERLL, The University of Texas at Austin, lizenziert unter CC BY 4.0.",
        },
        "retrieved": RETRIEVED,
        "modifications": {
            "ru": "Убраны навигация, вёрстка, аудио и изображения. Текст правил, примеров и упражнений скопирован дословно; HTML преобразован в простой текст.",
            "en": "Navigation, layout, audio and images were removed. Explanations, examples and exercises were copied verbatim; HTML was converted to plain text.",
            "de": "Navigation, Layout, Audio und Bilder wurden entfernt. Erklärungen, Beispiele und Übungen wurden wörtlich übernommen; HTML wurde in Klartext umgewandelt.",
        },
    }
    index = {
        "source_id": "grimm_grammar",
        "retrieved": RETRIEVED,
        "topic_count": len(topics_out),
        "exercise_count": exercise_count,
        "skipped_count": len(skipped),
        "topics": topics_out,
    }
    write_json(out_dir / "source.json", source)
    write_json(out_dir / "index.json", index)
    if skipped:
        write_json(out_dir / "skipped.json", skipped)
    return {"topics": len(topics_out), "exercises": exercise_count, "skipped": skipped}


# ---------------------------------------------------------------------------
# ZUM Grammatik-Kiste
# ---------------------------------------------------------------------------

ZUM_TOPIC_CATEGORIES = [
    "Adjektive",
    "Nomen und Artikel",
    "Präpositionen",
    "Wechselpräpositionen",
    "Pronomen",
    "Verben",
    "Konjunktiv",
    "Sätze",
    "Rechtschreibung",
]


def zum_api(**params: Any) -> dict[str, Any]:
    query = dict(params)
    query.setdefault("format", "json")
    query.setdefault("formatversion", "2")
    url = ZUM_API + "?" + urllib.parse.urlencode(query, doseq=True, safe=":")
    data = fetch_json(url)
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(f"ZUM API error: {data['error']}")
    return data


def zum_category_members(category: str, *, namespaces: set[int] | None = None) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    cont: dict[str, Any] = {}
    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Kategorie:{category}",
            "cmlimit": "500",
        }
        params.update(cont)
        data = zum_api(**params)
        batch = data.get("query", {}).get("categorymembers", [])
        for item in batch:
            if namespaces is not None and item.get("ns") not in namespaces:
                continue
            members.append(item)
        if "continue" in data:
            cont = data["continue"]
        else:
            break
    return members


def zum_kiste_pages() -> list[dict[str, str]]:
    """Pages listed by Grammatik-Kiste: intersection of Grammatik and each topic category."""
    grammatik = {m["title"] for m in zum_category_members("Grammatik", namespaces={0})}
    ordered: list[dict[str, str]] = []
    seen: set[str] = set()
    for cat in ZUM_TOPIC_CATEGORIES:
        for member in zum_category_members(cat, namespaces={0}):
            title = member["title"]
            if title not in grammatik or title in seen:
                continue
            seen.add(title)
            ordered.append(
                {
                    "title": title,
                    "category": cat,
                    "original_url": ZUM_WIKI + urllib.parse.quote(title.replace(" ", "_")),
                }
            )
    return ordered


def licence_violation(text: str) -> str | None:
    match = NON_CC_BY_LICENCE.search(text or "")
    if not match:
        return None
    snippet = match.group(0)
    return f"license: marked otherwise ({snippet})"


def parse_zum_html(html: str, title: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    tree = parse_html(html)
    root = tree.find(class_name="mw-parser-output") or tree
    sections: list[dict[str, str]] = []
    examples: list[dict[str, str]] = []
    current = _new_section("")

    def flush() -> None:
        nonlocal current
        if not current["text"].strip() and current["heading"]:
            current["text"] = current["heading"]
        if current["heading"] or current["text"].strip():
            sections.append(current)
        current = _new_section("")

    skip_classes = {
        "toc",
        "mw-editsection",
        "navbox",
        "catlinks",
        "printfooter",
        "mw-empty-elt",
        "noprint",
        "reference",
    }

    def skip(node: Node) -> bool:
        if node.tag in {"script", "style", "noscript"}:
            return True
        if any(c in skip_classes for c in node.classes):
            return True
        if node.id in {"toc", "catlinks"}:
            return True
        return False

    def handle(node: Node | str) -> None:
        nonlocal current
        if isinstance(node, str):
            if node.strip():
                _append_text(current, node)
            return
        if skip(node):
            return
        if node.tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            flush()
            heading = visible_text(node)
            heading = re.sub(
                r"\s*\[\s*(?:Bearbeiten|Edit)(?:\s*\|\s*Quelltext bearbeiten)?\s*\]",
                "",
                heading,
                flags=re.I,
            ).strip()
            current = _new_section(heading)
            return
        if node.tag == "table":
            _maybe_examples(node, examples)
            text = visible_text(node)
            if text:
                _append_text(current, text)
            return
        if node.tag in {"p", "ul", "ol", "dl", "pre", "blockquote"}:
            text = visible_text(node)
            if text:
                _append_text(current, text)
            return
        if node.tag == "div":
            # descent into generic divs, but keep box-like blocks as one chunk
            if any(c.lower().startswith("box") or c in {"hilfe", "info"} for c in node.classes):
                text = visible_text(node)
                if text:
                    _append_text(current, text)
                return
            for child in node.children:
                handle(child)
            return
        text = visible_text(node)
        if text:
            _append_text(current, text)

    for child in root.children:
        handle(child)
    flush()
    sections = [s for s in sections if s["text"].strip()]
    if not sections and title:
        sections = [{"heading": title, "text": title}]
    return sections, examples


def extract_zum_exercises(wikitext: str) -> list[dict[str, Any]]:
    """Extract only clearly structured in-wiki questions; do not invent H5P/LearningApps items."""
    exercises: list[dict[str, Any]] = []
    # MediaWiki quiz extension
    for block in re.finditer(r"<quiz\b[^>]*>(.*?)</quiz>", wikitext, re.I | re.S):
        body = block.group(1)
        current_q = None
        options: list[str] = []
        answer = None
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("{") or line.startswith("}"):
                continue
            if re.match(r"^\|\s*type\s*=", line, re.I):
                continue
            m_opt = re.match(r"^\[(?P<mark>[Xx +*-]?)\]\s*(?P<text>.+)$", line)
            if m_opt and current_q is not None:
                text = m_opt.group("text").strip()
                options.append(text)
                if m_opt.group("mark") in {"X", "x", "*"}:
                    answer = text
                continue
            # new question
            if current_q:
                item: dict[str, Any] = {"type": "choice" if options else "gap", "q": current_q}
                if options:
                    item["options"] = options
                if answer:
                    item["a"] = answer
                exercises.append(item)
            current_q = re.sub(r"^\{X\}", "", line).strip()
            options = []
            answer = None
        if current_q:
            item = {"type": "choice" if options else "gap", "q": current_q}
            if options:
                item["options"] = options
            if answer:
                item["a"] = answer
            exercises.append(item)
    return exercises


def import_zum(out_dir: Path) -> dict[str, Any]:
    print("ZUM Grammatik-Kiste: listing category intersection…")
    pages = zum_kiste_pages()
    print(f"  pages in Kiste: {len(pages)}")
    topics_out: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    exercise_count = 0
    used_stems: dict[str, int] = {}

    for i, meta in enumerate(pages, 1):
        title = meta["title"]
        url = meta["original_url"]
        print(f"  [{i}/{len(pages)}] {title}")
        try:
            parsed = zum_api(action="parse", page=title, prop="text|wikitext|categories", disablelimitreport=1)
        except Exception as exc:  # noqa: BLE001
            skipped.append({"title": title, "url": url, "reason": f"fetch failed: {exc}"})
            continue
        parse = parsed.get("parse") or {}
        wikitext = ((parse.get("wikitext") or {}) if isinstance(parse.get("wikitext"), dict) else None)
        if isinstance(parse.get("wikitext"), dict):
            wt = parse["wikitext"].get("*") or parse["wikitext"].get("content") or ""
        elif isinstance(parse.get("wikitext"), str):
            wt = parse.get("wikitext") or ""
        else:
            wt = ""
        html = ""
        text_field = parse.get("text")
        if isinstance(text_field, dict):
            html = text_field.get("*") or text_field.get("content") or ""
        elif isinstance(text_field, str):
            html = text_field
        cat_titles = []
        for cat in parse.get("categories") or []:
            if isinstance(cat, dict):
                cat_titles.append(cat.get("category") or cat.get("title") or cat.get("*") or "")
            else:
                cat_titles.append(str(cat))
        licence_bits = "\n".join([wt, html, "\n".join(cat_titles)])
        reason = licence_violation(licence_bits)
        if reason:
            skipped.append({"title": title, "url": url, "reason": reason})
            continue
        sections, examples = parse_zum_html(html or "", title)
        if not sections:
            skipped.append({"title": title, "url": url, "reason": "no extractable sections"})
            continue
        exercises = extract_zum_exercises(wt)
        cat_blob = " ".join(cat_titles).replace("_", " ")
        cefr = cefr_from_text(title, cat_blob)
        stem = slugify(title)
        used_stems[stem] = used_stems.get(stem, 0) + 1
        topic_id = stem if used_stems[stem] == 1 else f"{stem}_{used_stems[stem]}"
        topic = {
            "id": topic_id,
            "title": title,
            "original_url": url,
            "explanation_lang": "de",
            "section": meta.get("category") or None,
            "cefr": cefr,
            "sections": sections,
            "examples": examples,
            "exercises": exercises,
        }
        write_json(out_dir / f"{topic_id}.json", topic)
        topics_out.append(
            {
                "id": topic_id,
                "title": title,
                "original_url": url,
                "cefr": cefr,
                "section": meta.get("category") or None,
                "exercise_count": len(exercises),
            }
        )
        exercise_count += len(exercises)

    source = {
        "id": "zum_grammatik_kiste",
        "name": "Grammatik-Kiste",
        "publisher": "ZUM Deutsch Lernen / Zentrale für Unterrichtsmedien im Internet e. V. (ZUM)",
        "author": "Autorinnen und Autoren von ZUM Deutsch Lernen",
        "url": ZUM_KISTE,
        "license": LICENSE_CC_BY,
        "license_url": LICENSE_URL,
        "attribution": {
            "ru": "Grammatik-Kiste, ZUM Deutsch Lernen (Zentrale für Unterrichtsmedien im Internet e. V.), лицензия CC BY 4.0. См. также: " + ZUM_ABOUT,
            "en": "Grammatik-Kiste, ZUM Deutsch Lernen (Zentrale für Unterrichtsmedien im Internet e. V.), licensed under CC BY 4.0. See also: " + ZUM_ABOUT,
            "de": "Grammatik-Kiste, ZUM Deutsch Lernen (Zentrale für Unterrichtsmedien im Internet e. V.), lizenziert unter CC BY 4.0. Siehe auch: " + ZUM_ABOUT,
        },
        "retrieved": RETRIEVED,
        "modifications": {
            "ru": "Убраны навигация вики, шаблоны оформления и встроенные виджеты. Текст разделов и таблиц скопирован дословно; HTML/викиразметка преобразованы в простой текст. Интерактивные упражнения H5P и LearningApps в текст не разворачивались.",
            "en": "Wiki navigation, layout templates and embedded widgets were removed. Section text and tables were copied verbatim; HTML/wikitext was converted to plain text. H5P and LearningApps exercises were not expanded into text.",
            "de": "Wiki-Navigation, Layoutvorlagen und eingebettete Widgets wurden entfernt. Abschnittstexte und Tabellen wurden wörtlich übernommen; HTML/Wikitext wurde in Klartext umgewandelt. Interaktive H5P- und LearningApps-Übungen wurden nicht als Text aufgelöst.",
        },
        "license_note": {
            "ru": "По умолчанию материалы ZUM Deutsch Lernen стоят под CC BY 4.0; страницы с иной явно указанной лицензией пропущены.",
            "en": "ZUM Deutsch Lernen content is CC BY 4.0 by default; pages clearly marked with a different licence were skipped.",
            "de": "Inhalte von ZUM Deutsch Lernen stehen grundsätzlich unter CC BY 4.0; Seiten mit einer abweichend gekennzeichneten Lizenz wurden übersprungen.",
        },
    }
    index = {
        "source_id": "zum_grammatik_kiste",
        "retrieved": RETRIEVED,
        "topic_count": len(topics_out),
        "exercise_count": exercise_count,
        "skipped_count": len(skipped),
        "topics": topics_out,
    }
    write_json(out_dir / "source.json", source)
    write_json(out_dir / "index.json", index)
    if skipped:
        write_json(out_dir / "skipped.json", skipped)
    return {"topics": len(topics_out), "exercises": exercise_count, "skipped": skipped}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import CC BY German grammar sources as JSON data.")
    parser.add_argument("--only", choices=("grimm", "zum"), help="Import a single source")
    parser.add_argument("--out", type=Path, default=OUT_ROOT, help="Output directory for source folders")
    args = parser.parse_args(argv)
    out_root: Path = args.out
    out_root.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {}
    if args.only in (None, "grimm"):
        summary["grimm_grammar"] = import_grimm(out_root / "grimm_grammar")
    if args.only in (None, "zum"):
        summary["zum_grammatik_kiste"] = import_zum(out_root / "zum_grammatik_kiste")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
