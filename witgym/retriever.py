"""Online retriever — loads index, queries by comedy archetype+tension string.

Implements Principle 2: query is the abstract comedy metadata, not raw text.
Returns analogous situations (same violation type), not similar words.
"""
import json
import os
from typing import List
from loguru import logger
import numpy as np
from witgym import config
from witgym.schemas import TranscriptScene, ComedyMetadata

_index_cache = None  # Loaded once, reused across calls
_reranker_cache = None


def load_index(index_path: str = config.INDEX_PATH) -> dict:
    """Load index from NPZ (or legacy JSON). Caches in memory."""
    global _index_cache
    if _index_cache is not None:
        return _index_cache

    path = index_path
    if path.endswith(".json") and not os.path.exists(path):
        npz_fallback = path.removesuffix(".json") + ".npz"
        if os.path.exists(npz_fallback):
            path = npz_fallback

    if path.endswith(".npz"):
        archive = np.load(path, allow_pickle=True)
        scenes = [
            TranscriptScene.model_validate(s)
            for s in json.loads(archive["scenes_json"].tobytes().decode("utf-8"))
        ]
        embeddings = np.asarray(archive["embeddings"], dtype=np.float32)
    else:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        scenes = [TranscriptScene.model_validate(s) for s in data["scenes"]]
        embeddings = np.array(data["embeddings"], dtype=np.float32)

    _index_cache = {"scenes": scenes, "embeddings": embeddings}
    logger.info(f"Index loaded: {len(scenes)} scenes from {path}")
    return _index_cache


def _load_reranker():
    global _reranker_cache
    if not config.ENABLE_CROSS_ENCODER_RERANK:
        return None
    if _reranker_cache is not None:
        return _reranker_cache

    try:
        from sentence_transformers import CrossEncoder

        logger.info(f"Loading reranker: {config.RERANK_MODEL_ID} on {config.RERANK_DEVICE}")
        _reranker_cache = CrossEncoder(config.RERANK_MODEL_ID, device=config.RERANK_DEVICE)
        return _reranker_cache
    except Exception as e:
        logger.warning(f"Reranker unavailable; falling back to cosine only: {e}")
        _reranker_cache = False
        return None


def retrieve_scenes(
    index: dict,
    metadata: ComedyMetadata,
    embed_model,
    top_k: int = config.TOP_K_SCENES,
) -> List[TranscriptScene]:
    """Principle 2: query on abstract comedy fields, return analogous situations."""
    # Mirror the indexed representation: keep the structural labels, then add
    # the extracted subtext so the query has semantic detail comparable to setup.
    query = (
        f"{metadata.archetype.value} "
        f"{metadata.tension_type.value} "
        f"{metadata.violation_distance.value} "
        f"{metadata.subtext}"
    )
    logger.debug(f"RAG query: '{query}'")

    query_emb = embed_model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )[0]

    # Cosine similarity (embeddings are L2-normalised, so dot product == cosine)
    scores = index["embeddings"] @ query_emb
    scenes: List[TranscriptScene] = index["scenes"]

    # Rank all scenes by similarity
    ranked_indices = np.argsort(scores)[::-1]

    # Stage 1: pool by cosine (wide) → Stage 2: rerank (narrow)
    pool_size = max(config.RETRIEVE_POOL_SIZE, top_k * 3)
    pool_indices = ranked_indices[:pool_size]
    pool_scenes = [scenes[i] for i in pool_indices]

    reranker = _load_reranker()
    if reranker is not None:
        query_text = (
            f"{metadata.subtext}\n"
            f"archetype={metadata.archetype.value} "
            f"tension={metadata.tension_type.value} "
            f"distance={metadata.violation_distance.value}"
        )
        doc_texts = [
            (
                f"setup={s.setup}\n"
                f"why_it_works={s.why_it_works}\n"
                f"archetype={s.archetype.value} "
                f"tension={s.tension_type.value} "
                f"distance={s.violation_distance.value}"
            )
            for s in pool_scenes
        ]
        pairs = [[query_text, d] for d in doc_texts]
        rerank_scores = np.asarray(reranker.predict(pairs), dtype=np.float32)
        reranked_order = np.argsort(rerank_scores)[::-1]
        ranked_scenes = [pool_scenes[i] for i in reranked_order]
        logger.debug(
            "Rerank top5 scores: "
            + ", ".join(f"{rerank_scores[i]:.3f}" for i in reranked_order[:5])
        )
    else:
        ranked_scenes = pool_scenes

    # Same extracted archetype first; backfill from reranked pool only if thin
    target = metadata.archetype
    selected: List[TranscriptScene] = []
    for scene in ranked_scenes:
        if scene.archetype != target:
            continue
        selected.append(scene)
        if len(selected) >= top_k:
            break

    if len(selected) < top_k:
        for scene in ranked_scenes:
            if scene in selected:
                continue
            selected.append(scene)
            if len(selected) >= top_k:
                break

    if not selected:
        selected = ranked_scenes[:top_k]

    logger.info(f"Retrieved {len(selected)} scenes: {[s.archetype.value for s in selected]}")
    return selected
