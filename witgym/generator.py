"""Pass 2 — Generate 3 persona candidates + rank. Core of the comedy engine.

Implements Principles 4, 5, and 6 from the spec.
"""
from typing import List
from loguru import logger
from transformers import LogitsProcessorList
from witgym.model import generate_text, ClichePenaltyProcessor
from witgym.schemas import (
    ComedyMetadata, TranscriptScene, CandidateResponse, ComedyArchetype
)

PERSONA_INSTRUCTIONS = {
    "cynic": (
        "Expose the social hypocrisy or delusion in what was said. "
        "Find the gap between their self-image and reality. "
        "Be sharp but not cruel."
    ),
    "observer": (
        "Say the thing everyone sees but nobody says. "
        "Point at the recognizable truth they didn't intend to reveal. "
        "Be precise, not mean."
    ),
    "absurdist": (
        "Follow the logic of their situation to its most surreal honest conclusion. "
        "Stay grounded in their reality, then take one step too far. "
        "No random weirdness — logical weirdness only."
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
) -> List[CandidateResponse]:
    """Generate 3 candidates — one per persona — with ClichePenalty applied."""
    scenes_block = _build_scenes_block(scenes)
    used_str = ", ".join(a.value for a in used_archetypes) if used_archetypes else "none yet"

    cliche_processor = ClichePenaltyProcessor(metadata.obvious_response, tokenizer)
    processors = LogitsProcessorList([cliche_processor])

    candidates = []
    for persona_name, persona_instruction in PERSONA_INSTRUCTIONS.items():
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

    return candidates


RANK_PROMPT = """\
You are judging three comedy responses to: "{user_input}"

Candidate 1 ({p1}, {w1} words): {c1}
Candidate 2 ({p2}, {w2} words): {c2}
Candidate 3 ({p3}, {w3} words): {c3}

Pick the funniest one. Judge in this exact order of priority:

1. BREVITY — Shorter is almost always funnier. Compression is comedy. The correct answer is almost never the longest one.
2. SHARPNESS — Does the punchline land immediately, without unpacking? Can you feel it the first time you read it?
3. TRUTH — Does it say something recognizable that nobody said out loud?
4. BENIGN — Slightly uncomfortable but not offensive.

The correct answer is almost always NOT the longest or most complex one.
If two candidates are close on sharpness, always pick the shorter one.

Reply ONLY with a single digit: 1, 2, or 3. Nothing else."""


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

    # Shuffle into a random order for this call — eliminates positional bias
    import random
    shuffled = list(enumerate(candidates))   # [(orig_idx, candidate), ...]
    random.shuffle(shuffled)

    # Word counts — makes brevity signal machine-readable, not just verbal
    w_shuffled = [len(c.text.split()) for _, c in shuffled]

    prompt = RANK_PROMPT.format(
        user_input=user_input,
        p1=shuffled[0][1].persona, w1=w_shuffled[0], c1=shuffled[0][1].text,
        p2=shuffled[1][1].persona, w2=w_shuffled[1], c2=shuffled[1][1].text,
        p3=shuffled[2][1].persona, w3=w_shuffled[2], c3=shuffled[2][1].text,
    )

    raw = generate_text(prompt, model, tokenizer, config_type="rank")
    shuffle_order = [s[1].persona for s in shuffled]
    logger.debug(f"Rank raw output: '{raw}' | order: {shuffle_order} | words: {w_shuffled}")

    # Map chosen digit back through the shuffle to original candidate
    for ch in raw:
        if ch in "123":
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

