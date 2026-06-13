"""WitGym engine — pure function core. No I/O, no UI.

This is the single file that both CLI (main.py) and Gradio (app.py) call.
"""
import re
from typing import Optional
from loguru import logger
from sentence_transformers import SentenceTransformer
from witgym import config
from witgym.model import load_model
from witgym.schemas import WitGymResponse, fallback_metadata
from witgym.extractor import extract_comedy_metadata
from witgym.retriever import load_index, retrieve_scenes
from witgym.generator import generate_candidates, rank_candidates, compress_winner
from witgym.conversation import ConversationManager
from witgym.router import classify_intent, SMALLTALK_REPLY

_shared_resources = None


def _cap_two_sentences(text: str) -> str:
    """Hard cap at 2 sentences — safety net if model ignores prompt constraint."""
    # Split on sentence-ending punctuation followed by whitespace or end
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    if len(sentences) <= 2:
        return text.strip()
    return " ".join(sentences[:2]).strip()


class SharedResources:
    """Heavy resources loaded once per process (model/tokenizer, embedder, index)."""

    def __init__(self, index_path: str = config.INDEX_PATH):
        logger.info("Loading shared WitGym resources...")
        self.model, self.tokenizer = load_model()
        logger.info(f"Loading embedding model: {config.EMBED_MODEL_ID}")
        self.embed_model = SentenceTransformer(config.EMBED_MODEL_ID, device=config.DEVICE)
        self.index = load_index(index_path)
        logger.success("Shared resources ready.")


def get_shared_resources(index_path: str = config.INDEX_PATH) -> SharedResources:
    """Process-wide singleton for Spaces / Gradio multi-session use."""
    global _shared_resources
    if _shared_resources is None:
        _shared_resources = SharedResources(index_path=index_path)
    return _shared_resources


class WitGymEngine:
    """Stateful engine. Load once, call respond() in a loop."""

    def __init__(
        self,
        index_path: str = config.INDEX_PATH,
        resources: Optional[SharedResources] = None,
        conversation: Optional[ConversationManager] = None,
    ):
        if resources is None:
            logger.info("Initialising WitGymEngine...")
            self._resources = SharedResources(index_path=index_path)
        else:
            self._resources = resources
        self.conversation = conversation or ConversationManager()
        logger.success("WitGymEngine ready.")

    @property
    def model(self):
        return self._resources.model

    @property
    def tokenizer(self):
        return self._resources.tokenizer

    @property
    def embed_model(self):
        return self._resources.embed_model

    @property
    def index(self):
        return self._resources.index

    def respond(self, user_input: str) -> WitGymResponse:
        """Full two-pass pipeline. Returns WitGymResponse with all intermediate data."""
        if classify_intent(user_input) == "smalltalk":
            logger.info("Small-talk route — skipping humour pipeline")
            metadata = fallback_metadata(user_input)
            self.conversation.add_turn(user_input, SMALLTALK_REPLY, metadata)
            return WitGymResponse(
                metadata=metadata,
                retrieved_scenes=[],
                candidates=[],
                selected=SMALLTALK_REPLY,
                route="smalltalk",
            )

        # Check compression before adding new turn
        if self.conversation.needs_compression(self.tokenizer):
            self.conversation.compress(self.model, self.tokenizer)

        # PASS 1 — Extract comedy metadata (includes twist_potential 1-10)
        metadata = extract_comedy_metadata(user_input, self.model, self.tokenizer)

        # GATE — Flat inputs (twist_potential < 4) skip the full wit pipeline.
        # Prevents the uncanny valley: "structured-like-a-joke, lands-as-bizarre"
        # on inputs with no real comedy tension.
        if metadata.twist_potential < 4:
            logger.info(f"twist_potential={metadata.twist_potential} < 4 — returning straight reply")
            selected = "Yeah, that tracks."
            self.conversation.add_turn(user_input, selected, metadata)
            return WitGymResponse(
                metadata=metadata,
                retrieved_scenes=[],
                candidates=[],
                selected=selected,
                route="humour",
            )

        # RAG — Retrieve analogous situations (not similar text)
        scenes = retrieve_scenes(
            self.index,
            metadata,
            self.embed_model,
        )

        # PASS 2 — persona selection by twist_potential
        # ≤6: light inputs — cynic + absurdist only (conviction needs richer tension)
        # 7-8: full standard set — cynic, conviction, absurdist
        # >8: peak inputs — bisociate replaces conviction (domain-pivot vs. within-frame logic)
        context_str = self.conversation.get_context_string()
        personas_to_run = ["cynic", "conviction", "absurdist"]  # default: standard 3
        if metadata.twist_potential <= 6:
            personas_to_run = ["cynic", "absurdist"]
            logger.info(f"twist_potential={metadata.twist_potential} ≤ 6 — cynic + absurdist only")
        elif metadata.twist_potential > 8:
            personas_to_run = ["cynic", "absurdist", "bisociate"]
            logger.info(f"twist_potential={metadata.twist_potential} > 8 — bisociate replaces conviction")

        candidates = generate_candidates(
            user_input, metadata, scenes,
            self.model, self.tokenizer,
            context_str,
            personas_to_run=personas_to_run,
        )

        # RANK — Pick best candidate
        selected = rank_candidates(user_input, metadata, candidates, self.model, self.tokenizer)
        winning_persona = next((c.persona for c in candidates if c.text == selected), None)

        # COMPRESS — Swartzwelder pass: generate loose, cut ruthless (skips if ≤12 words)
        selected = compress_winner(selected, self.model, self.tokenizer)

        # Hard safety cap at 2 sentences
        selected = _cap_two_sentences(selected)

        # Update state
        self.conversation.add_turn(user_input, selected, metadata)

        return WitGymResponse(
            metadata=metadata,
            retrieved_scenes=scenes,
            candidates=candidates,
            selected=selected,
            route="humour",
            winning_persona=winning_persona,
        )
