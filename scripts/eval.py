"""
WitGym closed-loop evaluation harness.

Usage:
  # Before any changes — capture baseline:
  python scripts/eval.py --tag before

  # After all changes + index rebuild:
  python scripts/eval.py --tag after

  # Compare the two snapshots:
  python scripts/eval.py --compare

Each run saves results to data/eval_{tag}.json.
Compare prints a side-by-side table of selected outputs + word counts.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# Five canonical test inputs (from durable_memory.md §5)
TEST_INPUTS = [
    "I just got promoted to manager and I have no idea what I'm doing.",
    "My coworker keeps stealing my lunch from the fridge.",
    "I've been cc'd on an email chain I definitely should not be reading.",
    "I'm pretending to understand cryptocurrency at dinner parties.",
    "My therapist fell asleep during our session.",
]


def run_eval(tag: str, index_path: str = "data/index.npz") -> None:
    """Run all 5 test inputs, save results snapshot."""
    from witgym.engine import WitGymEngine

    if not Path(index_path).exists():
        print(f"[ERROR] Index not found at {index_path}. Run `witgym-index` first.")
        sys.exit(1)

    engine = WitGymEngine(index_path=index_path)
    results = []

    for i, user_input in enumerate(TEST_INPUTS, 1):
        print(f"\n[{i}/5] Input: {user_input[:60]}...")
        t0 = time.time()
        response = engine.respond(user_input)
        elapsed = time.time() - t0

        result = {
            "input": user_input,
            "selected": response.selected,
            "word_count": len(response.selected.split()),
            "archetype": response.metadata.archetype.value,
            "tension": response.metadata.tension_type.value,
            "violation_distance": response.metadata.violation_distance.value,
            "candidates": [
                {"persona": c.persona, "text": c.text, "words": len(c.text.split())}
                for c in response.candidates
            ],
            "retrieved_scenes": [
                {"show": s.show, "archetype": s.archetype.value, "setup": s.setup[:80]}
                for s in response.retrieved_scenes
            ],
            "latency_s": round(elapsed, 1),
        }

        # Add twist_potential if present (post-v2 schema)
        if hasattr(response.metadata, "twist_potential"):
            result["twist_potential"] = response.metadata.twist_potential

        print(f"  → [{response.metadata.archetype.value}] {response.selected}")
        print(f"  → {len(response.selected.split())} words | {elapsed:.1f}s")
        results.append(result)

    out_path = f"data/eval_{tag}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"tag": tag, "results": results}, f, indent=2)
    print(f"\n✓ Saved eval snapshot → {out_path}")


def compare_evals() -> None:
    """Side-by-side comparison of before vs after snapshots."""
    before_path = "data/eval_before.json"
    after_path = "data/eval_after.json"

    missing = [p for p in [before_path, after_path] if not Path(p).exists()]
    if missing:
        print(f"[ERROR] Missing snapshots: {missing}")
        print("  Run: python scripts/eval.py --tag before")
        print("  Then: python scripts/eval.py --tag after")
        sys.exit(1)

    with open(before_path) as f:
        before_data = json.load(f)
    with open(after_path) as f:
        after_data = json.load(f)

    before_results = {r["input"]: r for r in before_data["results"]}
    after_results = {r["input"]: r for r in after_data["results"]}

    print("\n" + "=" * 90)
    print("WITGYM EVAL: BEFORE vs AFTER")
    print("=" * 90)

    total_word_delta = 0
    total_latency_delta = 0

    for inp in TEST_INPUTS:
        b = before_results.get(inp)
        a = after_results.get(inp)
        if not b or not a:
            continue

        word_delta = a["word_count"] - b["word_count"]
        latency_delta = a["latency_s"] - b["latency_s"]
        total_word_delta += word_delta
        total_latency_delta += latency_delta

        print(f"\n📝 Input: {inp[:70]}")
        print(f"   BEFORE [{b['word_count']}w, {b['latency_s']}s, {b['archetype']}]:")
        print(f"   ✗  {b['selected']}")
        print(f"   AFTER  [{a['word_count']}w, {a['latency_s']}s, {a['archetype']}]:")
        print(f"   ✓  {a['selected']}")
        word_indicator = "↓ shorter" if word_delta < 0 else ("↑ longer" if word_delta > 0 else "= same")
        lat_indicator = "↓ faster" if latency_delta < 0 else ("↑ slower" if latency_delta > 0 else "= same")
        print(f"   Δ words={word_delta:+d} ({word_indicator}), Δ latency={latency_delta:+.1f}s ({lat_indicator})")

        # Show candidate diversity
        if a.get("candidates"):
            personas_after = [c["persona"] for c in a["candidates"]]
            print(f"   Candidates: {personas_after}")

    print("\n" + "-" * 90)
    print(f"SUMMARY — avg word delta: {total_word_delta/len(TEST_INPUTS):+.1f} words | avg latency delta: {total_latency_delta/len(TEST_INPUTS):+.1f}s")
    print("=" * 90)


def main():
    parser = argparse.ArgumentParser(description="WitGym closed-loop evaluator")
    parser.add_argument("--tag", choices=["before", "after"], help="Run eval and save snapshot with this tag")
    parser.add_argument("--compare", action="store_true", help="Compare before vs after snapshots")
    parser.add_argument("--index", default="data/index.npz")
    args = parser.parse_args()

    if args.compare:
        compare_evals()
    elif args.tag:
        run_eval(args.tag, args.index)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
