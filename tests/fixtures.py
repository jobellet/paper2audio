"""Synthetic papers for tests, built with reportlab.

The body text contains ordered markers (``mk001``, ``mk002``, ...) so tests
can check that the reading order is correct whatever the layout.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, Frame, FrameBreak, NextPageTemplate, PageTemplate, Paragraph, Spacer

W, H = A4
BODY = ParagraphStyle("body", fontName="Times-Roman", fontSize=9.5, leading=11.5, firstLineIndent=10)
HEAD = ParagraphStyle("head", fontName="Times-Bold", fontSize=11, leading=14, spaceBefore=6, spaceAfter=2)
TITLE = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=18, leading=22, spaceAfter=8)
SMALL = ParagraphStyle("small", fontName="Times-Roman", fontSize=7, leading=8.5)
AUTH = ParagraphStyle("auth", fontName="Times-Roman", fontSize=10, leading=12, spaceAfter=4)

FILLER = (
    "Saccadic eye movements shift the line of sight several times per second and the visual system "
    "must therefore compensate for the resulting image displacements on the retina. "
)


class Markers:
    def __init__(self) -> None:
        self.n = 0

    def __call__(self) -> str:
        self.n += 1
        return f"mk{self.n:03d}"


def para(m: Markers, sentences: int = 4, extra: str = "") -> str:
    text = " ".join(f"{m()} {FILLER}" for _ in range(sentences))
    return text + extra


def build_two_column(path: Path, *, line_numbers: bool = False, line_number_size: float = 6, header: str = "Journal of Testing (2024) 12:1-9",
                     doi: str = "10.9999/jtest.2024.001", banner: str | None = None,
                 methods_after_references: bool = False) -> int:
    """Two-column article. Returns the number of body markers written."""
    m = Markers()
    margin = 18 * mm
    gap = 8 * mm
    colw = (W - 2 * margin - gap) / 2
    top_h = 95 * mm

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFont("Times-Italic", 8)
        canvas.drawString(margin, H - 12 * mm, header)
        canvas.drawRightString(W - margin, 10 * mm, str(doc.page))
        if banner:
            canvas.setFont("Helvetica", 7)
            canvas.drawString(margin, H - 7 * mm, banner)
        if line_numbers:
            canvas.setFont("Times-Roman", line_number_size)
            y, n = H - 25 * mm, (doc.page - 1) * 60 + 1
            while y > 20 * mm:
                canvas.drawRightString(margin - 3 * mm, y, str(n))
                y -= 11.5
                n += 1
        canvas.restoreState()

    first = PageTemplate(id="first", onPage=decorate, frames=[
        Frame(margin, H - 20 * mm - top_h, W - 2 * margin, top_h, id="top"),
        Frame(margin, 18 * mm, colw, H - 40 * mm - top_h, id="l1"),
        Frame(margin + colw + gap, 18 * mm, colw, H - 40 * mm - top_h, id="r1"),
    ])
    later = PageTemplate(id="later", onPage=decorate, frames=[
        Frame(margin, 18 * mm, colw, H - 38 * mm, id="l"),
        Frame(margin + colw + gap, 18 * mm, colw, H - 38 * mm, id="r"),
    ])
    doc = BaseDocTemplate(str(path), pagesize=A4, pageTemplates=[first, later])

    story = [
        Paragraph("Predictive remapping of visual space across saccades", TITLE),
        Paragraph("Ada Lovelace<super>1</super>, Alan Turing<super>1,2</super> and Grace Hopper<super>2*</super>", AUTH),
        Paragraph("<super>1</super>Department of Vision Science, University of Testing, Germany. "
                  "<super>2</super>Institute of Examples, Sample City, USA", SMALL),
        Paragraph(f"*Correspondence: grace.hopper@example.org. https://doi.org/{doi}", SMALL),
        Paragraph("Abstract", HEAD),
        Paragraph(para(m, 3), BODY),
        Paragraph("Keywords: saccades; remapping; perception", AUTH),
        NextPageTemplate("later"),
        FrameBreak(),
        Paragraph("1. Introduction", HEAD),
        Paragraph(para(m, 5, " This was shown before [3, 5-7] and confirmed (Smith et al., 2019; Jones &amp; Lee, 2020a)."), BODY),
        Paragraph(para(m, 6, " Remapping was reported by Duhamel et al. (1992) in parietal cortex<super>12</super>."), BODY),
        Paragraph("2. Methods", HEAD),
        Paragraph("2.1 Participants", HEAD),
        Paragraph(para(m, 6, " Twelve observers took part (n = 12; 7 female)."), BODY),
        Paragraph("2.2 Analysis", HEAD),
        Paragraph(para(m, 8, " Accuracy was higher after the saccade (t(11) = 3.21, p = .008, d = 0.93)."), BODY),
        Paragraph("Fig. 1. Example trial sequence. A target appeared at 10 deg eccentricity.", SMALL),
        Paragraph("3. Results", HEAD),
        Paragraph(para(m, 7, " The effect was robust, F(1, 11) = 18.2, p &lt; 0.001, and lasted ~50 ms (Figure 2A)."), BODY),
        Paragraph(para(m, 9, " See doi:10.1234/abcd.5678 and www.example.org/data for details."), BODY),
        Paragraph("4. Discussion", HEAD),
        Paragraph(para(m, 8), BODY),
        Paragraph(para(m, 6), BODY),
        Paragraph("Acknowledgments", HEAD),
        Paragraph("We thank the reviewers. ACKNOWLEDGED-SECRET funding by the DFG.", BODY),
        Paragraph("References", HEAD),
    ]
    for i in range(1, 12):
        story.append(Paragraph(f"Author{i}, A. (20{i:02d}). REFERENCE-SECRET title {i}. J. Test. 1, 1-{i}.", SMALL))
    if methods_after_references:
        story += [
            Paragraph("Methods", HEAD),
            Paragraph("Eye tracking", HEAD),
            Paragraph(para(m, 5), BODY),
            Paragraph("Reporting summary", HEAD),
            Paragraph("REPORTING-SECRET further information on research design.", BODY),
            Paragraph("Data availability", HEAD),
            Paragraph("DATA-SECRET the data are available from the authors.", BODY),
        ]
    doc.build(story)
    return m.n


def build_single_column(path: Path) -> int:
    m = Markers()
    doc = BaseDocTemplate(str(path), pagesize=A4, pageTemplates=[
        PageTemplate(id="one", frames=[Frame(25 * mm, 20 * mm, W - 50 * mm, H - 40 * mm)]),
    ])
    story = [Paragraph("A single column report", TITLE), Paragraph("Introduction", HEAD)]
    for _ in range(6):
        story += [Paragraph(para(m, 5), BODY), Spacer(1, 4)]
    doc.build(story)
    return m.n
