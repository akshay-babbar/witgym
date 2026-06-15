"""Constants and configuration for WitGym."""
import os
import torch

# LLM — set LLM_MODEL_ID in env / HF Space secrets to swap models (local + API)
LLM_MODEL_ID = os.getenv("LLM_MODEL_ID", "Qwen/Qwen3.5-27B")
MODEL_ID = LLM_MODEL_ID  # backward compat for imports

EMBED_MODEL_ID = "BAAI/bge-small-en-v1.5"

# Device — MPS for Apple Silicon, fallback to cuda/cpu
if torch.backends.mps.is_available():
    DEVICE = "mps"
elif torch.cuda.is_available():
    DEVICE = "cuda"
else:
    DEVICE = "cpu"

DTYPE = torch.bfloat16

# Sampling
EXTRACT_TEMP = 0.2
EXTRACT_DO_SAMPLE = False
GENERATE_TEMP = 1.0  # slightly lower to reduce arbitrary domain invention
GENERATE_MIN_P = 0.06
GENERATE_MAX_NEW_TOKENS = 72
RANK_TEMP = 0.1
EXTRACT_MAX_NEW_TOKENS = 220   # JSON never exceeds ~150 tokens; 220 = 47% safety margin

# Context management
CONTEXT_WINDOW = 4096         # MPS-friendly; triggers earlier compression if history grows
COMPRESSION_THRESHOLD = 0.80  # Compress at 80% full
KEEP_LAST_N_TURNS = 4

# RAG
TOP_K_SCENES = 2
RETRIEVE_POOL_SIZE = 12
ENABLE_CROSS_ENCODER_RERANK = True
RERANK_MODEL_ID = "cross-encoder/ettin-reranker-32m-v1"
RERANK_DEVICE = "cpu"  # keep 9B on MPS; rerank on CPU to avoid unified-memory spikes
INDEX_PATH = "data/index.npz"
TRANSCRIPT_DIR = "data/transcripts"

# Generation guards
ENABLE_BAD_WORD_GUARD = True
BAD_WORD_PHRASES = (
    "PATH A",
    "PATH B",
    "PATHWAY SELECTION",
)
ENABLE_OVERLAP_GUARD = True
OVERLAP_NGRAM_SIZE = 6  # contiguous words shared with retrieved dialogue

# Cliché penalty (soft steering, not hard suppression)
CLICHE_LOGIT_PENALTY = -5.0
CLICHE_PENALTY_TOKENS = 6   # Penalise first N tokens of the obvious response

# HuggingFace auth + inference backend
def _hf_token_from_zshrc() -> str:
    zshrc = os.path.expanduser("~/.zshrc")
    if not os.path.isfile(zshrc):
        return ""
    with open(zshrc, encoding="utf-8") as f:
        for line in f:
            if line.startswith("export HF_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


_zshrc_hf = _hf_token_from_zshrc()
HF_TOKEN = _zshrc_hf or os.getenv("HF_TOKEN", "")
if _zshrc_hf:
    os.environ["HF_TOKEN"] = _zshrc_hf
# Org dataset on Spaces; override via env for local dev (e.g. akshay4/witgym-data)
WITGYM_DATA_REPO = os.getenv(
    "WITGYM_DATA_REPO",
    "build-small-hackathon/witgym-data" if os.getenv("SPACE_ID") else "",
)
# "local" = Transformers on device; "hf_api" = Inference Providers (Spaces default)
LLM_BACKEND = os.getenv("LLM_BACKEND", "local")
def _default_inference_providers() -> list[str]:
    if "Qwen3.5" in LLM_MODEL_ID and "27B" in LLM_MODEL_ID:
        return ["novita", "featherless-ai"]
    if "Qwen3.5" in LLM_MODEL_ID:
        return ["together", "featherless-ai"]
    if "Qwen3.6" in LLM_MODEL_ID:
        return ["featherless-ai", "ovhcloud"]
    return ["auto"]


HF_INFERENCE_PROVIDERS = [
    p.strip()
    for p in os.getenv(
        "HF_INFERENCE_PROVIDERS",
        ",".join(_default_inference_providers()),
    ).split(",")
    if p.strip()
]
HF_INFERENCE_PROVIDER = os.getenv(
    "HF_INFERENCE_PROVIDER",
    HF_INFERENCE_PROVIDERS[0] if HF_INFERENCE_PROVIDERS else "auto",
)
HF_API_TIMEOUT = float(os.getenv("HF_API_TIMEOUT", "120"))
HF_API_MAX_RETRIES = int(os.getenv("HF_API_MAX_RETRIES", "3"))

# Text-to-speech
TTS_ENABLED = os.getenv("TTS_ENABLED", "1").strip().lower() not in {"0", "false", "no"}
