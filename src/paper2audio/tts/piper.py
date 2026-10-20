"""Piper: offline neural voices (pip install piper-tts, then download a voice).

Voices: https://huggingface.co/rhasspy/piper-voices  (e.g. en_US-lessac-medium.onnx)
Pass the .onnx path as --voice.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from .base import TTSBackend


class PiperTTS(TTSBackend):
    name = "piper"
    extension = ".wav"

    @classmethod
    def available(cls) -> bool:
        return shutil.which("piper") is not None

    def synthesize(self, text: str, out_path: Path) -> Path:
        if not self.voice:
            sys.exit("piper needs --voice /path/to/voice.onnx")
        out_path = out_path.with_suffix(self.extension)
        cmd = ["piper", "--model", self.voice, "--output_file", str(out_path),
               "--length_scale", f"{1 / self.rate:.3f}"]
        subprocess.run(cmd, input=text.encode(), check=True)
        return out_path
