"""Golden-file regression corpus: real papers with their expected transcripts.

    tests/corpus/<case>/paper.pdf      the PDF (may be absent: case is skipped)
    tests/corpus/<case>/case.json      expectations that must always hold
    tests/corpus/<case>/expected.txt   the exact transcript last approved

Every heuristic change is checked against all cases. When a change is an
intended improvement, review the diff and approve it:

    python -m paper2audio.corpus check            # report, exit 1 on any difference
    python -m paper2audio.corpus diff nature-2023-cebra
    python -m paper2audio.corpus update [case...] # approve: rewrite expected.txt
    python -m paper2audio.corpus add paper.pdf my-case-id --source "..." --licence "..."
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .pipeline import run

# The corpus lives in its own private repository (copyrighted PDFs and their
# transcripts), checked out at tests/corpus/ or wherever $PAPER2AUDIO_CORPUS points.
ROOT = Path(os.environ.get("PAPER2AUDIO_CORPUS", Path(__file__).resolve().parents[2] / "tests" / "corpus"))
_END = re.compile(r"[.!?:)\]”\"’]$")


@dataclass
class Case:
    path: Path

    @property
    def id(self) -> str:
        return self.path.name

    @property
    def pdf(self) -> Path:
        return self.path / "paper.pdf"

    @property
    def expected_path(self) -> Path:
        return self.path / "expected.txt"

    @property
    def spec(self) -> dict:
        return json.loads((self.path / "case.json").read_text(encoding="utf-8"))


@dataclass
class Result:
    case: Case
    text: str = ""
    problems: list[str] = field(default_factory=list)  # broken invariants from case.json
    diff: list[str] = field(default_factory=list)  # difference from expected.txt
    skipped: str = ""

    @property
    def ok(self) -> bool:
        return not self.problems and not self.diff and not self.skipped


def cases(root: Path = ROOT, only: list[str] | None = None) -> list[Case]:
    found = [Case(p) for p in sorted(root.iterdir()) if (p / "case.json").exists()] if root.exists() else []
    if only:
        found = [c for c in found if c.id in only]
    return found


def check(case: Case) -> Result:
    res = Result(case)
    if not case.pdf.exists():
        res.skipped = "paper.pdf not available (not redistributable?)"
        return res
    spec = case.spec
    script = run(str(case.pdf))
    res.text = script.to_text()
    if spec.get("profile") and script.profile != spec["profile"]:
        res.problems.append(f"profile {script.profile!r}, expected {spec['profile']!r}")
    if spec.get("year") and script.year != spec["year"]:
        res.problems.append(f"year {script.year}, expected {spec['year']}")
    titles = [s.title for s in script.sections]
    res.problems += [f"missing section {t!r}" for t in spec.get("sections", []) if t not in titles]
    res.problems += [f"missing text {t!r}" for t in spec.get("must_contain", []) if t not in res.text]
    res.problems += [f"junk present {t!r}" for t in spec.get("must_not_contain", []) if t in res.text]
    main = res.text.split("\n## Methods")[0]
    cut = [p for p in main.split("\n\n") if p.strip() and not p.startswith("#") and not _END.search(p.strip())]
    if len(cut) > spec.get("max_cut_paragraphs", 1):
        res.problems.append(f"{len(cut)} paragraphs end mid-sentence: " + " | ".join(p[-60:] for p in cut[:3]))
    if case.expected_path.exists():
        expected = case.expected_path.read_text(encoding="utf-8")
        if expected != res.text:
            res.diff = list(difflib.unified_diff(
                expected.splitlines(), res.text.splitlines(), "expected.txt", "actual", lineterm="", n=0))
    else:
        res.diff = ["(no expected.txt yet: run `python -m paper2audio.corpus update`)"]
    return res


def summarize_diff(diff: list[str], limit: int = 40) -> str:
    """Unified diff, with long paragraphs narrowed to the changed words."""
    out = []
    for line in diff[:limit]:
        out.append(line if len(line) < 220 else line[:200] + f"… [{len(line)} chars]")
    if len(diff) > limit:
        out.append(f"… {len(diff) - limit} more diff lines")
    return "\n".join(out)


def word_diff(a: str, b: str, context: int = 6) -> list[str]:
    """Changed words with a little context: readable for paragraph-long lines."""
    wa, wb = a.split(), b.split()
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, wa, wb, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        before = " ".join(wa[max(0, i1 - context):i1])
        after = " ".join(wa[i2:i2 + context])
        out.append(f"…{before} [-{' '.join(wa[i1:i2])}-] {{+{' '.join(wb[j1:j2])}+}} {after}…")
    return out


def _cmd_check(args) -> int:
    failed = 0
    for case in cases(args.root, args.cases):
        res = check(case)
        if res.skipped:
            print(f"SKIP {case.id}: {res.skipped}")
            continue
        status = "ok  " if res.ok else "FAIL"
        print(f"{status} {case.id}")
        for p in res.problems:
            print(f"     ✗ {p}")
        if res.diff:
            print(f"     transcript differs from expected.txt ({sum(1 for d in res.diff if d[:1] in '+-')} lines)")
        failed += not res.ok
    return 1 if failed else 0


def _cmd_diff(args) -> int:
    for case in cases(args.root, args.cases):
        res = check(case)
        if res.skipped or not case.expected_path.exists():
            continue
        print(f"=== {case.id}")
        for change in word_diff(case.expected_path.read_text(encoding="utf-8"), res.text):
            print("  " + change)
    return 0


def _cmd_update(args) -> int:
    for case in cases(args.root, args.cases):
        res = check(case)
        if res.skipped:
            print(f"SKIP {case.id}: {res.skipped}")
            continue
        if res.problems and not args.force:
            print(f"REFUSED {case.id}: invariants broken (fix them or pass --force):")
            for p in res.problems:
                print(f"     ✗ {p}")
            continue
        changed = res.diff != []
        case.expected_path.write_text(res.text, encoding="utf-8")
        print(f"{'updated' if changed else 'unchanged'} {case.id}")
    return 0


def _cmd_add(args) -> int:
    target = args.root / args.id
    target.mkdir(parents=True, exist_ok=False)
    shutil.copy(args.pdf, target / "paper.pdf")
    script = run(str(target / "paper.pdf"))
    spec = {
        "source": args.source, "licence": args.licence, "redistributable": args.redistributable,
        "profile": script.profile, "year": script.year,
        "sections": [s.title for s in script.sections],
        "must_contain": [], "must_not_contain": [], "max_cut_paragraphs": 1,
    }
    (target / "case.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (target / "expected.txt").write_text(script.to_text(), encoding="utf-8")
    print(f"added {target}: read expected.txt carefully before committing, and list key phrases "
          f"and known junk in case.json (must_contain / must_not_contain)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m paper2audio.corpus", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=ROOT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "diff", "update"):
        p = sub.add_parser(name)
        p.add_argument("cases", nargs="*")
        if name == "update":
            p.add_argument("--force", action="store_true", help="approve even if case.json invariants fail")
    p = sub.add_parser("add")
    p.add_argument("pdf", type=Path)
    p.add_argument("id")
    p.add_argument("--source", default="")
    p.add_argument("--licence", default="unknown")
    p.add_argument("--redistributable", action="store_true")
    args = ap.parse_args(argv)
    return {"check": _cmd_check, "diff": _cmd_diff, "update": _cmd_update, "add": _cmd_add}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
