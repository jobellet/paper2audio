from . import register
from .generic import Generic


@register
class PLOS(Generic):
    """PLOS ONE, PLOS Biology, PLOS Computational Biology, ...

    Specifics: single wide text column, with a narrow left side-bar on the first
    page (citation, editor, dates, copyright, funding, competing interests).
    Running head "PLOS X | https://doi.org/... Month D, YYYY  3 / 25".
    """

    name = "plos"
    description = "PLOS journals (first-page side bar, single column)."
    doi_prefixes = ("10.1371",)
    signatures = (r"\bPLOS (ONE|Biology|Computational Biology|Genetics|Medicine|Pathogens)\b",
                  r"journals\.plos\.org")
    junk_lines = Generic.junk_lines + (
        r"^PLOS (ONE|Biology|Computational Biology|Genetics|Medicine|Pathogens|Neglected)\b.*\d+ / \d+$",
        r"^PLOS (ONE|Biology|Computational Biology|Genetics|Medicine|Pathogens)\s*\|",
        r"^\d+ / \d+$",
        r"^(OPEN ACCESS|RESEARCH ARTICLE|PEER-REVIEWED)$",
        r"^a\d+$|^a\s*\d+(\s+a\s*\d+)+$",  # affiliation letters
    )
    junk_paragraphs = Generic.junk_paragraphs + (
        r"citation:",
        r"editor:",
        r"received:",
        r"accepted:",
        r"published:",
        r"copyright:",
        r"data availability( statement)?:",
        r"funding:",
        r"competing interests:",
        r"\* ?[\w.+-]+@",
        r"these authors contributed equally",
        r"current address:",
    )
