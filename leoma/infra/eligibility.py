"""
Miner validation: chute check, HuggingFace model hash, plagiarism detection.
"""
import os
import asyncio
import hashlib
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import aiohttp
from huggingface_hub import HfApi

from leoma.bootstrap import HF_TOKEN, MODEL_HASH_CACHE_TTL, emit_log
from leoma.domain import MinerInfo
from leoma.infra.chute_resolver import get_chute_info

WEIGHT_EXTENSIONS = (".safetensors", ".bin", ".pt", ".pth", ".ckpt")
_model_hash_cache: Dict[Tuple[str, str], Tuple[Optional[Tuple[str, str]], float]] = {}
_api_blacklist_cache: Tuple[Set[str], float] = (set(), 0)
_API_BLACKLIST_CACHE_TTL = 300
_BLACKLIST_API_TIMEOUT_SECONDS = 10


def _get_cached_blacklist(now: float) -> Set[str] | None:
    cached_blacklist, cached_at = _api_blacklist_cache
    if cached_blacklist and (now - cached_at) < _API_BLACKLIST_CACHE_TTL:
        return cached_blacklist
    return None


def _is_event_loop_running() -> bool:
    try:
        return asyncio.get_event_loop().is_running()
    except RuntimeError:
        return False


def _cache_model_hash_result(key: Tuple[str, str], result: Optional[Tuple[str, str]], now: float) -> None:
    _model_hash_cache[key] = (result, now)


def _extract_weight_file_shas(siblings: list[Any]) -> Set[str]:
    shas: Set[str] = set()
    for sibling in siblings:
        filename = getattr(sibling, "rfilename", None) or getattr(sibling, "path", "") or ""
        lfs_info = getattr(sibling, "lfs", None)
        if not isinstance(lfs_info, dict) or "sha256" not in lfs_info:
            continue
        if not any(filename.endswith(ext) for ext in WEIGHT_EXTENSIONS):
            continue
        shas.add(str(lfs_info["sha256"]))
    return shas


def _build_empty_miner_info(
    uid: int,
    hotkey: str,
    model_name: str,
    model_revision: str,
    chute_id: str,
    block: int,
) -> MinerInfo:
    return MinerInfo(
        uid=uid,
        hotkey=hotkey,
        model_name=model_name,
        model_revision=model_revision,
        chute_id=chute_id,
        block=block,
    )


def load_blacklist() -> set:
    global _api_blacklist_cache
    now = time.time()
    cached_blacklist, cached_at = _api_blacklist_cache
    if _get_cached_blacklist(now) is not None:
        return cached_blacklist
    try:
        if _is_event_loop_running():
            return cached_blacklist
        blacklist = asyncio.run(_fetch_blacklist_from_api())
        _api_blacklist_cache = (blacklist, now)
        return blacklist
    except Exception as e:
        emit_log(f"Failed to fetch blacklist from API: {e}", "warn")
        return cached_blacklist


async def _fetch_blacklist_from_api() -> set:
    api_url = os.environ.get("API_URL", "https://api.leoma.ai")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{api_url}/blacklist/miners",
                timeout=aiohttp.ClientTimeout(total=_BLACKLIST_API_TIMEOUT_SECONDS),
            ) as response:
                if response.status == 200:
                    hotkeys = await response.json()
                    return set(hotkeys)
                emit_log(f"Blacklist API returned {response.status}", "warn")
                return set()
        except Exception as e:
            emit_log(f"Blacklist API request failed: {e}", "warn")
            return set()


async def get_model_hash(model_id: str, revision: str) -> Optional[Tuple[str, str]]:
    key = (model_id, revision)
    now = time.time()
    if key in _model_hash_cache:
        cached, cached_at = _model_hash_cache[key]
        if now - cached_at < MODEL_HASH_CACHE_TTL:
            return cached
    try:
        def _fetch():
            return HfApi(token=HF_TOKEN).repo_info(
                repo_id=model_id, repo_type="model", revision=revision, files_metadata=True
            )
        info = await asyncio.to_thread(_fetch)
        actual_revision = getattr(info, "sha", None)
        siblings = getattr(info, "siblings", None) or []
        shas = _extract_weight_file_shas(siblings)
        if not shas or not actual_revision:
            _cache_model_hash_result(key, None, now)
            return None
        combined = "".join(sorted(shas))
        model_hash = hashlib.sha256(combined.encode()).hexdigest()
        result = (model_hash, actual_revision)
        _cache_model_hash_result(key, result, now)
        return result
    except Exception as e:
        emit_log(f"Failed to fetch model info for {model_id}@{revision}: {e}", "warn")
        _cache_model_hash_result(key, None, now)
        return None


async def validate_miner(
    session: aiohttp.ClientSession,
    uid: int,
    hotkey: str,
    model_name: str,
    model_revision: str,
    chute_id: str,
    block: int,
) -> MinerInfo:
    info = _build_empty_miner_info(
        uid=uid, hotkey=hotkey, model_name=model_name,
        model_revision=model_revision, chute_id=chute_id, block=block,
    )
    chute = await get_chute_info(session, chute_id)
    if not chute:
        info.invalid_reason = "chute_fetch_failed"
        return info
    info.chute_slug = chute.get("slug", "")
    info.chute_status = "hot" if chute.get("hot", False) else "cold"
    if not chute.get("hot", False):
        info.invalid_reason = "chute_not_running"
        return info
    chute_revision = chute.get("revision", "")
    if chute_revision and model_revision != chute_revision:
        info.invalid_reason = f"revision_mismatch:chute={chute_revision}"
        return info
    model_info = await get_model_hash(model_name, model_revision)
    if not model_info:
        info.invalid_reason = "hf_model_fetch_failed"
        return info
    model_hash, hf_revision = model_info
    info.model_hash = model_hash
    if model_revision != hf_revision:
        info.invalid_reason = f"revision_mismatch:hf={hf_revision}"
        return info
    info.is_valid = True
    return info


def detect_plagiarism(miners: List[MinerInfo]) -> List[MinerInfo]:
    hash_to_miners: Dict[str, List[Tuple[int, int, MinerInfo]]] = {}
    for miner in miners:
        if not miner.is_valid or not miner.model_hash:
            continue
        if miner.model_hash not in hash_to_miners:
            hash_to_miners[miner.model_hash] = []
        hash_to_miners[miner.model_hash].append((miner.block, miner.uid, miner))
    for model_hash, group in hash_to_miners.items():
        if len(group) <= 1:
            continue
        group.sort(key=lambda x: (x[0], x[1]))
        _, earliest_uid, _ = group[0]
        for _, uid, miner in group[1:]:
            if miner.is_valid:
                miner.is_valid = False
                miner.invalid_reason = f"duplicate_model:earliest_uid={earliest_uid}"
                emit_log(
                    f"Duplicate model detected: uid={uid} copied from uid={earliest_uid} (hash={model_hash[:16]}...)",
                    "warn",
                )
    return miners
