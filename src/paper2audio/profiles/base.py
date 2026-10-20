"""Base class for journal profiles.

A profile bundles everything that is specific to a publisher / journal:

* how to recognise it (`doi_prefixes`, `signatures`, or a custom `detect`)
* lines that are always junk (running heads, "Downloaded from ..." stamps)
* paragraphs that are junk (first-page side boxes: "Received:", "Editor:", ...)
* which sections to skip, and which may follow the reference list
* text rules to add or disable
* hooks for anything else (`classify_lines`, `order_page`,
  `postprocess`)

To support a new journal, subclass `JournalProfile` (usually only by setting
class attributes), decorate it with `@register`, and drop the module into this
package. It is picked up automatically.
"""

from __future__ import annotations

import re
from functools import cached_property

from .. import layout
from ..cleaning import GENERIC_RULES, Rule
from ..models import Document, Line, Page, Section

GENERIC_SKIP_SECTIONS = (
    r"references?( and notes)?",
    r"bibliography",
    r"literature cited",
    r"works cited",
    r"cited literature",
    r"acknowledge?ments?",
    r"funding( information| sources| statement)?",
    r"grants?( support)?",
    r"uncited references?",  # Elsevier author proofs
    r"financial (support|disclosure)",
    r"author(s'?|'s)? contributions?",
    r"contributions",
    r"credit authorship contribution statement",
    r"(declaration of )?(competing|conflicts?( of)?|financial) interests?( statement)?",
    r"disclosure( statement)?s?",
    r"(data|code|data and code|materials?,? data,? and code|software) availability( statement)?",
    r"availability of data( and materials?)?",
    r"supplementary (information|material|materials|data|figures?)",
    r"supporting information",
    r"abbreviations",
    r"ethics( statement| approval.*)?",
    r"open access",
    r"additional information",
    r"publisher'?s note",
    r"appendix.*",
    r"keywords?",
    r"author information",
    r"correspondence",
    r"disclosures",
    r"endnotes?",
    r"citation diversity statement",
    r"(supplementary |extended data |supplemental )?(figure|table)s?( legends?| captions?)?",
    r"(figure|table) legends?",
    r"extended data( figures?| tables?)?.*",
    r"inclusion (and|&) diversity( statement)?",
)

# Sections that may legitimately come *after* the reference list.
GENERIC_RESUME_SECTIONS = (
    r"(online |materials and |star ?★? ?)?methods?",
    r"materials and methods",
    r"experimental procedures",
)


def _compile(patterns) -> list[re.Pattern]:
    return [re.compile(p, re.I) for p in patterns]


def _heading_key(title: str) -> str:
    # strip numbering such as "2.", "II.", "A." and trailing punctuation
    t = re.sub(r"^\s*((\d+(\.\d+)*|[IVX]+|[A-Z])[.)]?\s+)", "", title.strip())
    return t.strip(" .:—–-").lower()


