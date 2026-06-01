"""
Office transcript labeler — DeepSeek V4 Flash (deepseek-chat).

Cost math (all 4055 candidate scenes):
  ~300 tokens input + ~180 tokens output per scene
  = ~$0.32 total at deepseek-v4-flash pricing ($0.14/M in, $0.28/M out)

Concurrency: 50 simultaneous requests (limit is 2500 — zero 429 risk).
Speed: ~50 scenes/wave × ~2s/wave = all 4055 done in ~3 minutes.

Usage:
    uv run python scripts/build_transcripts.py

Resume-safe: already-labeled scenes are skipped on re-run.
"""
import asyncio
import json
import os
import random
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from datasets import load_dataset
from loguru import logger
from openai import AsyncOpenAI

# ── Config ─────────────────────────────────────────────────────────────────────
DEEPSEEK_BASE  = "https://api.deepseek.com"
MODEL          = "deepseek-chat"   # = deepseek-v4-flash: $0.14/M in, $0.28/M out, 2500 concurrency
CONCURRENCY    = 50                # Safe: limit is 2500
TARGET_SCENES  = 4055              # Label the whole candidate pool (~$0.32 total)
OUTPUT_PATH    = "data/transcripts/office_generated.txt"

VALID_ARCHETYPES = {
    "status_assertion", "self_delusion", "power_inversion",
    "anxiety_escalation", "social_fail", "misplaced_conf",
}
VALID_TENSIONS = {
    "social_embarrass", "existential", "status_threat",
    "identity_expose", "logic_collapse",
}
VALID_DISTANCES = {"mild", "moderate", "sharp"}
VALID_REGISTERS = {"resigned", "gleeful", "deadpan", "panicked", "oblivious", "indignant"}

COMEDY_CHARACTERS = {
    "Michael", "Dwight", "Jim", "Pam", "Ryan", "Andy", "Kevin",
    "Angela", "Oscar", "Phyllis", "Stanley", "Creed", "Meredith",
    "Kelly", "Toby", "Jan", "Darryl", "Gabe", "Robert",
}

LABEL_PROMPT = """\
You are labeling a scene from The Office (US) for a comedy retrieval engine.

SCENE (Season {season}, Episode {episode}):
{scene_text}

Identify the single FUNNIEST line and return ONLY this JSON (no markdown):
{{
  "character": "speaker of the funniest line",
  "setup": "one sentence: situation that makes the line funny (no spoilers)",
  "response": "exact verbatim funniest line from the scene",
  "archetype": "status_assertion | self_delusion | power_inversion | anxiety_escalation | social_fail | misplaced_conf",
  "tension_type": "social_embarrass | existential | status_threat | identity_expose | logic_collapse",
  "violation_distance": "mild | moderate | sharp",
  "why_it_works": "one sentence: what expectation is violated and why it lands",
  "emotional_register": "resigned | gleeful | deadpan | panicked | oblivious | indignant"
}}
If no genuinely funny line exists, return {{"skip": true}}"""


# ── Dataset ─────────────────────────────────────────────────────────────────────
def load_office_lines():
    logger.info("Loading jxm/the_office_lines from HuggingFace...")
    ds = load_dataset("jxm/the_office_lines", split="train")
    logger.info(f"Loaded {len(ds)} lines")
    return ds


def group_into_scenes(ds) -> list[dict]:
    scene_map = defaultdict(list)
    for row in ds:
        if row.get("deleted"):
            continue
        key = (row["season"], row["episode"], row["scene"])
        scene_map[key].append(row)

    candidates = []
    for (season, episode, scene_num), lines in scene_map.items():
        speakers = {l["speaker"] for l in lines}
        if not (speakers & COMEDY_CHARACTERS):
            continue
        if not (3 <= len(lines) <= 15):
            continue
        if not any(len(l["line_text"].split()) > 7 for l in lines):
            continue
        candidates.append({
            "season": season, "episode": episode,
            "scene": scene_num, "lines": lines,
        })

    logger.info(f"Candidate scenes: {len(candidates)}")
    return candidates


def format_scene(lines: list[dict]) -> str:
    return "\n".join(
        f"{l['speaker']}: {l['line_text'].strip()}"
        for l in lines if l["line_text"].strip()
    )


