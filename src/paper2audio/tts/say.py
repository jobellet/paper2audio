"""macOS built-in `say` command (offline)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .base import TTSBackend


class SayTTS(TTSBackend):
    name = "say"
    extension = ".aiff"

    @classmethod
    def available(cls) -> bool:
        return shutil.which("say") is not None

    def synthesize(self, text: str, out_path: Path) -> Path:
        out_path = out_path.with_suffix(self.extension)
        cmd = ["say", "-o", str(out_path), "-r", str(int(180 * self.rate))]
        if self.voice:
            cmd += ["-v", self.voice]
        subprocess.run(cmd, input=text.encode(), check=True)
        return out_path
