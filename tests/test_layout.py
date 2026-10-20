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
