# paper2audio

Turn a scientific paper (PDF) into an audio file you can listen to, with the clutter
removed and the text read in the right order.

**What it does**
- Follows the reading order: left column, then right column, then the next page.
  This also works around side boxes, full-width figures and two-column captions.
  Sentences that break across a column, a page or an equation are joined back
  together.
- Removes running heads and footers, page numbers, manuscript line numbers, rotated
  margin stamps, DOIs, URLs, e-mail addresses and ORCIDs.
- Removes numeric citations (`[3, 5–7]`, superscripts) and author–year citations
  (`(Smith et al., 2019; …)`). "Duhamel et al. (1992)" becomes "Duhamel et al".
- Removes statistics: `(t(11) = 3.21, p = .008, d = 0.93)`, `F(1, 11) = 18.2, p < .001`,
  95% CIs and Bayes factors. Prose such as "(n = 12; 7 female)" is kept.
- Removes references to figures and tables (`(Fig. 2A)`), figure captions, figure
  labels, tables, footnotes, equation fragments and code listings.
- Skips the front matter (authors, affiliations, dates, keywords) and these sections:
  References, Acknowledgements, Funding, Author contributions, Competing interests,
  Data availability, Supplementary information and similar. It still reads a Methods
  section placed after the reference list (Nature, Cell STAR Methods).
- Rewrites text so it sounds natural: "e.g." becomes "for example", "50 ms" becomes
  "50 milliseconds", "300°/s" becomes "300 degrees per second", "±" becomes
  "plus or minus".
- Writes one MP3 with a **chapter per section**.

## Install

```bash
pip install -e ".[edge]"        # neural voices (needs internet)
pip install -e ".[kokoro]"      # offline neural voices (model auto-downloaded, ~340 MB)
pip install -e ".[espeak]"      # fully offline fallback (robotic voice)
pip install -e ".[dev]"         # tests
```
`ffmpeg` must be on your PATH.

## Use

```bash
paper2audio paper.pdf                          # -> paper.mp3 (auto-detects the journal)
paper2audio paper.pdf --transcript             # also write paper.txt: check what will be read
paper2audio paper.pdf -e none                  # transcript only, no audio
paper2audio paper.pdf -v en-GB-SoniaNeural -r 1.2  # voice and speed
paper2audio paper.pdf --skip methods           # skip more sections (regex)
paper2audio paper.pdf --captions               # also read figure captions
paper2audio paper.pdf -p elsevier              # force a journal profile
paper2audio --list-profiles
paper2audio paper.pdf -e kokoro -v bf_emma     # offline neural voice
paper2audio paper.pdf --check                  # paragraphs that look cut or misplaced
paper2audio paper.pdf --debug                  # layout dump for tuning heuristics
```

TTS engines (`-e`):

| engine   | quality           | offline | notes                                                    |
|----------|-------------------|---------|----------------------------------------------------------|
| `edge`   | neural, very good | no      | default; `edge-tts list-voices` shows all voices         |
| `kokoro` | neural, very good | yes     | `am_michael`, `am_adam`, `af_heart`, `bm_george`, `bf_emma`, … ~2× real time on 4 CPU cores |
| `piper`  | neural, good      | yes     | `pip install piper-tts`; `-v path/to/voice.onnx`         |
| `say`    | good              | yes     | macOS only                                               |
| `espeak` | robotic           | yes     | installed with pip, no system package needed             |

From Python:

```python
from paper2audio import run
script = run("paper.pdf")          # Script(title, sections, profile, skipped)
print(script.to_text())
```

## How it works

```
extract.py   PDF -> positioned lines (font size, bold, bbox) + figure areas (images,
             vector-drawing clusters); citation superscripts dropped, R², s⁻¹ kept
layout.py    junk lines (running heads, line numbers, small text, figure labels, math,
             code) -> reading order by recursive XY-cut (split at vertical gutters, else
             into horizontal bands; bands sharing a gutter are merged) -> captions
             -> paragraphs (de-hyphenation, sentences joined across columns and pages)
pipeline.py  front matter, sections and skipping -> cleaning.py (citations, stats, links)
             -> speech.py (abbreviations, units, symbols)
audio.py     one TTS clip per section -> MP3 with chapters (ffmpeg)
profiles/    one module per journal / publisher
tts/         one module per TTS engine
```

## Journal profiles

Each journal family has a profile in `src/paper2audio/profiles/`. The best match is
picked automatically from DOI prefixes and signature strings on the first two pages.

| profile           | matches                                   | specifics                                                  |
|-------------------|-------------------------------------------|------------------------------------------------------------|
| `generic`         | anything                                  | fallback                                                   |
| `manuscript`      | submitted manuscripts, any journal        | detected by layout (line numbers, one column), not by journal name; a published article in the same journal gets that journal's profile |
| `arxiv`           | arXiv preprints                           | margin stamp, conference banners                           |
| `biorxiv`         | 10.1101 (bioRxiv, medRxiv)                | copyright banner on every page, line numbers               |
| `elsevier`        | 10.1016 (Vision Res, NeuroImage, Cell, …) | masthead, ARTICLE INFO box, CRediT, STAR Methods           |
| `springer_nature` | 10.1038, 10.1007, 10.1186                 | Methods after References, Reporting summary, Extended Data |
| `plos`            | 10.1371                                   | first-page side bar, `3 / 25` running head                 |
| `elife`           | 10.7554                                   | side bar, decision letter, author response                 |
| `jneurosci`       | 10.1523                                   | SfN running heads, first-page footnote                     |
| `aps`             | 10.1152 (J Neurophysiol, J Appl Physiol)  | small-caps headings, citation line before abstract         |
| `jov`             | 10.1167 (ARVO)                            | download stamp, citation box                               |

