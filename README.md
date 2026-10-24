# paper2audio

Listen to scientific papers. paper2audio turns a PDF into an MP3 with **one chapter
per section**, read in the right order and without the clutter: no citations,
statistics, figure references, running heads, page numbers or reference list.

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jobellet/paper2audio/blob/main/notebooks/paper2audio_colab.ipynb)
[![Open in Kaggle](https://kaggle.com/static/images/open-in-kaggle.svg)](https://kaggle.com/kernels/welcome?src=https://github.com/jobellet/paper2audio/blob/main/notebooks/paper2audio_colab.ipynb)
[![CI](https://github.com/jobellet/paper2audio/actions/workflows/ci.yml/badge.svg)](https://github.com/jobellet/paper2audio/actions/workflows/ci.yml)

## Quick start

### Option 1: in your browser, nothing to install

- **Colab:** click **Open in Colab** above, choose **Runtime → Change runtime type →
  T4 GPU**, then **Runtime → Run all** and upload your PDF.
- **Kaggle:** click **Open in Kaggle**, set **Settings → Accelerator → GPU T4** and
  **Internet → on**, add your PDF with **Add Input → Upload** (or paste a link in
  `PDF_URL`), then **Run All**. The MP3 appears under **Output**.

A 15-page paper takes about two minutes on the free T4 GPU (roughly 15× faster than
real time), read by a natural-sounding neural voice (Kokoro-82M), with the transcript.

- **Web page (self-hosted on GitHub):** after enabling **Settings → Pages → Source:
  GitHub Actions**, the page at
  `https://<you>.github.io/paper2audio/` turns a link to a PDF into an MP3 with one
  click: it pre-fills the *Web* workflow, GitHub Actions runs the full pipeline on a
  free runner (neural voices included), and the MP3 lands in the public `web` release,
  playable and downloadable straight from the page. See
  [docs/index.html](docs/index.html).

### Option 2: on your computer

You need Python 3.10 or newer and [ffmpeg](https://ffmpeg.org/):

| system  | install ffmpeg              |
|---------|-----------------------------|
| macOS   | `brew install ffmpeg`       |
| Ubuntu  | `sudo apt install ffmpeg`   |
| Windows | `winget install ffmpeg`     |

Then install paper2audio, preferably in its own environment:

```bash
conda create -n paper2audio python=3.12     # or: python -m venv .venv
conda activate paper2audio
pip install "paper2audio[edge,espeak] @ git+https://github.com/jobellet/paper2audio.git"
```

And convert a paper:

```bash
paper2audio paper.pdf                # -> paper.mp3, Microsoft Edge neural voice (needs internet)
paper2audio paper.pdf --fast         # -> paper.mp3 in about a minute, robotic offline voice
```

Not sure what will be read? `paper2audio paper.pdf -e none` writes only the
transcript (`paper.txt`) so you can check it first.

## What gets read, and what doesn't

**Read, in order:** the title, the abstract and every section of the main text,
left column then right column then the next page, with sentences that break across
columns, pages or equations joined back together. A Methods section placed after the
references (Nature, Cell STAR Methods) is still read.

**Removed:**
- citations: `[3, 5–7]`, superscripts, `(Smith et al., 2019; …)`. "Duhamel et al.
  (1992)" becomes "Duhamel et al".
- statistics: `(t(11) = 3.21, p = .008, d = 0.93)`, `F(1, 11) = 18.2`, 95% CIs and
  Bayes factors. Prose such as "(n = 12; 7 female)" is kept.
- figure and table references (`(Fig. 2A)`), captions, figure labels, tables,
  footnotes, display equations and code listings.
- running heads and footers, page and line numbers, margin stamps, DOIs, URLs, e-mail
  addresses and ORCIDs.
- front matter (authors, affiliations, dates, keywords) and the References,
  Acknowledgements, Funding, Author contributions, Competing interests, Data
  availability and Supplementary sections.

**Rewritten to sound natural:** "e.g." → "for example", "50 ms" → "50 milliseconds",
"300°/s" → "300 degrees per second", "±" → "plus or minus".

## Options

```bash
paper2audio paper.pdf --transcript            # also write paper.txt
paper2audio paper.pdf -o ~/Podcasts/smith.mp3 # output file
paper2audio paper.pdf -v en-GB-SoniaNeural    # another voice (edge-tts list-voices)
paper2audio paper.pdf -r 1.2                  # 20% faster
paper2audio paper.pdf --skip methods          # skip more sections (regex, repeatable)
paper2audio paper.pdf --captions              # also read figure captions
paper2audio paper.pdf -p elsevier             # force a journal profile (--list-profiles)
paper2audio paper.pdf --year 2014             # if the publication year is detected wrongly
paper2audio paper.pdf --check                 # list paragraphs that look cut or misplaced
```

### Voices (`-e`)

Extras go in the brackets of the install command, e.g. `paper2audio[edge,kokoro]`.

| engine   | quality           | offline | install / notes                                                    |
|----------|-------------------|---------|--------------------------------------------------------------------|
| `edge`   | neural, very good | no      | `[edge]` extra; the default                                        |
| `kokoro` | neural, very good | yes     | `[kokoro]` extra; model downloaded on first use (~340 MB); voices `am_michael`, `af_heart`, `bm_george`, `bf_emma`, …; ~2× real time on 4 CPU cores |
| `piper`  | neural, good      | yes     | `pip install piper-tts`; `-v path/to/voice.onnx`                   |
| `say`    | good              | yes     | macOS only, nothing to install                                     |
| `espeak` | robotic           | yes     | `[espeak]` extra; what `--fast` uses                               |
| `api`    | depends on server | no      | any OpenAI-compatible text-to-speech service, see below            |

`edge` and `api` synthesise 4 sections at once; change this with `-j`.

**Your own TTS service (`-e api`).** Works with OpenAI and with self-hosted servers
that implement the same `/v1/audio/speech` API (Kokoro-FastAPI, openedai-speech,
LocalAI, …):

```bash
export PAPER2AUDIO_TTS_URL=http://localhost:8880/v1/audio/speech  # default: OpenAI
export PAPER2AUDIO_TTS_KEY=...          # or OPENAI_API_KEY; local servers may need none
export PAPER2AUDIO_TTS_MODEL=kokoro     # default: tts-1
paper2audio paper.pdf -e api -v af_heart
```

### From Python

```python
from paper2audio import run
script = run("paper.pdf")          # Script(title, sections, profile, skipped)
print(script.to_text())
```

## Supported journals

The journal is detected automatically from the DOI and the first two pages; each
journal family has a *profile* with its own rules.

| profile           | matches                                   | checked on a real PDF |
|-------------------|-------------------------------------------|-----------------------|
| `manuscript`      | submitted manuscripts (line numbers, one column), any journal | ✓ |
| `springer_nature` | 10.1038, 10.1007, 10.1186 (Nature, Nature Mental Health, …)  | ✓ |
| `biorxiv`         | 10.1101 (bioRxiv, medRxiv)                | ✓ |
| `aps`             | 10.1152 (J Neurophysiol, J Appl Physiol)  | ✓ |
| `cell_press`      | 10.1016/j.neuron, j.cell, j.cub, j.celrep, Trends, … | ✓ (2012–2024) |
| `elsevier`        | other 10.1016 (Vision Res, NeuroImage, Cortex, …) | partly |
| `plos`            | 10.1371                                   | not yet |
| `elife`           | 10.7554                                   | not yet |
| `jneurosci`       | 10.1523                                   | not yet |
| `jov`             | 10.1167 (ARVO)                            | not yet |
| `arxiv`           | arXiv preprints                           | not yet |
| `generic`         | anything else                             | fallback |

If a paper comes out wrong, please open an issue with the journal name and what was
wrong (`paper2audio paper.pdf --check` helps). Please don't attach copyrighted PDFs.

## Known limitations

- Scanned PDFs without a text layer need OCR first (for example `ocrmypdf`).
- Inline math inside sentences is read from its text layer, which can be garbled,
  mostly in Methods sections.
- Narrative numeric citations ("described in 13") are not removed.

## Troubleshooting

- **`ffmpeg is required`**: install ffmpeg (see above) and open a new terminal.
- **pip spends a long time building PyMuPDF**: no prebuilt wheel exists for your
  platform's newest version. Run `pip install --only-binary=pymupdf pymupdf` first.
- **Edge voice fails or hangs**: it needs internet. Use `--fast` or `-e kokoro` offline.

---

## Contributing

### Development setup

```bash
git clone https://github.com/jobellet/paper2audio && cd paper2audio
conda create -n paper2audio python=3.12 && conda activate paper2audio
pip install -e ".[dev,edge]"
pytest
```

### How it works

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

### Adding a journal

1. Run `paper2audio paper.pdf --transcript -e none` and read the `.txt` file to see
   what comes out wrong.
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

Tunable parameters on every profile: `header_band` / `footer_band` (page fraction that
can hold running heads), `small_text_ratio`, `read_captions`, `read_footnotes`,
`read_tables`, `references_end_main_text`, `front_matter_end`.

4. Add tests: `tests/test_profiles.py` uses synthetic papers from `tests/fixtures.py`
   whose sentences are numbered (`mk001`, `mk002`, …), so tests can check the reading
   order exactly. Then add the real paper to your regression corpus (below).

### Publication year and layout eras

Journals redesign their layout from time to time, so a profile may need different
rules for a 2012 and a 2024 article. `year.py` estimates the publication year from
first-page clues, in this order: "Published (online)" / "First published", a
preprint's "posted" date, the journal citation line ("J Neurophysiol 121: 646–661,
2019"), "Accepted", "©", and as a last resort the PDF creation date. `--year`
overrides the estimate. A profile then switches its rules by year:

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

### Tests, CI and the regression corpus

```bash
pytest                                   # unit tests on synthetic papers (+ corpus if present)
python -m paper2audio.corpus check       # real papers vs approved transcripts
```

Heuristics that fix one journal can break another, so changes are checked against a
**regression corpus**: real papers, each with a transcript a person approved. Because
the PDFs are copyrighted, the corpus lives in a separate **private** repository
checked out at `tests/corpus/` (git-ignored). Each contributor keeps their own:

[![Create your private corpus repository](https://img.shields.io/badge/GitHub-Create%20your%20private%20corpus%20repo-24292f?logo=github)](https://github.com/new?name=paper2audio-corpus&visibility=private&description=Private%20regression%20corpus%20for%20paper2audio%20%28copyrighted%20PDFs%2C%20do%20not%20make%20public%29)

```bash
python -m paper2audio.corpus init --remote https://github.com/<you>/paper2audio-corpus.git
python -m paper2audio.corpus add paper.pdf nature-2023-smith --source "..." --licence "CC BY 4.0"
```

GitHub Actions (`.github/workflows/ci.yml`) runs the unit tests on every push, and the
corpus too when the `CORPUS_TOKEN` secret is set. If a change alters an approved
transcript on purpose, review and approve it:

```bash
python -m paper2audio.corpus diff nature-2023-cebra
python -m paper2audio.corpus update nature-2023-cebra
```

then push the corpus repository **before** the code. [CORPUS.md](CORPUS.md) has the
step-by-step setup, including the CI token.
