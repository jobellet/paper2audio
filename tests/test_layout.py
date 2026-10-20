import pytest
import re

import pymupdf

from paper2audio import run
from fixtures import build_single_column, build_two_column


def markers(text):
    return [int(m) for m in re.findall(r"mk(\d{3})", text)]


def test_two_column_reading_order(two_column):
    path, n = two_column
    text = run(str(path)).to_text()
    assert markers(text) == list(range(1, n + 1))


def test_junk_removed(two_column):
    path, _ = two_column
    text = run(str(path)).to_text()
    for junk in ("REFERENCE-SECRET", "ACKNOWLEDGED-SECRET", "Journal of Testing", "grace.hopper",
                 "University of Testing", "Keywords", "Example trial sequence", "doi", "www."):
        assert junk not in text, junk
    leftovers = re.findall(r"(?<![\w.])\d{1,3}(?![\w.])(?! (?:milliseconds|percent|degrees))", text)
    assert leftovers == ["12", "7"], leftovers


def test_title_and_sections(two_column):
    path, _ = two_column
    script = run(str(path))
    assert script.title == "Predictive remapping of visual space across saccades"
    assert [s.title for s in script.sections] == [
        "Abstract", "Introduction", "Methods: Participants", "Analysis", "Results", "Discussion"]
    assert script.skipped == ["Acknowledgments", "References"]


def test_body_size_line_numbers(tmp_path):
    """Line numbers set in the body font size must still be removed."""
    path = tmp_path / "ln.pdf"
    n = build_two_column(path, line_numbers=True, line_number_size=9.5)
    text = run(str(path)).to_text()
    assert markers(text) == list(range(1, n + 1))
    leftovers = re.findall(r"(?<![\w.])\d{1,3}(?![\w.])(?! (?:milliseconds|percent|degrees))", text)
    assert leftovers == ["12", "7"], leftovers  # only "(n = 12; 7 female)" remains


def test_single_column(tmp_path):
    path = tmp_path / "one.pdf"
    n = build_single_column(path)
    assert markers(run(str(path)).to_text()) == list(range(1, n + 1))


def test_glued_line_numbers(tmp_path):
    """Numbers that PyMuPDF puts in the same line as the text are stripped."""
    doc = pymupdf.open()
    page = doc.new_page()
    y = 80
    for i in range(1, 30):
        page.insert_text((40, y), str(i), fontsize=10)
        page.insert_text((62, y), f"mk{i:03d} this is a line of body text that goes on for a while", fontsize=10)
        y += 14
    path = tmp_path / "glued.pdf"
    doc.save(path)
    text = run(str(path)).to_text()
    assert markers(text) == list(range(1, 30))
    assert not re.search(r"(?<!mk)\b\d+\b", text)


def test_sentence_continues_across_columns(two_column):
    path, _ = two_column
    script = run(str(path))
    for s in script.sections:
        for p in s.paragraphs:
            # each synthetic paragraph starts with a marker; a paragraph split at
            # a column break would start mid-sentence
            assert p.text.startswith("mk"), p.text[:80]


def test_soft_hyphen_join():
    from paper2audio.layout import _join
    assert _join("DMN–LN hypocon­", "nectivity and") == "DMN–LN hyponnectivity and".replace("hyponn", "hypoconn")
    assert _join("twenty language-", "aligned models", {"language-aligned"}) == "twenty language-aligned models"
    assert _join("percep-", "tion is") == "perception is"


