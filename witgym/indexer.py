"""Offline indexer — parse transcript files, embed comedy metadata, persist to JSON.

Implements Principle 2: indexes on abstract comedy fields, NOT raw text.
The embedding is of: "{archetype} {tension_type} {setup_summary}"
"""
import json
import os
from pathlib import Path
from typing import List
from loguru import logger
import numpy as np
from witgym import config
from witgym.schemas import (
    ComedyArchetype, TensionType, ViolationDistance, TranscriptScene
)


def _parse_transcript_file(filepath: Path) -> List[TranscriptScene]:
    """Parse a transcript file in SHOW|CHAR|SETUP|RESPONSE|ARCH|TENSION|DIST|WHY format."""
    scenes = []
    with open(filepath, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) not in (8, 9):
                logger.warning(f"{filepath.name}:{lineno} — expected 8-9 fields, got {len(parts)}. Skipping.")
                continue
            show, character, setup, response, arch_raw, tension_raw, dist_raw, why = parts[:8]
            try:
                scene = TranscriptScene(
                    show=show.strip(),
                    character=character.strip(),
                    setup=setup.strip(),
                    response=response.strip(),
                    archetype=ComedyArchetype(arch_raw.strip()),
                    tension_type=TensionType(tension_raw.strip()),
                    violation_distance=ViolationDistance(dist_raw.strip()),
                    why_it_works=why.strip(),
                )
                scenes.append(scene)
            except Exception as e:
                logger.warning(f"{filepath.name}:{lineno} — schema error: {e}. Skipping.")
    return scenes


def _make_index_text(scene: TranscriptScene) -> str:
    """Principle 2: embed comedy metadata, NOT raw dialogue text."""
    return f"{scene.archetype.value} {scene.tension_type.value} {scene.violation_distance.value} {scene.setup}"


def build_index(transcript_dir: str = config.TRANSCRIPT_DIR, index_path: str = config.INDEX_PATH):
    """Parse all .txt files, embed comedy metadata strings, save index JSON."""
    from sentence_transformers import SentenceTransformer

    transcript_path = Path(transcript_dir)
    if not transcript_path.exists():
        raise FileNotFoundError(f"Transcript directory not found: {transcript_dir}")

    # Collect all scenes
    all_scenes: List[TranscriptScene] = []
    for txt_file in sorted(transcript_path.glob("*.txt")):
        file_scenes = _parse_transcript_file(txt_file)
        logger.info(f"Parsed {len(file_scenes)} scenes from {txt_file.name}")
        all_scenes.extend(file_scenes)

    if not all_scenes:
        raise ValueError(f"No valid scenes found in {transcript_dir}")

    logger.info(f"Total scenes: {len(all_scenes)}")

    # Log archetype distribution
    arch_dist = {}
    for s in all_scenes:
        arch_dist[s.archetype.value] = arch_dist.get(s.archetype.value, 0) + 1
    logger.info(f"Archetype distribution: {arch_dist}")

    # Embed the comedy metadata strings (NOT raw dialogue) — Principle 2
    logger.info(f"Loading embedding model: {config.EMBED_MODEL_ID}")
    embed_model = SentenceTransformer(config.EMBED_MODEL_ID, device=config.DEVICE)

    index_texts = [_make_index_text(s) for s in all_scenes]
    logger.info("Computing embeddings...")
    embeddings = embed_model.encode(
        index_texts,
        convert_to_numpy=True,
        normalize_embeddings=True,   # Normalised = cosine sim == dot product
        show_progress_bar=True,
    )

    # Persist to JSON
    index_data = {
        "scenes": [s.model_dump() for s in all_scenes],
        "embeddings": embeddings.tolist(),
        "index_texts": index_texts,
    }
    os.makedirs(os.path.dirname(index_path) if os.path.dirname(index_path) else ".", exist_ok=True)
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f)

    logger.success(f"Index saved to {index_path} ({len(all_scenes)} scenes)")
    return all_scenes
