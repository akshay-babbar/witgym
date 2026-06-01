"""Pydantic v2 schemas — Section 3 of the spec, verbatim."""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel


class ComedyArchetype(str, Enum):
    STATUS_ASSERTION = "status_assertion"
    SELF_DELUSION_EXPOSED = "self_delusion"
    POWER_INVERSION = "power_inversion"
    ANXIETY_ESCALATION = "anxiety_escalation"
    SOCIAL_PERFORMANCE_FAIL = "social_fail"
    MISPLACED_CONFIDENCE = "misplaced_conf"


class TensionType(str, Enum):
    SOCIAL_EMBARRASSMENT = "social_embarrass"
    EXISTENTIAL_ANXIETY = "existential"
    STATUS_THREAT = "status_threat"
    IDENTITY_EXPOSURE = "identity_expose"
    LOGIC_COLLAPSE = "logic_collapse"


class ViolationDistance(str, Enum):
    MILD = "mild"
    MODERATE = "moderate"
    SHARP = "sharp"


class ComedyMetadata(BaseModel):
    surface: str
    subtext: str
    archetype: ComedyArchetype
    tension_type: TensionType
    power_dynamic: str
    obvious_response: str
    violation_distance: ViolationDistance
    twist_potential: int = 5  # 1-10: comedy richness of the input; drives pipeline gating


class TranscriptScene(BaseModel):
    show: str
    character: str
    setup: str
    response: str
    archetype: ComedyArchetype
    tension_type: TensionType
    violation_distance: ViolationDistance
    why_it_works: str


class CandidateResponse(BaseModel):
    persona: str
    text: str
    violation_type: str


class WitGymResponse(BaseModel):
    metadata: ComedyMetadata
    retrieved_scenes: List[TranscriptScene]
    candidates: List[CandidateResponse]
    selected: str


# Fallback metadata when extraction fails
def fallback_metadata(user_input: str) -> ComedyMetadata:
    return ComedyMetadata(
        surface=user_input,
        subtext="unclear intent",
        archetype=ComedyArchetype.SOCIAL_PERFORMANCE_FAIL,
        tension_type=TensionType.SOCIAL_EMBARRASSMENT,
        power_dynamic="speaker vs. social expectation",
        obvious_response="I see. That sounds challenging.",
        violation_distance=ViolationDistance.MODERATE,
        twist_potential=5,
    )
