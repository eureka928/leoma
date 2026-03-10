"""Rank scores store."""
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import delete, func, select

from leoma.infra.db.pool import get_session
from leoma.infra.db.tables import RankScore


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class RankStore:
    """Access layer for rank_scores."""

    @staticmethod
    def _lookup(miner_hotkey: str, validator_hotkey: str):
        return select(RankScore).where(
            RankScore.miner_hotkey == miner_hotkey,
            RankScore.validator_hotkey == validator_hotkey,
        )

    @staticmethod
    def _build_payload(data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "score": data.get("score", 0.0),
            "total_samples": data.get("total_samples", 0),
            "total_passed": data.get("total_passed", 0),
            "pass_rate": data.get("pass_rate", 0.0),
        }

    @staticmethod
    def _row_to_agg(row: Any) -> Dict[str, Any]:
        total_samples = row.total_samples or 0
        total_passed = row.total_passed or 0
        return {
            "avg_score": float(row.avg_score or 0),
            "total_samples": total_samples,
            "total_passed": total_passed,
            "pass_rate": total_passed / total_samples if total_samples > 0 else 0.0,
            "validator_count": row.validator_count,
        }

    async def save_score(
        self,
        miner_hotkey: str,
        validator_hotkey: str,
        score: float,
        total_samples: int = 0,
        total_passed: int = 0,
        pass_rate: float = 0.0,
    ) -> RankScore:
        async with get_session() as session:
            r = await session.execute(self._lookup(miner_hotkey, validator_hotkey))
            existing = r.scalar_one_or_none()
            if existing:
                existing.score = score
                existing.total_samples = total_samples
                existing.total_passed = total_passed
                existing.pass_rate = pass_rate
                existing.updated_at = _now_utc()
                rank_score = existing
            else:
                rank_score = RankScore(
                    miner_hotkey=miner_hotkey,
                    validator_hotkey=validator_hotkey,
                    score=score,
                    total_samples=total_samples,
                    total_passed=total_passed,
                    pass_rate=pass_rate,
                )
                session.add(rank_score)
            await session.flush()
            return rank_score

    async def batch_save_scores(
        self, validator_hotkey: str, scores: Dict[str, Dict[str, Any]]
    ) -> int:
        count = 0
        for miner_hotkey, data in scores.items():
            p = self._build_payload(data)
            await self.save_score(
                miner_hotkey=miner_hotkey,
                validator_hotkey=validator_hotkey,
                score=p["score"],
                total_samples=p["total_samples"],
                total_passed=p["total_passed"],
                pass_rate=p["pass_rate"],
            )
            count += 1
        return count

    async def get_scores_by_validator(self, validator_hotkey: str) -> List[RankScore]:
        async with get_session() as session:
            r = await session.execute(
                select(RankScore).where(RankScore.validator_hotkey == validator_hotkey)
            )
            return list(r.scalars().all())

    async def get_scores_by_miner(self, miner_hotkey: str) -> List[RankScore]:
        async with get_session() as session:
            r = await session.execute(
                select(RankScore).where(RankScore.miner_hotkey == miner_hotkey)
            )
            return list(r.scalars().all())

    async def get_all_scores(self) -> List[RankScore]:
        async with get_session() as session:
            r = await session.execute(select(RankScore))
            return list(r.scalars().all())

    async def get_aggregated_scores(self) -> Dict[str, Dict[str, Any]]:
        async with get_session() as session:
            q = (
                select(
                    RankScore.miner_hotkey,
                    func.avg(RankScore.score).label("avg_score"),
                    func.sum(RankScore.total_samples).label("total_samples"),
                    func.sum(RankScore.total_passed).label("total_passed"),
                    func.count(RankScore.validator_hotkey).label("validator_count"),
                )
                .group_by(RankScore.miner_hotkey)
            )
            r = await session.execute(q)
            return {row.miner_hotkey: self._row_to_agg(row) for row in r.all()}

    async def delete_scores_by_validator(self, validator_hotkey: str) -> int:
        async with get_session() as session:
            stmt = delete(RankScore).where(RankScore.validator_hotkey == validator_hotkey)
            r = await session.execute(stmt)
            return r.rowcount

    async def delete_scores_by_miner(self, miner_hotkey: str) -> int:
        async with get_session() as session:
            stmt = delete(RankScore).where(RankScore.miner_hotkey == miner_hotkey)
            r = await session.execute(stmt)
            return r.rowcount

    async def get_validator_summaries(self) -> List[Dict[str, Any]]:
        async with get_session() as session:
            q = (
                select(
                    RankScore.validator_hotkey,
                    func.sum(RankScore.total_samples).label("total_samples"),
                    func.sum(RankScore.total_passed).label("total_passed"),
                    func.avg(RankScore.score).label("avg_score"),
                    func.max(RankScore.updated_at).label("last_updated"),
                )
                .group_by(RankScore.validator_hotkey)
            )
            r = await session.execute(q)
            out = []
            for row in r.all():
                total_samples = row.total_samples or 0
                total_passed = row.total_passed or 0
                out.append({
                    "validator_hotkey": row.validator_hotkey,
                    "total_samples": total_samples,
                    "total_passed": total_passed,
                    "avg_score": float(row.avg_score or 0),
                    "pass_rate": total_passed / total_samples if total_samples > 0 else 0.0,
                    "last_updated": row.last_updated,
                })
            return out
