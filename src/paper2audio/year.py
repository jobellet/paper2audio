"""Guess the publication year of a paper, so profiles can follow layout changes
of the same journal over time.

Clues are tried from the most to the least reliable; the first hit wins.
"""

from __future__ import annotations

import datetime
import re

from .models import Document

_MONTHS = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
_YEAR = r"((?:19|20)\d{2})"

# (name, pattern); group 1 is the year
CLUES: list[tuple[str, re.Pattern]] = [
    # "Published online: 3 May 2023", "Published: January 6, 2016", "First published December 19, 2018"
    ("published", re.compile(rf"\b(?:first )?published(?: online)?:?\s+(?:\d{{1,2}}\s+)?{_MONTHS}\s+(?:\d{{1,2}},?\s+)?{_YEAR}", re.I)),
    # bioRxiv / medRxiv: "this version posted October 15, 2026"
    ("posted", re.compile(rf"\bposted\s+{_MONTHS}\s+\d{{1,2}},?\s+{_YEAR}", re.I)),
    # journal citation lines: "J Neurophysiol 121: 646–661, 2019", "Nature | Vol 617 | 11 May 2023",
    # "Journal of Vision (2020) 20(8):1", "eLife 2020;9:e12345", "Vision Research 210 (2024) 108000"
    ("citation", re.compile(rf"\b\d+\s?:\s?\d+\s?[–-]\s?\d+,\s+{_YEAR}\b"
                            rf"|\|\s?Vol\.? \d+\s?\|\s?\d{{1,2}} {_MONTHS} {_YEAR}"
                            rf"|\(\s?{_YEAR}\s?\)\s?\d+\s?\(\d+\)"
                            rf"|\b[A-Za-z]{{2,}} {_YEAR};\d+:"
                            rf"|\b\d+ \({_YEAR}\) \d+")),
    ("accepted", re.compile(rf"\baccepted(?: in final form)?:?\s+(?:\d{{1,2}}\s+)?{_MONTHS}\s+(?:\d{{1,2}},?\s+)?{_YEAR}", re.I)),
    ("copyright", re.compile(rf"(?:©|\(c\)|copyright)\s*(?:©\s*)?{_YEAR}", re.I)),
    # preprint running head: "CMC lab preprint | Behrad et al. | December 1, 2025"
    ("dated", re.compile(rf"\|\s*{_MONTHS}\s+\d{{1,2}},\s+{_YEAR}\b")),
]


def _first_group(m: re.Match) -> int:
    return int(next(g for g in m.groups() if g))


def publication_year(doc: Document) -> tuple[int | None, str]:
    """Return (year, which clue gave it); (None, "") when nothing is found."""
    now = datetime.date.today().year
    text = doc.first_page_text(2)
    for name, pattern in CLUES:
        for m in pattern.finditer(text):
            year = _first_group(m)
            if 1900 <= year <= now + 1:
                return year, name
    created = str(doc.metadata.get("creationDate") or "")
    m = re.match(r"D:((?:19|20)\d{2})", created)
    if m and int(m.group(1)) <= now + 1:
        return int(m.group(1)), "pdf metadata"
    return None, ""
