"""Script -> one MP3 with a chapter per section (needs ffmpeg)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .pipeline import Script
from .tts import TTSBackend


def _duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _section_texts(script: Script) -> list[tuple[str, str]]:
    parts: list[tuple[str, str]] = []
    if script.title:
        parts.append(("Title", script.title + "."))
    for s in script.sections:
        heading = (s.title.rstrip(".") + ".\n\n") if s.title else ""
        parts.append((s.title or "Text", heading + "\n\n".join(p.text for p in s.paragraphs)))
    return parts


def render(script: Script, backend: TTSBackend, out_path: Path, pause: float = 1.0, progress=print,
           jobs: int = 1) -> Path:
    """`jobs` sections are synthesised at once if the backend allows it (network engines)."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to assemble the audio")
    out_path = Path(out_path)
    with tempfile.TemporaryDirectory(prefix="paper2audio-") as tmp:
        tmpdir = Path(tmp)
        parts = _section_texts(script)

        def clip(i: int, title: str, text: str) -> Path:
            progress(f"  [{i + 1}/{len(parts)}] {title}")
            raw = backend.synthesize(text, tmpdir / f"part{i:03d}")
            wav = tmpdir / f"part{i:03d}.norm.wav"
            # normalise all clips to one format and append the pause
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", f"apad=pad_dur={pause}",
                 "-ar", "24000", "-ac", "1", str(wav)],
                check=True,
            )
            return wav

        workers = max(1, jobs) if backend.concurrent else 1
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(clip, i, title, text) for i, (title, text) in enumerate(parts)]
            clips = [(title, f.result()) for (title, _), f in zip(parts, futures)]

        listing = tmpdir / "list.txt"
        listing.write_text("".join(f"file '{p}'\n" for _, p in clips))
        meta = [";FFMETADATA1", f"title={script.title or out_path.stem}", "genre=Speech"]
        t = 0.0
        for title, wav in clips:
            d = _duration(wav)
            meta += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(t * 1000)}", f"END={int((t + d) * 1000)}",
                     f"title={title.replace('=', ' ').replace(';', ',')}"]
            t += d
        meta_file = tmpdir / "meta.txt"
        meta_file.write_text("\n".join(meta) + "\n")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
             "-i", str(meta_file), "-map_metadata", "1", "-map_chapters", "1",
             "-c:a", "libmp3lame", "-q:a", "4", str(out_path)],
            check=True,
        )
    return out_path