class JournalProfile:
    #: unique id used on the command line (--profile)
    name: str = "base"
    description: str = ""

    # ---- detection
    doi_prefixes: tuple[str, ...] = ()
    #: regexes searched in the first two pages (and PDF metadata)
    signatures: tuple[str, ...] = ()

    # ---- line level
    header_band: float = 0.09  # top fraction of the page that may hold running heads
    footer_band: float = 0.09
    small_text_ratio: float = 0.82  # lines below body*ratio are footnotes/labels
    junk_lines: tuple[str, ...] = ()  # regex: drop any line that matches

    # ---- paragraph level
    junk_paragraphs: tuple[str, ...] = ()  # regex matched at the start of a paragraph
    read_captions: bool = False
    read_footnotes: bool = False
    read_tables: bool = False

    # ---- section level
    skip_sections: tuple[str, ...] = ()
    resume_sections: tuple[str, ...] = ()
    keep_sections: tuple[str, ...] = ()  # un-skip generic entries (e.g. "appendix.*")
    #: headings after which nothing at all is read (e.g. a reporting-summary form)
    end_sections: tuple[str, ...] = ()
    #: if True, everything after the reference list is skipped except resume_sections
    references_end_main_text: bool = True
    #: headings that mark the end of the front matter (title/authors/affiliations)
    front_matter_end: tuple[str, ...] = (
        r"abstract", r"summary", r"introduction", r"background", r"significance( statement)?",
        r"author summary", r"highlights", r"main",
    )

    # ---- text level
    extra_rules: tuple[Rule, ...] = ()
    disabled_rules: frozenset[str] = frozenset()

    # ---- layout changes over the years
    #: ((first_year, last_year, {attribute: value}), ...): applied in order when the
    #: publication year falls in [first_year, last_year]; None leaves a side open.
    #: E.g. ((None, 2016, {"header_band": 0.12}), (2017, None, {"end_sections": (...)})).
    #: For changes attributes cannot express, override `adapt` and test `self.year`.
    eras: tuple[tuple[int | None, int | None, dict], ...] = ()
    year: int | None = None

    def __init__(self, **options):
        for key, value in options.items():
            setattr(self, key, value)

    # ------------------------------------------------------------------ detection

    @classmethod
    def detect(cls, doc: Document) -> float:
        """Confidence in [0, 1] that this profile fits the document."""
        haystack = doc.first_page_text(2) + "\n" + " ".join(str(v) for v in doc.metadata.values())
        score = 0.0
        for prefix in cls.doi_prefixes:
            if re.search(r"\b" + re.escape(prefix) + r"[/.]", haystack):
                score = max(score, 0.6)
        hits = sum(1 for s in cls.signatures if re.search(s, haystack, re.I))
        if hits:
            score = max(score, min(1.0, 0.5 + 0.2 * hits))
        return score

    # ------------------------------------------------------------------ compiled patterns

    def compiled_junk_lines(self) -> list[re.Pattern]:
        return self._junk_lines

    @cached_property
    def _junk_lines(self) -> list[re.Pattern]:
        return _compile(self.junk_lines)

    @cached_property
    def junk_paragraph_patterns(self) -> list[re.Pattern]:
        return _compile(rf"^\s*(?:{p})" for p in self.junk_paragraphs)

    @cached_property
    def skip_patterns(self) -> list[re.Pattern]:
        return _compile(rf"^(?:{p})$" for p in (*GENERIC_SKIP_SECTIONS, *self.skip_sections))

    @cached_property
    def keep_patterns(self) -> list[re.Pattern]:
        return _compile(rf"^(?:{p})$" for p in self.keep_sections)

    @cached_property
    def resume_patterns(self) -> list[re.Pattern]:
        return _compile(rf"^(?:{p})$" for p in (*GENERIC_RESUME_SECTIONS, *self.resume_sections))

    @cached_property
    def front_matter_patterns(self) -> list[re.Pattern]:
        return _compile(rf"^(?:{p})$" for p in self.front_matter_end)

    def rules(self) -> list[Rule]:
        # profile rules first: they may need text the generic rules remove (a DOI, say)
        return [r for r in (*self.extra_rules, *GENERIC_RULES) if r.name not in self.disabled_rules]

    # ------------------------------------------------------------------ section helpers

    def is_skipped(self, title: str) -> bool:
        key = _heading_key(title)
        if any(p.match(key) for p in self.keep_patterns):
            return False
        return any(p.match(key) for p in self.skip_patterns)

    def is_references(self, title: str) -> bool:
        return bool(re.match(r"^(references?( and notes)?|bibliography|literature cited|works cited|cited literature)$", _heading_key(title)))

    def is_end(self, title: str) -> bool:
        key = _heading_key(title)
        return any(re.match(rf"^(?:{p})$", key, re.I) for p in self.end_sections)

    def is_resume(self, title: str) -> bool:
        key = _heading_key(title)
        return any(p.match(key) for p in self.resume_patterns)

    def ends_front_matter(self, title: str) -> bool:
        key = _heading_key(title)
        return any(p.match(key) for p in self.front_matter_patterns)

    # ------------------------------------------------------------------ hooks

    def adapt(self, year: int | None) -> None:
        """Hook: specialise the profile for the paper's publication year."""
        self.year = year
        if year is None:
            return
        for first, last, overrides in self.eras:
            if (first is None or year >= first) and (last is None or year <= last):
                for key, value in overrides.items():
                    setattr(self, key, value)

    def classify_lines(self, doc: Document, body_size: float) -> None:
        """Hook: re-label lines (Line.kind) after the generic classification."""

    def order_page(self, page: Page, body_size: float) -> list[Line]:
        """Hook: reading order of a page's lines (default: recursive XY-cut).

        Must set `Line.column` to an id of the text flow each line belongs to.
        """
        return layout.reading_order(page, body_size)

    def postprocess(self, sections: list[Section]) -> list[Section]:
        """Hook: last chance to edit sections before speech conversion."""
        return sections

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name!r}>"
