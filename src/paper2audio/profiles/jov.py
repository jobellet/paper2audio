from . import register
from .generic import Generic


@register
class JournalOfVision(Generic):
    """Journal of Vision and other ARVO journals (IOVS, TVST).

    Specifics: "Downloaded from jov.arvojournals.org on ..." stamp, running
    foot "Journal of Vision (2020) 20(8):1, 1–20", a "Citation:" box and
    Creative Commons notice on page 1, and "Keywords:" under the abstract.
    """

    name = "jov"
    description = "Journal of Vision / ARVO journals (download stamp, citation box)."
    doi_prefixes = ("10.1167",)
    signatures = (r"Journal of Vision \(\d{4}\)", r"arvojournals\.org", r"\bARVO\b")
    junk_lines = Generic.junk_lines + (
        r"arvojournals\.org",
        r"^Journal of Vision \(\d{4}\) \d+\(\d+\)",
        r"^(Investigative Ophthalmology|Translational Vision Science)",
        r"^Downloaded from",
        r"This work is licensed under a Creative Commons",
        r"^ISSN \d{4}-\d{3}[\dX]",
    )
    junk_paragraphs = Generic.junk_paragraphs + (
        r"citation:",
        r"this work is licensed under",
        r"received \w+ \d{1,2}, \d{4}",
        r"published \w+ \d{1,2}, \d{4}",
    )
