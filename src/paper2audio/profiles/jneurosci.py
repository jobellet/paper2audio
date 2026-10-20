from . import register
from .generic import Generic


@register
class JNeurosci(Generic):
    """Journal of Neuroscience (Society for Neuroscience).

    Specifics: running head "Author • Title  J. Neurosci., Month D, YYYY •
    41(5):1234–1245 • 1235", "Downloaded from" stamp, a small-font first-page
    footnote with dates, author contributions and correspondence, and a
    Significance Statement next to the Abstract.
    """

    name = "jneurosci"
    description = "Journal of Neuroscience (SfN running heads, first-page footnote)."
    doi_prefixes = ("10.1523",)
    signatures = (r"J\. ?Neurosci\.", r"jneurosci\.org", r"Society for Neuroscience")
    junk_lines = Generic.junk_lines + (
        r"J\. ?Neurosci\.,?\s+\w+ \d{1,2},? \d{4}",
        r"\d+\(\d+\):\d+\s*[–-]\s*\d+",
        r"jneurosci\.org",
        r"^(Research Articles?|Behavioral/Cognitive|Systems/Circuits|Cellular/Molecular|Development/Plasticity/Repair|Neurobiology of Disease)$",
        r"^Copyright © \d{4}",
    )
    junk_paragraphs = Generic.junk_paragraphs + (
        r"received \w+ \d{1,2}, \d{4}",
        r"author contributions:",
        r"this work was supported by",
        r"the authors declare no competing",
        r"correspondence should be addressed",
        r"https?://doi\.org/10\.1523",
    )
    front_matter_end = Generic.front_matter_end + (r"significance statement",)
