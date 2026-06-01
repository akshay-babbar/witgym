"""WitGym engine — pure function core. No I/O, no UI.

This is the single file that both CLI (main.py) and future Gradio (app.py) call.
"""
import re
from loguru import logger
from sentence_transformers import SentenceTransformer
from witgym import config
from witgym.model import load_model
from witgym.schemas import WitGymResponse
from witgym.extractor import extract_comedy_metadata
from witgym.retriever import load_index, retrieve_scenes
from witgym.generator import generate_candidates, rank_candidates
from witgym.conversation import ConversationManager


def _cap_two_sentences(text: str) -> str:
    """Hard cap at 2 sentences — safety net if model ignores prompt constraint."""
    # Split on sentence-ending punctuation followed by whitespace or end
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    if len(sentences) <= 2:
        return text.strip()
    return " ".join(sentences[:2]).strip()


class WitGymEngine:
    """Stateful engine. Load once, call respond() in a loop."""

    def __init__(self, index_path: str = config.INDEX_PATH):
        logger.info("Initialising WitGymEngine...")
        self.model, self.tokenizer = load_model()
        logger.info(f"Loading embedding model: {config.EMBED_MODEL_ID}")
        self.embed_model = SentenceTransformer(config.EMBED_MODEL_ID, device=config.DEVICE)
        self.index = load_index(index_path)
        self.conversation = ConversationManager()
        logger.success("WitGymEngine ready.")

    def respond(self, user_input: str) -> WitGymResponse:
        """Full two-pass pipeline. Returns WitGymResponse with all intermediate data."""
        # Check compression before adding new turn
        if self.conversation.needs_compression(self.tokenizer):
            self.conversation.compress(self.model, self.tokenizer)

        # PASS 1 — Extract comedy metadata
        metadata = extract_comedy_metadata(user_input, self.model, self.tokenizer)

        # RAG — Retrieve analogous situations (not similar text)
        scenes = retrieve_scenes(
            self.index,
            metadata,
            self.conversation.used_archetypes,
            self.embed_model,
        )

        # PASS 2 — Generate 3 persona candidates
        context_str = self.conversation.get_context_string()
        candidates = generate_candidates(
            user_input, metadata, scenes,
            self.model, self.tokenizer,
            context_str, self.conversation.used_archetypes,
        )

        # RANK — Pick best candidate + hard cap at 2 sentences
        selected = rank_candidates(user_input, candidates, self.model, self.tokenizer)
        selected = _cap_two_sentences(selected)

        # Update state
        self.conversation.add_turn(user_input, selected, metadata.archetype)

        return WitGymResponse(
            metadata=metadata,
            retrieved_scenes=scenes,
            candidates=candidates,
            selected=selected,
        )