### Publication year and layout eras

Journals redesign their layout from time to time, so the same profile may need
different rules for a 2012 and a 2024 article. `year.py` estimates the publication
year from first-page clues, in this order:
1. "Published (online)" / "First published"
2. a preprint's "posted" date
3. the journal citation line ("J Neurophysiol 121: 646–661, 2019", "Nature | Vol 617 | 11 May 2023")
4. "Accepted"
5. "©"
6. as a last resort, the PDF creation date

`--year` overrides the estimate. A profile then switches its rules by year:

```python
class JNeurophysiol(APS):
    eras = (
        (None, 2015, {"header_band": 0.12}),                    # before the redesign
        (2016, None, {"junk_lines": APS.junk_lines + (r"^New layout banner",)}),
    )

    def adapt(self, year):              # for anything the table cannot express
        super().adapt(year)
        if year and year >= 2020:
            ...
```

### Adding a journal

1. Run `paper2audio paper.pdf --transcript` and read the `.txt` file to see what
   comes out wrong.
2. Run `paper2audio paper.pdf --debug` to see every line with its column, kind, font
   size and position, in reading order.
3. Create `src/paper2audio/profiles/<journal>.py`. Modules in that folder load
   automatically; files whose name starts with `_` are ignored.

```python
from . import register
from .generic import Generic
from ..cleaning import rule


@register
class CurrentBiology(Generic):
    name = "current_biology"
    description = "Current Biology (Cell Press)"
    doi_prefixes = ("10.1016/j.cub",)
    signatures = (r"Current Biology \d+,",)          # regexes searched on pages 1-2

    junk_lines = Generic.junk_lines + (r"^Current Biology \d+, ",)  # dropped wherever they occur
    junk_paragraphs = Generic.junk_paragraphs + (r"in brief\b",)    # matched at paragraph start
    skip_sections = (r"key resources table", r"star.?methods")      # full-title regexes
    resume_sections = ()                    # sections that may follow the references
    extra_rules = (rule("cub_tag", r"\bCUB\d+\b"),)   # extra text clean-up
    disabled_rules = frozenset({"figure_reference"})  # disable a generic rule by name
    end_sections = ()                       # headings after which nothing is read

    # Hooks, for anything the attributes cannot express:
    # def classify_lines(self, doc, body_size): ...  re-label Line.kind
    # def order_page(self, page, body_size): ...     custom reading order (set Line.column)
    # def postprocess(self, sections): ...           final edits
```

4. Add tests:
   - `tests/test_profiles.py` uses synthetic papers from `tests/fixtures.py`. Their
     sentences are numbered (`mk001`, `mk002`, …), so tests can check the reading
     order exactly.
   - Add the paper to the regression corpus with
     `python -m paper2audio.corpus add` (see [CORPUS.md](CORPUS.md)).

Tunable parameters on every profile: `header_band` / `footer_band` (page fraction that
can hold running heads), `small_text_ratio`, `read_captions`, `read_footnotes`,
`read_tables`, `references_end_main_text`, `front_matter_end`.

## Tests and CI

```bash
pytest                                   # everything
python -m paper2audio.corpus check       # real papers vs approved transcripts
```

The regression corpus is a set of real papers, each with an approved transcript
(`expected.txt`) and invariants (`case.json`). It lives in a separate **private**
repository, checked out at `tests/corpus/`, because the PDFs and their transcripts
are copyrighted. The GitHub Actions workflow (`.github/workflows/ci.yml`) runs the
unit tests on every push, and also the corpus whenever the `CORPUS_TOKEN` secret is
set. Any heuristic change that alters an approved transcript fails CI.

When the change is an improvement, approve it:

```bash
python -m paper2audio.corpus diff nature-2023-cebra
python -m paper2audio.corpus update nature-2023-cebra
```

Then push the corpus repository. See [CORPUS.md](CORPUS.md) for the one-time setup
and for adding papers.

## Known limitations

- Scanned PDFs with no text layer would need OCR first (for example `ocrmypdf`).
- Display equations are dropped when they are recognisable as math. Inline math
  inside sentences is read as its text layer, which can be garbled, mostly in
  Methods sections.
- Narrative numeric citations ("described in 13") are not removed.
- Profiles checked against real PDFs so far: manuscript (a manuscript submitted to JoCN), Nature,
  Nature Mental Health, bioRxiv and J Neurophysiol. The other profiles (Elsevier,
  PLOS, eLife, J Neurosci, JOV, arXiv) are based on each publisher's known layout and
  still need checking against a real PDF.
