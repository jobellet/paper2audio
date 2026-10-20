"""Any OpenAI-compatible speech endpoint (POST /v1/audio/speech).

Works with OpenAI and with self-hosted servers that copy its API (Kokoro-FastAPI,
openedai-speech, LocalAI, ...). Configured with environment variables:

    PAPER2AUDIO_TTS_URL    endpoint (default https://api.openai.com/v1/audio/speech)
    PAPER2AUDIO_TTS_KEY    API key (falls back to OPENAI_API_KEY; local servers may need none)
    PAPER2AUDIO_TTS_MODEL  model name (default tts-1)
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from .base import TTSBackend

DEFAULT_URL = "https://api.openai.com/v1/audio/speech"
MAX_CHARS = 4000  # OpenAI rejects inputs over 4096 characters


def split_text(text: str, limit: int = MAX_CHARS) -> list[str]:
    """Pack paragraphs (then sentences, then words) into chunks of at most `limit` characters."""
    pieces: list[str] = []
    for para in (p.strip() for p in re.split(r"\n\s*\n", text)):
        if len(para) <= limit:
            pieces.append(para)
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", para):
            while len(sentence) > limit:
                cut = sentence.rfind(" ", 0, limit)
                cut = cut if cut > 0 else limit
                pieces.append(sentence[:cut])
                sentence = sentence[cut:].lstrip()
            pieces.append(sentence)
    chunks: list[str] = []
    for piece in filter(None, pieces):
        if chunks and len(chunks[-1]) + 2 + len(piece) <= limit:
            chunks[-1] += "\n\n" + piece
        else:
            chunks.append(piece)
    return chunks


class ApiTTS(TTSBackend):
    name = "api"
    extension = ".mp3"
    concurrent = True
    default_voice = "alloy"

    @classmethod
    def available(cls) -> bool:
        return bool(os.environ.get("PAPER2AUDIO_TTS_URL") or os.environ.get("PAPER2AUDIO_TTS_KEY")
                    or os.environ.get("OPENAI_API_KEY"))

    def _request(self, text: str) -> bytes:
        url = self.options.get("url") or os.environ.get("PAPER2AUDIO_TTS_URL", DEFAULT_URL)
        key = self.options.get("key") or os.environ.get("PAPER2AUDIO_TTS_KEY") or os.environ.get("OPENAI_API_KEY")
        body = {
            "model": self.options.get("model") or os.environ.get("PAPER2AUDIO_TTS_MODEL", "tts-1"),
            "input": text,
            "voice": self.voice or self.default_voice,
            "response_format": "mp3",
            "speed": self.rate,
        }
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"TTS API {url} returned {e.code}: {e.read().decode(errors='replace')[:500]}") from e

    def synthesize(self, text: str, out_path: Path) -> Path:
        out_path = out_path.with_suffix(self.extension)
        # MP3 streams can be concatenated; audio.render re-encodes the result anyway
        out_path.write_bytes(b"".join(self._request(chunk) for chunk in split_text(text)))
        return out_path
