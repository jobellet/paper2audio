from . import register
from .generic import Generic


@register
class ArXiv(Generic):
    """arXiv preprints (mostly LaTeX two-column conference/journal templates).

    Specifics: rotated "arXiv:XXXX.XXXXXvN [cs.XX] date" stamp in the left
    margin (dropped generically as rotated text), numbered sections
    ("1 Introduction", "II. METHODS"), numeric citations, appendices.
    """

    name = "arxiv"
    description = "arXiv LaTeX preprints (numbered sections, numeric citations)."
    signatures = (r"\barXiv:\d{4}\.\d{4,5}", r"\barxiv\.org\b",
                  r"Published as a conference paper at (?:ICLR|ICML|NeurIPS)")
    junk_lines = Generic.junk_lines + (
        r"^arXiv:\d{4}\.\d{4,5}",
        r"^Preprint\. Under review\.?$",
        r"^(Published|Accepted) as a conference paper at",
        r"^\d+(st|nd|rd|th) Conference on Neural Information Processing Systems",
    )
