import pytest

from paper2audio.cleaning import GENERIC_RULES, apply_rules, normalize_unicode
from paper2audio.speech import to_speech


def clean(text):
    return apply_rules(normalize_unicode(text), GENERIC_RULES)


@pytest.mark.parametrize("raw, expected", [
    # numeric citations
    ("as shown before [3, 5-7].", "as shown before."),
    ("as shown before [12].", "as shown before."),
    # author-year citations
    ("is well known (Smith et al., 2019; Jones & Lee, 2020a).", "is well known."),
    ("is well known (e.g., Smith, 2019).", "is well known."),
    ("is well known (see Rolfs, Jonikaitis, Deubel and Cavanagh, 2011).", "is well known."),
    ("as reported by Duhamel et al. (1992), neurons", "as reported by Duhamel et al., neurons"),
    ("found by van der Berg (2003)", "found by van der Berg"),
    # statistics
    ("was higher (t(11) = 3.21, p = .008, d = 0.93).", "was higher."),
    ("was robust, F(1, 11) = 18.2, p < 0.001, and lasted", "was robust, and lasted"),
    ("differed (p < .05, Bonferroni corrected).", "differed."),
    ("correlated (r = 0.45, 95% CI [0.2, 0.6], p = .01)", "correlated"),
    ("was significant (χ² = 12.3, p < .001)", "was significant"),
    ("the difference was reliable, p = 0.02.", "the difference was reliable."),
    ("the evidence was strong, BF10 = 23.5.", "the evidence was strong."),
    # prose with numbers must survive
    ("Twelve observers took part (n = 12; 7 female).", "Twelve observers took part (n = 12; 7 female)."),
    ("at t = 0 the target appeared", "at t = 0 the target appeared"),
    ("We tested two conditions (congruent and incongruent).", "We tested two conditions (congruent and incongruent)."),
    ("in the year (2019) data", "in the year (2019) data"),
    # identifiers
    ("Data at https://osf.io/abcd/ and doi:10.1234/xyz.5.", "Data at and."),
    ("see https://doi.org/10.1167/jov.20.8.1 for", "see for"),
    ("Contact jane.doe@uni-tuebingen.de now", "Contact now"),
    # what is left of a citation that was only numbers
    ("relatives using rivalry (but see [94]). However", "relatives using rivalry. However"),
    ("external cues (though see [94]), and", "external cues, and"),
    ("frameworks (for example, [57]) but also", "frameworks but also"),
    ("inhibition (for example, [27, 28]). Certain", "inhibition. Certain"),
    ("other factors (see [44] for an exhaustive review). It", "other factors. It"),
    ("a stimulus; see [7] for a review). While", "a stimulus). While"),
    ("conditions (see Glossary), which often", "conditions, which often"),
    ("(for example, monetary gain) stays", "(for example, monetary gain) stays"),
    ("(see Methods for details) stays", "(see Methods for details) stays"),
    # figure references
    ("was larger (Fig. 2A, B) than", "was larger than"),
    ("was larger (see Supplementary Figure S3) than", "was larger than"),
    ("was larger (Table 1) than", "was larger than"),
    ("Figure 2 shows the result", "Figure 2 shows the result"),
    # ligatures
    ("signiﬁcant eﬀect", "significant effect"),
])
def test_rules(raw, expected):
    assert clean(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("e.g., saccades", "for example, saccades"),
    ("i.e. the fovea", "that is, the fovea"),
    ("lasted 50 ms", "lasted 50 milliseconds"),
    ("at 10° eccentricity", "at 10 degrees eccentricity"),
    ("velocity of 300°/s", "velocity of 300 degrees per second"),
    ("mean 3.2 ± 0.4 s", "mean 3.2 plus or minus 0.4 s"),
    ("see Fig. 3", "see Figure 3"),
    ("between 2–5 trials", "between 2 to 5 trials"),
    ("a value of 10^-3", "a value of 10 to the minus 3"),
    ("Smith et al. found", "Smith et al found"),
])
def test_speech(raw, expected):
    assert to_speech(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("its 1st–99th percentile range", "its 1st to 99th percentile range"),
    ("camera (GS3-U3-41C6NIR-C, FLIR)", "camera (GS3-U3-41C6NIR-C, FLIR)"),
    ("equalled −20 dB", "equalled minus 20 dB"),
])
def test_speech_ranges(raw, expected):
    assert to_speech(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    # citations mixed with an abbreviation, names with particles, "et al" without period
    ("in the ventrolateral PFC (vlPFC; Romanski and Diehl, 2011), but", "in the ventrolateral PFC (vlPFC), but"),
    ("perception (Dehaene et al, 2001; Del Cul et al, 2009; Lau and Passingham, 2006), others",
     "perception, others"),
    # stats mixed with descriptive labels and figure pointers
    ("lasts (mean early-to-late consistency: r = 0.01, z = 0.59, p = .28; Fig. 1D, inset). In",
     "lasts. In"),
    ("regime (Kruskal-Wallis test, H(2) = 11.4, p = .003, ε² = 0.12): self",
     "regime: self"),
    ("correction (alpha = 0.05) across", "correction across"),
    ("a random subset (median: 7, min: 1, max: 11) of", "a random subset (median: 7, min: 1, max: 11) of"),
])
def test_real_paper_cases(raw, expected):
    assert clean(raw) == expected


