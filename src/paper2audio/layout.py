"""Layout analysis: junk lines, columns, reading order, paragraphs.

Everything here is journal-agnostic. Journal profiles tune it through the
parameters on `JournalProfile` and through their hooks.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import TYPE_CHECKING

from .models import Document, Kind, Line, Page, Paragraph

if TYPE_CHECKING:
    from .profiles.base import JournalProfile

_NUM = re.compile(r"^\d{1,4}$")
_CAPTION = re.compile(
    r"^(supplementary |extended data |supporting )?(fig(ure)?s?\.?|table|scheme|plate|box)\s*[S]?\d+[a-z]?\b[.:|]?",
    re.I,
)
_NUMBERED_HEADING = re.compile(r"^(\d+(\.\d+)*\.?|[IVX]+\.|[A-H]\.)\s+[A-Z]")
_SUBSECTION_NUMBER = re.compile(r"^\d+(\.\d+)+\.?\s+[A-Z]")  # "2.1. ", "3.2.1 "
_HEADING_WORD = re.compile(r"[A-Za-z]{4,}|^[A-Z]{2,}\b")  # "Methods", "RNA"; not "a" or "f x"
_CODEISH = re.compile(r"[\w.]+\(|\w+_\w+|^[{}\[\]=#]+$|^(import|def|return|lambda)$|[a-z_]+\.[a-z_]+\(?$")
_TERMINAL = re.compile(r"[.!?:]['\"”’)]*$")


# --------------------------------------------------------------------------- statistics


def body_font_size(doc: Document) -> float:
    sizes: Counter[float] = Counter()
    for ln in doc.lines:
        sizes[round(ln.size, 1)] += len(ln.text)
    return float(sizes.most_common(1)[0][0]) if sizes else 10.0


def _norm_hf(text: str) -> str:
    """Normalise header/footer text so 'Page 3 of 12' == 'Page 4 of 12'."""
    return re.sub(r"\d+", "#", text.lower()).strip()


# --------------------------------------------------------------------------- junk lines


def mark_headers_footers(doc: Document, profile: "JournalProfile") -> None:
    """Running heads/feet: text repeated in the top/bottom band of many pages."""
    if not doc.pages:
        return
    counts: Counter[str] = Counter()
    for page in doc.pages:
        seen = set()
        for ln in page.lines:
            if _in_band(ln, page, profile):
                seen.add(_norm_hf(ln.text))
        counts.update(seen)
    # absolute, not relative: Methods / Extended Data pages often carry a
    # different running head, so each variant covers only part of the document
    min_pages = 2 if len(doc.pages) <= 4 else 3
    for page in doc.pages:
        for ln in page.lines:
            if not _in_band(ln, page, profile):
                continue
            norm = _norm_hf(ln.text)
            if counts[norm] >= min_pages or _NUM.match(ln.text) or re.fullmatch(r"#( of #| / #)?|page #( of #)?", norm):
                ln.kind = Kind.HEADER_FOOTER


def _in_band(ln: Line, page: Page, profile: "JournalProfile") -> bool:
    return ln.y1 < page.height * profile.header_band or ln.y0 > page.height * (1 - profile.footer_band)


def mark_line_numbers(doc: Document, min_count: int = 5) -> None:
    """Manuscript line numbers: short integers stacked at the same x position.

    Positions are learned over the whole document, so a page with only two
    numbered lines is handled too. Numbers glued as the first span of a text
    line are stripped from it.
    """
    bins: dict[int, list[tuple[Line, bool]]] = defaultdict(list)
    for ln in doc.lines:
        if ln.kind != Kind.BODY:
            continue
        if _NUM.match(ln.text):
            bins[round(ln.x1 / 6)].append((ln, False))
        elif (ln.spans and _NUM.match(ln.spans[0].text.strip()) and len(ln.spans) > 1
              and ln.spans[1].x0 - ln.spans[0].x1 > ln.size * 0.8):  # set apart from the text, not "1 kHz"
            bins[round(ln.spans[0].x1 / 6)].append((ln, True))
    for members in bins.values():
        if len(members) < min_count:
            continue
        nums = [int(m[0].text.split()[0]) for m in members if m[0].text.split()[0].isdigit()]
        if len(set(nums)) < len(nums) * 0.7:  # line numbers are (mostly) distinct
            continue
        for ln, glued in members:
            if glued:
                ln.spans = ln.spans[1:]
                ln.x0 = ln.spans[0].x0
                ln.text = ln.text.split(" ", 1)[1] if " " in ln.text else ln.text
            else:
                ln.kind = Kind.LINE_NUMBER


def mark_small_text(doc: Document, body: float, profile: "JournalProfile") -> None:
    """Text clearly smaller than the body font: figure labels, footnotes, tables."""
    limit = body * profile.small_text_ratio
    for ln in doc.lines:
        if ln.kind == Kind.BODY and ln.size < limit:
            ln.kind = Kind.FOOTNOTE



def mark_fragment_flows(ordered: list[Line]) -> None:
    """A flow made of short, unpunctuated fragments is figure or table text
    (axis labels, legends, row names), not prose."""
    flows: dict[tuple[int, int], list[Line]] = defaultdict(list)
    for ln in ordered:
        flows[(ln.page, ln.column)].append(ln)
    for lines in flows.values():
        body = [ln for ln in lines if ln.kind == Kind.BODY]
        considered = [ln for ln in lines if ln.kind not in (Kind.HEADING, Kind.TITLE)]
        if not body or len(considered) < 2:
            continue
        short = [ln for ln in considered if len(ln.text.split()) <= 6 and not _TERMINAL.search(ln.text)]
        if len(short) >= 0.8 * len(considered) and sum(len(ln.text) for ln in considered) / len(considered) < 35:
            for ln in body:
                ln.kind = Kind.OTHER


def mark_captions(ordered: list[Line], body: float) -> None:
    """Label caption lines, after reading order is known.

    1. A caption starts at a "Fig. N" / "Table N" line that begins a block and
       continues through the following lines of the same flow in the same font
       size.
    2. If a font size other than the body size is used *mostly* by such
       captions (Nature: 7 pt captions, 8.2 pt text), every line in that size is
       caption text, e.g. the second half of a caption set across two columns.
       Journals that share the caption size with other text (APS: 9 pt captions
       and 9 pt Methods) keep that text.
    """
    last_in_flow: dict[tuple[int, int], Line] = {}
    open_caption: dict[tuple[int, int], Line] = {}
    for ln in ordered:
        key = (ln.page, ln.column)
        prev = last_in_flow.get(key)
        cap = open_caption.get(key)
        if ln.kind == Kind.BODY and is_caption_start(ln, prev, body):
            ln.kind = Kind.CAPTION
            open_caption[key] = ln
        elif cap is not None and ln.kind in (Kind.BODY, Kind.FOOTNOTE, Kind.HEADING) \
                and abs(ln.size - cap.size) <= 0.15 and prev is not None and ln.y0 - prev.y1 < prev.height * 1.5:
            ln.kind = Kind.CAPTION
        else:
            open_caption.pop(key, None)
        last_in_flow[key] = ln

    # extend captions geometrically: a title on the same baseline to the right
    # of "Table 2." and lines directly below a caption line
    by_page: dict[int, list[Line]] = defaultdict(list)
    for ln in ordered:
        by_page[ln.page].append(ln)
    for lines in by_page.values():
        lines = sorted(lines, key=lambda l: (l.y0, l.x0))
        caps = [ln for ln in lines if ln.kind == Kind.CAPTION]
        for ln in lines:
            if ln.kind != Kind.BODY:
                continue
            for cap in caps:
                # "Table 2." + its title on the same baseline, or the second column of
                # a caption set across two columns (Nature); not a column of body text
                # next to a caption line (J Neurosci 2006)
                beside = (abs(ln.y0 - cap.y0) < 2.5 and 0 <= ln.x0 - cap.x1 < 20
                          and (len(cap.text.split()) <= 3 or abs(ln.size - body) > 0.5))
                overlap = min(ln.x1, cap.x1) - max(ln.x0, cap.x0)
                # line boxes of tightly set captions overlap by a point or so; only
                # trust that for text smaller than the body (not a column of prose)
                tight = -cap.height * 0.3 if abs(ln.size - body) > 0.5 else 0
                below = tight <= ln.y0 - cap.y1 < cap.height * 0.8 \
                    and overlap > 0.5 * min(ln.width, cap.width) \
                    and abs(ln.size - cap.size) <= 1.5
                if beside or below:
                    ln.kind = Kind.CAPTION
                    caps.append(ln)
                    break

    size_chars: Counter[float] = Counter()
    caption_chars: Counter[float] = Counter()
    for ln in ordered:
        if ln.kind in (Kind.BODY, Kind.CAPTION):
            size_chars[round(ln.size, 1)] += len(ln.text)
            if ln.kind == Kind.CAPTION:
                caption_chars[round(ln.size, 1)] += len(ln.text)
    caption_sizes = [sz for sz, n in caption_chars.items()
                     if abs(sz - body) > 0.5 and n >= 0.4 * size_chars[sz]]
    # only in flows that hold a caption already: Methods set in the caption size
    # (J Neurosci: 46-60 % of that size is captions, Science captions 58 %) form
    # columns of their own, with no caption in them
    caption_flows = {(ln.page, ln.column) for ln in ordered if ln.kind == Kind.CAPTION}
    # an abstract may share the caption size (NeuroImage: 7.2 pt): first-page
    # text above the first section heading ("1. Introduction"; author names set
    # as a heading do not count) is never a caption by size alone. Without such
    # a heading on page 1 (Nature: drop cap), nothing is exempt.
    first = next((ln for ln in ordered if ln.page == 0 and ln.kind == Kind.HEADING
                  and (_SECTION_NAME.match(ln.text) or _NUMBERED_HEADING.match(ln.text))), None)
    front = set()
    if first is not None:
        for ln in ordered:
            if ln is first or ln.page > 0:
                break
            if ln.y1 <= first.y0:
                front.add(id(ln))
    for ln in ordered:
        if (ln.kind == Kind.BODY and id(ln) not in front and (ln.page, ln.column) in caption_flows
                and any(abs(ln.size - sz) <= 0.15 for sz in caption_sizes)):
            ln.kind = Kind.CAPTION


def _isolated(ln: Line, page: Page) -> bool:
    """No line of prose directly above or below: a label, not the end of a paragraph."""
    gap = 1.6 * ln.height
    return not any(o is not ln and o.kind == Kind.BODY and len(o.text.split()) >= 6
                   and o.x1 > ln.x0 and o.x0 < ln.x1 and ln.y0 - gap <= o.y1 and o.y0 <= ln.y1 + gap
                   for o in page.lines)


def mark_figure_text(doc: Document, body: float) -> None:
    """Axis labels, legends and panel text drawn inside figures.

    Lines inside a figure area are figure text, unless the area holds several
    full lines of prose (a shaded text box, or an area that overlaps the text).
    Short labels in a smaller font just outside an area (axis titles that the
    drawing clusters miss) are figure text too.
    """
    pad, near = 6, 24
    for page in doc.pages:
        for fx0, fy0, fx1, fy1 in page.figures:
            inside = [ln for ln in page.lines if ln.kind in (Kind.BODY, Kind.HEADING, Kind.FOOTNOTE)
                      and fx0 - pad <= ln.cx <= fx1 + pad and fy0 - pad <= (ln.y0 + ln.y1) / 2 <= fy1 + pad
                      and ln.x0 >= fx0 - 3 * pad and ln.x1 <= fx1 + 3 * pad]
            prose = [ln for ln in inside if len(ln.text.split()) >= 9]
            if len(prose) >= 3:
                continue  # the area overlaps running text (or is a shaded text box): leave it
            for ln in inside:
                if not _CAPTION.match(ln.text):
                    ln.kind = Kind.OTHER
            for ln in page.lines:
                if (ln.kind == Kind.BODY and ln.size < body - 0.5 and not ln.bold
                        and len(ln.text.split()) <= 6 and not re.search(r"[.!?:]$", ln.text.strip())
                        and ln.x1 > fx0 and ln.x0 < fx1 and fy0 - near <= ln.y1 and ln.y0 <= fy1 + near
                        and not _CAPTION.match(ln.text) and _isolated(ln, page)):
                    ln.kind = Kind.OTHER


_MATH_WORDS = {"log", "exp", "sin", "cos", "tan", "tanh", "max", "min", "argmax", "argmin", "softmax", "sign", "diag",
               "arg", "lim", "sup", "inf", "det", "var", "cov", "mod", "deg"}
_PROSE_SHORT = {"to", "of", "in", "is", "as", "at", "by", "or", "an", "on", "if", "be", "we", "it", "no", "so", "up"}
_UNMAPPED = re.compile(r"[\x00-\x08\x0b-\x1f\ue000-\uf8ff]")  # symbol-font glyphs without Unicode (θ, φ, ...)
_MATH_TOKEN = re.compile(r"^(?:[^\W\d_]{1,2}|[^\w\s]+|[^\W\d_][^\w\s]+)$")  # "x", "φ", "+", "f′"


def _continues_prose(prev: Line, ln: Line) -> bool:
    """`ln` closes a bracket that the prose line `prev` opened, or continues a
    range ("227–" + "260"). Not after a comma: "as follows," precedes equations."""
    if len(prev.text.split()) < 4 or ln.y0 - prev.y1 > prev.height or ln.y0 < prev.y0:
        return False
    opened = prev.text.count("(") - prev.text.count(")")
    closes = opened > 0 and ln.text.count(")") > ln.text.count("(") and (
        re.search(r"\)[.,;:]?$", ln.text.strip()) is not None  # "max = 4).", "2010)."
        or any(w.lower() not in _MATH_WORDS for w in re.findall(r"[A-Za-z]{4,}", ln.text)))
    return closes or prev.text.rstrip().endswith("–")


def mark_math(doc: Document) -> None:
    """Equation fragments ("x y φ", ") + log", "f x f y τ"): mostly 1-2 letter
    tokens; and code listings (monospace font)."""
    prev: Line | None = None
    for ln in doc.lines:
        before, prev = prev, (ln if ln.kind == Kind.BODY else prev)
        if ln.kind != Kind.BODY:
            continue
        if before is not None and before.page == ln.page and _continues_prose(before, ln):
            continue  # "(min = 1," + "max = 4).", "227–" + "260": the end of a prose line
        chars = [len(sp.text.strip()) for sp in ln.spans]
        if sum(c for c, sp in zip(chars, ln.spans) if sp.monospace) > 0.6 * sum(chars):
            ln.kind = Kind.OTHER
            continue
        words = ln.text.split()
        if len(words) >= 3 and sum(bool(_CODEISH.search(w)) for w in words) / len(words) > 0.4:
            ln.kind = Kind.OTHER  # code listing in an ordinary font
            continue
        bare = _UNMAPPED.sub("", ln.text).strip()
        if bare and re.fullmatch(r"[\d\s.+−\-=×/()]{1,20}", bare) and (" " in bare or re.fullmatch(r"\d{1,3}", bare)):
            ln.kind = Kind.OTHER  # "2 1 1": indices and exponents of a display equation
            continue
        # unmapped symbol glyphs (θ, φ, but also °) are dropped first, so that "360°)."
        # stays a number; numbers are neutral; "to", "of" are words, not variables;
        # a glyph standing alone ("Yk θ p(k") is math, one attached to a number is not
        symbols = sum(1 for t in ln.text.split() if _UNMAPPED.search(t) and not _UNMAPPED.sub("", t).strip("(),.;:"))
        text = _UNMAPPED.sub("", ln.text)
        tokens = [t for t in text.split() if not re.fullmatch(r"[-−–+×^\d.,;:()%]+", t)]
        mathy = symbols + sum(1 for t in tokens if (_MATH_TOKEN.match(t.rstrip(",.;:") or t)
                                                    and t.lower().strip(",.;:()") not in _PROSE_SHORT)
                              or t.lower().strip(",.;:()") in _MATH_WORDS)
        tokens += ["θ"] * symbols
        real_words = [w for w in re.findall(r"[A-Za-z]{4,}", ln.text) if w.lower() not in _MATH_WORDS]
        numbered_equation = re.search(r"\(\d{1,2}[a-z]?\)\s*$", ln.text) and len(real_words) <= 2
        if numbered_equation or (tokens and not real_words and (len(tokens) <= 12 or mathy == len(tokens)) and mathy / len(tokens) > 0.6):
            ln.kind = Kind.OTHER


def mark_patterns(doc: Document, profile: "JournalProfile") -> None:
    pats = profile.compiled_junk_lines()
    if not pats:
        return
    for ln in doc.lines:
        if ln.kind != Kind.HEADER_FOOTER and any(p.search(ln.text) for p in pats):
            ln.kind = Kind.HEADER_FOOTER


_SECTION_NAME = re.compile(
    r"^((\d+(\.\d+)*|[IVX]+)\.?\s+)?(abstract|summary|introduction|background|methods?|materials and methods|"
    r"experimental procedures|results( and discussion)?|discussion|conclusions?|general discussion|references|"
    r"bibliography|acknowledge?ments?|grants|disclosures|endnotes?|author contributions|funding|appendix)\s*$",
    re.I,
)


def _mark_plain_title(page: Page) -> None:
    """No large title font (preprints, manuscripts): take the first bold block near the top."""
    lines = sorted((ln for ln in page.lines if ln.kind in (Kind.BODY, Kind.HEADING)), key=lambda l: l.y0)
    title: list[Line] = []
    for ln in lines:
        if ln.y0 > page.height * 0.4:
            break
        if not title:
            if ln.bold and len(ln.text.split()) >= 3 and not _SECTION_NAME.match(ln.text):
                title.append(ln)
            continue
        if ln.bold and abs(ln.size - title[-1].size) < 0.3 and ln.y0 - title[-1].y1 < title[-1].height:
            title.append(ln)
        else:
            break
    for ln in title:
        ln.kind = Kind.TITLE


def mark_headings(doc: Document, body: float) -> None:
    title_size = 0.0
    if doc.pages:
        first = [ln.size for ln in doc.pages[0].lines if ln.kind == Kind.BODY and len(ln.text) > 3]
        title_size = max(first, default=0.0)
        if title_size <= body * 1.3:
            _mark_plain_title(doc.pages[0])
    italic_headings: set[int] = set()
    for ln in doc.lines:
        if ln.kind in (Kind.BODY, Kind.FOOTNOTE) and _SECTION_NAME.match(ln.text) and (ln.bold or ln.text.isupper()):
            ln.kind = Kind.HEADING  # "INTRODUCTION" in small caps, smaller than the body text
            continue
        if ln.kind != Kind.BODY:
            continue
        words = len(ln.text.split())
        if not _HEADING_WORD.search(ln.text) or _CAPTION.match(ln.text):
            continue  # panel letters "a", math "f x f y", numbers; "Figure 1. Title" is a caption
        if ln.page == 0 and title_size > body * 1.3 and ln.size >= title_size - 0.5:
            ln.kind = Kind.TITLE
        elif (words <= 14 and ln.size > body * 1.15 and (ln.bold or ln.size > body * 1.2)
              and not _TERMINAL.search(ln.text)):
            ln.kind = Kind.HEADING
        elif (words <= 18 and ln.bold and ln.size >= body - 0.5 and not ln.text.endswith((".", ",", ";"))
              and all(sp.bold for sp in ln.spans if sp.text.strip())):  # not a run-in heading
            ln.kind = Kind.HEADING
        elif (words <= 14 and _SUBSECTION_NUMBER.match(ln.text) and abs(ln.size - body) <= 0.5
              and not _TERMINAL.search(ln.text) and _all_italic(ln)):
            ln.kind = Kind.HEADING  # "2.1. Participants" in italics (Elsevier, Frontiers)
            italic_headings.add(id(ln))
    # "Receptive field mapping": a short italic line set larger than the text it
    # introduces (J Neurosci 2006: 9.5 pt italic over 8.5 pt Methods)
    for page in doc.pages:
        for prev, ln, nxt in zip([None, *page.lines], page.lines, [*page.lines[1:], None]):
            if (nxt is not None and ln.kind == Kind.BODY and nxt.kind == Kind.BODY and _all_italic(ln)
                    and len(ln.text.split()) <= 10 and not _TERMINAL.search(ln.text)
                    and ln.size >= nxt.size + 0.5 and not _all_italic(nxt)
                    and 0 <= nxt.y0 - ln.y1 < 1.5 * ln.height and _HEADING_WORD.search(ln.text)):
                ln.kind = Kind.HEADING
    _demote_bold_paragraphs(doc)
    # second line of a wrapped italic heading: italic, aligned, directly below
    for page in doc.pages:
        for prev, ln in zip(page.lines, page.lines[1:]):
            if (id(prev) in italic_headings and ln.kind == Kind.BODY and _all_italic(ln)
                    and abs(ln.x0 - prev.x0) < 2 and 0 <= ln.y0 - prev.y1 < prev.height
                    and abs(ln.size - prev.size) < 0.3 and len(ln.text.split()) <= 14):
                ln.kind = Kind.HEADING
                italic_headings.add(id(ln))


_KEYWORDS = re.compile(r"^key ?words?\s*[:.—–]", re.I)


def _demote_bold_paragraphs(doc: Document) -> None:
    """A stack of three or more bold lines in one size is a paragraph (the bold
    abstract of J Neurosci), not a series of headings; "Key words: ..." is not
    read at all."""
    for page in doc.pages:
        bold = [ln for ln in page.lines if ln.bold and ln.kind in (Kind.BODY, Kind.HEADING)]
        above: dict[int, Line] = {}
        for ln in bold:
            cands = [o for o in bold if o is not ln and abs(o.size - ln.size) < 0.3 and o.y1 <= ln.y0 + 1
                     and ln.y0 - o.y1 < 0.6 * ln.height and min(o.x1, ln.x1) - max(o.x0, ln.x0) > 0.5 * min(o.width, ln.width)]
            if cands:
                above[id(ln)] = max(cands, key=lambda o: o.y1)
        below = {id(o): ln for ln in bold if (o := above.get(id(ln))) is not None}
        seen: set[int] = set()
        for ln in bold:
            if id(ln) in seen or id(ln) in above:
                continue
            stack = [ln]  # walk down from the top of a stack
            while id(stack[-1]) in below:
                stack.append(below[id(stack[-1])])
            seen.update(id(x) for x in stack)
            if len(stack) >= 3:
                for x in stack:
                    if x.kind == Kind.HEADING and not (_SECTION_NAME.match(x.text) or _NUMBERED_HEADING.match(x.text)):
                        x.kind = Kind.BODY
        keywords = [ln for ln in page.lines if ln.kind in (Kind.HEADING, Kind.BODY) and _KEYWORDS.match(ln.text)]
        for kw in keywords:  # never read, and never glued to the prose that follows
            kw.kind = Kind.OTHER
            last = kw
            while True:  # the list may wrap: "...; working memory; delay activity"
                nxt = next((ln for ln in page.lines if ln.kind in (Kind.HEADING, Kind.BODY)
                            and 0 <= ln.y0 - last.y1 < last.height and abs(ln.x0 - kw.x0) < 2
                            and len(ln.text.split()) <= 15 and not re.search(r"[.!?]$", ln.text)), None)
                if nxt is None:
                    break
                nxt.kind = Kind.OTHER
                last = nxt


def _all_italic(ln: Line) -> bool:
    return all(sp.italic for sp in ln.spans if sp.text.strip())


# --------------------------------------------------------------------------- reading order
#
# Recursive XY-cut:
#   1. if a vertical gutter runs through every line of the region, split into
#      columns and read them left to right;
#   2. otherwise split into horizontal bands at vertical white space, merge
#      consecutive bands that share a column structure (so a coincidental gap in
#      both columns does not break the flow), and read the bands top to bottom;
#   3. a region with neither is one flow, read top to bottom.
# Every line gets `column` = an id of the flow it belongs to; paragraphs never
# continue silently across flows.


def vertical_cuts(lines: list[Line], min_gap: float) -> list[float]:
    """x positions of white-space gutters crossing every line of the region."""
    if len(lines) < 2:
        return []
    spans = sorted((ln.x0, ln.x1) for ln in lines)
    cuts: list[float] = []
    reach = spans[0][1]
    for x0, x1 in spans[1:]:
        if x0 - reach >= min_gap:
            cuts.append((reach + x0) / 2)
        reach = max(reach, x1)
    return cuts


def horizontal_bands(lines: list[Line], min_gap: float) -> list[list[Line]]:
    ordered = sorted(lines, key=lambda ln: ln.y0)
    bands: list[list[Line]] = [[ordered[0]]]
    bottom = ordered[0].y1
    for ln in ordered[1:]:
        if ln.y0 - bottom >= min_gap:
            bands.append([ln])
        else:
            bands[-1].append(ln)
        bottom = max(bottom, ln.y1)
    return bands


def xy_cut(lines: list[Line], body: float, path: tuple = ()) -> list[tuple[Line, tuple]]:
    if not lines:
        return []
    v_gap, h_gap = body * 0.8, body * 0.25
    cuts = vertical_cuts(lines, v_gap)
    if cuts:
        cols: list[list[Line]] = [[] for _ in range(len(cuts) + 1)]
        for ln in lines:
            cols[sum(1 for c in cuts if ln.cx > c)].append(ln)
        return [item for i, col in enumerate(cols) for item in xy_cut(col, body, path + (("v", i),))]

    bands = horizontal_bands(lines, h_gap)
    if len(bands) > 1:
        groups: list[list[Line]] = [bands[0]]
        for band in bands[1:]:
            last = groups[-1]
            both_flat = not vertical_cuts(last, v_gap) and not vertical_cuts(band, v_gap)
            if both_flat or vertical_cuts(last + band, v_gap):
                last.extend(band)
            else:
                groups.append(band)
        if len(groups) > 1:
            return [item for j, g in enumerate(groups) for item in xy_cut(g, body, path + (("h", j),))]
    return [(ln, path) for ln in sorted(lines, key=lambda ln: (round(ln.y0), ln.x0))]


def reading_order(page: Page, body: float) -> list[Line]:
    ids: dict[tuple, int] = {}
    out = []
    for ln, path in xy_cut(page.lines, body):
        ln.column = ids.setdefault(path, len(ids))
        out.append(ln)
    return out


# --------------------------------------------------------------------------- paragraphs


_WORD = re.compile(r"[A-Za-z][A-Za-z-]*[A-Za-z]")


def vocabulary(lines: list[Line]) -> set[str]:
    return {w.lower() for ln in lines for w in _WORD.findall(ln.text)}


def _join(a: str, b: str, vocab: set[str] = frozenset()) -> str:
    a = re.sub(r"[\u00ad\u2010\u2011]$", "-", a)  # soft / Unicode hyphens at line end
    m = re.search(r"([A-Za-z]+)-$", a)
    if m and b[:1].islower():
        head, tail = m.group(1), re.match(r"[A-Za-z]*", b).group(0)
        merged = (head + tail).lower()
        hyphenated = f"{head}-{tail}".lower()
        if hyphenated in vocab and merged not in vocab:
            return a + b  # a real compound: "language-" + "aligned"
        return a[:-1] + b  # de-hyphenate "percep-" + "tion"
    return a + " " + b


def is_caption_start(ln: Line, prev: Line | None, body: float) -> bool:
    """"Fig. 2 | ..." starting a caption, not "...shown in" / "Supplementary Fig. 12c." mid-paragraph."""
    m = _CAPTION.match(ln.text)
    if not m:
        return False
    # a sentence that starts with a figure reference, also in Methods set smaller
    # than the body (APS) and in bold (eLife): "Fig. 1D) and at ...", "Figure 3
    # illustrates the ...", or a line that continues the sentence of the line above
    rest = ln.text[m.end():].lstrip()
    if rest[:1] in (")", ",", ";") or (not re.search(r"[.:|]$", m.group(0)) and rest[:1].islower()):
        return False
    first = next((sp for sp in ln.spans if sp.text.strip()), None)
    if first is not None and first.bold:
        return True
    continued = (prev is not None and abs(prev.size - ln.size) < 0.3 and not _TERMINAL.search(prev.text)
                 and 0 <= ln.y0 - prev.y1 < prev.height * 0.6)
    if continued:
        return False
    if abs(ln.size - body) > 0.3:
        return True
    return prev is None or (_TERMINAL.search(prev.text) is not None and ln.y0 - prev.y1 > prev.height * 0.3)


_DANGLING = re.compile(r"(?:[-,(]|\b(?:the|a|an|of|and|or|in|on|at|to|for|with|by|from|that|which|as|is|are|was|were|than|between|we|our|its|their))$", re.I)


def _footnote_into_body(prev: Line, ln: Line, body: float) -> bool:
    """Small text (affiliations, footnotes) followed by body text: Nature's 8 pt
    affiliations, then on the next page the 9.5 pt introduction, which starts
    lowercase after its drop cap. Never one sentence."""
    return prev.size < body - 0.7 and abs(ln.size - body) <= 0.3


def _cut_sentence(prev: Line, ln: Line, body: float) -> bool:
    """Does `prev` end mid-sentence so that `ln` (in another column/page) continues it?"""
    if _TERMINAL.search(prev.text) or _footnote_into_body(prev, ln, body):
        return False
    return (_continuation_start(ln.text) or _DANGLING.search(prev.text) is not None
            or re.match(r"[A-Z]{2,}s?\b", ln.text) is not None)  # "...the diagnosed | ID group"


def _continuation_start(text: str) -> bool:
    """Text that cannot begin a sentence: 'loaded positively', '(rcv = 0.41)', '12 trials'."""
    return text[:1].islower() or text[:1] in "([0123456789,;"


def _continues(prev: Line, ln: Line, body: float) -> bool:
    """An unfinished sentence followed by a lowercase word: same paragraph."""
    return (_TERMINAL.search(prev.text) is None and _continuation_start(ln.text)
            and not _footnote_into_body(prev, ln, body))


_MAIN_FLOW = (Kind.BODY, Kind.HEADING, Kind.TITLE)


def build_paragraphs(ordered: list[Line], body: float, vocab: set[str] = frozenset()) -> list[Paragraph]:
    """Paragraphs of the main text and, separately, of captions/footnotes/math.

    The two are built apart so that a caption or equation sitting between the
    two halves of a sentence (typically across a column break) does not cut it.
    """
    main = [(i, ln) for i, ln in enumerate(ordered) if ln.kind in _MAIN_FLOW]
    main_ids = {i for i, _ in main}
    side = [(i, ln) for i, ln in enumerate(ordered) if i not in main_ids]
    paras = _paragraphs(main, body, vocab) + _paragraphs(side, body, vocab, join_flows=False)
    return [p for _, p in sorted(paras, key=lambda ip: ip[0])]


def _paragraphs(indexed: list[tuple[int, Line]], body: float, vocab: set[str],
                join_flows: bool = True) -> list[tuple[int, Paragraph]]:
    ordered = [ln for _, ln in indexed]
    paras: list[tuple[int, Paragraph]] = []
    prev: Line | None = None
    cur: Paragraph | None = None
    # column edges, measured apart for footnote-size text: Nature's 8 pt
    # affiliations run wider than the 9.5 pt abstract above them, which would
    # make every abstract line look short
    col_right: dict[tuple[int, int, bool], float] = {}
    col_left: dict[tuple[int, int, bool], float] = {}
    for ln in ordered:
        key = (ln.page, ln.column, ln.size < body - 0.7)
        col_right[key] = max(col_right.get(key, 0), ln.x1)
        col_left[key] = min(col_left.get(key, 1e9), ln.x0)

    for idx, ln in indexed:
        kind = ln.kind
        new = cur is None or prev is None
        if not new:
            assert prev is not None and cur is not None
            same_flow = prev.page == ln.page and prev.column == ln.column
            if kind != cur.kind and not (cur.kind == Kind.CAPTION and kind == Kind.BODY):
                new = True
            elif kind in (Kind.HEADING, Kind.TITLE):
                # a heading only wraps onto a second line when the first one is full
                prev_short = prev.x1 < col_right[(prev.page, prev.column, prev.size < body - 0.7)] - body * 6
                new = (
                    not same_flow
                    or (prev_short and not ln.text[:1].islower())
                    or ln.y0 - prev.y1 > max(ln.height, prev.height) * 0.5
                    or abs(ln.size - prev.size) > 0.5
                    or _NUMBERED_HEADING.match(ln.text) is not None
                )
            elif same_flow:
                gap = ln.y0 - prev.y1
                indent = ln.x0 - col_left[(ln.page, ln.column, ln.size < body - 0.7)] > body * 0.8
                short_prev = prev.x1 < col_right[(prev.page, prev.column, prev.size < body - 0.7)] - body * 2.5
                new = (
                    gap > max(prev.height, ln.height) * 0.7
                    or gap < -prev.height  # jumped upward: different region
                    or (indent and _TERMINAL.search(prev.text) is not None)
                    or (short_prev and _TERMINAL.search(prev.text) is not None)
                )
                if new and kind == Kind.BODY and _continues(prev, ln, body):
                    new = False  # e.g. "the criterion is [display equation] which, ..."
                if cur.kind == Kind.CAPTION and kind == Kind.BODY and not new:
                    kind = Kind.CAPTION
            else:
                # crossing a column or page: continue the sentence if it was visibly cut
                new = not join_flows or cur.kind == Kind.CAPTION or not _cut_sentence(prev, ln, body)
            new = new or (kind == Kind.CAPTION and _CAPTION.match(ln.text) is not None)
        if new:
            cur = Paragraph(text=ln.text, kind=kind, page=ln.page, size=ln.size)
            paras.append((idx, cur))
        else:
            assert cur is not None
            cur.text = _join(cur.text, ln.text, vocab)
        prev = ln
    return paras


def merge_broken(paras: list[Paragraph], vocab: set[str] = frozenset(), body: float = 0.0) -> list[Paragraph]:
    """Re-join body paragraphs split mid-sentence ("... early risk" + "stratification and ...")."""
    out: list[Paragraph] = []
    for p in paras:
        prev = next((q for q in reversed(out) if q.kind == Kind.BODY), None) if p.kind == Kind.BODY else None
        # only look back past non-main-flow paragraphs (captions, footnotes, math);
        # never from footnote-size text into body text (see _footnote_into_body)
        if prev is not None and all(q.kind not in _MAIN_FLOW for q in out[out.index(prev) + 1:]) \
                and _TERMINAL.search(prev.text) is None and _continuation_start(p.text) \
                and not (body and prev.size and prev.size < body - 0.7 and abs(p.size - body) <= 0.3):
            prev.text = _join(prev.text, p.text, vocab)
            continue
        out.append(p)
    return out


_TABLEISH = re.compile(r"^[-−+±]?[\d.,%]+$")


def mark_code(paras: list[Paragraph]) -> None:
    """Program listings set in an ordinary font: dense in calls, snake_case, '='."""
    for p in paras:
        tokens = p.text.split()
        if p.kind == Kind.BODY and len(tokens) >= 4 and sum(bool(_CODEISH.search(t)) for t in tokens) / len(tokens) > 0.3:
            p.kind = Kind.OTHER


def mark_tables(paras: list[Paragraph]) -> None:
    for p in paras:
        if p.kind != Kind.BODY:
            continue
        tokens = p.text.split()
        if len(tokens) >= 6 and sum(bool(_TABLEISH.match(t)) for t in tokens) / len(tokens) > 0.4:
            p.kind = Kind.TABLE


# --------------------------------------------------------------------------- driver


def analyse(doc: Document, profile: "JournalProfile", keep_junk: bool = False) -> list[Paragraph]:
    body = body_font_size(doc)
    mark_patterns(doc, profile)
    mark_headers_footers(doc, profile)
    mark_line_numbers(doc)
    mark_small_text(doc, body, profile)
    mark_figure_text(doc, body)
    mark_math(doc)
    mark_headings(doc, body)
    profile.classify_lines(doc, body)

    ordered: list[Line] = []
    for page in doc.pages:
        junk = [ln for ln in page.lines if ln.kind in (Kind.HEADER_FOOTER, Kind.LINE_NUMBER)]
        page.lines = [ln for ln in page.lines if ln.kind not in (Kind.HEADER_FOOTER, Kind.LINE_NUMBER)]
        page.lines = profile.order_page(page, body)
        ordered.extend(page.lines)
        if keep_junk:
            page.lines += junk
    mark_fragment_flows(ordered)
    mark_captions(ordered, body)
    paras = build_paragraphs(ordered, body, vocabulary(ordered))
    for p in paras:
        if p.kind == Kind.HEADING and len(p.text.split()) > 25:
            p.kind = Kind.BODY
    paras = merge_broken(paras, vocabulary(ordered), body)
    mark_tables(paras)
    mark_code(paras)
    return paras
