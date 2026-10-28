"""PDF -> Document of positioned lines, using PyMuPDF."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

import pymupdf as fitz

from .models import Document, Line, Page, Span

# Superscripts that are references/footnote/affiliation markers, never speech.
_SUP_MARKER = re.compile(r"^[\s\d,;–\-−‒*†‡§¶#a-z]{1,20}$")
# A horizontal gap this many times the font size splits a line in two
# (PyMuPDF occasionally glues text across a narrow column gutter).
_SPLIT_GAP = 2.0
_SHORT_WORDS = {"a", "an", "as", "at", "be", "by", "if", "in", "is", "it", "no", "of", "on", "or", "so", "to", "we"}
_MONO_FONTS = ("courier", "mono", "consola", "menlo", "inconsolata", "sourcecodepro", "cmtt", "lucidaconsole")


# ligatures split a word at a line end as well: "eﬃ-" + "ciency" must join
_LIGATURES = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"})

# Math fonts of the typesetting system behind eLife, J Neurosci and others: parentheses, equals and plus sit at
# the code of an accented letter. The font names are obfuscated but stable; the codes are not guaranteed to mean
# the same in every PDF, so only the printable ones are trusted everywhere.
_COMMON_MATH_FONTS: dict[str, dict[str, str]] = {
    "AdvP4C4E74": {"ð": "(", "Þ": ")", "¼": "=", "þ": "+", "½": "["},
}
# eLife: Greek letters are stored at the code of a Latin letter, and signs at control codes
_ELIFE_MATH_FONTS: dict[str, dict[str, str]] = {
    "AdvP4C4E74": {**_COMMON_MATH_FONTS["AdvP4C4E74"], "\x00": "−", "\x01": "·", "\x02": "×", "\x03": "*", "\x06": "±",
                   "\x14": "≤", "\x15": "≥", "!": "→", "h": "⟨", "i": "⟩", "j": "|", "f": "{", "g": "}",
                   "\x8a": "", "\x11": ""},
    "AdvP697C": {"t": "τ", "D": "Δ", "»": "≈"},
    "AdvP3E2F88": {"h": "η", "d": "δ", "a": "α", "s": "σ", "p": "π"},
    "AdvP4C4E51": {'"': "ε", ";": ",", "\x18": "ξ"},
    "AdvPi1": {"q": "∂"},
    "AdvP4C4E46": {"P": "∑", "X": "∑", "Z": "∫", "ﬃ": ""},   # large operators; "ﬃﬃﬃ" is the stem of a radical sign
}
_COMMON_MAPS = {font: str.maketrans(chars) for font, chars in _COMMON_MATH_FONTS.items()}
_ELIFE_MAPS = {font: str.maketrans(chars) for font, chars in _ELIFE_MATH_FONTS.items()}


def _is_bold(span: dict) -> bool:
    font = span.get("font", "").lower()
    if span.get("flags", 0) & 16 or any(w in font for w in ("bold", "black", "heavy", "semibold")):
        return True
    # obfuscated names (AdvOT1efcda3b.B, AdvPSA5BD): trust only an explicit style suffix
    if re.search(r"[0-9a-f]{8}", font) or re.fullmatch(r"(?:[a-z]{6}\+)?adv(?:ps|ot|tt|p)?[0-9a-f]+(\.\w+)?", font):
        return re.search(r"\.b(i|o)?$", font) is not None
    # abbreviated weights: AdvPSHN-H (Helvetica Neue Heavy), AdvCaceiliaHVY, AdvCaeciliaBdIt
    return re.search(r"(hn-(h|hv|b|bd)|hvy|bd(it|i)?|[-_]b(i|it)?)$", font) is not None


def _make_span(s: dict, maps: dict | None = None) -> Span:
    x0, _, x1, _ = s["bbox"]
    flags = s.get("flags", 0)
    text = s["text"]
    if text.strip() == "d" and re.search(r"mpi\d", s.get("font", "").lower()):
        text = text.replace("d", "•")  # Mathematical Pi bullet (Cell Press lists)
    maps = _COMMON_MAPS if maps is None else maps
    if s.get("font", "") in maps:
        text = text.translate(maps[s["font"]])  # "x ð t Þ" is x(t); in eLife, "h" in the Greek font is η
    return Span(
        text=text,
        x0=x0,
        x1=x1,
        size=round(s["size"], 1),
        bold=_is_bold(s),
        italic=bool(flags & 2),
        superscript=bool(flags & 1),
        monospace=bool(flags & 8) or any(m in s.get("font", "").lower() for m in _MONO_FONTS),
        color=int(s.get("color", 0) or 0),
        font=s.get("font", ""),
    )


def _spans_text(spans: list[Span]) -> str:
    out: list[str] = []
    for i, sp in enumerate(spans):
        t = sp.text
        if sp.superscript and _SUP_MARKER.match(t.strip() or "x"):
            prev = "".join(out).rstrip()
            sup = t.strip()
            if re.fullmatch(r"[-−–]\d{1,2}", sup) and re.search(r"(10|[A-Za-z])$", prev):
                out.append("^" + sup)  # exponents: 10^-3, s^-1 (spoken later)
            elif sup in ("2", "3") and re.search(r"(?:^|[\s(])(?:[A-Za-z]|[cdkμm]?m|pseudo-R)$", prev):
                out.append("^" + sup)  # R^2, cm^2, m^3; not a citation after a word
            continue
        if (t.strip() == ":" and re.fullmatch(r"Adv[A-Z0-9]{5,}", sp.font) and i + 1 < len(spans)
                and re.search(r"\d$", "".join(out)) and re.match(r"\s?\d", spans[i + 1].text)):
            out.append(".")  # a decimal point set in eLife's math font: "0:03"
            continue
        if out and sp.x0 - spans[i - 1].x1 > sp.size * 0.15 and not out[-1].endswith(" ") and not t.startswith(" "):
            t = " " + t
        out.append(t)
    text = re.sub(r"\s+", " ", "".join(out)).strip().translate(_LIGATURES)
    # a missing space after a full stop: "processing.In that respect" (J Neurosci, Cell Press)
    return re.sub(r"(?<=[a-z]{2}[.;:?!])(?=[A-Z][a-z]+\b)", " ", text)


def _group(spans: list[Span]) -> list[list[Span]]:
    """Split a line's spans where there is a gutter-sized horizontal gap."""
    groups: list[list[Span]] = [[spans[0]]]
    for prev, sp in zip(spans, spans[1:]):
        if sp.x0 - prev.x1 > _SPLIT_GAP * max(sp.size, prev.size):
            groups.append([sp])
        else:
            groups[-1].append(sp)
    return groups


