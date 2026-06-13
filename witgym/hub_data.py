"""Fetch >1MB artifacts from a private HF dataset repo."""
import os
from pathlib import Path
from typing import Optional

from loguru import logger

from witgym import config

HUB_ARTIFACTS = ("index.npz", "office_generated.txt")
HUB_CACHE_DIR = "data/hub_cache"


def _local_default_path(filename: str) -> Optional[Path]:
    if filename == "index.npz":
        return Path(config.INDEX_PATH)
    if filename == "office_generated.txt":
        return Path(config.TRANSCRIPT_DIR) / filename
    return None


def ensure_artifact(filename: str, local_dir: str = HUB_CACHE_DIR) -> Path:
    """Return local path; use existing file, cache, or download from Hub."""
    default = _local_default_path(filename)
    if default is not None and default.exists():
        return default

    cache_dest = Path(local_dir) / filename
    if cache_dest.exists():
        return cache_dest

    if os.getenv("WITGYM_SKIP_HUB") or not config.WITGYM_DATA_REPO or not config.HF_TOKEN:
        raise FileNotFoundError(f"{filename} not found locally and Hub fetch disabled")

    from huggingface_hub import hf_hub_download

    logger.info(f"Downloading {filename} from {config.WITGYM_DATA_REPO}")
    downloaded = hf_hub_download(
        repo_id=config.WITGYM_DATA_REPO,
        filename=filename,
        repo_type="dataset",
        token=config.HF_TOKEN,
        local_dir=local_dir,
    )
    return Path(downloaded)


def materialize_hub_transcripts() -> None:
    """Copy hub transcript into data/transcripts/ so indexer glob stays unchanged."""
    if os.getenv("WITGYM_SKIP_HUB") or not config.WITGYM_DATA_REPO:
        return

    dest = Path(config.TRANSCRIPT_DIR) / "office_generated.txt"
    if dest.exists():
        return

    try:
        hub_txt = ensure_artifact("office_generated.txt")
    except FileNotFoundError:
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(hub_txt.read_bytes())
    logger.info(f"Materialized {dest} from Hub")