def test_refs_parenthetical():
    assert clean("in S1 (refs. 34–36), we") == "in S1, we"
    assert clean("tops out at 0.6 (ref. 38). Nonetheless") == "tops out at 0.6. Nonetheless"


@pytest.mark.parametrize("raw, expected", [
    ("with R^2 = 88%", "with R squared = 88 percent"),
    ("at 50–100 steps s^−1", "at 50 to 100 steps per second"),
])
def test_speech_exponents(raw, expected):
    assert to_speech(raw) == expected


@pytest.mark.parametrize("raw, spoken", [
    ("INTRODUCTION", "Introduction"),
    ("I. INTRODUCTION", "Introduction"),
    ("II. METHODS", "Methods"),
    ("MATERIALS AND METHODS", "Materials and methods"),
    ("THEORIES OF CONSCIOUSNESS: Global neuronal workspace theory",
     "Theories of consciousness: Global neuronal workspace theory"),
    ("Method 6: DGCCA", "Method 6: DGCCA"),  # an acronym in a mixed title stays
    ("PCA", "PCA"),
    ("2. Methods: 2.1 Participants", "Methods: Participants"),
])
def test_section_titles_spoken(raw, spoken):
    from paper2audio.models import Paragraph, Section
    from paper2audio.pipeline import clean_sections
    from paper2audio.profiles.generic import Generic

    section = Section(title=raw, paragraphs=[Paragraph(text="Some words to read.", kind=None, page=0)])
    assert clean_sections([section], Generic())[0].title == spoken


@pytest.mark.parametrize("raw, expected", [
    # numeric citations with a label, in brackets (Nature-style preprints)
    ("Dynamical Similarity Analysis [DSA, 47] is a framework", "Dynamical Similarity Analysis (DSA) is a framework"),
    ("with traditional criteria [AICc, 70] and", "with traditional criteria (AICc) and"),
    ("the set-up used before [similar to 47] and", "the set-up used before and"),
    ("the original DSA [see, 47, for mathematical details] and", "the original DSA (for mathematical details) and"),
    ("by more principled procedures [e.g., 85]. Using", "by more principled procedures. Using"),
    ("alternatives [for example, Wasserstein-based similarity, 72, 73].", "alternatives (for example, Wasserstein-based similarity)."),
    # brackets with no reference number are mathematics, not citations
    ("the range [10^-6, 10] was searched", "the range [10^-6, 10] was searched"),
    ("started at [x0, y0, z0] = 1", "started at [x0, y0, z0] = 1"),
    # a name split at a line end, and a name with an initial (Elsevier)
    ("selection of the units (Perez- Nieves et al, 2021) and", "selection of the units and"),
    ("studies (X. Shen et al, 2017), to select", "studies, to select"),
    # the equation that opens a sentence, and the one that ends it
    ("τ∗ = ω(β) ⋅ xmed, where xmed is the median", "Where xmed is the median"),
    ("with σ = 10, ρ = 28, and β =. The true state", "with σ = 10, ρ = 28. The true state"),
])
def test_arxiv_style_brackets_and_equations(raw, expected):
    assert clean(raw) == expected
