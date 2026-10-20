"""Command line interface: paper2audio paper.pdf [-o paper.mp3]."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import profiles
from .pipeline import debug_layout, quality_report, run
from .tts import BACKENDS, get_backend


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="paper2audio", description=__doc__)
    ap.add_argument("pdf", nargs="?", help="scientific paper (PDF)")
    ap.add_argument("-o", "--output", help="output .mp3 (default: next to the PDF)")
    ap.add_argument("-p", "--profile", default="auto", help="journal profile (default: auto-detect)")
    ap.add_argument("-e", "--engine", default="edge", choices=["auto", "none", *BACKENDS],
                    help="TTS engine; 'none' writes only the transcript")
    ap.add_argument("-v", "--voice", help="voice name (edge/say/espeak) or .onnx model path (piper)")
    ap.add_argument("-r", "--rate", type=float, default=1.0, help="speaking speed, 1.0 = normal")
    ap.add_argument("--captions", action="store_true", help="also read figure/table captions")
    ap.add_argument("--skip", action="append", default=[], metavar="REGEX",
                    help="extra section titles to skip, e.g. --skip methods")
    ap.add_argument("--transcript", action="store_true", help="also write the transcript (.txt)")
    ap.add_argument("--debug", action="store_true",
                    help="write a line-by-line layout dump (.layout.txt) for tuning profiles, then exit")
    ap.add_argument("--year", type=int, help="publication year, if auto-detection is wrong")
    ap.add_argument("--check", action="store_true",
                    help="report paragraphs that look cut or misplaced (no audio)")
    ap.add_argument("--list-profiles", action="store_true", help="list journal profiles and exit")
    args = ap.parse_args(argv)

    if args.list_profiles:
        for name, cls in profiles.available().items():
            print(f"{name:18s} {cls.description}")
        return 0
    if not args.pdf:
        ap.error("the pdf argument is required")

    pdf = Path(args.pdf)
    options: dict = {}
    if args.captions:
        options["read_captions"] = True
    if args.skip:
        options["skip_sections"] = tuple(args.skip)
    if args.year:
        options["year"] = args.year
    out = Path(args.output) if args.output else pdf.with_suffix(".mp3")
    if args.debug:
        dump = out.with_suffix(".layout.txt")
        dump.write_text(debug_layout(str(pdf), profile=args.profile, **options), encoding="utf-8")
        print(f"layout dump: {dump}", file=sys.stderr)
        return 0
    script = run(str(pdf), profile=args.profile, **options)

    print(f"profile: {script.profile}, year: {script.year or 'unknown'}"
          f"{f' (from {script.year_source})' if script.year_source else ''}", file=sys.stderr)
    print(f"sections: {', '.join(s.title or '(untitled)' for s in script.sections)}", file=sys.stderr)
    if script.skipped:
        print(f"skipped: {', '.join(script.skipped)}", file=sys.stderr)
    if args.check:
        print(quality_report(script))
        return 0

    if args.transcript or args.engine == "none":
        txt = out.with_suffix(".txt")
        txt.write_text(script.to_text(), encoding="utf-8")
        print(f"transcript: {txt}", file=sys.stderr)
    if args.engine == "none":
        return 0

    from .audio import render

    backend = get_backend(args.engine, voice=args.voice, rate=args.rate)
    print(f"synthesising with {backend.name} ...", file=sys.stderr)
    render(script, backend, out, progress=lambda m: print(m, file=sys.stderr))
    print(f"audio: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
