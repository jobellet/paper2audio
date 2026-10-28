import pytest

from paper2audio import run
from paper2audio.extract import extract
from paper2audio.models import Document, Line, Page
from paper2audio.profiles.base import JournalProfile
from paper2audio.year import publication_year
from fixtures import build_two_column


def doc_with(text: str, metadata=None) -> Document:
    page = Page(number=0, width=600, height=800,
                lines=[Line(t, 50, 50 + 12 * i, 300, 60 + 12 * i, 10, False, 0) for i, t in enumerate(text.split("\n"))])
    return Document(path="x.pdf", pages=[page], metadata=metadata or {})


@pytest.mark.parametrize("text, year, source", [
    ("Received: 30 March 2022\nAccepted: 28 March 2023\nPublished online: 3 May 2023", 2023, "published"),
    ("J Neurophysiol 121: 646–661, 2019.\nFirst published December 19, 2018; doi:10.1152/jn.00601.2018.", 2018, "published"),
    ("bioRxiv preprint doi: ...; this version posted October 15, 2026. The copyright holder", 2026, "posted"),
    ("360 | Nature | Vol 617 | 11 May 2023", 2023, "citation"),
    ("Journal of Vision (2020) 20(8):1, 1–20", 2020, "citation"),
    ("Lovelace et al. eLife 2021;10:e12345. DOI: ...", 2021, "citation"),
    ("Published online: xx xx xxxx\nAccepted: 15 September 2026", 2026, "accepted"),
    ("Copyright © 2014 the authors 0270-6474/14/341234-10$15.00/0", 2014, "copyright"),
    ("CMC lab preprint | Behrad et al. | December 1, 2025 | 1–31", 2025, "dated"),
])
def test_year_clues(text, year, source):
    assert publication_year(doc_with(text)) == (year, source)


def test_year_from_metadata_and_unknown():
    assert publication_year(doc_with("no date here", {"creationDate": "D:20150102120000"})) == (2015, "pdf metadata")
    assert publication_year(doc_with("no date here")) == (None, "")


class EraProfile(JournalProfile):
    name = "test_era"
    skip_sections = ()
    eras = (
        (None, 2015, {"skip_sections": (r"discussion",)}),  # old layout
        (2016, None, {"read_captions": True}),               # new layout
    )


def test_eras_apply_by_year():
    old, new, unknown = EraProfile(), EraProfile(), EraProfile()
    old.adapt(2010), new.adapt(2020), unknown.adapt(None)
    assert old.skip_sections == (r"discussion",) and not old.read_captions
    assert new.skip_sections == () and new.read_captions
    assert unknown.skip_sections == () and not unknown.read_captions and unknown.year is None


def test_year_given_overrides_detection(tmp_path):
    path = tmp_path / "p.pdf"
    build_two_column(path)
    assert run(str(path), profile=EraProfile(), year=2010).year == 2010
    titles_old = [s.title for s in run(str(path), profile=EraProfile(), year=2010).sections]
    titles_new = [s.title for s in run(str(path), profile=EraProfile(), year=2020).sections]
    assert "Discussion" not in titles_old and "Discussion" in titles_new
