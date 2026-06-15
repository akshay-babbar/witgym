"""Minimal post-pipeline TTS helper using HF Inference Providers."""

from __future__ import annotations

import base64
from functools import lru_cache

from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError, InferenceTimeoutError
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


@lru_cache(maxsize=4)
def _client(provider: str) -> InferenceClient:
    return InferenceClient(
        provider=provider,
        api_key=config.HF_TOKEN or None,
        timeout=config.HF_API_TIMEOUT,
    )


def synthesize_line(text: str, character: str = "AI") -> str | None:
    """Return a data URL for generated audio, or None on failure."""
    if not config.TTS_ENABLED or not config.HF_TOKEN:
        return None

    text = (text or "").strip()
    if not text:
        return None

    voice = _voice_for_character(character or "AI")
    for provider in config.TTS_INFERENCE_PROVIDERS:
        try:
            audio = _client(provider).text_to_speech(
                text=text,
                model=config.TTS_MODEL_ID,
                extra_body={"voice": voice},
            )
            b64 = base64.b64encode(audio).decode("ascii")
            return f"data:{config.TTS_AUDIO_FORMAT};base64,{b64}"
        except (InferenceTimeoutError, HfHubHTTPError) as exc:
            logger.warning(f"TTS failed via provider={provider} voice={voice}: {exc}")
        except Exception as exc:  # pragma: no cover - safety fallback for provider drift
            logger.warning(f"Unexpected TTS failure via provider={provider} voice={voice}: {exc}")

    return None
