"""TTS via HF Inference API (facebook/mms-tts-eng), Kokoro fallback for local dev."""

from __future__ import annotations

import base64
import io
import os
import wave
from threading import Lock

import numpy as np
from loguru import logger

from witgym import config

# ── HF Inference API ──────────────────────────────────────────────────────────

_TTS_MODEL = "facebook/mms-tts-eng"
_TTS_API_URL = f"https://api-inference.huggingface.co/models/{_TTS_MODEL}"


def _hf_token() -> str | None:
    return (
        os.getenv("HF_TOKEN")
        or os.getenv("HUGGING_FACE_HUB_TOKEN")
    )


def _synthesize_via_api(text: str) -> str | None:
    """Call HF Inference API, return base64 data URL or None."""
    token = _hf_token()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        import requests  # transitive dep via huggingface-hub
        r = requests.post(
            _TTS_API_URL,
            headers=headers,
            json={"inputs": text},
            timeout=12,
        )
        if r.status_code == 200 and r.content:
            ct = r.headers.get("content-type", "audio/flac").split(";")[0].strip()
            b64 = base64.b64encode(r.content).decode("ascii")
            return f"data:{ct};base64,{b64}"
        logger.warning(f"HF TTS API returned {r.status_code}: {r.text[:200]}")
    except Exception as exc:
        logger.warning(f"HF TTS API error: {exc}")
    return None


# ── Kokoro local fallback (used when no network / local dev) ──────────────────

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
            logger.info("Loading Kokoro-82M pipeline (local fallback)…")
            _pipeline = KPipeline(lang_code="a")
            logger.info("Kokoro-82M ready.")
        except Exception as exc:
            logger.error(f"Failed to load Kokoro pipeline: {exc}")
            _pipeline = None
    return _pipeline


def _synthesize_via_kokoro(text: str, character: str) -> str | None:
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


# ── Public API ────────────────────────────────────────────────────────────────

def synthesize_line(text: str, character: str = "AI") -> str | None:
    """Return a data URL for the synthesized audio, or None on failure."""
    if not config.TTS_ENABLED:
        return None
    text = (text or "").strip()
    if not text:
        return None

    # Try HF API first (fast, works on Spaces)
    result = _synthesize_via_api(text)
    if result:
        return result

    # Kokoro fallback (local dev, character-specific voices)
    logger.info("HF API TTS unavailable, falling back to Kokoro")
    return _synthesize_via_kokoro(text, character)
