# Antigravity Developer & Workspace Instructions (AGENTS.md)

Welcome, Agent! You are continuing work on **WitGym** — a Case-Based Reasoning Retrieval-Augmented Generation (CBR-RAG) comedy engine built for the HuggingFace Build Small 2026 Hackathon (Track 2).

---

## 🚨 MANDATORY INSTRUCTION: Read the Durable Memory Bank First
Before you execute any commands, modify any source files, or write any code, you **MUST** read the detailed project status, architecture breakdown, hardware optimization strategies, and current task plans documented in:
👉 [Durable Memory Bank](file:///Users/akshaybabbar/Desktop/work/huggingface_witgym_hackathon_2026/.agents/memory/durable_memory.md)

---

## 🛠️ Global Developer Constitution Rules
As a world-class AI engineer and strategic partner, you must strictly adhere to the following principles:

1. **Grounding & Freshness**: Prioritize codebase-grounded research. Do not guess real-time API structures or assume how `witgym` is loaded. Inspect imports and files.
2. **Surgical Precision**: Touch only the exact files/lines required. Avoid cleanups or drive-by refactorings of adjacent files.
3. **Simplicity First**: Deliver the simplest, most direct, and verifiable solutions. No speculative over-engineering.
4. **Think Before Acting**: Clearly state all context assumptions, outline alternatives, and halt on ambiguous requirements.
5. **No Placeholders**: Never write placeholders, print logs, or mock data. Everything should be production-grade.

---

## 💡 Local Project Constraints & Guidelines

- **MacBook Unified Memory Constraints**:
  - The model is configured as `Qwen/Qwen3.5-9B` running on Apple Silicon MPS with `bfloat16`.
  - To prevent RAM consumption spiking over 50 GB, ensure `CONTEXT_WINDOW` is set conservatively (e.g. `4096` or `8192` tokens) in [config.py](file:///Users/akshaybabbar/Desktop/work/huggingface_witgym_hackathon_2026/witgym/config.py).
  - Explicitly clear active cache blocks with `torch.mps.empty_cache()` and run `gc.collect()` after each inference step.
  - Terminate any running Python processes before starting a run.

- **Transcript Homogeneity**:
  - Keep dialogues restricted strictly to **The Office** sitcom content. Avoid Seinfeld or other sitcom scripts.
  - Verify that the index is compiled exclusively from *The Office* data.

- **Closed-Loop Experiments**:
  - Execute a comprehensive evaluation loop after every major modification using `python -m witgym.main --debug` with standard test inputs.
  - Evaluate result brevity, sharpness, humor, and alignment with the retrieved precedents.

- **⚠️ Testing Rule — API Only, Never Local Model**:
  - **Never** load the local Qwen model (27B on MPS) during UI/closed-loop testing. It takes 2–5 minutes to load weights and blocks verification.
  - For UI changes: verify visually via `preview_screenshot` on the landing page and inject synthetic HTML via `preview_eval` to test CSS/layout of practice-screen elements.
  - For functional tests requiring inference: use the HF Inference API endpoint, not `uv run python app.py` waiting for local weights.
