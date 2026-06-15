"""Pass 2 — Generate 3 persona candidates + rank. Core of the comedy engine.

Implements Principles 4, 5, and 6 from the spec.
"""
from typing import Iterator, List, Set
from collections import Counter
import re as _re
import json as _json
from loguru import logger
from transformers import LogitsProcessorList, NoBadWordsLogitsProcessor
from witgym.model import generate_text, generate_text_stream, ClichePenaltyProcessor, _strip_thinking
from witgym import config
from witgym.schemas import (
    ComedyMetadata, TranscriptScene, CandidateResponse,
)
from witgym.prompts import CHARACTER_VOICE_MODIFIERS

PERSONA_INSTRUCTIONS = {
    "cynic": (
        "PATHWAY SELECTION — pick one silently before generating:\n"
        "  PATH A (subtext contains avoidance, spiral, or self-protection): "
        "Name the specific function the behavior is performing. "
        "What is it protecting? What does it cost? State it precisely.\n"
        "  PATH B (subtext contains status claim or competence assertion): "
        "State the actual outcome as if it has already become concrete. Past tense. "
        "One specific image or action anchored in the user's situation. "
        "Reuse nouns/verbs from surface or subtext. Do NOT import a new setting, industry, or object.\n"
        "You pick the path silently. Output only the wit line — never the path label.\n\n"
        "You've seen this exact rationalization a hundred times. "
        "You're not angry — you're just tired. "
        "Lead with something concrete: the situation, the consequence, the outcome. "
        "Not a generic observation about the person."
    ),
    "conviction": (
        "You have a firm, specific belief about how this situation works. "
        "State it as established fact with total sincerity. "
        "Do not hedge. Do not qualify. Do not acknowledge any other interpretation exists. "
        "The belief should be wrong in a way that exposes something true about the speaker. "
        "No irony. No wink. Absolute conviction.\n\n"
        "Worldview seed — pick the one matching the archetype field above and speak from inside it:\n"
        "- status_assertion: 'Success is a social contract. Claiming it publicly is legally binding.'\n"
        "- self_delusion: 'Self-awareness is a hobby. Confidence is infrastructure.'\n"
        "- anxiety_escalation: 'Being prepared means announcing every possible failure in advance.'\n"
        "- social_fail: 'Social norms are suggestions. The boldest person defines the room.'\n"
        "- power_inversion: 'The person who asks the fewest questions is clearly the most senior.'\n"
        "- misplaced_conf: 'Certainty is competence. You can always correct course once everyone agrees.'\n"
        "Inhabit that worldview completely. Do not name it."
    ),
    "absurdist": (
        "PATHWAY SELECTION — pick one silently before generating:\n"
        "  PATH A (subtext contains fear, avoidance, or escalation logic — anxiety_escalation or existential tension): "
        "Follow the anxiety's own internal logic to its physical inevitable endpoint. "
        "Name the specific form: a concrete image, measurable action, or physical object "
        "from the user's situation.\n"
        "  PATH B (connector field is non-null): "
        "Land on the second meaning of the connector word, but keep the setting and nouns inside the user's situation.\n"
        "You pick the path silently. Output only the wit line — never the path label.\n\n"
        "You're the only person in the room who sees where this logically ends. "
        "You're not being weird — you're just following the math. "
        "End with a single concrete image anchored in the user's situation. "
        "Not an abstraction. A physical object or measurable action the input already implies."
    ),
    "bisociate": (
        "PATHWAY SELECTION — pick one silently before generating:\n"
        "  PATH A (connector field is non-null): "
        "Your punchline must land on the second meaning of the connector word. "
        "The setup's expected reading of that word is the straight path. You take the other one.\n"
        "  PATH B (connector is null): "
        "Apply the dominant verb from the subtext (use the exact verb/action) to the most structurally incongruous object from daily life. "
        "Deliver from inside that object's world, as if you've been there all along. "
        "Do not name the parallel. Do not explain the connection.\n"
        "You pick the path silently. Output only the wit line — never the path label.\n\n"
        "You notice that what they're describing is not unique to their situation. "
        "The same need, avoidance, or craving exists somewhere completely different. "
        "State the parallel as if it is obvious and everyone already knows this. "
        "Do not reference any topic already mentioned in the conversation context."
    ),
}

