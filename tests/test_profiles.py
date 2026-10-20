import pymupdf
import pytest

from paper2audio import profiles, run
from paper2audio.extract import extract
from paper2audio.profiles.base import JournalProfile
from fixtures import build_two_column


def test_all_profiles_registered():
    names = set(profiles.available())
    assert {"generic", "biorxiv", "elsevier", "springer_nature", "plos", "elife",
            "jneurosci", "jov", "arxiv"} <= names


@pytest.mark.parametrize("doi, header, banner, expected", [
    ("10.1101/2024.01.01.123456", "Preprint", "bioRxiv preprint doi: https://doi.org/10.1101/2024.01.01.123456; this version posted January 2, 2024. The copyright holder for this preprint", "biorxiv"),
    ("10.1016/j.visres.2024.108000", "Vision Research 210 (2024) 108000", "Contents lists available at ScienceDirect", "elsevier"),
    ("10.1038/s41467-024-00001-1", "Nature Communications | (2024) 15:1", None, "springer_nature"),
    ("10.1371/journal.pcbi.1004668", "PLOS Computational Biology | https://doi.org/10.1371/journal.pcbi.1004668 January 6, 2016", None, "plos"),
    ("10.7554/eLife.12345", "Lovelace et al. eLife 2024;13:e12345. DOI: https://doi.org/10.7554/eLife.12345", None, "elife"),
    ("10.1523/JNEUROSCI.1234-23.2024", "Lovelace et al. • Remapping J. Neurosci., May 1, 2024 • 44(18):e1234232024", None, "jneurosci"),
    ("10.1167/jov.24.1.1", "Journal of Vision (2024) 24(1):1, 1-9", "Downloaded from jov.arvojournals.org on 10/20/2026", "jov"),
    ("10.9999/x", "Journal of Testing (2024) 12:1-9", None, "generic"),
])
def test_detection(tmp_path, doi, header, banner, expected):
    path = tmp_path / "p.pdf"
    build_two_column(path, header=header, doi=doi, banner=banner)
    prof, score, _ = profiles.detect(extract(str(path)))
    assert prof.name == expected


def test_biorxiv_banner_removed(tmp_path):
    path = tmp_path / "b.pdf"
    banner = ("bioRxiv preprint doi: https://doi.org/10.1101/2024.01.01.123456; this version posted "
              "January 2, 2024. The copyright holder for this preprint")
    build_two_column(path, header="(which was not certified by peer review) is the author/funder.",
                     doi="10.1101/2024.01.01.123456", banner=banner, line_numbers=True, line_number_size=9.5)
    script = run(str(path))
    assert script.profile == "biorxiv"
    text = script.to_text()
    assert "bioRxiv" not in text and "copyright holder" not in text and "peer review" not in text


def test_custom_profile_hooks(tmp_path):
    """A profile can be passed directly, with its own skip list and hooks."""

    class NoDiscussion(JournalProfile):
        name = "test_no_discussion"
        skip_sections = (r"discussion",)

        def postprocess(self, sections):
            for s in sections:
                s.title = s.title.upper()
            return sections

    path = tmp_path / "c.pdf"
    build_two_column(path)
    script = run(str(path), profile=NoDiscussion())
    titles = [s.title for s in script.sections]
    assert "DISCUSSION" not in titles and "RESULTS" in titles


def test_read_captions_option(tmp_path):
    path = tmp_path / "d.pdf"
    build_two_column(path)
    assert "Example trial sequence" not in run(str(path)).to_text()
    # captions here are small text: reading them requires footnotes too
    text = run(str(path), read_captions=True, read_footnotes=True).to_text()
    assert "Example trial sequence" in text


def test_methods_after_references(tmp_path):
    path = tmp_path / "n.pdf"
    n = build_two_column(path, header="Nature Communications | (2024) 15:1", doi="10.1038/s41467-024-00001-1",
                         methods_after_references=True)
    script = run(str(path))
    assert script.profile == "springer_nature"
    text = script.to_text()
    assert f"mk{n:03d}" in text  # methods (after the references) are read
    assert [s.title for s in script.sections][-1] == "Methods: Eye tracking"
    for secret in ("REFERENCE-SECRET", "REPORTING-SECRET", "DATA-SECRET"):
        assert secret not in text
