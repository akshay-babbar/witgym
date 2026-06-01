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
  "tension_type": one of ["social_embarrass", "existential", "status_threat", "identity_expose", "logic_collapse"],
  "power_dynamic": "who has power and who doesn't, one sentence",
  "obvious_response": "the most boring, expected response to this input",
  "violation_distance": one of ["mild", "moderate", "sharp"]
}}

Think carefully about the ARCHETYPE — pick the one that most accurately describes the comedy mechanism hiding in this input.
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
            logger.info(f"Extracted: archetype={metadata.archetype.value}, tension={metadata.tension_type.value}")
            return metadata
        except Exception as e:
            logger.warning(f"Parse error (attempt {attempt + 1}): {e}")
            if attempt == 0:
                prompt += f"\n\nParse error: {e}. Fix and return ONLY valid JSON."

    logger.error("Extractor failed twice. Using fallback metadata.")
    return fallback_metadata(user_input)
