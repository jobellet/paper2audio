"""Golden-file regression tests on real papers (see paper2audio/corpus.py).

A failure means a heuristic change altered a transcript that was approved
before. If the change is an improvement, inspect it with
`python -m paper2audio.corpus diff <case>` and approve it with
`python -m paper2audio.corpus update <case>`.
"""

import pytest

from paper2audio import corpus

CASES = corpus.cases()


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_corpus_case(case):
    res = corpus.check(case)
    if res.skipped:
        pytest.skip(res.skipped)
    assert not res.problems, "\n".join(res.problems)
    if res.diff:
        expected = case.expected_path.read_text(encoding="utf-8") if case.expected_path.exists() else ""
        changes = corpus.word_diff(expected, res.text)[:15]
        pytest.fail(f"transcript changed ({len(changes)}+ edits); approve with "
                    f"`python -m paper2audio.corpus update {case.id}` if intended:\n  " + "\n  ".join(changes))