def test_axis_labels_next_to_figure_dropped():
    """Small isolated labels just outside a drawing cluster are figure text;
    small-font prose beside the figure, and its short last line, are kept."""
    from paper2audio.layout import mark_figure_text
    from paper2audio.models import Document, Kind, Line, Page

    def line(text, x0, y0, x1, size=9.0):
        return Line(text, x0, y0, x1, y0 + size, size, False, 0)

    axis = line("Amount of training samples (s)", 97, 292, 219)            # 11 pt below the panel
    title = line("Training subject", 362, 235, 426)                       # 16 pt above the panel
    prose = [line("A small-font text box that sits right next to the figure,", 300, 120, 560),
             line("so its words must still be read", 300, 131, 450)]       # short last line of a paragraph
    body = line("Thus, through training, the net-", 307, 730, 560, size=10.0)
    page = Page(0, 600, 800, lines=[axis, title, *prose, body],
                figures=[(79, 226, 231, 281), (267, 260, 537, 485), (230, 100, 290, 140)])
    mark_figure_text(Document("x.pdf", [page]), body=10.0)
    assert axis.kind == title.kind == Kind.OTHER
    assert [ln.kind for ln in (*prose, body)] == [Kind.BODY] * 3


@pytest.mark.parametrize("font, bold", [
    ("AdvPSHN-H", True), ("AdvPSHN-M", False),              # Cell Press: Helvetica Neue Heavy / Medium
    ("AdvCaceiliaHVY", True), ("AdvCaeciliaBdIt", True),    # Cortex
    ("AdvCaeciliaRm", False), ("AdvCaeciliaLtSc", False),
    ("AdvOT1efcda3b.B", True), ("AdvOT7fb33346.I", False),  # obfuscated names: only the suffix counts
    ("AdvOTa1b2c3bd", False), ("AdvPSA5BD", False), ("AdvPSA183", False), ("AdvPSMPi6", False),  # eLife
    ("Helvetica-Bold", True), ("MinionPro-Bd", True), ("Times-Roman", False), ("Arial-ItalicMT", False),
])
def test_bold_from_font_name(font, bold):
    from paper2audio.extract import _is_bold
    assert _is_bold({"font": font, "flags": 0}) is bold


def test_italic_numbered_subheading_wraps():
    """'3.5. Reduced gamma ... strong' + 'correlations with ...' in italics is one heading;
    an italic sentence and a numbered list item in roman type are not headings."""
    from paper2audio.layout import mark_headings
    from paper2audio.models import Document, Kind, Line, Page, Span

    def line(text, y, italic=True, x0=38):
        return Line(text, x0, y, 284, y + 8, 8.0, False, 0, spans=[Span(text, x0, 284, 8.0, italic=italic)])

    head = line("3.5. Reduced gamma response in early visual cortex does not show strong", 572)
    cont = line("correlations with alpha/beta power or phase in any of the tested ROIs", 583)
    prose = line("To test our hypothesis that feedback from high-level visually re-", 604, italic=False, x0=50)
    item = line("2.1. Participants were recruited from the university pool and paid", 620, italic=False)
    page = Page(0, 595, 794, lines=[head, cont, prose, item])
    mark_headings(Document("x.pdf", [page]), body=8.0)
    assert [ln.kind for ln in page.lines] == [Kind.HEADING, Kind.HEADING, Kind.BODY, Kind.BODY]


def test_line_box_at_least_font_size():
    """PyMuPDF 2.0 reports 6 pt glyph boxes for some 8.5 pt fonts; line boxes
    are extended to the font size so that gap tests agree across versions."""
    from paper2audio.extract import _make_line
    from paper2audio.models import Span

    tight = _make_line([Span("FBA Modulates", 311, 400, 8.5, bold=True)], 222.3, 228.3, 0)
    roomy = _make_line([Span("FBA Modulates", 311, 400, 8.5, bold=True)], 219.0, 228.3, 0)
    assert (tight.y0, tight.y1) == (228.3 - 8.5, 228.3)
    assert roomy.y0 == 219.0


