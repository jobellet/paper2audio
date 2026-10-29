from . import register
import re

from ..models import Paragraph, Section
from .generic import Generic


@register
class ELife(Generic):
    """eLife.

    Specifics: first-page left side-bar (correspondence, competing interests,
    funding, dates, reviewing editor, copyright), running head
    "Author et al. eLife 2020;9:e12345. DOI: ... 3 of 25", subject banner on
    page 1, and review material (decision letter, author response) at the end.
    """

    name = "elife"
    description = "eLife (side bar, 'N of M' running head, decision letters)."
    doi_prefixes = ("10.7554",)
    signatures = (r"\beLife \d{4};\d+:", r"elifesciences\.org", r"\beLife digest\b")
    junk_lines = Generic.junk_lines + (
        r"\beLife \d{4};\d+:",
        r"^\d+ of \d+$",
        r"^(Research article|Research advance|Short report|Tools and resources)\b",
        r"^(Neuroscience|Computational and Systems Biology|Cell Biology)$",
        r"elifesciences\.org",
        r"^(Reviewed preprint|Version of record|VOR)\b",
    )
    junk_paragraphs = Generic.junk_paragraphs + (
        r"\*?for correspondence:",
        r"competing interests?:",
        r"funding:",
        r"received:",
        r"accepted:",
        r"published:",
        r"reviewing editor:",
        r"(senior|reviewing) editor",
        r"copyright\b",
        r"this article is distributed under the terms",
        r"cite (this article )?as:",
        r"†these authors contributed equally",
    )
    skip_sections = (
        r"additional information",
        r"additional files",
        r"decision letter",
        r"author response",
        r"article and author information",
        r"ethics",
        r"transparent reporting form",
        r"reviewer #\d.*",
        r"recommendations for the authors",
        r"elife assessment",
    )

    def postprocess(self, sections: list[Section]) -> list[Section]:
        # the abstract opens with a bold run-in "Abstract", on the line of its first sentence
        if sections and not sections[0].title and sections[0].paragraphs:
            first = sections[0].paragraphs[0]
            if re.match(r"Abstract\s+\S", first.text):
                rest = re.sub(r"^Abstract\s+", "", first.text)
                sections[0] = Section(title="Abstract", paragraphs=[
                    Paragraph(text=rest, kind=first.kind, page=first.page), *sections[0].paragraphs[1:]])
        return sections
