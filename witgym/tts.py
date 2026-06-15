"""Local Kokoro-82M TTS — runs on-device, no API calls, no provider dependency."""

from __future__ import annotations

import base64
import io
import wave
from threading import Lock

import numpy as np
from loguru import logger

from witgym import config

_FEMALE_VOICES = {
    "AI": "af_bella",
    "Pam": "af_bella",
    "Angela": "bf_emma",
    "Kelly": "af_nicole",
}

_MALE_VOICES = {
    "Michael": "am_michael",
    "Dwight": "am_fenrir",
    "Jim": "am_puck",
    "Kevin": "bm_george",
    "Andy": "am_michael",
    "Stanley": "bm_george",
    "Ryan": "am_puck",
}


def _voice_for_character(character: str) -> str:
    if character in _FEMALE_VOICES:
        return _FEMALE_VOICES[character]
    if character in _MALE_VOICES:
        return _MALE_VOICES[character]
    return _FEMALE_VOICES["AI"]


_pipeline = None
_pipeline_lock = Lock()


def _get_pipeline():
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    with _pipeline_lock:
        if _pipeline is not None:
            return _pipeline
        try:
            from kokoro import KPipeline
            logger.info("Loading Kokoro-82M pipeline (first call)…")
            _pipeline = KPipeline(lang_code="a")
            logger.info("Kokoro-82M ready.")
        except Exception as exc:
            logger.error(f"Failed to load Kokoro pipeline: {exc}")
            _pipeline = None
    return _pipeline


def synthesize_line(text: str, character: str = "AI") -> str | None:
    """Return a WAV data URL for the text, or None on failure."""
    if not config.TTS_ENABLED:
        return None
    text = (text or "").strip()
    if not text:
        return None

    pipeline = _get_pipeline()
    if pipeline is None:
        return None

    voice = _voice_for_character(character or "AI")
    try:
        chunks = [audio for _, _, audio in pipeline(text, voice=voice)]
        if not chunks:
            return None
        audio = np.concatenate(chunks)
        pcm = (audio * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(pcm.tobytes())
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:audio/wav;base64,{b64}"
    except Exception as exc:
        logger.warning(f"Kokoro TTS failed voice={voice}: {exc}")
        return None
