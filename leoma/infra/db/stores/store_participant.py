"""Participant (valid miners) store."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, func, select, update

from leoma.bootstrap import emit_log
from leoma.infra.db.pool import get_session
from leoma.infra.db.tables import ValidMiner


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ParticipantStore:
    """Access layer for valid_miners."""

    @staticmethod
    def _apply_miner_fields(
        miner: ValidMiner,
        *,
        miner_hotkey: str,
        block: Optional[int],
        model_name: Optional[str],
        model_revision: Optional[str],
        model_hash: Optional[str],
        chute_id: Optional[str],
        chute_slug: Optional[str],
        is_valid: bool,
        invalid_reason: Optional[str],
    ) -> None:
        miner.miner_hotkey = miner_hotkey
        miner.block = block
        miner.model_name = model_name
        miner.model_revision = model_revision
        miner.model_hash = model_hash
        miner.chute_id = chute_id
        miner.chute_slug = chute_slug
        miner.is_valid = is_valid
        miner.invalid_reason = invalid_reason
        miner.last_validated_at = _now_utc()

    @staticmethod
    def _save_miner_kwargs(miner_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "uid": miner_data["uid"],
            "miner_hotkey": miner_data["miner_hotkey"],
            "block": miner_data.get("block"),
            "model_name": miner_data.get("model_name"),
            "model_revision": miner_data.get("model_revision"),
            "model_hash": miner_data.get("model_hash"),
            "chute_id": miner_data.get("chute_id"),
            "chute_slug": miner_data.get("chute_slug"),
            "is_valid": miner_data.get("is_valid", False),
            "invalid_reason": miner_data.get("invalid_reason"),
        }

    async def save_miner(
        self,
        uid: int,
        miner_hotkey: str,
        block: Optional[int] = None,
        model_name: Optional[str] = None,
        model_revision: Optional[str] = None,
        model_hash: Optional[str] = None,
        chute_id: Optional[str] = None,
        chute_slug: Optional[str] = None,
        is_valid: bool = False,
        invalid_reason: Optional[str] = None,
    ) -> ValidMiner:
        async with get_session() as session:
            existing = await session.get(ValidMiner, uid)
            if existing:
                self._apply_miner_fields(
                    existing,
                    miner_hotkey=miner_hotkey,
                    block=block,
                    model_name=model_name,
                    model_revision=model_revision,
                    model_hash=model_hash,
                    chute_id=chute_id,
                    chute_slug=chute_slug,
                    is_valid=is_valid,
                    invalid_reason=invalid_reason,
                )
                miner = existing
            else:
                miner = ValidMiner(
                    uid=uid,
                    miner_hotkey=miner_hotkey,
                    block=block,
                    model_name=model_name,
                    model_revision=model_revision,
                    model_hash=model_hash,
                    chute_id=chute_id,
                    chute_slug=chute_slug,
                    is_valid=is_valid,
                    invalid_reason=invalid_reason,
                    last_validated_at=_now_utc(),
                )
                session.add(miner)
            await session.flush()
            return miner

    async def get_miner_by_uid(self, uid: int) -> Optional[ValidMiner]:
        async with get_session() as session:
            return await session.get(ValidMiner, uid)

    async def get_miner_by_hotkey(self, hotkey: str) -> Optional[ValidMiner]:
        async with get_session() as session:
            r = await session.execute(select(ValidMiner).where(ValidMiner.miner_hotkey == hotkey))
            return r.scalar_one_or_none()

    async def get_valid_miners(self) -> List[ValidMiner]:
        async with get_session() as session:
            r = await session.execute(select(ValidMiner).where(ValidMiner.is_valid == True))
            return list(r.scalars().all())

    async def get_all_miners(self) -> List[ValidMiner]:
        async with get_session() as session:
            r = await session.execute(select(ValidMiner).order_by(ValidMiner.uid))
            return list(r.scalars().all())

    async def set_validation_status(
        self,
        uid: int,
        is_valid: bool,
        invalid_reason: Optional[str] = None,
    ) -> bool:
        async with get_session() as session:
            stmt = (
                update(ValidMiner)
                .where(ValidMiner.uid == uid)
                .values(
                    is_valid=is_valid,
                    invalid_reason=invalid_reason,
                    last_validated_at=_now_utc(),
                )
            )
            result = await session.execute(stmt)
            return result.rowcount > 0

    async def batch_upsert_miners(self, miners: List[Dict[str, Any]]) -> int:
        count = 0
        for miner_data in miners:
            await self.save_miner(**self._save_miner_kwargs(miner_data))
            count += 1
        emit_log(f"Processed {count} miners", "info")
        return count

    async def delete_stale_miners(self, active_uids: List[int]) -> int:
        if not active_uids:
            emit_log("delete_stale_miners called with empty active_uids list, skipping", "warn")
            return 0
        async with get_session() as session:
            stmt = delete(ValidMiner).where(ValidMiner.uid.not_in(active_uids))
            result = await session.execute(stmt)
            deleted = result.rowcount
            if deleted > 0:
                emit_log(f"Deleted {deleted} stale miners", "info")
            return deleted

    async def get_valid_count(self) -> int:
        async with get_session() as session:
            r = await session.execute(
                select(func.count(ValidMiner.uid)).where(ValidMiner.is_valid == True)
            )
            return r.scalar_one()

    async def get_total_count(self) -> int:
        async with get_session() as session:
            r = await session.execute(select(func.count(ValidMiner.uid)))
            return r.scalar_one()
