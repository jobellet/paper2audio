from . import register
from .generic import Generic


@register
class BioRxiv(Generic):
    """bioRxiv / medRxiv preprints.

    Specifics: a 2-3 line copyright banner on every page, frequent manuscript
    line numbers, double spacing, and figures + legends collected at the end.
    """

    name = "biorxiv"
    description = "bioRxiv / medRxiv preprints (banner on every page, line numbers)."
    doi_prefixes = ("10.1101",)
    signatures = (r"bioRxiv preprint", r"medRxiv preprint", r"certified by peer review")

    header_band = 0.12  # the banner is taller than a normal running head
    junk_lines = Generic.junk_lines + (
        r"(bio|med)Rxiv preprint",
        r"this version posted",
        r"the copyright holder for this preprint",
        r"certified by peer review\)? is the author/funder",
        r"(granted|has granted) (bio|med)Rxiv a license",
        r"made available under a\s*CC[- ]BY",
        r"^CC[- ]BY(-NC)?(-ND)?\s*[\d.]*\s*International license",
        r"^It is made available under",
        r"^All rights reserved\. No reuse allowed without permission",
    )
