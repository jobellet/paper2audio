"""PDF -> Document of positioned lines, using PyMuPDF."""

from __future__ import annotations

import re
from collections import Counter

import pymupdf as fitz

from .models import Document, Line, Page, Span

# Superscripts that are references/footnote/affiliation markers, never speech.
_SUP_MARKER = re.compile(r"^[\s\d,;–\-−‒*†‡§¶#a-z]{1,20}$")
# A horizontal gap this many times the font size splits a line in two
# (PyMuPDF occasionally glues text across a narrow column gutter).
_SPLIT_GAP = 2.0
_MONO_FONTS = ("courier", "mono", "consola", "menlo", "inconsolata", "sourcecodepro", "cmtt", "lucidaconsole")


def _is_bold(span: dict) -> bool:
    font = span.get("font", "").lower()
    return (bool(span.get("flags", 0) & 16) or any(w in font for w in ("bold", "black", "heavy", "semibold"))
            or re.search(r"hn-(h|hv|b|bd)$", font) is not None)  # Helvetica Neue weights: AdvPSHN-H (Cell Press)


def _make_span(s: dict) -> Span:
    x0, _, x1, _ = s["bbox"]
    flags = s.get("flags", 0)
    text = s["text"]
    if text.strip() == "d" and re.search(r"mpi\d", s.get("font", "").lower()):
        text = text.replace("d", "•")  # Mathematical Pi bullet (Cell Press lists)
    return Span(
        text=text,
        x0=x0,
        x1=x1,
        size=round(s["size"], 1),
        bold=_is_bold(s),
        italic=bool(flags & 2),
        superscript=bool(flags & 1),
        monospace=bool(flags & 8) or any(m in s.get("font", "").lower() for m in _MONO_FONTS),
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
        if out and sp.x0 - spans[i - 1].x1 > sp.size * 0.15 and not out[-1].endswith(" ") and not t.startswith(" "):
            t = " " + t
        out.append(t)
    return re.sub(r"\s+", " ", "".join(out)).strip()


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
        y0=y0,
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


def extract(path: str) -> Document:
    pdf = fitz.open(path)
    pages: list[Page] = []
    for pno, fpage in enumerate(pdf):
        rect = fpage.rect
        page = Page(number=pno, width=rect.width, height=rect.height, figures=figure_regions(fpage))
        data = fpage.get_text("dict")
        for block in data["blocks"]:
            if block.get("type", 0) != 0:
                continue  # image block
            for ln in block["lines"]:
                dx, dy = ln.get("dir", (1, 0))
                if abs(dy) > 0.1:
                    # rotated text: margin stamps, arXiv ids, journal banners
                    page.rotated.append("".join(s["text"] for s in ln["spans"]))
                    continue
                spans = [_make_span(s) for s in ln["spans"] if s["text"].strip()]
                if not spans:
                    continue
                spans.sort(key=lambda s: s.x0)
                _, y0, _, y1 = ln["bbox"]
                for grp in _group(spans):
                    line = _make_line(grp, y0, y1, pno)
                    if line:
                        page.lines.append(line)
        pages.append(page)
    meta = dict(pdf.metadata or {})
    pdf.close()
    return Document(path=str(path), pages=pages, metadata=meta)
