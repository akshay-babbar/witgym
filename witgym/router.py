"""LLM intent router with heuristic fallback when provider returns thinking output."""
import re
from typing import Literal

from loguru import logger
from witgym.prompts import ROUTER_PROMPT

Route = Literal["banter", "quick_wit", "coaching"]

_VALID_ROUTES = frozenset({"banter", "quick_wit", "coaching"})

_COACHING_SIGNALS = (
    "help me", "how do i respond", "how would you handle", "coach me", "teach me",
    "can you explain", "what should i say when", "how should i respond",
)

_HUMOUR_SIGNALS = (
    "roast", "comeback", "witty", "funny", "humor", "humour",
    "punchline", "joke", "make it funny", "one-liner", "one liner",
    "practice humour", "practice humor", "sharp line",
)

_BANTER_EXACT = {
    "hi", "hello", "hey", "helo", "hiya", "yo", "sup", "howdy",
    "thanks", "thank you", "thx", "ok", "okay", "bye", "goodbye",
}


def _looks_like_thinking(raw: str) -> bool:
    lower = raw.lower()
    return (
        "thinking process" in lower
        or "analyze user" in lower
        or "**analyze" in lower
        or raw.lstrip().startswith("1.")
    )


def _heuristic_route(text: str) -> Route:
    normalized = text.strip().lower()
    normalized = re.sub(r"[^\w\s'?]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    if not normalized:
        return "banter"

    if any(sig in normalized for sig in _COACHING_SIGNALS):
        return "coaching"

    if any(sig in normalized for sig in _HUMOUR_SIGNALS):
        return "quick_wit"

    if normalized in _BANTER_EXACT:
        return "banter"

    if len(normalized.split()) <= 3 and normalized.endswith("?"):
        if any(k in normalized for k in ("who", "what", "how", "why")):
            if "respond" not in normalized and "say" not in normalized:
                return "banter"

    if len(normalized) <= 12 and normalized.replace(" ", "").isdigit():
        return "banter"

    if "book" in normalized and "flight" in normalized:
        return "banter"

    if len(normalized) > 40 or " " in normalized:
        return "quick_wit"

    return "banter"


def _parse_route(raw: str) -> Route | None:
    normalized = raw.strip().lower()
    for label in ("quick_wit", "coaching", "banter"):
        if label in normalized:
            return label  # type: ignore[return-value]
    for token in normalized.replace(",", " ").replace("|", " ").split():
        cleaned = token.strip(".,!\"'`")
        if cleaned in _VALID_ROUTES:
            return cleaned  # type: ignore[return-value]
    return None


def classify_intent(text: str, model, tokenizer) -> Route:
    """Route banter | quick_wit | coaching via LLM, with heuristic fallback."""
    from witgym.model import generate_text

    if not text.strip():
        return "banter"

    heuristic = _heuristic_route(text)

    raw = generate_text(
        ROUTER_PROMPT.format(user_input=text.strip()),
        model,
        tokenizer,
        config_type="rank",
    )
    route = _parse_route(raw)
    if route is None or _looks_like_thinking(raw):
        logger.warning(
            f"Router LLM unusable ({raw[:60]!r}…); heuristic fallback → {heuristic!r}"
        )
        route = heuristic
    else:
        logger.info(f"Router: {route!r} for input {text[:60]!r}")
    return route