def _make_line(spans: list[Span], y0: float, y1: float, page_no: int) -> Line | None:
    text = _spans_text(spans)
    if not text:
        return None
    sizes: Counter[float] = Counter()
    bold_chars = 0
    for sp in spans:
        if sp.superscript:
            continue
        n = len(sp.text.strip())
        sizes[sp.size] += n
        bold_chars += n if sp.bold else 0
    total = sum(sizes.values()) or 1
    size = sizes.most_common(1)[0][0] if sizes else spans[0].size
    return Line(
        text=text,
        x0=min(s.x0 for s in spans),
        # PyMuPDF 2.0 reports tight glyph boxes for some fonts (6 pt high for 8.5 pt
        # type); at least the font size keeps every gap test version-independent
        y0=min(y0, y1 - size),
        x1=max(s.x1 for s in spans),
        y1=y1,
        size=size,
        bold=bold_chars / total > 0.6,
        page=page_no,
        spans=spans,
    )


def _merge_rects(rects: list[tuple], gap: float) -> list[tuple]:
    rects = [tuple(r) for r in rects]
    merged = True
    while merged:
        merged = False
        out: list[tuple] = []
        for r in rects:
            for i, o in enumerate(out):
                if r[0] - gap <= o[2] and o[0] - gap <= r[2] and r[1] - gap <= o[3] and o[1] - gap <= r[3]:
                    out[i] = (min(r[0], o[0]), min(r[1], o[1]), max(r[2], o[2]), max(r[3], o[3]))
                    merged = True
                    break
            else:
                out.append(r)
        rects = out
    return rects


def figure_regions(fpage) -> list[tuple[float, float, float, float]]:
    """Areas covered by images and by clusters of vector drawings."""
    rects = [tuple(i["bbox"]) for i in fpage.get_image_info()]
    try:
        clusters = fpage.cluster_drawings(x_tolerance=5, y_tolerance=5)
    except Exception:  # older PyMuPDF
        clusters = []
    rects += [tuple(r) for r in clusters if r.width > 20 or r.height > 20]
    page_area = fpage.rect.width * fpage.rect.height
    regions = _merge_rects(rects, gap=20)
    # big enough to be a figure, but not a frame around the whole page
    return [r for r in regions if (r[2] - r[0]) > 40 and (r[3] - r[1]) > 40
            and (r[2] - r[0]) * (r[3] - r[1]) < 0.85 * page_area]


