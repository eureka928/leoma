"""
Weights endpoint for validators.

Top-ranked-only weighting: returns winner_uid and per-miner list (hotkey, uid, pass_rate, weight).
Validators set weight 1.0 for winner_uid, 0 for others. If no top-ranked miner, winner_uid=0 (burn alpha).
"""

from typing import List

from fastapi import APIRouter

from leoma.delivery.http.contracts import WeightsResponse, MinerWeightEntry
from leoma.infra.db.stores import MinerRankStore, ParticipantStore


router = APIRouter()
miner_rank_dao = MinerRankStore()
valid_miners_dao = ParticipantStore()


@router.get("", response_model=WeightsResponse)
async def get_weights() -> WeightsResponse:
    """Return top-ranked UID (`winner_uid`) and each miner's hotkey, uid, pass_rate, and weight (1.0 or 0).
    
    Validators use this to set on-chain weights: only winner_uid gets 1.0, others 0.
    miners list gives each miner's score (pass_rate) and assigned weight for transparency.
    If no top-ranked miner, winner_uid=0 so validators set weight to UID 0 (burn alpha).
    """
    rows = await miner_rank_dao.get_all_ordered_by_rank()
    winner_hotkey = await miner_rank_dao.get_winner_hotkey()
    winner_uid = 0
    if winner_hotkey:
        miner = await valid_miners_dao.get_miner_by_hotkey(winner_hotkey)
        if miner:
            winner_uid = miner.uid

    miners: List[MinerWeightEntry] = []
    for r in rows:
        miner = await valid_miners_dao.get_miner_by_hotkey(r.miner_hotkey)
        uid = miner.uid if miner else 0
        weight = 1.0 if r.rank == 1 and winner_uid and uid == winner_uid else 0.0
        miners.append(
            MinerWeightEntry(
                miner_hotkey=r.miner_hotkey,
                uid=uid,
                pass_rate=r.pass_rate,
                weight=weight,
            )
        )
    return WeightsResponse(winner_uid=winner_uid, miners=miners)
