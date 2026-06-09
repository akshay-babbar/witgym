"""Heuristic router: small talk vs humour practice (no extra LLM call)."""
import re
from typing import Literal

Route = Literal["smalltalk", "humour"]

_SMALLTALK_EXACT = {
    "hi", "hello", "hey", "helo", "hiya", "yo", "sup", "howdy",
    "thanks", "thank you", "thx", "ok", "okay", "bye", "goodbye",
}

_CORE_GREETINGS = ("hi", "hey", "hello", "howdy", "sup", "yo")


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = curr
    return prev[-1]


def _is_greeting_token(token: str) -> bool:
    if len(token) > 6:
        return False
    return any(_levenshtein(token, g) <= 1 for g in _CORE_GREETINGS)

_SMALLTALK_PREFIXES = (
    "hi ", "hello ", "hey ", "what's up", "whats up", "how are you",
    "who are you", "what are you", "what is witgym", "what is this",
    "how does this work", "help", "how do i use",
)

_HUMOUR_SIGNALS = (
    "roast", "comeback", "witty", "funny", "humor", "humour",
    "punchline", "joke", "make it funny", "one-liner", "one liner",
    "practice humour", "practice humor", "sharp line", "wit ",
)


def classify_intent(text: str) -> Route:
    """Return 'smalltalk' for greetings/meta; 'humour' for scenarios or explicit wit asks."""
    normalized = text.strip().lower()
    normalized = re.sub(r"[^\w\s'?]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    if not normalized:
        return "smalltalk"

    if any(sig in normalized for sig in _HUMOUR_SIGNALS):
        return "humour"

    if len(normalized) > 80:
        return "humour"

    if normalized in _SMALLTALK_EXACT:
        return "smalltalk"

    if any(normalized.startswith(p) for p in _SMALLTALK_PREFIXES):
        return "smalltalk"

    if len(normalized.split()) <= 4 and normalized.endswith("?"):
        if any(k in normalized for k in ("who", "what", "how", "help")):
            return "smalltalk"

    tokens = normalized.split()
    if len(tokens) == 1 and _is_greeting_token(tokens[0]):
        return "smalltalk"

    return "humour"


SMALLTALK_REPLY = (
    "I'm WitGym — I help you practice sharper one-liners. "
    "Paste a real situation (work awkwardness, social fail, misplaced confidence) "
    "and I'll generate a punchy line while showing how I reasoned through it in the logs. "
    "No need to ask for jokes explicitly — just describe the moment."
)
