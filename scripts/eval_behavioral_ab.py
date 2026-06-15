"""A/B eval: baseline (main/deployed) vs behavioral_observation branch changes.

Uses LLM_BACKEND=hf_api only. Does not touch corpus/index.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("LLM_BACKEND", "hf_api")

ROOT = Path(__file__).resolve().parents[1]
CHANGED = [
    "witgym/schemas.py",
    "witgym/extractor.py",
    "witgym/prompts.py",
    "witgym/generator.py",
]
BACKUP_DIR = ROOT / "data" / ".eval_behavioral_backup"

SINGLE_TURN = [
    "I just got promoted to manager and I have no idea what I'm doing.",
    "My coworker keeps stealing my lunch from the fridge.",
    "I've been cc'd on an email chain I definitely should not be reading.",
    "I'm pretending to understand cryptocurrency at dinner parties.",
    "My therapist fell asleep during our session.",
    "I still haven't replied to that email from three weeks ago.",
    "My boss says he trusts me, but he rewrites every message I send.",
    "I told everyone the meeting would be quick and it is now ruining lives.",
    "I keep calling it networking when really I'm just begging professionally.",
    'I said "circle back" because I ran out of courage.',
    "I keep acting like I'm choosing not to date when the market has actually made that decision for me.",
    "I described panic as being detail-oriented and now people believe me.",
]

COACHING_FLOWS = [
    (
        "Help me come up with something funny to say to my micromanaging boss.",
        "He keeps interrupting me in meetings and then repeating my point like he invented it.",
    ),
    (
        "Coach me on a funny response for a social situation.",
        'A friend asked if I was free this weekend and I panicked and said I was "booked" when I meant emotionally.',
    ),
    (
        "Help me respond better in awkward situations.",
        "I told my date I love routines and then described anxiety like it was a hobby.",
    ),
]


def _backup_modified() -> None:
    if BACKUP_DIR.exists():
        shutil.rmtree(BACKUP_DIR)
    BACKUP_DIR.mkdir(parents=True)
    for rel in CHANGED:
        src = ROOT / rel
        if src.exists():
            shutil.copy2(src, BACKUP_DIR / Path(rel).name)


def _restore_modified() -> None:
    for rel in CHANGED:
        name = Path(rel).name
        src = BACKUP_DIR / name
        if src.exists():
            shutil.copy2(src, ROOT / rel)


def _reset_to_baseline() -> None:
    subprocess.run(
        ["git", "checkout", "--", *CHANGED],
        cwd=ROOT,
        check=True,
    )


def _run_one(engine, user_input: str, *, coaching_turn2: str | None = None) -> dict:
    from witgym.engine import WitGymEngine

    eng = WitGymEngine(index_path="data/index.npz", resources=engine)
    t0 = time.time()
    if coaching_turn2 is None:
        r = eng.respond(user_input)
        meta = r.metadata
        return {
            "input": user_input,
            "kind": "single",
            "selected": r.selected,
            "word_count": len(r.selected.split()),
            "behavioral_observation": getattr(meta, "behavioral_observation", None),
            "subtext": meta.subtext,
            "archetype": meta.archetype.value,
            "latency_s": round(time.time() - t0, 1),
            "candidates": [c.text for c in r.candidates],
        }

    turn1 = eng.respond(user_input)
    eng2 = WitGymEngine(
        index_path="data/index.npz",
        resources=engine,
        conversation=eng.conversation,
    )
    t1 = time.time()
    r2 = eng2.respond(coaching_turn2)
    meta = r2.metadata
    return {
        "input": f"{user_input} → {coaching_turn2}",
        "kind": "coaching_turn2",
        "coaching_question": turn1.coaching_question or turn1.selected,
        "selected": r2.selected,
        "word_count": len(r2.selected.split()),
        "behavioral_observation": getattr(meta, "behavioral_observation", None),
        "subtext": meta.subtext,
        "archetype": meta.archetype.value,
        "latency_s": round(time.time() - t1, 1),
        "candidates": [c.text for c in r2.candidates],
    }


def _run_variant_subprocess(tag: str) -> None:
    """Run one variant in a fresh Python process so code changes take effect."""
    env = os.environ.copy()
    env.setdefault("LLM_BACKEND", "hf_api")
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "eval_behavioral_ab.py"),
        "--worker",
        tag,
    ]
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)


def run_variant(tag: str) -> list[dict]:
    from witgym.engine import SharedResources

    if not Path("data/index.npz").exists():
        print("[ERROR] data/index.npz missing")
        sys.exit(1)

    shared = SharedResources(index_path="data/index.npz")
    results: list[dict] = []
    total = len(SINGLE_TURN) + len(COACHING_FLOWS)
    n = 0

    for prompt in SINGLE_TURN:
        n += 1
        print(f"\n[{tag}] [{n}/{total}] {prompt[:70]}...")
        row = _run_one(shared, prompt)
        print(f"  → {row['selected']}")
        if row.get("behavioral_observation"):
            print(f"  obs: {row['behavioral_observation'][:100]}")
        results.append(row)

    for turn1, turn2 in COACHING_FLOWS:
        n += 1
        print(f"\n[{tag}] [{n}/{total}] coaching: {turn1[:50]}...")
        row = _run_one(shared, turn1, coaching_turn2=turn2)
        print(f"  → {row['selected']}")
        if row.get("behavioral_observation"):
            print(f"  obs: {row['behavioral_observation'][:100]}")
        results.append(row)

    out = ROOT / "data" / f"eval_behavioral_{tag}.json"
    payload = {"tag": tag, "results": results}
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\n✓ Saved {out}")
    return results


def compare() -> None:
    b_path = ROOT / "data" / "eval_behavioral_baseline.json"
    m_path = ROOT / "data" / "eval_behavioral_modified.json"
    if not b_path.exists() or not m_path.exists():
        print("[ERROR] Run full eval first")
        sys.exit(1)

    baseline = {r["input"]: r for r in json.loads(b_path.read_text())["results"]}
    modified = {r["input"]: r for r in json.loads(m_path.read_text())["results"]}

    print("\n" + "=" * 100)
    print("BEHAVIORAL_OBSERVATION A/B — baseline (main/HF) vs modified")
    print("=" * 100)

    rows = []
    for key in baseline:
        b, m = baseline[key], modified.get(key)
        if not m:
            continue
        print(f"\n📝 {key[:90]}")
        print(f"   BASE [{b['word_count']}w]: {b['selected']}")
        print(f"   MOD  [{m['word_count']}w]: {m['selected']}")
        if m.get("behavioral_observation") and not b.get("behavioral_observation"):
            print(f"   OBS  (modified only): {m['behavioral_observation']}")
        elif b.get("behavioral_observation") or m.get("behavioral_observation"):
            print(f"   OBS baseline: {b.get('behavioral_observation')}")
            print(f"   OBS modified: {m.get('behavioral_observation')}")
        rows.append({"input": key, "baseline": b["selected"], "modified": m["selected"]})

    sheet = ROOT / "data" / "eval_behavioral_sheet.json"
    sheet.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\n✓ Comparison sheet → {sheet}")


def main() -> None:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--compare-only", action="store_true")
    p.add_argument("--worker", choices=["baseline", "modified"])
    args = p.parse_args()

    if args.worker:
        run_variant(args.worker)
        return

    if args.compare_only:
        compare()
        return

    _backup_modified()
    try:
        print("=== BASELINE (main / deployed HF) ===")
        _reset_to_baseline()
        _run_variant_subprocess("baseline")
        print("\n=== MODIFIED (behavioral_observation) ===")
        _restore_modified()
        _run_variant_subprocess("modified")
        compare()
    finally:
        _restore_modified()


if __name__ == "__main__":
    main()
