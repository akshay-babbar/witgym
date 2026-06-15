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
  - comedy
  - rag
  - case-based-reasoning
  - qwen
  - thousand-token-wood
  - achievement:offbrand
  - achievement:best-agent
  - achievement:best-demo
  - achievement:bonus-quest-champion
  - sponsor:openai
---

# 🎭 WitGym

> *A comedy coaching engine grounded in human precedent — not vibes.*

Paste an awkward real-life situation (or tap a starter). WitGym dissects the **structural comedy of the moment**, retrieves analogous scenes from The Office, drafts 2–3 persona candidates (cynic, conviction, absurdist — twist-gated), ranks them, and returns one compressed sharp line. After a reply, use coach drills to sharpen it, try a different angle, or explain why it lands.

**[→ Try it live on Hugging Face Spaces](https://huggingface.co/spaces/build-small-hackathon/WitGym)**

---

## How to use

1. **Start** — click *Start Training* on the landing screen.
2. **Describe the moment** — paste your own awkward situation, or tap a starter chip in the sidebar (*Status*, *Social*, *Delusion*, etc.).
3. **Get a line** — WitGym returns one sharp wit line grounded in Office precedent (not an in-character Michael/Dwight impersonation).
4. **Coach drills** — after a reply, use *sharpen it*, *different angle*, or *explain the joke* to iterate on the same situation.
5. **Character panel** — the Office cast cards on the landing page are reference bios only; you do **not** pick a character to role-play.

---

## Why comedy is hard for AI

Every comedy coaching app just asks a model to "be funny." That's like asking someone to "be good at chess" without ever showing them a game.

Wit has **structure**. It emerges from the gap between what's socially expected and what gets said. The Office didn't write jokes — it wrote *situations*, then let characters navigate them in character-consistent ways. That's the thing to learn from.

WitGym treats comedy the way researchers do: as a system of **social violations, status games, and tension types** — then grounds responses in scenes that worked for the same reason.

---

## Architecture

```mermaid
flowchart TD
    A[User: paste awkward situation] --> B{Small talk?}
    B -- yes --> C[Identity reply — no pipeline]
    B -- no --> D

    D[Pass 1 — Neurology of Comedy\nQwen3.5-27B extracts 10 structural fields]
    D --> E[Archetype + Tension + Distance\nComedyMetadata schema]
    E --> F[BGE-small embedder\n384-dim semantic vector]
    F --> G[Cosine retrieval + rerank\n4021 Office scene index]
    G --> H[Top-2 precedent scenes\nwith why_it_works annotations]
    H --> I[Pass 2 — Persona Generation\n2–3 candidates: Cynic · Conviction · Absurdist]
    I --> J[Pass 3 — Tournament Ranking\nranked by structural fit to the metadata]
    J --> K[Pass 4 — Compression\nreduce to one sharp line]
    K --> L[Coaching\noptional: what made this work?]
    L --> M[Response + full debug trace]

    style D fill:#1a1a2e,color:#ffd700,stroke:#ffd700
    style G fill:#16213e,color:#4fc3f7,stroke:#4fc3f7
    style I fill:#0f3460,color:#f8f8f8,stroke:#e94560
    style M fill:#1a1a2e,color:#b0f4b0,stroke:#4caf50
```

---

## The Comedy Science

WitGym models comedy as three interacting structural properties:

| Property | Enum | What it captures |
|---|---|---|
| **Archetype** | `ComedyArchetype` | *Why* this moment is funny in principle — e.g. `STATUS_ASSERTION`, `SELF_DELUSION_EXPOSED`, `POWER_INVERSION` |
| **Tension type** | `TensionType` | *What* is at stake — e.g. `SOCIAL_EMBARRASSMENT`, `STATUS_THREAT`, `IDENTITY_EXPOSURE` |
| **Violation distance** | `ViolationDistance` | *How far* to push — `mild`, `moderate`, `sharp` |

These aren't vibes. They're used to:
1. Select the right **precedent scenes** from the index (cosine similarity on archetype + semantic embedding)
2. Constrain **persona generation** (each persona must violate in a structurally consistent way)
3. **Rank** candidates (the winner resolves the tension most cleanly)

The pipeline produces a `ComedyMetadata` object with 10 fields — including `connector` (the double-meaning word that makes a line land), `subtext` (what's actually being communicated), and `twist_potential` (comedy richness score 1–10 used to gate the full pipeline vs. quick response).

---

## The Retrieval System

4,021 indexed scenes from The Office, each annotated with:
- `archetype`, `tension_type`, `violation_distance` — structural labels
- `why_it_works` — a one-sentence explanation of the comedy mechanism
- `setup` + `response` — the actual scene

At query time, the user's situation is embedded with **BGE-small** (33M params) and retrieved against the index via cosine similarity. The retrieval finds scenes with the **same comedy structure** — not the same topic.

```mermaid
flowchart LR
    A[User situation] --> B[BGE-small encoder\n33M params]
    B --> C[384-dim vector]
    C --> D[NumPy cosine index\n4021 scenes × 384 dims]
    D --> E[Top-2 scenes\nthen cross-encoder rerank]
    E --> F[Injected as few-shot\nexamples into Pass 2 prompt]
    style B fill:#1a3a5c,color:#4fc3f7
    style D fill:#1a3a5c,color:#4fc3f7
```

---

## Pipeline flow

```mermaid
sequenceDiagram
    participant U as User
    participant A as app.py
    participant E as WitGymEngine
    participant L as LLM (Qwen3.5-27B)
    participant I as BGE Index

    U->>A: Paste situation
    A->>E: respond(user_input)

    Note over E,L: Pass 1 — Metadata extraction
    E->>L: Extract ComedyMetadata (10 fields)
    L-->>E: archetype + tension + distance + subtext...

    Note over E,I: RAG retrieval
    E->>I: embed(surface) → cosine search
    I-->>E: 2 precedent scenes

    Note over E,L: Pass 2 — Candidate generation
    E->>L: Generate 2–3 personas (cynic, conviction, absurdist — twist-gated)
    L-->>E: 3 candidate responses (streaming)

    Note over E,L: Pass 3 — Tournament ranking
    E->>L: Rank candidates by structural fit
    L-->>E: winner + explanation

    Note over E,L: Pass 4 — Compression
    E->>L: Compress winner to one sharp line
    L-->>E: final response

    E-->>A: PipelineEvent stream
    A-->>U: Streaming response + debug trace
```

---

## UI: Progressive Disclosure

The practice screen is situation-first: you paste or pick a starter, then receive a streaming coach reply. The landing **coaching panel** shows Office character bios (tap for a popup) — reference flavor, not a character picker.

The trace uses **progressive disclosure** — the reply stays front-and-center, while the expandable rail reveals the underlying structured pipeline as JSON:

- **Trace** — expandable JSON payload with metadata, retrieved scenes, candidates, and selected output
- **Chips / capsules** — used only where the product needs human-facing explanation, not as a substitute for the execution trace

New elements animate in with a shimmer sweep + border glow system that stops on first interaction. This mirrors how Notion and Apple iOS handle progressive discovery — purposeful discoverability signaling, not decoration.

---

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| **LLM** | Qwen3.5-27B via HF Inference Providers | ≤32B constraint; best instruction-following at this size |
| **Embedder** | BGE-small (33M params) | Fast, accurate, runs on CPU in < 50ms |
| **Index** | NumPy cosine retrieval + optional 32M cross-encoder rerank, 4021 scenes × 384 dims | No server needed; loaded at startup from Hub dataset |
| **UI** | Gradio 6.x on HF Spaces | Streaming SSE, custom CSS theming |
| **Validation** | Pydantic v2 | Schema-enforced extraction; fallback on parse failure |
| **Retry** | Exponential backoff on all LLM calls | Handles upstream provider flakiness gracefully |

---

## Build Small compliance

- **Model size**: Qwen3.5-27B ≤ 32B ✓
- **Embedder**: BGE-small 33M — runs on CPU, no GPU needed for retrieval ✓
- **Deployed on HF Spaces**: Gradio app, streams via SSE ✓
- **Open source**: Apache 2.0 licensed ✓
- **Use case**: whimsical entertainment / comedy coaching grounded in structured precedent ✓
- **Interaction design**: custom Gradio interface with progressive disclosure and streaming feedback ✓
- **Agentic flow**: route -> extract -> retrieve -> generate -> rank -> compress ✓
- No fine-tuning required — all comedy structure is in the retrieval index and prompts

---

## How to cite WitGym

If you use or build on this project, please cite:

```bibtex
@software{babbar2026witgym,
  author = {Babbar, Akshay},
  title = {WitGym: CBR-RAG Comedy Coaching Engine},
  year = {2026},
  url = {https://github.com/akshay-babbar/witgym},
  note = {Hugging Face Build Small Hackathon 2026 submission}
}
```

See also [`CITATION.cff`](CITATION.cff) for machine-readable metadata.

---

## What makes this different

| Approach | Problem |
|---|---|
| "Respond wittily to: [situation]" | No structural understanding; generic, contextless outputs |
| RAG on jokes | Jokes don't transfer — the *situation structure* transfers |
| **WitGym** | Extracts comedy structure → retrieves same-structure precedents → generates constrained by that structure |

The insight: The Office didn't write great jokes. It wrote great **situations**, then populated them with characters who respond in structurally consistent ways. WitGym learns from the situations, not the punchlines.

---

## Run locally

```bash
# Install
uv sync  # or: pip install -e .

# Build index (The Office transcripts)
witgym-index

# Run with HF Inference API (recommended — no local weights needed)
export HF_TOKEN=hf_...
export LLM_BACKEND=hf_api
python app.py

# Run with local weights (MPS/CUDA)
python app.py
```

---

## HF Spaces configuration

Set these in Space settings — **not** in GitHub. CI only syncs code; runtime auth is separate.

| Secret | Value |
|---|---|
| `HF_TOKEN` | Write token with read access to the data dataset |
| `LLM_BACKEND` | `hf_api` |
| `WITGYM_DATA_REPO` | `build-small-hackathon/witgym-data` (default) |

Optional: `HF_INFERENCE_PROVIDER` (defaults to `together`), `WITGYM_INDEX_PATH`.

Do **not** set `WITGYM_SKIP_HUB` on the Space.

---

## Large data on HF Hub

Files over 1 MB (`office_generated.txt`, `index.npz`) live in a private org dataset, not in git. At startup the app fetches `index.npz` from the Hub; if auth fails it falls back to rebuilding from bundled transcripts.

```bash
hf upload build-small-hackathon/witgym-data \
  data/index.npz index.npz --repo-type dataset

hf upload build-small-hackathon/witgym-data \
  data/transcripts/office_generated.txt office_generated.txt \
  --repo-type dataset --private
```

When transcripts change: re-run `witgym-index`, then re-upload `index.npz`. Offline dev: set `WITGYM_SKIP_HUB=1`.

---

## CI/CD

Pushes to `main` sync code to the Space via [`.github/workflows/sync-to-hub.yml`](.github/workflows/sync-to-hub.yml).

| Where | Secret | Purpose |
|---|---|---|
| GitHub repo secrets | `HF_TOKEN` | CI push to Space only |
| Space secrets | `HF_TOKEN`, `WITGYM_DATA_REPO`, `LLM_BACKEND` | Runtime Hub API + dataset + inference |

These are **two different** `HF_TOKEN` placements. Configuring GitHub does not configure the Space runtime.

---

Built for the [Hugging Face Build Small Hackathon 2026](https://huggingface.co/build-small-hackathon).
