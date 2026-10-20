import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from fixtures import build_single_column, build_two_column  # noqa: E402


@pytest.fixture(scope="session")
def two_column(tmp_path_factory):
    path = tmp_path_factory.mktemp("pdf") / "two.pdf"
    n = build_two_column(path, line_numbers=True)
    return path, n
