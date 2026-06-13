"""Fetch >1MB artifacts from a private HF dataset repo."""
import os
from pathlib import Path
from typing import List, Optional

from loguru import logger

from witgym import config

HUB_ARTIFACTS = ("index.npz", "office_generated.txt")
HUB_CACHE_DIR = "data/hub_cache"

_startup_status: List[str] = []


def get_startup_status() -> List[str]:
    return list(_startup_status)


def clear_startup_status() -> None:
    _startup_status.clear()


def _record(msg: str) -> None:
    _startup_status.append(msg)
    logger.info(msg)


def _local_default_path(filename: str) -> Optional[Path]:
    if filename == "index.npz":
        return Path(config.INDEX_PATH)
    if filename == "office_generated.txt":
        return Path(config.TRANSCRIPT_DIR) / filename
    return None


def _hub_fetch_error_message(exc: Exception, filename: str) -> str:
    err = str(exc).lower()
    if "401" in err or "invalid username or password" in err or "unauthorized" in err:
        return (
            f"Hub auth failed for {filename}: HF_TOKEN cannot read "
            f"{config.WITGYM_DATA_REPO}. Use a Write token with dataset access."
        )
    if "404" in err or "not found" in err or "repository not found" in err:
        return f"Hub artifact missing: {filename} not in {config.WITGYM_DATA_REPO}"
    return f"Hub fetch failed for {filename}: {exc}"


def try_ensure_artifact(filename: str, local_dir: str = HUB_CACHE_DIR) -> Optional[Path]:
    """Return local path or None. Hub HTTP/auth errors never propagate."""
    default = _local_default_path(filename)
    if default is not None and default.exists():
        _record(f"Using local {filename} at {default}")
        return default

    cache_dest = Path(local_dir) / filename
    if cache_dest.exists():
        _record(f"Using cached {filename} at {cache_dest}")
        return cache_dest

    if os.getenv("WITGYM_SKIP_HUB"):
        _record(f"Hub fetch skipped for {filename} (WITGYM_SKIP_HUB=1)")
        return None

    if not config.WITGYM_DATA_REPO:
        _record(f"Hub fetch skipped for {filename} (WITGYM_DATA_REPO not set)")
        return None

    if not config.HF_TOKEN:
        _record(f"Hub fetch skipped for {filename} (HF_TOKEN not set)")
        return None

    try:
        from huggingface_hub import hf_hub_download

        logger.info(f"Downloading {filename} from {config.WITGYM_DATA_REPO}")
        downloaded = hf_hub_download(
            repo_id=config.WITGYM_DATA_REPO,
            filename=filename,
            repo_type="dataset",
            token=config.HF_TOKEN,
            local_dir=local_dir,
        )
        path = Path(downloaded)
        _record(f"Downloaded {filename} from {config.WITGYM_DATA_REPO}")
        return path
    except Exception as e:
        msg = _hub_fetch_error_message(e, filename)
        logger.warning(msg)
        _record(msg)
        return None


def ensure_artifact(filename: str, local_dir: str = HUB_CACHE_DIR) -> Path:
    """Return local path; raise FileNotFoundError if unavailable."""
    path = try_ensure_artifact(filename, local_dir)
    if path is None:
        raise FileNotFoundError(f"{filename} not found locally and Hub fetch failed or disabled")
    return path


def materialize_hub_transcripts() -> None:
    """Optional: copy hub transcript into data/transcripts/. Never aborts startup."""
    if os.getenv("WITGYM_SKIP_HUB") or not config.WITGYM_DATA_REPO:
        return

    dest = Path(config.TRANSCRIPT_DIR) / "office_generated.txt"
    if dest.exists():
        return

    hub_txt = try_ensure_artifact("office_generated.txt")
    if hub_txt is None:
        _record("office_generated.txt unavailable — continuing with bundled transcripts")
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(hub_txt.read_bytes())
    _record(f"Materialized {dest} from Hub")
