"""Constants and configuration for WitGym."""
import os
import torch

# Model
MODEL_ID = "Qwen/Qwen3.5-9B"
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
GENERATE_TEMP = 1.15  # lowered after anchor/retrieval fixes to reduce domain invention
GENERATE_MIN_P = 0.06
GENERATE_MAX_NEW_TOKENS = 40
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
INDEX_PATH = "data/index.json"
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

# HuggingFace auth
HF_TOKEN = os.getenv("HF_TOKEN", "")
