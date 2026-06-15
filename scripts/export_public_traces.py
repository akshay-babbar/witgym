"""Export a small, public-safe set of WitGym traces (Sharing is Caring).

This writes deterministic-ish JSONL traces for a fixed set of canonical prompts.
It intentionally omits any raw Office transcript text from retrieved scenes.
"""

from __future__ import annotations

import json
import os
import time
import hashlib
import sys
from pathlib import Path


CANONICAL_SINGLE_TURN = [
    "I just got promoted to manager and I have no idea what I'm doing.",
    "My coworker keeps stealing my lunch from the fridge.",
    "My boss says he trusts me, but he rewrites every message I send.",
]


def _scene_id(setup: str, response: str) -> str:
    h = hashlib.sha256((setup + "\n" + response).encode("utf-8")).hexdigest()
    return h[:12]


def _safe_scene(scene) -> dict:
    # Do not export setup/response verbatim; this keeps traces inspectable without
    # publishing transcript text.
    return {
        "scene_id": _scene_id(scene.setup, scene.response),
        "show": scene.show,
        "character": scene.character,
        "archetype": scene.archetype.value,
        "tension_type": scene.tension_type.value,
        "violation_distance": scene.violation_distance.value,
    }


def _pipeline_logs(result) -> list[dict]:
    meta = result.metadata
    scenes = result.retrieved_scenes
    candidates = result.candidates
    return [
        {
            "step": "metadata",
            "status": "ok",
            "detail": f"twist={meta.twist_potential} archetype={meta.archetype.value}",
        },
        {
            "step": "retrieval",
            "status": "ok",
            "detail": ", ".join(f"{s.character}:{s.archetype.value}" for s in scenes) or "no precedent scenes",
        },
        {
            "step": "candidate_generation",
            "status": "ok",
            "detail": ", ".join(f"{c.persona}:{len(c.text.split())}w" for c in candidates) or "no candidates",
        },
        {"step": "ranking", "status": "ok", "detail": result.winning_persona or "none"},
        {"step": "compression", "status": "ok", "detail": "selected line finalized"},
    ]


def _run_single(engine, user_input: str) -> dict:
    t0 = time.time()
    result = engine.respond(user_input)
    dt = time.time() - t0

    meta = result.metadata
    return {
        "kind": "single_turn",
        "input": user_input,
        "route": result.route,
        "model_id": os.getenv("LLM_MODEL_ID", "Qwen/Qwen3.5-27B"),
        "llm_backend": os.getenv("LLM_BACKEND", "hf_api"),
        "latency_s": round(dt, 2),
        "metadata": {
            "surface": meta.surface,
            "subtext": meta.subtext,
            "behavioral_observation": getattr(meta, "behavioral_observation", None),
            "archetype": meta.archetype.value,
            "archetype_confidence": meta.archetype_confidence,
            "tension_type": meta.tension_type.value,
            "power_dynamic": meta.power_dynamic,
            "speaker_strategy": meta.speaker_strategy,
            "obvious_response": meta.obvious_response,
            "violation_distance": meta.violation_distance.value,
            "twist_potential": meta.twist_potential,
            "connector": meta.connector,
        },
        "retrieved_scenes": [_safe_scene(s) for s in result.retrieved_scenes],
        "candidates": [
            {"persona": c.persona, "word_count": len(c.text.split())}
            for c in result.candidates
        ],
        "winning_persona": result.winning_persona,
        "selected": result.selected,
        "logs": _pipeline_logs(result),
    }


def main() -> int:
    # Prefer HF API for reproducible “no local weights” runs.
    os.environ.setdefault("LLM_BACKEND", "hf_api")

    # Allow running without installing the package (pip/uv editable install).
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from witgym.engine import WitGymEngine

    out_path = Path("data/public_traces.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    engine = WitGymEngine(index_path="data/index.npz")

    rows: list[dict] = []
    for prompt in CANONICAL_SINGLE_TURN:
        rows.append(_run_single(engine, prompt))

    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"✓ Wrote {len(rows)} trace rows → {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

