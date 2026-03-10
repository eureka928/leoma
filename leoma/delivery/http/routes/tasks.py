"""
Tasks routes for Leoma API.

Provides endpoints for task id (latest sampled task for validators),
miner task list, and task-miner detail.
"""

from typing import List

from fastapi import APIRouter, HTTPException

from leoma.delivery.http.validators import validate_miner_hotkey
from leoma.delivery.http.routes._task_utils import (
    build_miner_task_entries,
    build_task_detail_entries,
    stake_weighted_pass,
)
from leoma.infra.db.stores import (
    SampleStore,
    SamplingStateStore,
    ValidatorStore,
)
from leoma.infra.storage_backend import get_task_media_presigned_urls
from leoma.delivery.http.contracts import (
    MinerTaskEntry,
    TaskDetailResponse,
    TaskMinerDetailResponse,
    TaskMinerValidatorResult,
)


router = APIRouter()
sampling_state_dao = SamplingStateStore()
validator_samples_dao = SampleStore()
validators_dao = ValidatorStore()


@router.get("/latest")
async def get_latest_task_id() -> dict:
    """Return the latest sampled task id for validators."""
    task_id = await sampling_state_dao.get_latest_task_id()
    if task_id is None:
        raise HTTPException(status_code=404, detail="No task sampled yet")
    return {"task_id": task_id}


@router.get("", response_model=List[MinerTaskEntry])
async def get_miner_tasks(
    miner_hotkey: str,
) -> List[MinerTaskEntry]:
    """List tasks for a miner with stake-weighted pass/fail, latency, updated.
    
    Query param: miner_hotkey (required).
    """
    miner_hotkey = validate_miner_hotkey(miner_hotkey)
    samples = await validator_samples_dao.get_samples_by_miner_and_task_ids(miner_hotkey)
    if not samples:
        return []
    validators = await validators_dao.get_all_validators()
    stake_map = {v.hotkey: max(0.0, float(v.stake)) for v in validators}
    return build_miner_task_entries(samples, stake_map)


@router.get("/{task_id:int}", response_model=TaskDetailResponse)
async def get_task_detail(task_id: int) -> TaskDetailResponse:
    """Task detail with one aggregated entry per miner for the given task."""
    samples = await validator_samples_dao.get_samples_by_task_id(task_id)
    if not samples:
        raise HTTPException(status_code=404, detail="Task not found")

    validators = await validators_dao.get_all_validators()
    stake_map = {v.hotkey: max(0.0, float(v.stake)) for v in validators}
    entries = build_task_detail_entries(samples, stake_map)
    validator_count = len({sample.validator_hotkey for sample in samples})
    presigned = await get_task_media_presigned_urls(task_id, samples[0].miner_hotkey)
    prefix = str(task_id)

    return TaskDetailResponse(
        task_id=task_id,
        description=(samples[0].prompt if samples[0].prompt else None),
        s3_prefix=prefix,
        first_frame_path=f"{prefix}/first_frame.png",
        original_clip_path=f"{prefix}/original_clip.mp4",
        first_frame_url=presigned.get("first_frame_url") if presigned else None,
        original_clip_url=presigned.get("original_clip_url") if presigned else None,
        miner_count=len(entries),
        validator_count=validator_count,
        miners=entries,
    )


@router.get("/{task_id:int}/miner/{miner_hotkey}", response_model=TaskMinerDetailResponse)
async def get_task_miner_detail(
    task_id: int,
    miner_hotkey: str,
) -> TaskMinerDetailResponse:
    """Task detail for a miner: description placeholder, S3 paths, validator results, final pass/fail."""
    miner_hotkey = validate_miner_hotkey(miner_hotkey)
    samples = await validator_samples_dao.get_samples_by_task_and_miner(task_id, miner_hotkey)
    if not samples:
        raise HTTPException(status_code=404, detail="No evaluations for this task/miner")
    validators = await validators_dao.get_all_validators()
    stake_map = {v.hotkey: max(0.0, float(v.stake)) for v in validators}
    with_stakes = [(s.passed, stake_map.get(s.validator_hotkey, 0.0)) for s in samples]
    final_passed = stake_weighted_pass(with_stakes)
    latency_ms = None
    for s in samples:
        if getattr(s, "latency_ms", None) is not None:
            latency_ms = getattr(s, "latency_ms", None)
            break
    validator_results = [
        TaskMinerValidatorResult(
            validator_hotkey=s.validator_hotkey,
            passed=s.passed,
            stake=stake_map.get(s.validator_hotkey, 0.0),
            evaluated_at=getattr(s, "evaluated_at", None),
            confidence=getattr(s, "confidence", None),
            reasoning=getattr(s, "reasoning", None),
        )
        for s in samples
    ]
    prefix = str(task_id)
    safe_hotkey = miner_hotkey.replace("/", "_").replace("\\", "_")
    presigned = await get_task_media_presigned_urls(task_id, miner_hotkey)
    return TaskMinerDetailResponse(
        task_id=task_id,
        miner_hotkey=miner_hotkey,
        description=(samples[0].prompt if samples and samples[0].prompt else None),
        s3_prefix=prefix,
        first_frame_path=f"{prefix}/first_frame.png",
        original_clip_path=f"{prefix}/original_clip.mp4",
        generated_video_path=f"{prefix}/generated_videos/{safe_hotkey}.mp4",
        first_frame_url=presigned.get("first_frame_url") if presigned else None,
        original_clip_url=presigned.get("original_clip_url") if presigned else None,
        generated_video_url=presigned.get("generated_video_url") if presigned else None,
        validators=validator_results,
        final_passed=final_passed,
        latency_ms=latency_ms,
    )
