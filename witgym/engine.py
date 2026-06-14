"""WitGym engine — pure function core. No I/O, no UI.

This is the single file that both CLI (main.py) and Gradio (app.py) call.
"""
import re
import time
from typing import Iterator, Optional
from loguru import logger
from sentence_transformers import SentenceTransformer
from witgym import config
from witgym.model import load_model, generate_text
from witgym.schemas import WitGymResponse, PipelineEvent, fallback_metadata
from witgym.extractor import extract_comedy_metadata
from witgym.retriever import load_index, retrieve_scenes
from witgym.generator import (
    generate_candidates_stream,
    rank_candidates,
    compress_winner_stream,
)
from witgym.conversation import ConversationManager
from witgym.router import classify_intent
from witgym.prompts import BANTER_PROMPT, COACHING_ASK_PROMPT, EXPLAIN_PROMPT, SHARPEN_PROMPT, DRILL_KEYS

_shared_resources = None

STREAM_MIN_INTERVAL = 0.08
STREAM_MIN_CHARS = 3


def _cap_two_sentences(text: str) -> str:
    """Hard cap at 2 sentences — safety net if model ignores prompt constraint."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    if len(sentences) <= 2:
        return text.strip()
    return " ".join(sentences[:2]).strip()


def _maybe_emit_token(
    phase: str,
    persona: Optional[str],
    acc: str,
    last_emit: float,
    metadata,
    scenes,
    candidates,
    **extra,
) -> tuple[Optional[PipelineEvent], float, str]:
    now = time.monotonic()
    if len(acc) >= STREAM_MIN_CHARS or (now - last_emit) >= STREAM_MIN_INTERVAL:
        event = PipelineEvent(
            phase=phase,
            persona=persona,
            partial_text=acc,
            metadata=metadata,
            scenes=scenes,
            candidates=candidates,
            **extra,
        )
        return event, now, ""
    return None, last_emit, acc


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
        last_wit_response: Optional[WitGymResponse] = None,
        character: str = "AI",
    ):
        if resources is None:
            logger.info("Initialising WitGymEngine...")
            self._resources = SharedResources(index_path=index_path)
        else:
            self._resources = resources
        self.conversation = conversation or ConversationManager()
        self._last_wit_response: Optional[WitGymResponse] = last_wit_response
        self.character = character
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
        result = None
        for event in self.respond_stream(user_input):
            if event.phase == "done" and event.response is not None:
                result = event.response
        if result is None:
            raise RuntimeError("respond_stream did not emit a done event")
        return result

    def respond_stream(self, user_input: str) -> Iterator[PipelineEvent]:
        """Incremental pipeline for Gradio streaming UI."""
        drill_type = DRILL_KEYS.get(user_input.strip())
        if drill_type and self._last_wit_response is not None:
            yield from self._handle_drill(drill_type, self._last_wit_response)
            return

        if self.conversation.coaching_state.get("awaiting"):
            from witgym.router import _heuristic_route
            if _heuristic_route(user_input) == "banter" or len(user_input.strip()) < 5:
                self.conversation.coaching_state = {}
                yield from self._handle_banter(user_input)
                return
            original = self.conversation.coaching_state.get("original_input", user_input)
            yield from self._run_wit_pipeline(
                user_input,
                route="coaching",
                display_input=user_input,
                coaching_context=(original, user_input),
                include_explanation=True,
            )
            return

        route = classify_intent(user_input, self.model, self.tokenizer)

        if route == "banter":
            yield from self._handle_banter(user_input)
            return

        if route == "coaching":
            yield from self._handle_coaching_ask(user_input)
            return

        self.conversation.set_mode("quick_wit")
        yield from self._run_wit_pipeline(user_input, route="quick_wit")

    def _handle_banter(self, user_input: str) -> Iterator[PipelineEvent]:
        logger.info("Banter route — dynamic reply")
        self.conversation.set_mode("banter")
        self._last_wit_response = None
        reply = generate_text(
            BANTER_PROMPT.format(user_input=user_input),
            self.model,
            self.tokenizer,
            config_type="generate",
        )
        reply = _cap_two_sentences(reply.strip())
        if not reply or reply.lstrip().startswith("1.") or "analyze user" in reply.lower():
            reply = "I'm here for awkward moments and sharp comebacks — toss me a situation."
        metadata = fallback_metadata(user_input)
        self.conversation.add_turn(user_input, reply, metadata, mode="banter")
        response = WitGymResponse(
            metadata=metadata,
            retrieved_scenes=[],
            candidates=[],
            selected=reply,
            route="banter",
        )
        yield PipelineEvent(phase="banter", response=response)
        yield PipelineEvent(phase="done", response=response)

    def _handle_coaching_ask(self, user_input: str) -> Iterator[PipelineEvent]:
        logger.info("Coaching route — Turn 1 clarifying question")
        self.conversation.set_mode("coaching")
        question = generate_text(
            COACHING_ASK_PROMPT.format(user_input=user_input),
            self.model,
            self.tokenizer,
            config_type="generate",
        )
        question = question.strip().split("\n")[0].strip() or "What did you actually say back?"
        self.conversation.coaching_state = {
            "awaiting": True,
            "original_input": user_input,
        }
        metadata = fallback_metadata(user_input)
        response = WitGymResponse(
            metadata=metadata,
            retrieved_scenes=[],
            candidates=[],
            selected=question,
            route="coaching",
            coaching_question=question,
        )
        yield PipelineEvent(phase="coaching_ask", partial_text=question, response=response)
        yield PipelineEvent(phase="done", response=response)

    def _handle_drill(self, drill_type: str, last: WitGymResponse) -> Iterator[PipelineEvent]:
        """Refine the last wit response. Does NOT call add_turn() — no memory pollution."""
        joke = last.selected
        metadata = last.metadata

        if drill_type == "angle":
            yield from self._run_wit_pipeline(
                metadata.surface,
                route=last.route,
                exclude_joke=joke,
            )
            return

        if drill_type == "sharpen":
            situation = last.retrieved_scenes[0].setup if last.retrieved_scenes else metadata.surface
            reply = generate_text(
                SHARPEN_PROMPT.format(situation=situation, joke=joke, subtext=metadata.subtext),
                self.model, self.tokenizer, config_type="generate",
            )
            reply = _cap_two_sentences(reply.strip())
            self._last_wit_response = WitGymResponse(
                metadata=metadata,
                retrieved_scenes=last.retrieved_scenes,
                candidates=last.candidates,
                selected=reply,
                route=last.route,
                winning_persona=last.winning_persona,
            )
        else:  # explain
            reply = generate_text(
                EXPLAIN_PROMPT.format(
                    joke=joke,
                    archetype=metadata.archetype.value,
                    subtext=metadata.subtext,
                ),
                self.model, self.tokenizer, config_type="generate",
            )
            reply = _cap_two_sentences(reply.strip())

        response = WitGymResponse(
            metadata=metadata,
            retrieved_scenes=last.retrieved_scenes,
            candidates=last.candidates,
            selected=reply,
            route="drill",
        )
        yield PipelineEvent(phase="banter", response=response)
        yield PipelineEvent(phase="done", response=response)

    def _run_wit_pipeline(
        self,
        user_input: str,
        route: str = "quick_wit",
        *,
        display_input: Optional[str] = None,
        coaching_context: Optional[tuple[str, str]] = None,
        include_explanation: bool = False,
        exclude_joke: Optional[str] = None,
    ) -> Iterator[PipelineEvent]:
        """CBR-RAG pipeline shared by quick_wit and coaching Turn 2."""
        turn_user_input = display_input or user_input

        if self.conversation.needs_compression(self.tokenizer):
            self.conversation.compress(self.model, self.tokenizer)

        metadata = extract_comedy_metadata(
            user_input,
            self.model,
            self.tokenizer,
            coaching_context=coaching_context,
        )
        yield PipelineEvent(phase="metadata", metadata=metadata)

        if metadata.twist_potential < 4:
            logger.info(f"twist_potential={metadata.twist_potential} < 4 — returning straight reply")
            selected = "Yeah, that tracks."
            self.conversation.add_turn(turn_user_input, selected, metadata, mode=route)
            response = WitGymResponse(
                metadata=metadata,
                retrieved_scenes=[],
                candidates=[],
                selected=selected,
                route=route,
            )
            yield PipelineEvent(
                phase="ranked",
                metadata=metadata,
                scenes=[],
                candidates=[],
                selected=selected,
            )
            yield PipelineEvent(phase="done", response=response)
            return

        scenes = retrieve_scenes(self.index, metadata, self.embed_model)
        yield PipelineEvent(phase="scenes", metadata=metadata, scenes=scenes)

        context_str = self.conversation.get_context_string()
        if exclude_joke:
            context_str = f"[Previous line — do NOT repeat]: {exclude_joke}\n" + context_str
        personas_to_run = ["cynic", "conviction", "absurdist"]
        if metadata.twist_potential <= 6:
            personas_to_run = ["cynic", "absurdist"]
            logger.info(f"twist_potential={metadata.twist_potential} ≤ 6 — cynic + absurdist")
        elif metadata.twist_potential > 8:
            personas_to_run = ["cynic", "absurdist", "bisociate"]
            logger.info(f"twist_potential={metadata.twist_potential} > 8 — bisociate replaces conviction")

        candidates = []
        candidate_acc = ""
        candidate_persona: Optional[str] = None
        last_emit = 0.0
        pending_chars = ""

        for item in generate_candidates_stream(
            user_input, metadata, scenes,
            self.model, self.tokenizer,
            context_str,
            personas_to_run=personas_to_run,
            character=self.character,
        ):
            event_type = item[0]
            payload = item[1] if len(item) == 2 else item[1:]
            if event_type == "candidate_start":
                candidate_acc = ""
                candidate_persona = payload
                yield PipelineEvent(
                    phase="candidate_start",
                    persona=payload,
                    metadata=metadata,
                    scenes=scenes,
                    candidates=list(candidates),
                )
            elif event_type == "candidate_token":
                persona_name, token_piece = payload
                candidate_acc += token_piece
                pending_chars += token_piece
                evt, last_emit, pending_chars = _maybe_emit_token(
                    "candidate_token",
                    persona_name,
                    pending_chars,
                    last_emit,
                    metadata,
                    scenes,
                    list(candidates),
                )
                if evt:
                    evt.partial_text = candidate_acc
                    yield evt
            elif event_type == "candidate_done":
                if pending_chars and candidate_persona:
                    yield PipelineEvent(
                        phase="candidate_token",
                        persona=candidate_persona,
                        partial_text=candidate_acc,
                        metadata=metadata,
                        scenes=scenes,
                        candidates=list(candidates),
                    )
                    pending_chars = ""
                if payload is not None:
                    candidates.append(payload)
                yield PipelineEvent(
                    phase="candidate_done",
                    persona=getattr(payload, "persona", None),
                    metadata=metadata,
                    scenes=scenes,
                    candidates=list(candidates),
                )
            elif event_type == "candidates_complete":
                candidates = payload

        selected = rank_candidates(user_input, metadata, candidates, self.model, self.tokenizer)
        winning_persona = next((c.persona for c in candidates if c.text == selected), None)
        yield PipelineEvent(
            phase="ranked",
            metadata=metadata,
            scenes=scenes,
            candidates=candidates,
            selected=selected,
            winning_persona=winning_persona,
        )

        yield PipelineEvent(phase="final_start", partial_text=selected, winning_persona=winning_persona)
        compressed = selected
        final_acc = ""
        pending_chars = ""
        last_emit = 0.0
        for event_type, payload in compress_winner_stream(selected, self.model, self.tokenizer):
            if event_type == "skip":
                compressed = payload
                yield PipelineEvent(phase="final_token", partial_text=compressed, winning_persona=winning_persona)
            elif event_type == "start":
                final_acc = selected
            elif event_type == "token":
                final_acc += payload
                pending_chars += payload
                evt, last_emit, pending_chars = _maybe_emit_token(
                    "final_token",
                    winning_persona,
                    pending_chars,
                    last_emit,
                    metadata,
                    scenes,
                    candidates,
                    winning_persona=winning_persona,
                )
                if evt:
                    evt.partial_text = final_acc
                    yield evt
            elif event_type == "done":
                if pending_chars:
                    yield PipelineEvent(
                        phase="final_token",
                        partial_text=final_acc,
                        winning_persona=winning_persona,
                    )
                compressed = payload

        selected = _cap_two_sentences(compressed)
        explanation = None
        if include_explanation:
            explanation = generate_text(
                EXPLAIN_PROMPT.format(
                    joke=selected,
                    archetype=metadata.archetype.value,
                    subtext=metadata.subtext,
                ),
                self.model,
                self.tokenizer,
                config_type="generate",
            )
            explanation = _cap_two_sentences(explanation.strip())

        self.conversation.add_turn(turn_user_input, selected, metadata, mode=route)

        response = WitGymResponse(
            metadata=metadata,
            retrieved_scenes=scenes,
            candidates=candidates,
            selected=selected,
            route=route,
            winning_persona=winning_persona,
            explanation=explanation,
        )
        self._last_wit_response = response
        yield PipelineEvent(phase="done", response=response)
