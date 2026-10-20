from . import register
from .base import JournalProfile


@register
class Generic(JournalProfile):
    name = "generic"
    description = "Fallback for any paper: generic column, citation and statistics heuristics."

    junk_lines = (
        r"^downloaded from\b",
        r"^this article is protected by copyright",
        r"^accepted manuscript$",
        r"^(©|copyright ©?)\s*\d{4}",
        r"^all rights reserved\.?$",
        # a DOI or URL on a line of its own: first-page footers, licence notes
        r"^(https?://(dx\.)?doi\.org/|doi:\s*)10\.\S+$",
        r"^\(?https?://\S+\)?[.,;]?$",
    )
    junk_paragraphs = (
        r"([*∗]\s*)?correspond(ing author|ence)( to| should be addressed to)?\b",
        r"[\d*∗†‡]*\s*(these |the |both |all )?authors contributed equally",
        r"(received|accepted|published|revised)( online)?:?\s+\d",
        r"(received|accepted|published)( online)? \w+ \d{1,2},? \d{4}",
        r"key ?words?\s*[:.—–]",
        r"e-?mail( address)?:",
        r"declaration of (generative )?ai\b",
    )
