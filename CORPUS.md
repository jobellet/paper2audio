# Regression corpus

The corpus is a set of real papers, each stored with a transcript a person checked
and approved. Every heuristic change is re-run against all of them, so a fix for one
journal cannot silently break another.

It is kept in a **separate private repository** (default `<you>/paper2audio-corpus`)
because published PDFs and their transcripts are copyrighted. In this repository,
`tests/corpus/` is git-ignored, and the corpus repository's own README explains what
it is for. Nobody else's corpus is shared: each contributor builds their own from the
papers they read.

## Set up your own corpus

1. Create an empty private repository (the button pre-fills the name and
   *Private*; don't add a README or licence):

   [![Create your private corpus repository](https://img.shields.io/badge/GitHub-Create%20your%20private%20corpus%20repo-24292f?logo=github)](https://github.com/new?name=paper2audio-corpus&visibility=private&description=Private%20regression%20corpus%20for%20paper2audio%20%28copyrighted%20PDFs%2C%20do%20not%20make%20public%29)

   or `gh repo create paper2audio-corpus --private`.

2. From the code repository, start the corpus and add your first paper:

   ```bash
   python -m paper2audio.corpus init --remote https://github.com/<you>/paper2audio-corpus.git
   python -m paper2audio.corpus add paper.pdf jneurophysiol-2024-smith \
          --source "Smith et al. (2024) J Neurophysiol 131:1" --licence "© APS"
   ```

   `init` creates `tests/corpus/` with a README and a git repository. Read the new
   `expected.txt` from start to finish, fix the heuristics until it is right, and list
   a few key sentences and the junk you saw removed in `case.json`
   (`must_contain` / `must_not_contain`).

3. Commit and push it:

   ```bash
   cd tests/corpus && git add -A && git commit -m "First case" && git push -u origin main
   ```

If you already have a corpus repository, clone it instead:
`git clone https://github.com/<you>/paper2audio-corpus.git tests/corpus`. The corpus
can also live elsewhere if you set `PAPER2AUDIO_CORPUS=/path/to/corpus`.

## Layout of the corpus repository

```
<case-id>/paper.pdf      the paper
<case-id>/case.json      source, licence, expected profile and year, and invariants
<case-id>/expected.txt   the approved transcript
README.md                what the repository is for, and the licence table
```

Use one case id per journal **and era** (`jneurophysiol-2019-…`,
`jneurophysiol-2024-…`), because layouts change over the years.

## Day to day

```bash
python -m paper2audio.corpus check                 # same check as CI
python -m paper2audio.corpus diff [case]           # word-level diff against expected.txt
python -m paper2audio.corpus update [case]         # approve an intended change
```

Order matters when a heuristic change alters a transcript on purpose:
1. Push the updated `expected.txt` to the corpus repository.
2. Then push the code change.

CI checks out the corpus at its latest commit.

## CI setup (one time)

1. Create a **fine-grained personal access token**: GitHub → Settings → Developer
   settings → Fine-grained tokens
   ([direct link](https://github.com/settings/personal-access-tokens/new)). Give it
   access to *only* `paper2audio-corpus`, with the permission **Contents: Read-only**.
2. Add it to the **code** repository (not the corpus repository): Settings → Secrets
   and variables → Actions → New repository secret, named `CORPUS_TOKEN`. Or:
   `gh secret set CORPUS_TOKEN -R <you>/paper2audio`.
3. Optional: if the corpus repository has another name or owner, add an Actions
   *variable* `CORPUS_REPO=owner/name`.

Without the secret (for example, pull requests from forks), CI runs the unit tests
and skips the corpus with a notice.

## Size

Plain git copes with a few hundred PDFs, at most about 1 GB of repository. For more
than that, enable Git LFS for `*.pdf` in the corpus repository. LFS bandwidth counts
against your quota on every CI checkout.
