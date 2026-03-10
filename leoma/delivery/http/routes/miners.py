"""Miners routes for Leoma API."""
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from leoma.delivery.http.verifier import verify_signature
from leoma.delivery.http.contracts import MinerResponse, MinersListResponse, MinerTaskEntry
from leoma.delivery.http.routes._task_utils import build_miner_task_entries
from leoma.delivery.http.validators import validate_miner_hotkey
from leoma.infra.db.stores import ParticipantStore, SampleStore, ValidatorStore


router = APIRouter()
valid_miners_dao = ParticipantStore()
validator_samples_dao = SampleStore()
validators_dao = ValidatorStore()


def _to_miner_response(miner: Any) -> MinerResponse:
    """Convert miner ORM/entity model to API response model."""
    return MinerResponse(
        uid=miner.uid,
        hotkey=miner.miner_hotkey,
        model_name=miner.model_name,
        model_revision=miner.model_revision,
        model_hash=miner.model_hash,
        chute_id=miner.chute_id,
        chute_slug=miner.chute_slug,
        is_valid=miner.is_valid,
        invalid_reason=miner.invalid_reason,
        block=miner.block,
        last_validated_at=miner.last_validated_at,
    )


def _to_miners_list_response(
    miners: list[Any],
    *,
    total: int,
    valid_count: int,
) -> MinersListResponse:
    """Convert miner entities into list response payload."""
    return MinersListResponse(
        miners=[_to_miner_response(miner) for miner in miners],
        total=total,
        valid_count=valid_count,
    )


@router.get("/uid/{uid}", response_model=MinerResponse)
async def get_miner_by_uid(uid: int) -> MinerResponse:
    """Get miner by UID (public dashboard endpoint).
    
    Args:
        uid: Miner UID on the subnet
        
    Returns:
        Miner details
        
    Raises:
        HTTPException: If miner not found
    """
    miner = await valid_miners_dao.get_miner_by_uid(uid)
    if not miner:
        raise HTTPException(status_code=404, detail="Miner not found")
    return _to_miner_response(miner)


@router.get("/list", response_model=MinersListResponse)
async def get_miners_list() -> MinersListResponse:
    """Get list of all miners (valid and invalid) for dashboard display.
    
    Public endpoint; no authentication required.
    
    Returns:
        List of all miners with their details
    """
    miners = await valid_miners_dao.get_all_miners()
    valid_count = await valid_miners_dao.get_valid_count()
    return _to_miners_list_response(
        miners,
        total=len(miners),
        valid_count=valid_count,
    )


@router.get("/valid", response_model=MinersListResponse)
async def get_valid_miners(
    _hotkey: Annotated[str, Depends(verify_signature)],
) -> MinersListResponse:
    """Get list of valid miners.
    
    Requires validator signature authentication.
    
    Returns:
        List of valid miners with their details
    """
    miners = await valid_miners_dao.get_valid_miners()
    all_miners = await valid_miners_dao.get_all_miners()
    miner_responses = [_to_miner_response(m) for m in miners]
    return MinersListResponse(
        miners=miner_responses,
        total=len(all_miners),
        valid_count=len(miners),
    )


@router.get("/all", response_model=MinersListResponse)
async def get_all_miners(
    _hotkey: Annotated[str, Depends(verify_signature)],
) -> MinersListResponse:
    """Get all miners (valid and invalid).
    
    Requires validator signature authentication.
    
    Returns:
        List of all miners with their details
    """
    miners = await valid_miners_dao.get_all_miners()
    valid_count = await valid_miners_dao.get_valid_count()
    
    return _to_miners_list_response(
        miners,
        total=len(miners),
        valid_count=valid_count,
    )


@router.get("/{miner_hotkey}/tasks", response_model=list[MinerTaskEntry])
async def get_miner_tasks(
    miner_hotkey: str,
) -> list[MinerTaskEntry]:
    """List tasks for a miner with stake-weighted pass/fail, latency, updated (for miner detail page)."""
    miner_hotkey = validate_miner_hotkey(miner_hotkey)
    samples = await validator_samples_dao.get_samples_by_miner_and_task_ids(miner_hotkey)
    if not samples:
        return []
    validators = await validators_dao.get_all_validators()
    stake_map = {v.hotkey: max(0.0, float(v.stake)) for v in validators}
    return build_miner_task_entries(samples, stake_map)


@router.get("/info/{miner_hotkey}", response_model=MinerResponse)
async def get_miner_info(
    miner_hotkey: str,
) -> MinerResponse:
    """Get details for a specific miner (public dashboard endpoint).
    
    Args:
        miner_hotkey: Miner's SS58 hotkey
    
    Returns:
        Miner details
        
    Raises:
        HTTPException: If miner not found
    """
    miner_hotkey = validate_miner_hotkey(miner_hotkey)
    miner = await valid_miners_dao.get_miner_by_hotkey(miner_hotkey)
    if not miner:
        raise HTTPException(status_code=404, detail="Miner not found")
    return _to_miner_response(miner)


@router.get("/{miner_hotkey}", response_model=MinerResponse)
async def get_miner(
    miner_hotkey: str,
    _hotkey: Annotated[str, Depends(verify_signature)],
) -> MinerResponse:
    """Get details for a specific miner.
    
    Args:
        miner_hotkey: Miner's SS58 hotkey
        
    Requires validator signature authentication.
    
    Returns:
        Miner details
        
    Raises:
        HTTPException: If miner not found
    """
    miner_hotkey = validate_miner_hotkey(miner_hotkey)
    miner = await valid_miners_dao.get_miner_by_hotkey(miner_hotkey)
    
    if not miner:
        raise HTTPException(status_code=404, detail="Miner not found")
    
    return _to_miner_response(miner)
