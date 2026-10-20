from . import register
from .generic import Generic


@register
class SpringerNature(Generic):
    """Nature, Nature <X>, Nature Communications, Scientific Reports, Springer.

    Specifics: in Nature-family articles the Methods section comes *after* the
    main reference list and has its own references, followed by many
    administrative sections.
    """

    name = "springer_nature"
    description = "Nature portfolio and Springer journals (Methods after References)."
    doi_prefixes = ("10.1038", "10.1007", "10.1186")
    signatures = (
        r"\bnature\.com\b",
        r"Nature (Communications|Neuroscience|Human Behaviour|Methods)\s*\|",
        r"Scientific Reports\s*\|",
        r"springer(link|nature)?",
        r"\| www\.nature\.com/",
    )
    junk_lines = Generic.junk_lines + (
        r"^(\d+\s*\|\s*)?nature\s*(\w+\s*)?\|\s*(vol|www)",
        r"^Nature (Communications|Neuroscience|Human Behaviour)\s*\|",
        r"^Scientific Reports\s*\|",
        r"^\|\s*https?://doi\.org",
        r"^www\.nature\.com/",
        r"^Article$",
        r"^Check for updates$",
        r"^OPEN$",
    )
    end_sections = (r"reporting summary",)
    skip_sections = (
        r"online content",
        r"reporting summary",
        r"peer review( information)?",
        r"extended data.*",
        r"rights and permissions",
        r"about this article",
        r"inclusion (and|&) ethics",
        r"ethics declarations",
        r"source data",
    )
    junk_paragraphs = Generic.junk_paragraphs + (
        r"received:?\s*\d{1,2} \w+ \d{4}",
        r"published online:?",
        r"(reprints and permissions|correspondence and requests for materials)",
        r"springer nature (or its licensor|remains neutral)",
        r"open access this article is licensed",
    )
