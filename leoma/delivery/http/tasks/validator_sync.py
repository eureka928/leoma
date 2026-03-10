"""
Validator sync background task.

Syncs validators from the metagraph: any hotkey with stake >= MIN_VALIDATOR_STAKE
is automatically added to the validator list and can participate in evaluation
and setting weights. Sync runs on a configurable interval (default 10 minutes).
"""

import asyncio
from datetime import datetime, timezone

import bittensor as bt

from leoma.bootstrap import (
    emit_log as log,
    emit_header as log_header,
    log_exception,
    MIN_VALIDATOR_STAKE,
    NETUID,
    NETWORK,
    VALIDATOR_SYNC_INTERVAL,
)
from leoma.infra.db.stores import ValidatorStore


def _get_stake(meta, uid: int) -> float:
    """Get stake for a UID from metagraph. Prefer .S then .stake."""
    stake_vec = getattr(meta, "S", None) or getattr(meta, "stake", None)
    if stake_vec is None:
        return 0.0
    try:
        if uid < len(stake_vec):
            return float(stake_vec[uid])
    except (TypeError, IndexError):
        pass
    return 0.0


class ValidatorSyncTask:
    """Background task that syncs validators from metagraph by stake."""

    def __init__(self):
        self.validator_store = ValidatorStore()
        self._running = False

    async def run(self) -> None:
        """Run the validator sync loop."""
        self._running = True
        log(
            f"Validator sync task starting (interval={VALIDATOR_SYNC_INTERVAL}s, min_stake={MIN_VALIDATOR_STAKE})",
            "start",
        )
        await asyncio.sleep(5)
        while self._running:
            try:
                await self._sync_validators()
            except Exception as e:
                log(f"Validator sync error: {e}", "error")
                log_exception("Validator sync error", e)
            await asyncio.sleep(VALIDATOR_SYNC_INTERVAL)

    def stop(self) -> None:
        """Stop the task."""
        self._running = False

    async def _sync_validators(self) -> None:
        """Sync validator list from metagraph: add/update those with stake >= MIN_VALIDATOR_STAKE."""
        log_header("Validator Sync (metagraph)")
        subtensor = bt.AsyncSubtensor(network=NETWORK)
        try:
            meta = await subtensor.metagraph(NETUID)
            hotkeys = getattr(meta, "hotkeys", []) or []
            if not hotkeys:
                log("No hotkeys in metagraph", "warn")
                return
            synced_uids: set[int] = set()
            for uid in range(len(hotkeys)):
                hotkey = hotkeys[uid]
                if not hotkey or not isinstance(hotkey, str):
                    continue
                stake = _get_stake(meta, uid)
                if stake < MIN_VALIDATOR_STAKE:
                    continue
                await self.validator_store.save_validator(
                    uid=uid,
                    hotkey=hotkey,
                    stake=stake,
                )
                synced_uids.add(uid)
            deleted = await self.validator_store.delete_validators_except_uids(synced_uids)
            log(
                f"Synced {len(synced_uids)} validators (stake >= {MIN_VALIDATOR_STAKE}), removed {deleted} stale",
                "success",
            )
        finally:
            await subtensor.close()
