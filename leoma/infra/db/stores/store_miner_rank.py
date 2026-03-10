"""Miner rank store."""
from typing import List, Optional

from sqlalchemy import select

from leoma.infra.db.pool import get_session
from leoma.infra.db.tables import MinerRank


class MinerRankStore:
    """Access layer for miner_ranks."""

    async def upsert(
        self,
        miner_hotkey: str,
        rank: int,
        passed_count: int,
        pass_rate: float,
        block: Optional[int] = None,
    ) -> MinerRank:
        async with get_session() as session:
            r = await session.execute(
                select(MinerRank).where(MinerRank.miner_hotkey == miner_hotkey)
            )
            row = r.scalar_one_or_none()
            if row:
                row.rank = rank
                row.passed_count = passed_count
                row.pass_rate = pass_rate
                row.block = block
                await session.flush()
                return row
            row = MinerRank(
                miner_hotkey=miner_hotkey,
                rank=rank,
                passed_count=passed_count,
                pass_rate=pass_rate,
                block=block,
            )
            session.add(row)
            await session.flush()
            return row

    async def replace_all(self, entries: List[dict]) -> None:
        async with get_session() as session:
            await session.execute(MinerRank.__table__.delete())
            for e in entries:
                session.add(
                    MinerRank(
                        miner_hotkey=e["miner_hotkey"],
                        rank=e["rank"],
                        passed_count=e.get("passed_count", 0),
                        pass_rate=e.get("pass_rate", 0.0),
                        block=e.get("block"),
                    )
                )
            await session.flush()

    async def get_winner_hotkey(self) -> Optional[str]:
        async with get_session() as session:
            r = await session.execute(
                select(MinerRank.miner_hotkey).where(MinerRank.rank == 1).limit(1)
            )
            row = r.scalar_one_or_none()
            return row[0] if row else None

    async def get_all_ordered_by_rank(self) -> List[MinerRank]:
        async with get_session() as session:
            r = await session.execute(select(MinerRank).order_by(MinerRank.rank.asc()))
            return list(r.scalars().all())

    async def get_by_miner(self, miner_hotkey: str) -> Optional[MinerRank]:
        async with get_session() as session:
            r = await session.execute(
                select(MinerRank).where(MinerRank.miner_hotkey == miner_hotkey)
            )
            return r.scalar_one_or_none()
