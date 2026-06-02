"""Pass 2 — Generate 3 persona candidates + rank. Core of the comedy engine.

Implements Principles 4, 5, and 6 from the spec.
"""
from typing import List, Set
from collections import Counter
import re as _re
from loguru import logger
from transformers import LogitsProcessorList
from witgym.model import generate_text, ClichePenaltyProcessor
from witgym.schemas import (
    ComedyMetadata, TranscriptScene, CandidateResponse, ComedyArchetype
)

PERSONA_INSTRUCTIONS = {
    "cynic": (
        "You've seen this exact rationalization a hundred times. "
        "You're not angry about it — you're just tired. "
        "State what's actually happening with the weariness of someone who has been right about this for years. "
        "Open with the situation, the consequence, or the outcome as your subject — "
        "lead with something concrete and specific, not a generic observation about the person."
    ),
    "conviction": (
        "You have a firm, specific belief about how this situation works. "
        "State it as established fact with total sincerity. "
        "Do not hedge. Do not qualify. Do not acknowledge any other interpretation exists. "
        "The belief should be wrong in a way that exposes something true about the speaker. "
        "No irony. No wink. Absolute conviction."
    ),
    "absurdist": (
        "You're the only person in the room who sees where this logically ends. "
        "You're not being weird — you're just following the math. "
        "State the inevitable conclusion with the calm of someone reading from a manual. "
        "End with a single, specific concrete image that makes the conclusion visible — "
        "not an abstraction, not a restatement. A physical object, a measurable action, a named institution."
    ),
}

GENERATION_PROMPT = """\
You are a sharp, brief conversational wit engine.
You are responding to: "{user_input}"

SITUATION ANALYSIS:
- What's happening: {surface}
- What they really mean: {subtext}
- The comedy mechanism: {archetype}
- The tension: {tension_type}
- Power dynamic: {power_dynamic}

HUMAN COMEDY PRECEDENT (structurally similar situations — same violation type, NOT same words):
{scenes_block}

PERSONA: {persona_name}
{persona_instruction}

CONSTRAINTS (ALL must be satisfied):
1. Match the VIOLATION TYPE from the precedent — not the words, not the names.
2. NEVER mention character names from the examples (George Costanza, Michael Scott, Dwight, Larry, etc.).
3. NEVER quote or paraphrase any line from the precedent examples.
4. Your entire response is ONE sentence. Two sentences absolute maximum. STOP after the punchline.
5. Lead with the punchline. Do not build up to it.
6. No preamble. No "Here's a response:". No hedging. Start with the wit directly.
7. Stay benign. The violation must be recognizable, not offensive.
8. Do NOT use these violation types already used in this conversation: {used_archetypes_str}
9. Suppress this boring response style: "{obvious_response}"

CONVERSATION CONTEXT (last turns, for callbacks):
{context_str}

Respond now with ONE or TWO sentences. Nothing else."""



def _build_scenes_block(scenes: List[TranscriptScene]) -> str:
    blocks = []
    for s in scenes:
        blocks.append(
            f"  Show: {s.show} | Character: {s.character}\n"
            f"  Situation: {s.setup}\n"
            f"  What they said: {s.response}\n"
            f"  Why it worked: {s.why_it_works}"
        )
    return "\n\n".join(blocks)


