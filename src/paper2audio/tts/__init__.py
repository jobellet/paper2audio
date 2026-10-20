"""TTS backends and audio assembly."""

from __future__ import annotations

from .api import ApiTTS
from .base import TTSBackend
from .edge import EdgeTTS
from .espeak import EspeakTTS
from .kokoro import KokoroTTS
from .piper import PiperTTS
from .say import SayTTS

BACKENDS: dict[str, type[TTSBackend]] = {b.name: b for b in (EdgeTTS, KokoroTTS, PiperTTS, SayTTS, EspeakTTS, ApiTTS)}


def get_backend(name: str, **kwargs) -> TTSBackend:
    if name == "auto":
        for cls in BACKENDS.values():
            if cls.available():
                return cls(**kwargs)
        raise RuntimeError("no TTS backend available; pip install edge-tts, kokoro-onnx or espeakng-loader")
    if name not in BACKENDS:
        raise KeyError(f"unknown TTS backend {name!r}; choose from {', '.join(BACKENDS)}")
    return BACKENDS[name](**kwargs)


__all__ = ["TTSBackend", "BACKENDS", "get_backend"]
