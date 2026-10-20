import subprocess

import pytest

from paper2audio import run
from paper2audio.audio import render
from paper2audio.tts import EspeakTTS
from fixtures import build_single_column


@pytest.mark.skipif(not EspeakTTS.available(), reason="espeak not installed")
def test_render_mp3_with_chapters(tmp_path):
    pdf = tmp_path / "one.pdf"
    build_single_column(pdf)
    script = run(str(pdf))
    script.sections[0].paragraphs = script.sections[0].paragraphs[:1]  # keep the test fast
    out = render(script, EspeakTTS(), tmp_path / "one.mp3", progress=lambda m: None)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_chapters", "-show_format", str(out)],
                           capture_output=True, text=True, check=True).stdout
    assert "format_name=mp3" in probe
    assert probe.count("[CHAPTER]") == 1 + len(script.sections)
    duration = float(probe.split("duration=")[1].split()[0])
    assert duration > 5
