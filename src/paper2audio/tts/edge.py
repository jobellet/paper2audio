"""Microsoft Edge neural voices via `edge-tts` (free, needs internet)."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from .base import TTSBackend


class EdgeTTS(TTSBackend):
    name = "edge"
    extension = ".mp3"
    concurrent = True
    default_voice = "en-US-AndrewNeural"

    @classmethod
    def available(cls) -> bool:
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            return False
        return True

    def synthesize(self, text: str, out_path: Path) -> Path:
        import edge_tts

        pct = round((self.rate - 1.0) * 100)
        kwargs = {}
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        if proxy:
            kwargs["proxy"] = proxy
        comm = edge_tts.Communicate(text, self.voice or self.default_voice, rate=f"{pct:+d}%", **kwargs)
        out_path = out_path.with_suffix(self.extension)
        asyncio.run(comm.save(str(out_path)))
        return out_path