def generate_candidates(
    user_input: str,
    metadata: ComedyMetadata,
    scenes: List[TranscriptScene],
    model,
    tokenizer,
    context_str: str,
    used_archetypes: set,
    personas_to_run: List[str] = None,
) -> List[CandidateResponse]:
    """Generate persona candidates (1-3) with ClichePenalty applied.

    personas_to_run: optional subset of PERSONA_INSTRUCTIONS keys.
    None = all three (default). Engine gates this based on twist_potential.
    """
    scenes_block = _build_scenes_block(scenes)
    used_str = ", ".join(a.value for a in used_archetypes) if used_archetypes else "none yet"

    active_personas = {
        name: instr for name, instr in PERSONA_INSTRUCTIONS.items()
        if personas_to_run is None or name in personas_to_run
    }

    cliche_processor = ClichePenaltyProcessor(metadata.obvious_response, tokenizer)
    processors = LogitsProcessorList([cliche_processor])

    candidates = []
    for persona_name, persona_instruction in active_personas.items():
        prompt = GENERATION_PROMPT.format(
            user_input=user_input,
            surface=metadata.surface,
            subtext=metadata.subtext,
            archetype=metadata.archetype.value,
            tension_type=metadata.tension_type.value,
            power_dynamic=metadata.power_dynamic,
            scenes_block=scenes_block,
            persona_name=persona_name.upper(),
            persona_instruction=persona_instruction,
            used_archetypes_str=used_str,
            obvious_response=metadata.obvious_response,
            context_str=context_str or "(no prior context)",
        )

        raw = generate_text(prompt, model, tokenizer, config_type="generate", logits_processors=processors)
        logger.info(f"[{persona_name}] → {raw[:80]}...")

        candidates.append(CandidateResponse(
            persona=persona_name,
            text=raw.strip(),
            violation_type=f"{metadata.archetype.value} via {persona_name} lens",
        ))

        # Lexical carry-forward: ban top content words from previous candidate
        # in all subsequent candidates to force vocabulary divergence
        _STOP_WORDS = {
            "the", "a", "an", "is", "was", "i", "you", "it", "in", "of",
            "to", "and", "that", "this", "they", "their", "are", "be",
            "have", "has", "but", "not", "or", "at", "by", "we", "he", "she",
        }
        words = [
            w.lower() for w in _re.findall(r"\b\w+\b", raw)
            if w.lower() not in _STOP_WORDS and len(w) > 3
        ]
        if words:
            top_words = [w for w, _ in Counter(words).most_common(8)]
            # Add these word token IDs to the penalty set for next candidates
            for word in top_words:
                extra_ids = tokenizer.encode(word, add_special_tokens=False)
                cliche_processor.penalty_ids.update(extra_ids[:2])  # first 2 tokens of each word

    return candidates


RANK_PROMPT = """\
You are judging {n} comedy responses to: "{user_input}"

{candidates_block}

Pick the funniest one using this exact priority order:

1. CONCRETE IMAGE — The best response ends with a single specific, unexpected image or action that makes the human truth visible. Responses using only abstract concepts or bureaucratic jargon with no specific image always lose. "The drill is merely a gentle hug" beats "the patient submitted a fitness statement."
2. SHARPNESS — Does the punchline land on first read without unpacking?
3. TRUTH — Does it name something recognizable that nobody said out loud?
4. BREVITY — If sharpness and image quality are equal, pick the shorter one.

A sharp 20-word line with a specific concrete image beats a flat 10-word line of jargon.
Responses that are purely bureaucratic or purely abstract always lose, regardless of length.

Reply ONLY with a single digit ({valid_digits}). Nothing else."""