GENERATION_PROMPT = """\
You're in the writer's room. Someone just said: "{user_input}" — what's the line?

SITUATION ANALYSIS:
- What's happening: {surface}
- What they really mean: {subtext}
- The comedy mechanism: {archetype}
- Archetype confidence: {archetype_confidence}/10
- The tension: {tension_type}
- Power dynamic: {power_dynamic}
- Speaker strategy: {speaker_strategy}
- Connector word (two readings, if present): {connector}

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
8. The boring version of this would be: "{obvious_response}". The better version doesn't avoid that — it finds the specific truth underneath it. What is the precise mechanism they are using? What does it cost them that they haven't named?
9. NEVER output "PATH A", "PATH B", "PATHWAY SELECTION", or any routing label. Output ONLY the comedy line.
10. If any phrase from the precedent block appears in your line, rewrite it — use the mechanism only, never the precedent's wording.
11. DOMAIN ANCHOR — Do not introduce institutions, departments, legal process, or workplace nouns unless already implied by surface, subtext, or power_dynamic. Prefer nouns from the user input.
12. Treat unexpected domain shifts (HR, litigation, supply chain, middle-manager hierarchy) as defects unless the input already implies them.
13. CROSS-DOMAIN PIVOT — Only BISOCIATE may introduce a new domain/object. If persona is not BISOCIATE, stay inside the user's world. If BISOCIATE pivots domains, the pivot must be discoverable from a verb/action explicitly present in the subtext or from the connector’s second meaning; otherwise rewrite.

CONVERSATION CONTEXT (last turns, for callbacks):
{context_str}
{character_modifier}
Respond now with ONE or TWO sentences. Nothing else."""


