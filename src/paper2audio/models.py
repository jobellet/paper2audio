"""Plain data structures shared by every stage of the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Kind(str, Enum):
    BODY = "body"
    HEADING = "heading"
    TITLE = "title"
    CAPTION = "caption"
    TABLE = "table"
    FOOTNOTE = "footnote"
    HEADER_FOOTER = "header_footer"
    LINE_NUMBER = "line_number"
    OTHER = "other"


@dataclass
class Span:
    text: str
    x0: float
    x1: float
    size: float
    bold: bool = False
    italic: bool = False
    superscript: bool = False
    monospace: bool = False
    color: int = 0  # sRGB integer of the text colour (0 = black)
    font: str = ""


@dataclass
class Line:
    """One visual line of text, as laid out on the page."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float  # dominant font size (character weighted)
    bold: bool
    page: int
    spans: list[Span] = field(default_factory=list)
    kind: Kind = Kind.BODY
    column: int = 0  # -1 = spans the page, 0 = left/single, 1 = right, ...

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    def __repr__(self) -> str:  # compact, handy while debugging heuristics
        return f"<Line p{self.page} c{self.column} {self.kind.value} {self.size:.1f} {self.text[:50]!r}>"


@dataclass
class Page:
    number: int
    width: float
    height: float
    lines: list[Line] = field(default_factory=list)
    #: rotated text (margin stamps); never read, but useful for detection
    rotated: list[str] = field(default_factory=list)
    #: (x0, y0, x1, y1) of figure areas: images and clusters of vector drawings
    figures: list[tuple[float, float, float, float]] = field(default_factory=list)


@dataclass
class Document:
    path: str
    pages: list[Page]
    metadata: dict = field(default_factory=dict)

    @property
    def lines(self) -> list[Line]:
        return [ln for p in self.pages for ln in p.lines]

    def first_page_text(self, n_pages: int = 1) -> str:
        return "\n".join(
            [ln.text for p in self.pages[:n_pages] for ln in p.lines]
            + [t for p in self.pages[:n_pages] for t in p.rotated]
        )


@dataclass
class Paragraph:
    text: str
    kind: Kind = Kind.BODY
    page: int = 0
    size: float = 0.0  # font size of its first line (0: unknown)


@dataclass
class Section:
    title: str
    paragraphs: list[Paragraph] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(p.text for p in self.paragraphs)