def load_already_done(path: str) -> set:
    done = set()
    p = Path(path)
    if not p.exists():
        return done
    for line in p.read_text().splitlines():
        m = re.match(r"# S(\d+)E(\d+)Scene(\d+)", line)
        if m:
            done.add((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return done


def to_pipe(scene: dict, label: dict) -> str:
    reg = label.get("emotional_register", "deadpan")
    if reg not in VALID_REGISTERS:
        reg = "deadpan"
    return (
        f"The Office|{label['character']}|{label['setup']}|{label['response']}"
        f"|{label['archetype']}|{label['tension_type']}|{label['violation_distance']}"
        f"|{label['why_it_works']}|{reg}"
    )


# ── API ─────────────────────────────────────────────────────────────────────────
def get_api_key() -> str:
    for var in ["DEEPSEEK_API_KEY", "DEEPSEEK_KEY"]:
        key = os.environ.get(var)
        if key:
            return key
    # Fallback: extract from ~/.zshrc
    for var in ["DEEPSEEK_API_KEY", "DEEPSEEK_KEY"]:
        try:
            r = subprocess.run(
                ["bash", "-c", f"source ~/.zshrc 2>/dev/null; echo ${var}"],
                capture_output=True, text=True, timeout=5,
            )
            val = r.stdout.strip()
            if val and not val.startswith("$"):
                logger.info(f"Loaded {var} from ~/.zshrc")
                return val
        except Exception:
            pass
    logger.error("No DEEPSEEK_API_KEY or DEEPSEEK_KEY found in env or ~/.zshrc")
    sys.exit(1)


def parse_label(raw: str) -> dict | None:
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(m.group())
        if d.get("skip"):
            return None
        if d.get("archetype") not in VALID_ARCHETYPES:
            return None
        if d.get("tension_type") not in VALID_TENSIONS:
            return None
        if d.get("violation_distance") not in VALID_DISTANCES:
            return None
        for f in ["character", "setup", "response", "why_it_works"]:
            if not d.get(f):
                return None
            d[f] = d[f].replace("|", " ").strip()
        d["emotional_register"] = d.get("emotional_register", "deadpan").replace("|", " ").strip()
        return d
    except (json.JSONDecodeError, KeyError):
        return None


async def label_one(
    client: AsyncOpenAI,
    scene: dict,
    sem: asyncio.Semaphore,
    n_done: list,  # mutable counter [int]
    n_total: int,
    out_f,
    lock: asyncio.Lock,
) -> None:
    prompt = LABEL_PROMPT.format(
        season=scene["season"],
        episode=scene["episode"],
        scene_text=format_scene(scene["lines"]),
    )
    try:
        async with sem:
            resp = await client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=380,
            )
        label = parse_label(resp.choices[0].message.content or "")
    except Exception as e:
        logger.warning(f"S{scene['season']}E{scene['episode']}: {str(e)[:60]}")
        return

    if label is None:
        return

    sid = (scene["season"], scene["episode"], scene["scene"])
    line = f"# S{sid[0]}E{sid[1]}Scene{sid[2]}\n{to_pipe(scene, label)}\n"

    async with lock:
        out_f.write(line)
        out_f.flush()
        n_done[0] += 1
        if n_done[0] % 50 == 0 or n_done[0] <= 5:
            logger.info(
                f"[{n_done[0]}/{n_total}] S{sid[0]}E{sid[1]} "
                f"→ {label['archetype']} | {label['character']}: {label['response'][:55]}..."
            )


async def main_async():
    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)

    ds = load_office_lines()
    candidates = group_into_scenes(ds)

    already_done = load_already_done(OUTPUT_PATH)
    logger.info(f"Already labeled: {len(already_done)}")

    todo = [
        c for c in candidates
        if (c["season"], c["episode"], c["scene"]) not in already_done
    ]
    random.seed(42)
    random.shuffle(todo)
    todo = todo[:TARGET_SCENES]

    if not todo:
        logger.success("Nothing to do — all scenes already labeled.")
        return

    # Cost estimate
    n = len(todo)
    est_cost = n * (300 * 0.14 + 180 * 0.28) / 1_000_000
    est_min  = round(n / CONCURRENCY * 2 / 60, 1)  # ~2s per wave
    logger.info(
        f"Labeling {n} scenes | est. cost ≈ ${est_cost:.3f} | "
        f"est. time ≈ {est_min} min @ concurrency={CONCURRENCY}"
    )

    api_key = get_api_key()
    client  = AsyncOpenAI(api_key=api_key, base_url=DEEPSEEK_BASE)

    # Quick connectivity check
    try:
        test = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "Say OK"}],
            temperature=0.1, max_tokens=5,
        )
        logger.success(f"API OK — {test.choices[0].message.content!r}")
    except Exception as e:
        logger.error(f"API failed: {e}")
        sys.exit(1)

    sem  = asyncio.Semaphore(CONCURRENCY)
    lock = asyncio.Lock()
    n_done = [0]

    with open(OUTPUT_PATH, "a", encoding="utf-8") as out_f:
        tasks = [
            label_one(client, scene, sem, n_done, n, out_f, lock)
            for scene in todo
        ]
        await asyncio.gather(*tasks)

    total = len(already_done) + n_done[0]
    logger.success(f"Done. Labeled={n_done[0]}, total in file={total}")


if __name__ == "__main__":
    asyncio.run(main_async())