def _normalize_for_overlap(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for n-gram checks."""
    text = text.lower()
    text = _re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def _ngrams(words: List[str], n: int) -> Set[str]:
    if len(words) < n:
        return set()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def _precedent_prompt_texts(scenes: List[TranscriptScene]) -> List[str]:
    """Text actually injected into the generation prompt (overlap guard surface)."""
    return [s.why_it_works for s in scenes]


def _copies_retrieved_phrase(candidate: str, scenes: List[TranscriptScene], n: int) -> bool:
    """True if candidate shares an n-word contiguous phrase with precedent prompt text."""
    cand_words = _normalize_for_overlap(candidate).split()
    if len(cand_words) < n:
        return False
    cand_grams = _ngrams(cand_words, n)
    if not cand_grams:
        return False
    for source in _precedent_prompt_texts(scenes):
        src_grams = _ngrams(_normalize_for_overlap(source).split(), n)
        if cand_grams & src_grams:
            return True
    return False


def _build_scenes_block(scenes: List[TranscriptScene]) -> str:
    """Mechanism-only precedent — tags + why_it_works, no raw setup or dialogue."""
    blocks = []
    for s in scenes:
        blocks.append(
            f"  Archetype: {s.archetype.value} | Tension: {s.tension_type.value} | "
            f"Distance: {s.violation_distance.value}\n"
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
    personas_to_run: List[str] = None,
    character: str = "AI",
) -> List[CandidateResponse]:
    """Generate persona candidates (1-3) with ClichePenalty applied.

    personas_to_run: optional subset of PERSONA_INSTRUCTIONS keys.
    None = all three (default). Engine gates this based on twist_potential.
    character: Office character name for voice modifier, or "AI" for default.
    """
    scenes_block = _build_scenes_block(scenes)
    character_modifier = CHARACTER_VOICE_MODIFIERS.get(character, "")

    active_personas = {
        name: instr for name, instr in PERSONA_INSTRUCTIONS.items()
        if personas_to_run is None or name in personas_to_run
    }

    processors = None
    cliche_processor = None
    if config.LLM_BACKEND == "local" and tokenizer is not None:
        cliche_processor = ClichePenaltyProcessor(metadata.obvious_response, tokenizer)
        processors = LogitsProcessorList([cliche_processor])
        if config.ENABLE_BAD_WORD_GUARD:
            bad_words_ids = [
                tokenizer.encode(phrase, add_special_tokens=False)
                for phrase in config.BAD_WORD_PHRASES
            ]
            processors.append(NoBadWordsLogitsProcessor(bad_words_ids, eos_token_id=tokenizer.eos_token_id))

    candidates = []
    ngram_n = config.OVERLAP_NGRAM_SIZE
    last_raw = None
    last_persona = None
    for persona_name, persona_instruction in active_personas.items():
        prompt = GENERATION_PROMPT.format(
            user_input=user_input,
            surface=metadata.surface,
            subtext=metadata.subtext,
            archetype=metadata.archetype.value,
            archetype_confidence=metadata.archetype_confidence,
            tension_type=metadata.tension_type.value,
            power_dynamic=metadata.power_dynamic,
            speaker_strategy=metadata.speaker_strategy or "none",
            connector=metadata.connector or "none",
            scenes_block=scenes_block,
            persona_name=persona_name.upper(),
            persona_instruction=persona_instruction,
            obvious_response=metadata.obvious_response,
            context_str=context_str or "(no prior context)",
            character_modifier=character_modifier,
        )

        raw = generate_text(prompt, model, tokenizer, config_type="generate", logits_processors=processors)
        last_raw, last_persona = raw, persona_name
        if any(phrase in raw for phrase in config.BAD_WORD_PHRASES):
            logger.warning(f"[{persona_name}] leaked routing label — dropping candidate")
            continue
        if config.ENABLE_OVERLAP_GUARD and _copies_retrieved_phrase(raw, scenes, ngram_n):
            logger.warning(f"[{persona_name}] copies precedent phrasing — dropping candidate")
            continue

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
        if words and cliche_processor is not None and tokenizer is not None:
            top_words = [w for w, _ in Counter(words).most_common(8)]
            for word in top_words:
                extra_ids = tokenizer.encode(word, add_special_tokens=False)
                cliche_processor.penalty_ids.update(extra_ids[:2])

    if not candidates and last_raw:
        logger.warning(f"All candidates dropped — keeping last line from {last_persona}")
        candidates.append(CandidateResponse(
            persona=last_persona,
            text=last_raw.strip(),
            violation_type=f"{metadata.archetype.value} via {last_persona} lens",
        ))

    return candidates


def generate_candidates_stream(
    user_input: str,
    metadata: ComedyMetadata,
    scenes: List[TranscriptScene],
    model,
    tokenizer,
    context_str: str,
    personas_to_run: List[str] = None,
    character: str = "AI",
) -> Iterator[tuple[str, object]]:
    """Stream persona drafts. Yields (event, payload) tuples for engine/UI."""
    scenes_block = _build_scenes_block(scenes)
    character_modifier = CHARACTER_VOICE_MODIFIERS.get(character, "")
    active_personas = {
        name: instr for name, instr in PERSONA_INSTRUCTIONS.items()
        if personas_to_run is None or name in personas_to_run
    }

    processors = None
    cliche_processor = None
    if config.LLM_BACKEND == "local" and tokenizer is not None:
        cliche_processor = ClichePenaltyProcessor(metadata.obvious_response, tokenizer)
        processors = LogitsProcessorList([cliche_processor])
        if config.ENABLE_BAD_WORD_GUARD:
            bad_words_ids = [
                tokenizer.encode(phrase, add_special_tokens=False)
                for phrase in config.BAD_WORD_PHRASES
            ]
            processors.append(NoBadWordsLogitsProcessor(bad_words_ids, eos_token_id=tokenizer.eos_token_id))

    candidates: List[CandidateResponse] = []
    ngram_n = config.OVERLAP_NGRAM_SIZE
    last_raw = None
    last_persona = None

    for persona_name, persona_instruction in active_personas.items():
        prompt = GENERATION_PROMPT.format(
            user_input=user_input,
            surface=metadata.surface,
            subtext=metadata.subtext,
            archetype=metadata.archetype.value,
            archetype_confidence=metadata.archetype_confidence,
            tension_type=metadata.tension_type.value,
            power_dynamic=metadata.power_dynamic,
            speaker_strategy=metadata.speaker_strategy or "none",
            connector=metadata.connector or "none",
            scenes_block=scenes_block,
            persona_name=persona_name.upper(),
            persona_instruction=persona_instruction,
            obvious_response=metadata.obvious_response,
            context_str=context_str or "(no prior context)",
            character_modifier=character_modifier,
        )

        yield ("candidate_start", persona_name)
        raw_parts: List[str] = []
        for token in generate_text_stream(prompt, model, tokenizer, config_type="generate", logits_processors=processors):
            raw_parts.append(token)
            yield ("candidate_token", persona_name, token)

        raw = _strip_thinking("".join(raw_parts))
        last_raw, last_persona = raw, persona_name
        if any(phrase in raw for phrase in config.BAD_WORD_PHRASES):
            logger.warning(f"[{persona_name}] leaked routing label — dropping candidate")
            yield ("candidate_done", None)
            continue
        if config.ENABLE_OVERLAP_GUARD and _copies_retrieved_phrase(raw, scenes, ngram_n):
            logger.warning(f"[{persona_name}] copies precedent phrasing — dropping candidate")
            yield ("candidate_done", None)
            continue

        logger.info(f"[{persona_name}] → {raw[:80]}...")
        candidate = CandidateResponse(
            persona=persona_name,
            text=raw.strip(),
            violation_type=f"{metadata.archetype.value} via {persona_name} lens",
        )
        candidates.append(candidate)
        yield ("candidate_done", candidate)

        _STOP_WORDS = {
            "the", "a", "an", "is", "was", "i", "you", "it", "in", "of",
            "to", "and", "that", "this", "they", "their", "are", "be",
            "have", "has", "but", "not", "or", "at", "by", "we", "he", "she",
        }
        words = [
            w.lower() for w in _re.findall(r"\b\w+\b", raw)
            if w.lower() not in _STOP_WORDS and len(w) > 3
        ]
        if words and cliche_processor is not None and tokenizer is not None:
            top_words = [w for w, _ in Counter(words).most_common(8)]
            for word in top_words:
                extra_ids = tokenizer.encode(word, add_special_tokens=False)
                cliche_processor.penalty_ids.update(extra_ids[:2])

    if not candidates and last_raw:
        logger.warning(f"All candidates dropped — keeping last line from {last_persona}")
        candidate = CandidateResponse(
            persona=last_persona,
            text=last_raw.strip(),
            violation_type=f"{metadata.archetype.value} via {last_persona} lens",
        )
        candidates.append(candidate)
        yield ("candidate_done", candidate)

    yield ("candidates_complete", candidates)


RANK_PROMPT = """\
You are judging {n} comedy responses to: "{user_input}"
Connector word (has two simultaneous readings in the input): "{connector}"
Extracted context:
- subtext: "{subtext}"
- archetype: "{archetype}"
- tension_type: "{tension_type}"
- speaker_strategy: "{speaker_strategy}"

{candidates_block}

Pick the funniest one using this exact priority order:

1. DOMAIN ANCHOR — Prefer lines that stay inside the user's world from surface/subtext. Down-rank candidates that import HR, legal process, supply chain, new departments, or institutional bureaucracy unless the user input already implies them. A grounded but slightly softer punchline beats a sharper line that drifts into an unsupported external domain.
2. FINAL CLAUSE — The punchline is always the last clause. Judge the quality of the ENDING, not the setup. A sharp ending on a flat setup beats a flat ending on a sharp setup. The best ending is a single specific, unexpected image or action that makes the human truth visible. Responses where the final clause is abstract, bureaucratic, or jargon always lose.
3. CONNECTOR — If a response lands on the second meaning of the connector word in its punchline, this is a strong quality signal. It means the wit is structurally grounded in the input, not floating free.
4. SHARPNESS — Does the punchline land on first read without unpacking?
5. TRUTH — Does it name something recognizable that nobody said out loud?
6. BREVITY — If sharpness and image quality are equal, pick the shorter one.

A sharp 20-word line with a specific concrete ending beats a flat 10-word line of jargon.
Responses that are purely bureaucratic or purely abstract always lose, regardless of length.

Final-word test: Read the last word of each candidate. If the last word is an abstract noun, institutional term, or connector word (e.g. 'their', 'itself', 'you', 'it', 'this', 'that'), the punchline is buried — rank it below candidates whose final word is a concrete noun, unexpected verb, or specific image, even if the rest of that line is stronger.

Reply ONLY with a single digit ({valid_digits}). Nothing else."""


def rank_candidates(
    user_input: str,
    metadata: ComedyMetadata,
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
        connector=(metadata.connector or "none"),
        subtext=metadata.subtext,
        archetype=metadata.archetype.value,
        tension_type=metadata.tension_type.value,
        speaker_strategy=metadata.speaker_strategy or "none",
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
The following comedy line is good but possibly too long. Compress it to ≤22 words while keeping the punchline completely intact.

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
    if len(winner.split()) <= 22:
        return winner  # Already tight — skip the LLM call

    prompt = _COMPRESS_PROMPT.format(winner=winner)
    compressed = generate_text(prompt, model, tokenizer, config_type="extract")
    compressed = compressed.strip().strip('"').strip("'")

    # Defensive JSON parse: model sometimes wraps output as {"compressed_line": "..."}
    if compressed.startswith("{"):
        try:
            obj = _json.loads(compressed)
            compressed = next(iter(obj.values())) if obj else compressed
        except Exception:
            pass
    compressed = str(compressed).strip().strip('"').strip("'")

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


def compress_winner_stream(winner: str, model, tokenizer) -> Iterator[tuple[str, str]]:
    """Stream compress pass tokens, or yield skip when already tight."""
    if len(winner.split()) <= 22:
        yield ("skip", winner)
        return

    prompt = _COMPRESS_PROMPT.format(winner=winner)
    yield ("start", winner)
    parts: List[str] = []
    for token in generate_text_stream(prompt, model, tokenizer, config_type="extract"):
        parts.append(token)
        yield ("token", token)
    raw = _strip_thinking("".join(parts)).strip()

    # Defensive extraction: model sometimes returns plain text, pure JSON,
    # or a messy plain-text prefix followed by {"compressed_line": "..."}.
    compressed = raw
    json_match = _re.search(r'"compressed_line"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
    if json_match:
        try:
            compressed = _json.loads(f'"{json_match.group(1)}"')
        except Exception:
            compressed = json_match.group(1)
    elif raw.startswith("{"):
        try:
            obj = _json.loads(raw)
            compressed = next(iter(obj.values())) if obj else raw
        except Exception:
            compressed = raw
    compressed = str(compressed).strip().strip('"').strip("'")

    _FRAGMENT_STARTS = (
        "but ", "and ", "or ", "which ", "that ", "because ",
        "while ", "since ", "although ", "if ", "though ",
    )
    if len(compressed.split()) < 4 or len(compressed.split()) >= len(winner.split()):
        logger.debug("Compression rejected (collapsed/expanded). Keeping original.")
        yield ("done", winner)
        return
    if compressed.lower().startswith(_FRAGMENT_STARTS):
        logger.debug(f"Compression rejected (fragment start: '{compressed[:20]}'). Keeping original.")
        yield ("done", winner)
        return

    _FUNCTION_WORDS = {
        "a", "an", "the",
        "to", "of", "for", "in", "on", "at", "with", "as", "by", "from", "into",
        "like", "than", "then", "that", "which", "because", "until", "while", "since",
    }
    words = [w.lower() for w in _re.findall(r"\b\w+\b", compressed)]
    if len(words) >= 8 and not any(w in _FUNCTION_WORDS for w in words):
        logger.debug("Compression rejected (telegraphic/no function words). Keeping original.")
        yield ("done", winner)
        return

    logger.info(f"Compressed: {len(winner.split())}w → {len(compressed.split())}w | '{compressed}'")
    yield ("done", compressed)