def rank_candidates(
    user_input: str,
    candidates: List[CandidateResponse],
    model,
    tokenizer,
) -> str:
    """Rank 3 candidates. Brevity-first prompt + positional shuffle + shortest fallback.

    Positional bias fix: shuffle candidates before presenting to ranker so the
    model can't exploit fixed-position preferences (e.g. always picking slot 3).
    """
    if len(candidates) == 1:
        return candidates[0].text

    # Pre-rank refusal filter: remove any candidate that leaked prompt internals or refused
    # This must happen BEFORE the LLM ranker sees candidates
    _REFUSAL_SIGNALS = (
        "i cannot", "i'm unable", "the prompt requires", "i am unable",
        "i need to clarify", "as an ai", "i can't complete",
    )
    clean_candidates = [
        c for c in candidates
        if not any(sig in c.text.lower() for sig in _REFUSAL_SIGNALS)
    ]
    if len(clean_candidates) == 0:
        logger.warning("All candidates were refusals — returning shortest original")
        w_orig = [len(c.text.split()) for c in candidates]
        return candidates[min(range(len(candidates)), key=lambda i: w_orig[i])].text
    if len(clean_candidates) < len(candidates):
        logger.warning(f"Filtered {len(candidates) - len(clean_candidates)} refusal candidate(s) before ranking")
    candidates = clean_candidates

    if len(candidates) == 1:
        return candidates[0].text

    # Fall through to LLM ranker for both 2 and 3 candidate paths

    # Shuffle into a random order for this call — eliminates positional bias
    import random
    shuffled = list(enumerate(candidates))   # [(orig_idx, candidate), ...]
    random.shuffle(shuffled)

    # Word counts — makes brevity signal machine-readable, not just verbal
    w_shuffled = [len(c.text.split()) for _, c in shuffled]

    # Build dynamic candidates block (works for 2 or 3 candidates)
    digits = [str(i + 1) for i in range(len(shuffled))]
    lines = [
        f"Candidate {i + 1} ({shuffled[i][1].persona}, {w_shuffled[i]} words): {shuffled[i][1].text}"
        for i in range(len(shuffled))
    ]
    prompt = RANK_PROMPT.format(
        n=len(shuffled),
        user_input=user_input,
        candidates_block="\n".join(lines),
        valid_digits="/".join(digits),
    )

    raw = generate_text(prompt, model, tokenizer, config_type="rank")
    shuffle_order = [s[1].persona for s in shuffled]
    logger.debug(f"Rank raw output: '{raw}' | order: {shuffle_order} | words: {w_shuffled}")

    # Map chosen digit back through the shuffle to original candidate
    for ch in raw:
        if ch in digits:
            shuffled_choice = int(ch) - 1
            if 0 <= shuffled_choice < len(shuffled):
                orig_idx, winner = shuffled[shuffled_choice]
                logger.info(f"Ranked: slot={shuffled_choice + 1} → {winner.persona} ({w_shuffled[shuffled_choice]} words)")
                return winner.text

    # Fallback: deterministic shortest across ALL candidates (not shuffled order)
    w_orig = [len(c.text.split()) for c in candidates]
    shortest_idx = min(range(len(candidates)), key=lambda i: w_orig[i])
    logger.warning(f"Ranking failed — shortest fallback: {candidates[shortest_idx].persona} ({w_orig[shortest_idx]} words)")
    return candidates[shortest_idx].text


_COMPRESS_PROMPT = """\
The following comedy line is good but possibly too long. Compress it to ≤18 words while keeping the punchline completely intact.

Original: "{winner}"

Rules:
- The FINAL CLAUSE of the sentence is almost always the punchline. NEVER cut it. Cut from the setup or the middle only.
- If the final clause must be removed to hit ≤18 words, return the original UNCHANGED.
- Do NOT change the joke structure — only remove filler words from the setup.
- Return ONLY the compressed version or the original. No explanation. No quotes."""


def compress_winner(winner: str, model, tokenizer) -> str:
    """Swartzwelder compression pass: generate loose, cut ruthless.

    Skipped if winner is already ≤18 words (already tight).
    Guards: rejects output that is < 4 words or longer than the original.
    """
    if len(winner.split()) <= 18:
        return winner  # Already tight — skip the LLM call

    prompt = _COMPRESS_PROMPT.format(winner=winner)
    compressed = generate_text(prompt, model, tokenizer, config_type="extract")
    compressed = compressed.strip().strip('"').strip("'")

    # Sanity guards: reject if collapsed, expanded, or starts with a fragment marker
    _FRAGMENT_STARTS = (
        "but ", "and ", "or ", "which ", "that ", "because ",
        "while ", "since ", "although ", "if ", "though ",
    )
    if len(compressed.split()) < 4 or len(compressed.split()) >= len(winner.split()):
        logger.debug(f"Compression rejected (collapsed/expanded). Keeping original.")
        return winner
    if compressed.lower().startswith(_FRAGMENT_STARTS):
        logger.debug(f"Compression rejected (fragment start: '{compressed[:20]}'). Keeping original.")
        return winner

    # Grammar-ish guard: reject "telegraphic" outputs that drop almost all function words.
    # This is intentionally crude but catches the common failure mode:
    # "Stared at smoking toaster until fire needs human response registered like software update."
    _FUNCTION_WORDS = {
        "a", "an", "the",
        "to", "of", "for", "in", "on", "at", "with", "as", "by", "from", "into",
        "like", "than", "then", "that", "which", "because", "until", "while", "since",
    }
    words = [w.lower() for w in _re.findall(r"\b\w+\b", compressed)]
    if len(words) >= 8 and not any(w in _FUNCTION_WORDS for w in words):
        logger.debug("Compression rejected (telegraphic/no function words). Keeping original.")
        return winner

    logger.info(f"Compressed: {len(winner.split())}w → {len(compressed.split())}w | '{compressed}'")
    return compressed

