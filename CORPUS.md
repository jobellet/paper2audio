# Regression corpus

The corpus is a set of real papers, each stored with its approved transcript. It is
kept in a **separate private repository** (default `<owner>/paper2audio-corpus`),
because published PDFs and their transcripts are copyrighted. In this repository,
`tests/corpus/` is git-ignored.

## Layout of the corpus repository

```
<case-id>/paper.pdf      the paper
<case-id>/case.json      source, licence, expected profile and year, and invariants
<case-id>/expected.txt   the approved transcript
README.md                licence table
```

## Working locally

```bash
git clone git@github.com:<owner>/paper2audio-corpus.git tests/corpus
python -m paper2audio.corpus check                 # same check as CI
python -m paper2audio.corpus diff [case]           # word-level diff against expected.txt
python -m paper2audio.corpus update [case]         # approve an intended change
python -m paper2audio.corpus add paper.pdf jneurophysiol-2024-smith --source "..." --licence "..."
cd tests/corpus && git add -A && git commit -m "..." && git push
```

The corpus can also live elsewhere if you set `PAPER2AUDIO_CORPUS=/path/to/corpus`.

Order matters when a heuristic change alters a transcript on purpose:
1. Push the updated `expected.txt` to the corpus repository.
2. Then push the code change.

CI checks out the corpus at its latest commit.

## CI setup (one time)

1. Create the private repository `paper2audio-corpus` and push the corpus to it.
2. Create a **fine-grained personal access token**: GitHub → Settings → Developer
   settings → Fine-grained tokens. Give it access to *only* `paper2audio-corpus`,
   with the permission **Contents: Read-only**.
3. In the code repository: Settings → Secrets and variables → Actions → New
   repository secret. Name it `CORPUS_TOKEN` and paste the token.
4. Optional: if the corpus repository has another name or owner, add an Actions
   *variable* `CORPUS_REPO=owner/name`.

Without the secret (for example, pull requests from forks), CI runs the unit tests
and skips the corpus with a notice.

## Size

Plain git copes with a few hundred PDFs, at most about 1 GB of repository. For more
than that, enable Git LFS for `*.pdf` in the corpus repository. LFS bandwidth counts
against your quota on every CI checkout.
