# WitGym — Field Notes (Build Small 2026)

## What I built
WitGym is a comedy coaching engine for real-life awkward moments. You paste a situation, it produces **one sharp line**, then lets you iterate with drills (sharpen / different angle / explain).

The core bet: **comedy transfers by structure, not by topic**. Instead of “RAG on jokes”, WitGym does **CBR-RAG on comedy mechanics** and uses precedent from *The Office* to ground the response.

## The small-model constraint (≤32B) changed the design
Under the Build Small constraint, the goal wasn’t “generate funnier text by scaling”, it was “get reliable *wit* by adding structure”:

- **Pass 1 (extraction)**: extract a compact schema (`ComedyMetadata`) describing the moment: archetype, tension, violation distance, subtext, behavioral observation, etc.\n
- **Retrieval (CBR-RAG)**: retrieve *structurally similar* precedent scenes from a prebuilt index.\n
- **Pass 2 (generation)**: draft 2–3 persona candidates with strict constraints.\n
- **Pass 3 (ranking)**: pick a winner with an explicit judging rubric (truth precision + strong ending + domain anchoring).\n
- **Pass 4 (compression)**: optionally tighten the winner to one crisp line.\n

## What was unexpectedly important
- **Behavioral observation > feelings**: naming the *move* (“renamed procrastination as ‘keeping options open’”) is a better generative seed than therapy-language subtext.\n
- **Ranking beats clever prompting**: the biggest quality jumps came from forcing a tournament-style selection rubric, especially “truth precision” and “final clause” quality.\n
- **Progressive disclosure UX matters**: streaming phase updates and an expandable trace makes judges trust the system (it’s not “vibes”; you can see what it did).\n

## Models used
- **LLM**: `Qwen/Qwen3.5-27B` (≤32B) via Hugging Face Inference Providers (recommended runtime path).\n
- **Embedder**: `BAAI/bge-small-en-v1.5` (33M) for retrieval.\n
- **Reranker (optional)**: `cross-encoder/ettin-reranker-32m-v1` (CPU) for pool reranking.\n

## What I’d improve next (post-hackathon)
- Make “coach mode” differentiate *response style*, not just “add an explanation panel”.\n
- Add a public, privacy-safe trace export that covers **both** evaluation runs and real usage patterns (with de-identification).\n
- Tighten the “small talk” and “low twist” path so it’s still delightful without running the full pipeline.\n

