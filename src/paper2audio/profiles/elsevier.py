import re

from . import register
from .generic import Generic
from ..cleaning import rule
from ..models import Kind


@register
class Elsevier(Generic):
    """Elsevier journals (Vision Research, NeuroImage, Neuron, Current Biology, ...).

    Specifics: first-page masthead ("Contents lists available at ScienceDirect"),
    an ARTICLE INFO box (history, keywords) next to the abstract, CRediT and
    declaration sections at the end, Cell Press "STAR★Methods" after references.
    """

    name = "elsevier"
    description = "Elsevier and Cell Press journals (ScienceDirect layout, STAR Methods)."
    doi_prefixes = ("10.1016",)
    signatures = (
        r"Contents lists available at ScienceDirect",
        r"journal homepage:\s*www\.(elsevier|journals\.elsevier)\.com",
        r"\bElsevier (Ltd|Inc|B\.V\.)",
        r"\bCell Press\b",
    )
    junk_lines = Generic.junk_lines + (
        r"Contents lists available at",
        r"^ScienceDirect$",
        r"journal homepage:",
        r"^a r t i c l e\s+i n f o$|^article info$",
        r"^a b s t r a c t$",
        r"^Article history:?$",
        r"^(Received|Accepted|Available online|Received in revised form)\b.*\d{4}$",
        r"\bElsevier (Ltd|Inc|B\.V\.)\b",
        r"^\d{4}-\d{3}[\dX]/©",
        r"^Please cite this article",
        r"^(Current Biology|Neuron|Cell Reports|iScience|Cell)\s+\d+,",
        r"ª \d{4}",  # Cell Press copyright glyph
    )
    junk_paragraphs = Generic.junk_paragraphs + (
        r"article history:",
        r"\*\s*corresponding author",
        r"available online",
        r"lead contact",
        r"in brief\b",
    )
    skip_sections = (
        r"highlights",
        r"graphical abstract",
        r"key resources table",
        r"resource availability",
        r"lead contact",
        r"materials availability",
        r"declaration of (competing interest|interests|generative ai.*)",
        r"appendix [a-z]\.? supplementary (data|material)",
        r"in brief",
        r"etoc",
    )
    front_matter_end = Generic.front_matter_end + (r"a b s t r a c t", r"summary")
    extra_rules = (
        rule("star_methods", r"STAR\s?★\s?Methods", "STAR Methods"),
    )

    def classify_lines(self, doc, body_size: float) -> None:
        """The journal name in the first-page masthead is set as large as the title."""
        if not doc.pages:
            return
        page = doc.pages[0]
        homepage = [ln.y1 for ln in page.lines if re.search(r"journal homepage", ln.text, re.I)]
        if homepage:
            for ln in page.lines:
                if ln.kind == Kind.TITLE and ln.y1 <= max(homepage) + 2:
                    ln.kind = Kind.HEADER_FOOTER


@register
class CellPress(Elsevier):
    """Cell Press journals (Neuron, Cell, Current Biology, Cell Reports, Trends, ...).

    Specifics: the running head (journal name, or the "ll" logo with "OPEN ACCESS")
    and the article type ("Article", "Perspective", "Review") reach lower than the
    Elsevier default header band; prose starts below 12% of the page height.
    Older layouts open with a summary page (Authors, Correspondence, In Brief) and
    repeat journal, article type and title above the SUMMARY. Since about 2020,
    section headings are capitals in the body font ("WHY REALITY MATTERS: ...").
    """

    name = "cell_press"
    description = "Cell Press journals (Neuron, Cell, Current Biology, Cell Reports, Trends)."
    doi_prefixes = tuple(f"10.1016/j.{j}" for j in (
        "cell", "neuron", "cub", "celrep", "isci", "cels", "chom", "devcel", "immuni", "molcel", "cmet",
        "stem", "str", "chembiol", "ajhg", "xcrm", "crmeth", "patter", "tins", "tics", "tibs", "tig", "tcb",
        "tree", "molmed"))
    header_band = 0.11
    junk_lines = Elsevier.junk_lines + (
        r"^(Neuron|Cell|Current Biology|Cell Reports|iScience|Cell Systems|Trends in [A-Z][a-z]+( [A-Z][a-z]+)*)$",
        r"^(Article|Report|Review|Perspective|Resource|Short Article|NeuroView|Primer|Essay|Theory|Matters Arising)$",
        r"^OPEN ACCESS$",
    )
    skip_sections = Elsevier.skip_sections + (r"authors",)
    junk_paragraphs = Elsevier.junk_paragraphs + (
        r"detailed methods are provided in the online version",  # contents of the online-only STAR Methods
        r"• (key resources table|resource availability|contact for reagent|experimental model|method details"
        r"|quantification and statistical analysis|data and (code|software) availability)",
        r"supplemental information (can be found|includes)",
    )

    @classmethod
    def detect(cls, doc) -> float:
        haystack = doc.first_page_text(2)
        if not any(re.search(r"\b" + re.escape(p) + r"[/.]", haystack, re.I) for p in cls.doi_prefixes):
            return 0.0
        return Elsevier.detect(doc) + 0.05  # beats the publisher-wide profile

    def classify_lines(self, doc, body_size: float) -> None:
        """Headings in capitals and the body font, which may wrap onto a second line."""
        super().classify_lines(doc, body_size)
        for page in doc.pages:
            for ln in sorted(page.lines, key=lambda l: l.y0):
                if not (ln.kind == Kind.BODY and ln.text.isupper() and abs(ln.size - body_size) < 0.4
                        and len(ln.text.split()) <= 14 and not ln.text.startswith("•")):  # list items
                    continue
                above = [o for o in page.lines if o is not ln and o.y1 <= ln.y0 + 1 and o.x0 < ln.x1 and o.x1 > ln.x0]
                prev = max(above, key=lambda o: o.y1, default=None)
                gap = ln.y0 - prev.y1 if prev else 1e9
                if prev is not None and prev.kind == Kind.HEADING and prev.text.isupper() and gap < ln.height:
                    ln.kind = Kind.HEADING  # second line of a wrapped heading
                elif len(re.findall(r"[^\W\d_]{3,}", ln.text)) >= 2 and gap > 0.8 * ln.height:
                    ln.kind = Kind.HEADING

    def postprocess(self, sections):
        for s in sections:
            if re.search(r"(^|: )summary$", s.title, re.I):
                s.title = "Summary"  # "Neuron: Article: <title>: SUMMARY"
        return sections
