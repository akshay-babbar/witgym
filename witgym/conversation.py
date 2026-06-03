"""Multi-turn conversation history with compression. Implements Principle 5."""
from typing import List, Tuple, Set
from loguru import logger
from witgym import config
from witgym.schemas import ComedyArchetype, ComedyMetadata

COMPRESS_PROMPT = """\
Summarise the following conversation into a compact factual paragraph (max 100 words).
Preserve: who said what themes, key topics, any running jokes or callbacks.
Do NOT include actual jokes — just the situation and topic structure.

CONVERSATION:
{history_text}

Return ONLY the summary paragraph."""


class ConversationManager:
    def __init__(self):
        self.history: List[Tuple[str, str]] = []   # (user, assistant)
        self.used_archetypes: Set[ComedyArchetype] = set()
        self._summary: str = ""  # Compressed summary of old turns
        self._mechanisms: List[Tuple[str, str, str, str, str]] = []  # (user_input, subtext, archetype, tension, distance)

    def add_turn(self, user_input: str, response: str, metadata: ComedyMetadata):
        self.history.append((user_input, response))
        self.used_archetypes.add(metadata.archetype)
        self._mechanisms.append((
            user_input,
            metadata.subtext,
            metadata.archetype.value,
            metadata.tension_type.value,
            metadata.violation_distance.value,
        ))

    def get_context_string(self) -> str:
        """Return the last N turns as mechanism-only context (archetype + tension).

        Mechanism-only context for callbacks — no prior topic text. user_input and subtext are
        stored in _mechanisms but intentionally not exposed here — topic contamination
        makes turn-level evaluation unreliable and anchors the current joke to prior topics.
        Re-enable richer output when multi-turn callback quality is validated.
        """
        recent = self._mechanisms[-config.KEEP_LAST_N_TURNS:]
        lines = []
        if self._summary:
            lines.append(f"[Earlier conversation summary]: {self._summary}")
        for i, (user_in, subtext, arch, tension, dist) in enumerate(recent, 1):
            lines.append(f"Turn -{len(recent) - i + 1}: archetype={arch}, tension={tension}")
        return "\n".join(lines)

    def needs_compression(self, tokenizer) -> bool:
        """Check if token count of full history exceeds 80% of context window."""
        full_text = self.get_context_string()
        token_count = len(tokenizer.encode(full_text))
        threshold = int(config.CONTEXT_WINDOW * config.COMPRESSION_THRESHOLD)
        if token_count > threshold:
            logger.info(f"Context compression triggered: {token_count} tokens > {threshold}")
            return True
        return False

    def compress(self, model, tokenizer):
        """Summarise all but the last N turns. Preserves used_archetypes (stored in set, not text)."""
        from witgym.model import generate_text

        if len(self.history) <= config.KEEP_LAST_N_TURNS:
            return  # Nothing to compress

        old_turns = self.history[:-config.KEEP_LAST_N_TURNS]
        history_text = "\n".join(
            f"User: {u}\nWitGym: {a}" for u, a in old_turns
        )
        prompt = COMPRESS_PROMPT.format(history_text=history_text)
        summary = generate_text(prompt, model, tokenizer, config_type="extract")
        self._summary = summary
        # Keep only last N turns in memory
        self.history = self.history[-config.KEEP_LAST_N_TURNS:]
        logger.info(f"Compressed {len(old_turns)} turns into summary. kept_archetypes={len(self.used_archetypes)}")
