---
description: Comprehensive background, architectural layout, and active execution guides for the WitGym project.
---

# Project Context: WitGym Comedy Engine

This workflow provides a strategic breakdown of the WitGym project context to assist incoming agents in executing tasks efficiently.

---

## 🎭 Context & Background
WitGym is an experimental conversational AI grounded in Case-Based Reasoning (CBR) and Retrieval-Augmented Generation (RAG) to generate contextually relevant, sharp, and brief comedy responses inspired by **The Office**.

The engine operates on two core principles:
1. **Pass 1 — Abstract Conceptual Indexing**: We extract comedy archetypes and tension points from user setups instead of relying on direct text similarity.
2. **Pass 2 — Grounded Persona Generation**: We retrieve analogous Office scenarios and feed them into three creative generation pipelines (Cynic, Observer, Absurdist), selecting the final response through a brevity-biased ranker.

---

## 📂 Codebase Navigation & Key Interfaces

### [config.py](file:///Users/akshaybabbar/Desktop/work/huggingface_witgym_hackathon_2026/witgym/config.py)
Defines constants, model targets, context window limits, and clichés. Keeps variables decoupled.

### [model.py](file:///Users/akshaybabbar/Desktop/work/huggingface_witgym_hackathon_2026/witgym/model.py)
Contains model loading and direct PyTorch operations. Implements `ClichePenaltyProcessor` (soft logits manipulation) and MPS cache eviction mechanics.

### [engine.py](file:///Users/akshaybabbar/Desktop/work/huggingface_witgym_hackathon_2026/witgym/engine.py)
The stateful orchestration core. Keeps the API completely clean and separate from user interface logic.

### [generator.py](file:///Users/akshaybabbar/Desktop/work/huggingface_witgym_hackathon_2026/witgym/generator.py)
Houses the candidate generation prompts and the positional-bias-free brevity ranking logic.

---

## ⚙️ RAM Optimization Strategy
When transitioning to larger models (e.g. Qwen3.5-9B) on local hardware (48 GB Unified Memory Macs):
- **Reduce KV Cache Size**: Set `CONTEXT_WINDOW` in `config.py` to `4096`.
- **Force PyTorch Garbage Collection**: Call `torch.mps.empty_cache()` and `gc.collect()` after each run.
- **Process Termination**: Kill dangling python processes before execution.

---

## 🔬 Next Closed-Loop Experiment Steps
To verify correctness and rule out regressions:
1. Re-index with `python -m witgym.main index`.
2. Run interactive chat via `python -m witgym.main --debug`.
3. Input 5 diverse setup prompts representing all archetypes.
4. Evaluate and refine generation prompts or penalties if necessary.
