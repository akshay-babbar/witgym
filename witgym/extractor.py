"""Pass 1 — Extract ComedyMetadata from user input."""
import json
import re
from loguru import logger
from witgym.schemas import ComedyMetadata, fallback_metadata
from witgym.model import generate_text

EXTRACT_PROMPT = """\
Analyse the following conversational input and return a JSON object.

INPUT: "{user_input}"

Return ONLY a JSON object with these exact fields (no explanation, no markdown, no code block):
{{
  "surface": "what was literally said in one sentence",
  "subtext": "what the speaker actually means or feels",
  "archetype": one of ["status_assertion", "self_delusion", "power_inversion", "anxiety_escalation", "social_fail", "misplaced_conf"],
  "archetype_confidence": an integer from 1 to 10 (how confident you are in the archetype choice),
  "tension_type": one of ["social_embarrass", "existential", "status_threat", "identity_expose", "logic_collapse"],
  "power_dynamic": "who has power and who doesn't, one sentence",
  "speaker_strategy": "one short phrase describing how the speaker is trying to be perceived (e.g. competent, unbothered, in-control), or null if unclear",
  "obvious_response": "the most boring, expected response to this input",
  "violation_distance": one of ["mild", "moderate", "sharp"],
  "twist_potential": an integer from 1 to 10 rating how much hidden comedy tension is in this input (1=completely flat, 10=extremely rich setup for wit),
  "connector": "the specific word or phrase in the input that could mean two different things simultaneously, or null if no such word exists"
}}

Think carefully about the ARCHETYPE — pick the one that most accurately describes the comedy mechanism hiding in this input.
Archetype selection guidance (avoid overusing self_delusion):
- status_assertion: claiming authority/status/rightness as if saying it makes it true
- misplaced_conf: confident competence claim immediately unsupported by reality
- anxiety_escalation: small trigger spun into catastrophe / inevitable doom logic
- social_fail: awkward performance, norm violation, cringe, saying the wrong thing at the wrong time
- power_inversion: low-status person is the only honest/correct one, or social power overrides institutional power
- self_delusion: specifically a self-image story ("I'm fine / I'm great / I'm the best") contradicted by behavior/evidence in the same moment
If unsure between self_delusion vs social_fail/anxiety_escalation, prefer the more specific one (social_fail/anxiety_escalation) unless there is an explicit self-image contradiction.
For twist_potential: score high if the input has self-delusion, status gap, or absurd logic. Score low if it is a neutral factual statement with no tension.
If the input is ONLY a greeting, social opener, or typo-greeting with no described situation, set twist_potential to 1 and subtext to "greeting only — no situational content". Do not invent comedy tension.
For connector: look for a single word or short phrase that carries an expected meaning in context AND a second meaning that reframes the situation. Most inputs will have null. Return null unless a genuine dual-reading exists (e.g. "manage" can mean control people or barely cope; "balance" can mean financial or emotional equilibrium).
Return ONLY the JSON. Nothing else."""


def extract_comedy_metadata(user_input: str, model, tokenizer) -> ComedyMetadata:
    """Pass 1: extract comedy metadata. Retries once on parse failure."""
    prompt = EXTRACT_PROMPT.format(user_input=user_input)

    for attempt in range(2):
        raw = generate_text(prompt, model, tokenizer, config_type="extract")
        logger.debug(f"Extractor raw output (attempt {attempt + 1}):\n{raw}")

        # Strip any accidental markdown fences
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()

        # Find the JSON object
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            logger.warning(f"No JSON found in extractor output (attempt {attempt + 1})")
            if attempt == 0:
                prompt += f"\n\nYour previous response contained no valid JSON. Return ONLY the JSON object."
            continue

        try:
            data = json.loads(match.group())
            metadata = ComedyMetadata.model_validate(data)
            logger.info(f"Extracted: archetype={metadata.archetype.value}, tension={metadata.tension_type.value}, twist_potential={metadata.twist_potential}")
            return metadata
        except Exception as e:
            logger.warning(f"Parse error (attempt {attempt + 1}): {e}")
            if attempt == 0:
                prompt += f"\n\nParse error: {e}. Fix and return ONLY valid JSON."

    logger.error("Extractor failed twice. Using fallback metadata.")
    return fallback_metadata(user_input)
