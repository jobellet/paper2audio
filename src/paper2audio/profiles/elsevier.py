from . import register
from .generic import Generic
from ..cleaning import rule


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
