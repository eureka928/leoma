"""
Miner validation background task.

Periodically syncs metagraph and validates miners:
- Parses commitment data
- Verifies HuggingFace model exists
- Checks chute endpoint is responsive
"""

import os
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict

import aiohttp
import bittensor as bt

from leoma.bootstrap import emit_log as log, emit_header as log_header, log_exception, NETUID, NETWORK
from leoma.infra.db.stores import BlacklistStore, ParticipantStore
from leoma.infra.commit_parser import parse_commit, validate_commit_fields
from leoma.infra.eligibility import validate_miner
from leoma.delivery.http.routes.health import update_last_sync


# Configuration
MINER_VALIDATION_INTERVAL = int(os.environ.get("MINER_VALIDATION_INTERVAL", "300"))  # 5 minutes


class MinerValidationTask:
    """Background task for miner validation."""
    
    def __init__(self):
        self.valid_miners_dao = ParticipantStore()
        self.blacklist_dao = BlacklistStore()
        self._running = False
    
    async def run(self) -> None:
        """Run the miner validation task loop."""
        self._running = True
        log(f"Miner validation task starting (interval={MINER_VALIDATION_INTERVAL}s)", "start")
        
        # Initial delay to let other services start
        await asyncio.sleep(5)
        
        while self._running:
            try:
                await self._validate_miners()
            except Exception as e:
                log(f"Miner validation error: {e}", "error")
                log_exception("Miner validation error", e)
            
            await asyncio.sleep(MINER_VALIDATION_INTERVAL)
    
    def stop(self) -> None:
        """Stop the task."""
        self._running = False

    @staticmethod
    def _blacklisted_entry(uid: int, hotkey: str) -> Dict[str, Any]:
        """Build invalid entry for blacklisted miner."""
        return {
            "uid": uid,
            "miner_hotkey": hotkey,
            "is_valid": False,
            "invalid_reason": "blacklisted",
        }

    @staticmethod
    def _invalid_commit_entry(
        uid: int,
        hotkey: str,
        block: int,
        reason: str | None,
    ) -> Dict[str, Any]:
        """Build invalid entry for malformed commitment payload."""
        return {
            "uid": uid,
            "miner_hotkey": hotkey,
            "block": block,
            "is_valid": False,
            "invalid_reason": reason,
        }

    @staticmethod
    def _validated_entry(
        uid: int,
        hotkey: str,
        miner_info,
    ) -> Dict[str, Any]:
        """Build persistence payload from validated miner info."""
        return {
            "uid": uid,
            "miner_hotkey": hotkey,
            "block": miner_info.block,
            "model_name": miner_info.model_name,
            "model_revision": miner_info.model_revision,
            "model_hash": miner_info.model_hash,
            "chute_id": miner_info.chute_id,
            "chute_slug": miner_info.chute_slug,
            "is_valid": miner_info.is_valid,
            "invalid_reason": miner_info.invalid_reason,
        }
    
    async def _validate_miners(self) -> None:
        """Validate all miners from metagraph."""
        log_header("Miner Validation Sync")
        
        # Connect to subtensor
        subtensor = bt.AsyncSubtensor(network=NETWORK)
        
        try:
            # Get current block and commitments
            current_block = await subtensor.get_current_block()
            commits = await subtensor.get_all_revealed_commitments(NETUID, block=current_block)
            
            if not commits:
                log("No miner commitments found", "warn")
                return
            
            meta = await subtensor.metagraph(NETUID)
            
            # Get blacklist
            blacklisted_miners = set(await self.blacklist_dao.get_hotkeys())
            
            # Validate each miner
            validated_miners = []
            
            async with aiohttp.ClientSession() as session:
                for uid, hotkey in enumerate(meta.hotkeys):
                    commit_data = commits.get(hotkey)
                    if not commit_data:
                        continue

                    # Check blacklist
                    if hotkey in blacklisted_miners:
                        validated_miners.append(self._blacklisted_entry(uid, hotkey))
                        continue
                    
                    # Parse commitment
                    commit_block, commit_value = commit_data[-1]
                    parsed = parse_commit(commit_value)
                    
                    # Validate commit fields (model_name must start with "leoma", end with hotkey)
                    is_valid, reason = validate_commit_fields(parsed, hotkey=hotkey)
                    if not is_valid:
                        validated_miners.append(
                            self._invalid_commit_entry(uid, hotkey, commit_block, reason)
                        )
                        continue
                    
                    # Full validation (HuggingFace, Chutes)
                    miner_info = await validate_miner(
                        session=session,
                        uid=uid,
                        hotkey=hotkey,
                        model_name=parsed["model_name"],
                        model_revision=parsed["model_revision"],
                        chute_id=parsed["chute_id"],
                        block=commit_block,
                    )
                    log(f"Miner info: {miner_info}", "info")
                    
                    validated_miners.append(self._validated_entry(uid, hotkey, miner_info))
            
            # Update database
            await self.valid_miners_dao.batch_upsert_miners(validated_miners)
            
            # Delete stale miners
            active_uids = [m["uid"] for m in validated_miners]
            await self.valid_miners_dao.delete_stale_miners(active_uids)
            
            # Update health check
            update_last_sync(datetime.now(timezone.utc))
            
            # Log summary
            valid_count = sum(1 for m in validated_miners if m.get("is_valid"))
            invalid_count = len(validated_miners) - valid_count
            log(f"Validated {len(validated_miners)} miners: {valid_count} valid, {invalid_count} invalid", "success")
            
        finally:
            await subtensor.close()
