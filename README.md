---
title: WitGym
emoji: 🎭
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: "6.17.3"
python_version: "3.12"
app_file: app.py
pinned: false
license: apache-2.0
short_description: Paste awkward. Get one sharp wit line + coach drills.
tags:
  - build-small-hackathon
  - track:wood
  - thousand-token-wood
  - comedy
  - rag
  - case-based-reasoning
  - qwen
  - achievement:offbrand
  - achievement:sharing
  - achievement:fieldnotes
  - sponsor:openai
---

# 🎭 WitGym

**One sharp line, grounded in human precedent. Then drills to sharpen it.**

WitGym is a comedy coaching engine for awkward real-life moments. It extracts the **comedy structure**, retrieves analogous precedent from *The Office*, drafts constrained persona candidates, runs a **tournament ranker**, and returns one crisp line with optional coaching.

**Live Space**: [build-small-hackathon/WitGym](https://huggingface.co/spaces/build-small-hackathon/WitGym)

### Why I built this
Comedy has always been a personal interest — not just watching it, but understanding how a line lands. I wanted a **humor coach** for real awkward moments: paste what happened, get one sharp line, then drill on it. *The Office* felt like the right precedent library (I'm a longtime fan) — not to impersonate characters, but to learn from situations that already work. WitGym is my attempt to make that coach real under the ≤32B constraint.

### 30‑second demo
- Paste: “My boss says he trusts me, but he rewrites every message I send.”
- Watch the phases: extract → retrieve → draft → rank → polish (streaming)
- Tap drills: **sharpen it**, **different angle**, **explain the joke**

### What makes it different
- **CBR‑RAG on comedy mechanics**: retrieve by archetype, tension, and violation distance — not topic keywords
- **Behavioral observation as the generative seed**: name the human move, then write from that
- **Tournament ranking for landing**: truth precision, final-clause quality, domain anchoring
- **Inspectable traces**: progressive disclosure in the UI; public JSONL export for Sharing is Caring

### How it works
1. **Extract** — `Qwen/Qwen3.5-27B` → `ComedyMetadata` (12 fields)
2. **Retrieve** — `BAAI/bge-small-en-v1.5` cosine pool + optional `cross-encoder/ettin-reranker-32m-v1`
3. **Generate** — 2–3 twist-gated persona candidates
4. **Rank** — fixed rubric selects the winner
5. **Compress** — optional polish to one sharp line

### Evidence / badges
- **Sharing is Caring** (`achievement:sharing`): [public pipeline traces](data/public_traces.jsonl) — sanitized JSONL (metadata, scene IDs, candidate stats, execution log; no Office dialogue text). Regenerate: `uv run python scripts/export_public_traces.py`
- **Field Notes** (`achievement:fieldnotes`): [docs/field-notes.md](docs/field-notes.md)
- **Off‑Brand UI** (`achievement:offbrand`): custom Gradio UI + streaming trace disclosure

> **Validator**: add demo video + social post links here before submission. [Validate README](https://build-small-hackathon-field-guide.hf.space/submit)

### Run locally

```bash
uv sync
witgym-index
export LLM_BACKEND=hf_api
export HF_TOKEN=hf_...
uv run python app.py
```

Built for the [Build Small Hackathon 2026](https://huggingface.co/build-small-hackathon) — Thousand Token Wood.
