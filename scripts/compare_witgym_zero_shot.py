"""WitGym vs zero-shot baseline — same model, same API backend."""
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# 7 diverse scenarios (5 canonical + 2 extra)
TEST_INPUTS = [
    "I just got promoted to manager and I have no idea what I'm doing.",
    "My coworker keeps stealing my lunch from the fridge.",
    "I've been cc'd on an email chain I definitely should not be reading.",
    "I'm pretending to understand cryptocurrency at dinner parties.",
    "My therapist fell asleep during our session.",
    "My boss called a quick sync that's been going for two hours.",
    "I waved back at someone who wasn't waving at me.",
]

ZERO_SHOT_PROMPT = """You are a witty friend. The user shares an awkward or funny situation.
Reply with ONE sharp, funny line. Maximum 2 sentences. No preamble.

User: {user_input}

Funny reply:"""


def zero_shot_reply(user_input: str, model, tokenizer) -> str:
    from witgym.model import generate_text

    prompt = ZERO_SHOT_PROMPT.format(user_input=user_input)
    raw = generate_text(prompt, model, tokenizer, config_type="generate")
    return raw.strip().strip('"')


def run_experiment(index_path: str = "data/index.npz") -> dict:
    import os

    os.environ.setdefault("LLM_BACKEND", "hf_api")

    from witgym import config
    from witgym.engine import WitGymEngine
    from witgym.model import load_model

    if not Path(index_path).exists():
        print(f"[ERROR] Index missing: {index_path}")
        sys.exit(1)

    print(f"Model: {config.LLM_MODEL_ID} | Backend: {config.LLM_BACKEND}")
    print(f"Providers: {config.HF_INFERENCE_PROVIDERS}\n")

    # Shared embedder/index only — fresh engine per input (no conversation bleed)
    shared = None
    model, tokenizer = load_model()

    rows = []
    for i, user_input in enumerate(TEST_INPUTS, 1):
        print(f"[{i}/{len(TEST_INPUTS)}] {user_input[:65]}...")

        from witgym.engine import WitGymEngine, SharedResources

        nonlocal_shared = shared
        if nonlocal_shared is None:
            nonlocal_shared = SharedResources(index_path=index_path)
            shared = nonlocal_shared
        engine = WitGymEngine(index_path=index_path, resources=nonlocal_shared)

        t0 = time.time()
        wg = engine.respond(user_input)
        wg_elapsed = time.time() - t0

        t0 = time.time()
        zs = zero_shot_reply(user_input, model, tokenizer)
        zs_elapsed = time.time() - t0

        row = {
            "input": user_input,
            "witgym": {
                "text": wg.selected,
                "words": len(wg.selected.split()),
                "latency_s": round(wg_elapsed, 1),
                "archetype": wg.metadata.archetype.value,
                "candidates": [c.text for c in wg.candidates],
            },
            "zero_shot": {
                "text": zs,
                "words": len(zs.split()),
                "latency_s": round(zs_elapsed, 1),
            },
        }
        rows.append(row)
        print(f"  WitGym ({row['witgym']['words']}w, {wg_elapsed:.1f}s): {wg.selected}")
        print(f"  Zero   ({row['zero_shot']['words']}w, {zs_elapsed:.1f}s): {zs}\n")

    out = {
        "model": config.LLM_MODEL_ID,
        "backend": config.LLM_BACKEND,
        "zero_shot_prompt": ZERO_SHOT_PROMPT,
        "results": rows,
    }
    out_path = Path("data/eval_witgym_vs_zero_shot.json")
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Saved → {out_path}")
    return out


if __name__ == "__main__":
    run_experiment()
