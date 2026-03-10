"""
Score calculation service for Leoma.

Reads samples from the Hippius S3 bucket and calculates pass rates per miner.
This is used as a fallback when API is unavailable.

Note: In normal operation, scores are calculated server-side from submitted
samples and stored in the rank_scores table.
"""

import json
import asyncio
from typing import Any, Dict, Optional

from minio import Minio

from leoma.bootstrap import SAMPLES_BUCKET
from leoma.bootstrap import emit_log as log


def _new_score_entry(slug: Optional[str]) -> Dict[str, Any]:
    """Create a fresh score container for a miner."""
    return {
        "passed_count": 0,
        "total": 0,
        "slug": slug or "unknown",
    }


async def _list_sample_metadata(minio_client: Minio) -> list[Any]:
    """List all sample metadata objects from the samples bucket."""
    objects = await asyncio.to_thread(
        lambda: list(minio_client.list_objects(SAMPLES_BUCKET, recursive=True))
    )
    return [obj for obj in objects if obj.object_name.endswith("metadata.json")]


async def _read_metadata_json(minio_client: Minio, object_name: str) -> Dict[str, Any]:
    """Read and parse a metadata.json object from Minio."""
    response = await asyncio.to_thread(minio_client.get_object, SAMPLES_BUCKET, object_name)
    try:
        metadata_bytes = response.read()
    finally:
        response.close()
        response.release_conn()
    return json.loads(metadata_bytes.decode("utf-8"))


def _accumulate_miner_score(
    scores: Dict[str, Dict[str, Any]],
    hotkey: str,
    miner_info: Dict[str, Any],
) -> None:
    """Update score counters for a single miner sample record."""
    if hotkey not in scores:
        scores[hotkey] = _new_score_entry(miner_info.get("slug"))

    score = scores[hotkey]
    score["total"] += 1
    evaluation = miner_info.get("evaluation", {}) or {}
    passed = evaluation.get("passed", False)
    if passed:
        score["passed_count"] += 1

    # Keep the latest non-empty slug if available.
    if miner_info.get("slug"):
        score["slug"] = miner_info["slug"]


def _attach_pass_rates(scores: Dict[str, Dict[str, Any]]) -> None:
    """Populate pass_rate for each miner in-place."""
    for score in scores.values():
        total = score["total"]
        score["pass_rate"] = (score["passed_count"] / total) if total > 0 else 0.0


async def calculate_scores_from_s3(minio_client: Minio) -> Dict[str, Dict[str, Any]]:
    """
    Read all samples from the Hippius bucket and calculate pass rates per miner.
    
    Args:
        minio_client: Minio client for Hippius S3
    
    Returns:
        Dict mapping hotkey to {"passed_count": int, "total": int, "pass_rate": float, "slug": str}
    """
    scores: Dict[str, Dict[str, Any]] = {}
    
    try:
        metadata_files = await _list_sample_metadata(minio_client)
        log(f"Found {len(metadata_files)} samples in S3 bucket", "info")
        
        for obj in metadata_files:
            try:
                metadata = await _read_metadata_json(minio_client, obj.object_name)
                miners_data = metadata.get("miners", {})
                for hotkey, miner_info in miners_data.items():
                    _accumulate_miner_score(scores, hotkey, miner_info)
                        
            except Exception as e:
                log(f"Error reading sample {obj.object_name}: {e}", "warn")
                continue
        
        _attach_pass_rates(scores)
        
    except Exception as e:
        log(f"Error calculating scores from S3: {e}", "error")
    
    return scores


async def calculate_scores_from_samples(minio_client: Minio) -> Dict[str, Dict[str, Any]]:
    """
    Calculate pass rates per miner from S3 samples.
    
    This is a fallback method when API is unavailable.
    In normal operation, use the API to get scores calculated server-side.
    
    Args:
        minio_client: Minio client for Hippius S3
    
    Returns:
        Dict mapping hotkey to {"passed_count": int, "total": int, "pass_rate": float, "slug": str}
    """
    return await calculate_scores_from_s3(minio_client)
