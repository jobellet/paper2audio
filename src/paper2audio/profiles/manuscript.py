import re

from . import register
from .generic import Generic


@register
class Manuscript(Generic):
    """Author manuscripts prepared for submission (any target journal).

    Recognised by layout, not by journal: one wide column, a large body font,
    and manuscript line numbers in the margin. Figures and legends usually
    follow the references. The published version of the same paper looks
    completely different and is handled by that journal's profile, so nothing
    here is tied to a journal name (a manuscript for JoCN is not a JoCN article).
    """

    name = "manuscript"
    description = "Submitted manuscripts for any journal (line numbers, single column, figures at the end)."

    @classmethod
    def detect(cls, doc) -> float:
        pages = doc.pages[:6]
        if not pages:
            return 0.0
        numbered = wide = text_lines = 0
        for page in pages:
            margin = [ln for ln in page.lines if re.fullmatch(r"\d{1,4}", ln.text)
                      and (ln.x1 < page.width * 0.15 or ln.x0 > page.width * 0.85)]
            numbered += len(margin) >= 10
            text = [ln for ln in page.lines if ln not in margin]
            text_lines += len(text)
            wide += sum(1 for ln in text if ln.width > page.width * 0.6)
        single_column = wide > 0.5 * text_lines
        if numbered >= len(pages) / 2 and single_column:
            return 0.45  # any journal or preprint profile with a DOI/signature match wins
        return 0.0
