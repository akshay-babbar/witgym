"""Online retriever — loads index, queries by comedy archetype+tension string.

Implements Principle 2: query is the abstract comedy metadata, not raw text.
Returns analogous situations (same violation type), not similar words.
"""
import json
from typing import List, Set
from loguru import logger
import numpy as np
from witgym import config
from witgym.schemas import ComedyArchetype, TensionType, ViolationDistance, TranscriptScene, ComedyMetadata

_index_cache = None  # Loaded once, reused across calls


def load_index(index_path: str = config.INDEX_PATH) -> dict:
    """Load index from JSON. Caches in memory."""
    global _index_cache
    if _index_cache is not None:
        return _index_cache

    with open(index_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Reconstruct TranscriptScene objects and numpy embeddings
    scenes = [TranscriptScene.model_validate(s) for s in data["scenes"]]
    embeddings = np.array(data["embeddings"], dtype=np.float32)

    _index_cache = {"scenes": scenes, "embeddings": embeddings}
    logger.info(f"Index loaded: {len(scenes)} scenes")
    return _index_cache


def retrieve_scenes(
    index: dict,
    metadata: ComedyMetadata,
    used_archetypes: Set[ComedyArchetype],
    embed_model,
    top_k: int = config.TOP_K_SCENES,
) -> List[TranscriptScene]:
    """Principle 2: query on abstract comedy fields, return analogous situations.

    Over-fetches (top_k * 3) then filters out already-used archetypes to
    prevent repetition across the conversation.
    """
    # Build query string from comedy metadata — NOT from raw user text
    query = f"{metadata.archetype.value} {metadata.tension_type.value} {metadata.violation_distance.value}"
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

    # Filter: exclude scenes whose archetype is already used in this session,
    # AND enforce intra-call diversity (no two retrieved scenes share the same archetype)
    selected = []
    selected_archetypes: Set[ComedyArchetype] = set()
    for idx in ranked_indices:
        scene = scenes[idx]
        if scene.archetype in used_archetypes:
            continue
        if scene.archetype in selected_archetypes:
            continue  # Already have a scene of this archetype in this call
        selected.append(scene)
        selected_archetypes.add(scene.archetype)
        if len(selected) >= top_k:
            break

    # Fallback 1: relax intra-call diversity if not enough distinct archetypes found
    if len(selected) < top_k:
        for idx in ranked_indices:
            scene = scenes[idx]
            if scene.archetype in used_archetypes:
                continue
            if scene not in selected:
                selected.append(scene)
            if len(selected) >= top_k:
                break

    # Fallback 2: all session archetypes exhausted — return top matches without filter
    if not selected:
        logger.warning("All archetypes used — returning top scenes without archetype filter")
        selected = [scenes[i] for i in ranked_indices[:top_k]]

    logger.info(f"Retrieved {len(selected)} scenes: {[s.archetype.value for s in selected]}")
    return selected
