import shutil
import subprocess

import pytest

from paper2audio import corpus
from fixtures import build_single_column


@pytest.mark.skipif(not shutil.which("git"), reason="git not installed")
def test_init_then_add(tmp_path):
    root = tmp_path / "corpus"
    assert corpus.main(["--root", str(root), "init", "--remote", "https://example.invalid/c.git"]) == 0
    assert "What this repository is for" in (root / "README.md").read_text()
    remote = subprocess.run(["git", "-C", str(root), "remote", "get-url", "origin"],
                            capture_output=True, text=True, check=True).stdout.strip()
    assert remote == "https://example.invalid/c.git"

    pdf = tmp_path / "one.pdf"
    build_single_column(pdf)
    assert corpus.main(["--root", str(root), "add", str(pdf), "synthetic-one"]) == 0
    assert [c.id for c in corpus.cases(root)] == ["synthetic-one"]
    assert corpus.check(corpus.cases(root)[0]).ok
    assert corpus.main(["--root", str(root), "init"]) == 1  # refuses to re-initialise a corpus
