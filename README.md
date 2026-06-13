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
license: mit
tags:
  - comedy
  - rag
  - case-based-reasoning
  - qwen
---

# WitGym

Conversational wit grounded in human comedy precedent — a Case-Based Reasoning RAG (CBR-RAG) engine.

Paste a real-life awkward situation. WitGym extracts the comedy structure, retrieves analogous precedents, generates persona candidates, ranks the sharpest line, and shows every intermediate step in the logs panel.

## Run locally

```bash
# Install
uv sync  # or pip install -e .

# Build index (The Office transcripts only)
witgym-index

# CLI (local 9B on MPS/CUDA)
python -m witgym.main --debug

# Gradio UI (local model)
python app.py

# Gradio UI via Hugging Face Inference Providers (no local 9B weights)
export HF_TOKEN=hf_...
export LLM_BACKEND=hf_api
python app.py
```

## Hugging Face Space secrets

| Secret | Value |
|--------|--------|
| `HF_TOKEN` | Your Hugging Face access token |
| `LLM_BACKEND` | `hf_api` (recommended on Spaces) |
| `WITGYM_DATA_REPO` | Private dataset repo, e.g. `akshay4/witgym-data` |

Optional: `HF_INFERENCE_PROVIDER` (defaults to `together` for Qwen3.5-9B — required for `enable_thinking: false`), `WITGYM_INDEX_PATH`.

## Large data on Hugging Face Hub

Files over 1 MB (`office_generated.txt`, `index.npz`) live in a **private dataset repo**, not in git. The app fetches them at startup via `hf_hub_download`.

**One-time setup** (create private dataset `witgym-data`, then upload):

```bash
hf upload akshay4/witgym-data \
  data/transcripts/office_generated.txt office_generated.txt \
  --repo-type dataset --private

hf upload akshay4/witgym-data \
  data/index.npz index.npz \
  --repo-type dataset
```

**When transcripts change:** re-run `witgym-index`, then re-upload `index.npz`.

**Offline local dev:** set `WITGYM_SKIP_HUB=1` and keep local copies in `data/`.

## Deploy (GitHub → Space)

Pushes to `main` sync to [build-small-hackathon/WitGym](https://huggingface.co/spaces/build-small-hackathon/WitGym) via `.github/workflows/sync-to-hub.yml`. Add `HF_TOKEN` as a GitHub repository secret.

## Architecture

- **Small talk** (hi, who are you) → polite identity reply, no pipeline
- **Humour practice** → Pass 1 metadata → RAG retrieval → Pass 2 personas → rank → compress

Backend: `local` (Transformers) or `hf_api` (Inference Providers via `huggingface_hub.InferenceClient`).
