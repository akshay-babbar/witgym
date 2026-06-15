"""TTS via HF Inference API (facebook/mms-tts-eng).

Returns:
  data URL string  — audio ready to play
  "tts:loading"    — model cold-starting on HF Spaces (503); caller shows toast
  None             — TTS disabled or empty text
"""

from __future__ import annotations

import base64
import os

from loguru import logger

from witgym import config

_TTS_MODEL = "facebook/mms-tts-eng"
_TTS_API_URL = f"https://api-inference.huggingface.co/models/{_TTS_MODEL}"

TTS_LOADING = "tts:loading"


def _hf_token() -> str | None:
    return os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")


def synthesize_line(text: str, character: str = "AI") -> str | None:
    """Return a data URL, TTS_LOADING sentinel, or None."""
    if not config.TTS_ENABLED:
        return None
    text = (text or "").strip()
    if not text:
        return None

    token = _hf_token()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        import requests
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
        if r.status_code in (503, 500):
            logger.info(f"HF TTS model loading (HTTP {r.status_code})")
            return TTS_LOADING
        logger.warning(f"HF TTS API returned {r.status_code}: {r.text[:200]}")
    except Exception as exc:
        logger.warning(f"HF TTS API error: {exc}")

    return None
