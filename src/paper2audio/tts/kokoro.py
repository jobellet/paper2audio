"""Kokoro-82M: offline neural voices (Apache-2.0), good quality, CPU friendly.

pip install kokoro-onnx  ·  models are downloaded on first use (~340 MB) to
$PAPER2AUDIO_MODELS or ~/.cache/paper2audio/kokoro.
Voices: am_michael, am_adam, af_heart, af_bella, bm_george, bf_emma, ...
"""

from __future__ import annotations

import logging
import os
import re
import urllib.request
import wave
from pathlib import Path

from .base import TTSBackend

_RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
_FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")


def model_dir() -> Path:
    return Path(os.environ.get("PAPER2AUDIO_MODELS", Path.home() / ".cache" / "paper2audio" / "kokoro"))


def _ensure_models(directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    for name in _FILES:
        target = directory / name
        if not target.exists():
            print(f"downloading {name} ...")
            tmp = target.with_suffix(".part")
            urllib.request.urlretrieve(_RELEASE + name, tmp)
            tmp.rename(target)
    return directory / _FILES[0], directory / _FILES[1]


class KokoroTTS(TTSBackend):
    name = "kokoro"
    extension = ".wav"
    default_voice = "am_michael"
    _engine = None

    @classmethod
    def available(cls) -> bool:
        try:
            import kokoro_onnx  # noqa: F401
        except ImportError:
            return False
        return True

    def _kokoro(self):
        if KokoroTTS._engine is None:
            import onnxruntime
            from kokoro_onnx import Kokoro

            onnxruntime.disable_telemetry_events()  # onnxruntime phones home by default
            # "words count mismatch" for most paragraphs: harmless, and floods notebooks
            logging.getLogger("phonemizer").setLevel(logging.ERROR)

            model, voices = _ensure_models(Path(self.options.get("model_dir") or model_dir()))
            if "CUDAExecutionProvider" in onnxruntime.get_available_providers() and hasattr(Kokoro, "from_session"):
                # onnxruntime's default exhaustive cuDNN search fails on Kokoro's
                # convolutions with recent cuDNN (9.27 on Colab, Oct 2026); DEFAULT runs
                session = onnxruntime.InferenceSession(str(model), providers=[
                    ("CUDAExecutionProvider", {"cudnn_conv_algo_search": "DEFAULT"}), "CPUExecutionProvider"])
                KokoroTTS._engine = Kokoro.from_session(session, str(voices))
            else:
                KokoroTTS._engine = Kokoro(str(model), str(voices))
        return KokoroTTS._engine

    def synthesize(self, text: str, out_path: Path) -> Path:
        import numpy as np

        engine = self._kokoro()
        voice = self.voice or self.default_voice
        lang = "en-gb" if voice[:1] == "b" else "en-us"
        out_path = out_path.with_suffix(self.extension)
        chunks = []
        sample_rate = 24000
        # paragraph by paragraph keeps memory flat and inserts natural pauses
        for para in (p.strip() for p in re.split(r"\n\s*\n", text)):
            if not para:
                continue
            samples, sample_rate = engine.create(para, voice=voice, speed=self.rate, lang=lang)
            chunks += [samples, np.zeros(int(sample_rate * 0.45), dtype=samples.dtype)]
        audio = np.concatenate(chunks) if chunks else np.zeros(1, dtype="float32")
        pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
        with wave.open(str(out_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(pcm.tobytes())
        return out_path
