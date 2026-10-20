from . import register
from ..cleaning import rule
from .generic import Generic


@register
class APS(Generic):
    """American Physiological Society: J Neurophysiol, J Appl Physiol, Am J Physiol, Physiol Rep.

    Specifics: section headings in small bold capitals (smaller than the body
    text), Methods and figure legends set in a smaller font than the main
    text, an abstract that opens with the full citation of the article
    ("Bellet ME, ... J Neurophysiol 121: 646-661, 2019. ... doi:10.1152/....—"),
    a NEW & NOTEWORTHY box, a keyword line, and GRANTS / DISCLOSURES / AUTHOR
    CONTRIBUTIONS / ENDNOTE sections.
    """

    name = "aps"
    description = "American Physiological Society journals (J Neurophysiol, J Appl Physiol, ...)."
    doi_prefixes = ("10.1152",)
    signatures = (r"\bJ Neurophysiol \d+:", r"\bJ Appl Physiol \d+:", r"Am J Physiol", r"physiology\.org",
                  r"American Physiological Society")
    junk_lines = Generic.junk_lines + (
        r"^J (Neurophysiol|Appl Physiol)\b.*\b(doi|www|\d{4})",
        r"^First published \w+ \d{1,2}, \d{4}",
        r"^Downloaded from (www\.)?(journals\.)?physiology\.org",
        r"^\d{4}-\d{4}/\d{2} Copyright ©",
        r"^(INNOVATIVE METHODOLOGY|RESEARCH ARTICLE|RAPID REPORT|REVIEW|CALL FOR PAPERS)\b",
        r"^www\.(jn|jap|ajp\w*)\.org$",
    )
    junk_paragraphs = Generic.junk_paragraphs + (
        r"NEW (&|and) NOTEWORTHY",
        r"submitted \d{1,2} \w+ \d{4}",
        r"address for reprint requests",
        r"\*\s?[A-Z]\.[A-Z.]+ and [A-Z.]+ contributed equally",
    )
    skip_sections = (r"grants", r"disclosures", r"endnotes?", r"supplemental material")
    extra_rules = (
        # "Bellet ME, ..., Berens P. Title. J Neurophysiol 121: 646-661, 2019. First published ...; doi:10.1152/jn.00601.2018.—Saccades are ..."
        rule("aps_abstract_citation", r"^[^—]{0,600}?doi:\s?10\.1152/[\w.]+?\.?\s?—\s?"),
    )
