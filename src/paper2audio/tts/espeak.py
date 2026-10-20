"""eSpeak NG: fully offline, installable with pip (`espeakng-loader`), robotic.

Uses the system `espeak-ng` command if present, otherwise the shared library
bundled in the `espeakng-loader` wheel through ctypes.
"""

from __future__ import annotations

import ctypes
import shutil
import subprocess
import wave
from pathlib import Path

from .base import TTSBackend

_SYNCHRONOUS = 2
_RATE = 1
_CHARS_UTF8 = 1
_POS_CHARACTER = 1

_lib = None
_sample_rate = 0
_buffer: list[bytes] = []
_CALLBACK = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p)


@_CALLBACK
def _collect(wav, n, _events):
    if n > 0:
        _buffer.append(ctypes.string_at(wav, n * 2))
    return 0


def _load():
    global _lib, _sample_rate
    if _lib is None:
        import espeakng_loader

        lib = ctypes.CDLL(espeakng_loader.get_library_path())
        data_parent = str(Path(espeakng_loader.get_data_path()).parent).encode()
        _sample_rate = lib.espeak_Initialize(_SYNCHRONOUS, 0, data_parent, 0)
        if _sample_rate <= 0:
            raise RuntimeError("espeak_Initialize failed")
        lib.espeak_SetSynthCallback(_collect)
        _lib = lib
    return _lib


class EspeakTTS(TTSBackend):
    name = "espeak"
    extension = ".wav"

    @classmethod
    def available(cls) -> bool:
        if shutil.which("espeak-ng"):
            return True
        try:
            import espeakng_loader  # noqa: F401
        except ImportError:
            return False
        return True

    def synthesize(self, text: str, out_path: Path) -> Path:
        out_path = out_path.with_suffix(self.extension)
        wpm = int(175 * self.rate)
        exe = shutil.which("espeak-ng")
        if exe:
            subprocess.run([exe, "-v", self.voice or "en-us", "-s", str(wpm), "-w", str(out_path)],
                           input=text.encode(), check=True)
            return out_path
        lib = _load()
        lib.espeak_SetVoiceByName((self.voice or "en-us").encode())
        lib.espeak_SetParameter(_RATE, wpm, 0)
        _buffer.clear()
        data = text.encode("utf-8") + b"\0"
        lib.espeak_Synth(data, len(data), 0, _POS_CHARACTER, 0, _CHARS_UTF8, None, None)
        lib.espeak_Synchronize()
        with wave.open(str(out_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(_sample_rate)
            w.writeframes(b"".join(_buffer))
        return out_path