def test_split_line_regrouped_by_baseline():
    """One printed line that PyMuPDF splits at citation superscripts is one line again;
    math fragments on the same baseline stay apart."""
    from paper2audio.extract import _visual_lines
    from paper2audio.models import Page

    def piece(text, x0, x1, y0, sup=None):
        spans = [{"text": text, "bbox": (x0, y0, x1, 285), "origin": (x0, 283), "size": 8.5, "flags": 0, "font": "AdvPSA183"}]
        if sup:
            spans.append({"text": sup, "bbox": (x1, 275, x1 + 6, 280), "origin": (x1, 279), "size": 5.0, "flags": 1, "font": "AdvPSA183"})
        return {"dir": (1, 0), "bbox": (x0, y0, x1 + (6 if sup else 0), 285), "spans": spans}

    block = {"lines": [piece("motion", 60, 86, 277), piece("(Figure", 93, 118, 277), piece("2B),", 126, 142, 275, "95"),
                       piece("movement", 155, 195, 277), piece("trajectories,", 202, 246, 275, "96"),
                       piece("or", 260, 267, 277), piece("causal", 275, 299, 277), piece("ψ =", 320, 335, 277)]}
    rows = _visual_lines(block, Page(0, 600, 800))
    texts = [" ".join(sp.text for sp in spans if not sp.superscript) for spans, _, _ in rows]
    assert texts == ["motion (Figure 2B), movement trajectories, or causal", "ψ ="]


def _chars(text, x0=42.0, size=10.0, letter_gap=-0.2, word_gap=1.4, width=4.5):
    out, x = [], x0
    for i, ch in enumerate(text):
        if ch == "_":  # a word boundary without a space character
            x += word_gap - letter_gap
            continue
        out.append({"c": ch, "bbox": (x, 0, x + width, size)})
        x += width + letter_gap
    return {"chars": out, "size": size, "font": "MinionMM-SemiBoldCondens"}


def test_missing_spaces_restored():
    """J Neurosci PDFs position words without space characters; normal text and
    odd glyph boxes inside words are left alone."""
    from paper2audio.extract import _respace

    assert _respace(_chars("one_item_was_given_as_a_cue,_and")) == "one item was given as a cue, and"
    # justified line with narrower word gaps (0.117 em above the letter gap)
    assert _respace(_chars("of_decoding_noisy_neural", word_gap=0.97)) == "of decoding noisy neural"
    # a single word whose glyph boxes leave a 0.08 em gap: "ep ilepsy" must not happen
    assert _respace(_chars("ep_ilepsy", size=8.5, letter_gap=0.0, word_gap=0.6)) == "epilepsy"
    from paper2audio.extract import _spans_text
    from paper2audio.models import Span
    assert _spans_text([Span("boosts perceptual processing.In that respect", 0, 200, 8.5)]) == \
        "boosts perceptual processing. In that respect"
    # no split before an apostrophe or after an accent
    assert _respace(_chars("observer_’s_choice_was_made", word_gap=1.4)) == "observer’s choice was made"


def test_bold_abstract_is_not_headings():
    """A bold abstract (J Neurosci) has short, unpunctuated lines that look like bold
    headings; three or more stacked bold lines are a paragraph. Key words are not read."""
    from paper2audio.layout import mark_headings
    from paper2audio.models import Document, Kind, Line, Page, Span

    def line(text, y, size=10.0, bold=True, x0=42, x1=544):
        return Line(text, x0, y, x1, y + size, size, bold, 0, spans=[Span(text, x0, x1, size, bold=bold)])

    abstract = [line("The responses of neurons within posterior visual cortex are enhanced when", 249),
                line("neurons at retinotopically corresponding sites within the macaque monkey", 261),
                line("tion, presaccadic enhancement of V4 activity was increased and FEF", 273)]
    keywords = [line("Key words: extrastriate cortex; eye movements; motor command; prefrontal", 291),
                line("cortex; top-down control; visual attention", 303)]
    intro = line("Introduction", 330, size=12.0, x1=103)
    body = line("We shift our gaze to an object of interest many times each day.", 345, size=9.5, bold=False)
    title = line("A Distinct Contribution of the Frontal Eye Field", 115, size=22.0, x1=539)
    page = Page(0, 612, 792, lines=[title, *abstract, *keywords, intro, body])
    mark_headings(Document("x.pdf", [page]), body=9.5)
    assert [ln.kind for ln in abstract] == [Kind.BODY] * 3, [ln.kind for ln in abstract]
    assert [ln.kind for ln in keywords] == [Kind.OTHER, Kind.OTHER]
    assert intro.kind == Kind.HEADING