def _respace(span: dict) -> str:
    """Span text, with word spaces restored where the PDF has none.

    Some PDFs (J Neurosci 2006-2018) position every word but store no space
    characters: "oneitemwasgivenasacue,and". Letters of a word sit about
    -0.2 pt apart, words about 0.14 em: a gap well above the typical one is a space.
    """
    chars = span.get("chars", [])
    text = "".join(c["c"] for c in chars) if chars else span.get("text", "")
    pairs = [(c, n) for c, n in zip(chars, chars[1:]) if c["c"] != " " and n["c"] != " "]
    if len(pairs) < 8 or re.match(r"(cmmi|cmsy|cmex|msbm|msam)\d|.*math", span.get("font", "").lower()):
        return text
    gaps = sorted(n["bbox"][0] - c["bbox"][2] for c, n in pairs)
    # typical letter gap + a margin. Missing spaces measure 0.12-0.15 em above
    # the letter gap; odd glyph boxes in normal text ("ep ilepsy", "ref lected",
    # italic overhangs) up to 0.085 em. A long span without any space is glued
    # text for sure, and gets the lower margin.
    glued = " " not in text and len(chars) >= 15
    limit = gaps[len(gaps) // 2] + (0.09 if glued else 0.12) * span["size"]
    out = [chars[0]["c"]]
    for c, n in zip(chars, chars[1:]):
        if (c["c"] != " " and n["c"] != " " and n["bbox"][0] - c["bbox"][2] > limit
                and not unicodedata.combining(n["c"]) and not unicodedata.combining(c["c"])
                and n["c"] not in "’'”),.;:!?–-"):
            out.append(" ")
        out.append(n["c"])
    return "".join(out)


def _baseline(raw_spans: list[dict]) -> float:
    ys = sorted(s["origin"][1] for s in raw_spans if not s.get("flags", 0) & 1 and "origin" in s)
    return ys[len(ys) // 2] if ys else raw_spans[0]["bbox"][3]


def _unflag_text_after_subscript(spans: list[Span]) -> None:
    """A PyMuPDF line that starts with a subscript ("ij") flags the rest of it as superscript.

    Real superscripts are smaller than the text they follow; flagged spans as large as the
    largest span of the line, next to a clearly smaller one, are ordinary text ("... and a
    winner-take-all rule is applied ...") that would otherwise be dropped as a citation mark.
    """
    biggest = max(sp.size for sp in spans)
    smallest = min((sp.size for sp in spans if not sp.superscript), default=biggest)
    if biggest - smallest <= 1.5:
        return
    unflagged = False
    for sp in spans:
        if sp.superscript and sp.size >= biggest - 0.3:
            sp.superscript = False
            unflagged = True
    if unflagged:  # the subscript that opens the line belongs to the equation on the line above
        while len(spans) > 1 and spans[0].size < biggest - 1.5 and len(spans[0].text.strip()) <= 4:
            del spans[0]


def _visual_lines(block: dict, page: Page, maps: dict | None = None) -> list[tuple[list[Span], float, float]]:
    """PyMuPDF lines of a block regrouped by baseline.

    PyMuPDF sometimes splits one printed line into several when citation
    superscripts raise part of it ("motion (Figure 2B),95 movement
    trajectories,96 ..."); sorted by y0, the pieces would come out shuffled.
    Adjacent pieces on the same baseline are one line again, if both are words
    or citations: math fragments stay apart, so that they are still dropped.
    """
    def wordy(spans: list[Span]) -> bool:
        text = "".join(sp.text for sp in spans).strip()
        return (any(sp.superscript for sp in spans) or re.search(r"[A-Za-z]{3,}", text) is not None
                or text in _SHORT_WORDS)

    def adjacent(spans: list[Span], others: list[Span]) -> bool:
        gap = min(min(abs(sp.x0 - o.x1), abs(o.x0 - sp.x1)) for sp in spans for o in others)
        return gap < _SPLIT_GAP * max(sp.size for sp in spans)

    rows: list[list] = []  # [baseline, spans, y0, y1]
    for ln in block["lines"]:
        dx, dy = ln.get("dir", (1, 0))
        if abs(dy) > 0.1:
            # rotated text: margin stamps, arXiv ids, journal banners
            page.rotated.append("".join(s["text"] for s in ln["spans"]))
            continue
        raw = [s for s in ln["spans"] if s["text"].strip()]
        if not raw:
            continue
        spans = [_make_span(s, maps) for s in raw]
        _unflag_text_after_subscript(spans)
        base = _baseline(raw)
        _, y0, _, y1 = ln["bbox"]
        for row in rows:
            if (abs(row[0] - base) < 1.5 and wordy(spans) and wordy(row[1]) and adjacent(spans, row[1])
                    and all(sp.x1 <= o.x0 or sp.x0 >= o.x1 for sp in spans for o in row[1])):
                row[1] += spans
                row[2], row[3] = min(row[2], y0), max(row[3], y1)
                break
        else:
            rows.append([base, spans, y0, y1])
    out = []
    for _, spans, y0, y1 in rows:
        spans.sort(key=lambda sp: sp.x0)
        out.append((spans, y0, y1))
    return out


def extract(path: str) -> Document:
    pdf = fitz.open(path)
    maps = _ELIFE_MAPS if len(pdf) and "10.7554/eLife" in pdf[0].get_text() else _COMMON_MAPS
    pages: list[Page] = []
    for pno, fpage in enumerate(pdf):
        rect = fpage.rect
        page = Page(number=pno, width=rect.width, height=rect.height, figures=figure_regions(fpage))
        data = fpage.get_text("rawdict")  # "dict" plus character boxes, for _respace
        for block in data["blocks"]:
            for ln in block.get("lines", []):
                for sp in ln["spans"]:
                    sp["text"] = _respace(sp)
            if block.get("type", 0) != 0:
                continue  # image block
            for spans, y0, y1 in _visual_lines(block, page, maps):
                for grp in _group(spans):
                    line = _make_line(grp, y0, y1, pno)
                    if line:
                        page.lines.append(line)
        pages.append(page)
    meta = dict(pdf.metadata or {})
    pdf.close()
    return Document(path=str(path), pages=pages, metadata=meta)
