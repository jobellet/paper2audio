"""TTS backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class TTSBackend(ABC):
    name: str = "base"
    #: file extension the backend writes natively
    extension: str = ".wav"
    #: True if several clips can be synthesised at once (network engines)
    concurrent: bool = False

    def __init__(self, voice: str | None = None, rate: float = 1.0, **options):
        self.voice = voice
        self.rate = rate  # 1.0 = normal speed
        self.options = options

    @abstractmethod
    def synthesize(self, text: str, out_path: Path) -> Path:
        """Write `text` as audio to `out_path` (with `self.extension`)."""

    @classmethod
    def available(cls) -> bool:
        return True
