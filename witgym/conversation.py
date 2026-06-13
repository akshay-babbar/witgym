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
        self.history: List[Tuple[str, str]] = []
        self.used_archetypes: Set[ComedyArchetype] = set()
        self._summary: str = ""
        self.wit_mechanisms: List[Tuple[str, str, str, str, str]] = []
        self.banter_log: List[Tuple[str, str]] = []
        self.active_mode: str = "quick_wit"
        self.coaching_state: dict = {}

    def set_mode(self, mode: str):
        """Track mode transitions. Reset coaching state when leaving coaching."""
        if mode != self.active_mode and mode != "coaching":
            self.coaching_state = {}
        self.active_mode = mode

    def add_turn(
        self,
        user_input: str,
        response: str,
        metadata: ComedyMetadata,
        mode: str = "quick_wit",
    ):
        self.history.append((user_input, response))
        if mode == "banter":
            self.banter_log.append((user_input, response))
            return

        self.used_archetypes.add(metadata.archetype)
        self.wit_mechanisms.append((
            user_input,
            metadata.subtext,
            metadata.archetype.value,
            metadata.tension_type.value,
            metadata.violation_distance.value,
        ))
        if mode == "coaching":
            self.coaching_state = {}

    def get_context_string(self) -> str:
        """Mechanism-only context from quick_wit/coaching turns — banter excluded."""
        recent = self.wit_mechanisms[-config.KEEP_LAST_N_TURNS:]
        lines = []
        if self._summary:
            lines.append(f"[Earlier conversation summary]: {self._summary}")
        for i, (_user_in, _subtext, arch, tension, _dist) in enumerate(recent, 1):
            lines.append(f"Turn -{len(recent) - i + 1}: archetype={arch}, tension={tension}")
        return "\n".join(lines)

    def needs_compression(self, tokenizer=None) -> bool:
        """Check if token count of full history exceeds 80% of context window."""
        full_text = self.get_context_string()
        if tokenizer is not None:
            token_count = len(tokenizer.encode(full_text))
        else:
            token_count = len(full_text) // 4
        threshold = int(config.CONTEXT_WINDOW * config.COMPRESSION_THRESHOLD)
        if token_count > threshold:
            logger.info(f"Context compression triggered: {token_count} tokens > {threshold}")
            return True
        return False

    def compress(self, model, tokenizer):
        """Summarise all but the last N turns. Preserves used_archetypes (stored in set, not text)."""
        from witgym.model import generate_text

        if len(self.history) <= config.KEEP_LAST_N_TURNS:
            return

        old_turns = self.history[:-config.KEEP_LAST_N_TURNS]
        history_text = "\n".join(
            f"User: {u}\nWitGym: {a}" for u, a in old_turns
        )
        prompt = COMPRESS_PROMPT.format(history_text=history_text)
        summary = generate_text(prompt, model, tokenizer, config_type="extract")
        self._summary = summary
        self.history = self.history[-config.KEEP_LAST_N_TURNS:]
        logger.info(f"Compressed {len(old_turns)} turns into summary. kept_archetypes={len(self.used_archetypes)}")
