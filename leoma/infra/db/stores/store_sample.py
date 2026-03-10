"""Validator samples store."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, func, distinct, select
from sqlalchemy import Integer

from leoma.bootstrap import emit_log
from leoma.infra.db.pool import get_session
from leoma.infra.db.tables import ValidatorSample


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class SampleStore:
    """Access layer for validator_samples."""

    @staticmethod
    def _lookup(validator_hotkey: str, task_id: int, miner_hotkey: str):
        return select(ValidatorSample).where(
            ValidatorSample.validator_hotkey == validator_hotkey,
            ValidatorSample.task_id == task_id,
            ValidatorSample.miner_hotkey == miner_hotkey,
        )

    @staticmethod
    def _stats_from_row(row: Any) -> Dict[str, Any]:
        total = row.total or 0
        passed_count = row.passed_count or 0
        return {"passed_count": passed_count, "total": total, "pass_rate": passed_count / total if total > 0 else 0.0}

    async def save_sample(
        self,
        validator_hotkey: str,
        task_id: int,
        miner_hotkey: str,
        s3_bucket: str,
        s3_prefix: str,
        passed: bool,
        prompt: Optional[str] = None,
        confidence: Optional[int] = None,
        reasoning: Optional[str] = None,
        latency_ms: Optional[int] = None,
        original_artifacts: Optional[str] = None,
        generated_artifacts: Optional[str] = None,
        presentation_order: Optional[str] = None,
    ) -> ValidatorSample:
        async with get_session() as session:
            r = await session.execute(self._lookup(validator_hotkey, task_id, miner_hotkey))
            existing = r.scalar_one_or_none()
            if existing:
                existing.s3_bucket = s3_bucket
                existing.s3_prefix = s3_prefix
                existing.passed = passed
                existing.prompt = prompt
                existing.confidence = confidence
                existing.reasoning = reasoning
                existing.evaluated_at = _now_utc()
                if latency_ms is not None:
                    existing.latency_ms = latency_ms
                if original_artifacts is not None:
                    existing.original_artifacts = original_artifacts
                if generated_artifacts is not None:
                    existing.generated_artifacts = generated_artifacts
                if presentation_order is not None:
                    existing.presentation_order = presentation_order
                sample = existing
            else:
                sample = ValidatorSample(
                    validator_hotkey=validator_hotkey,
                    task_id=task_id,
                    miner_hotkey=miner_hotkey,
                    s3_bucket=s3_bucket,
                    s3_prefix=s3_prefix,
                    passed=passed,
                    prompt=prompt,
                    confidence=confidence,
                    reasoning=reasoning,
                    latency_ms=latency_ms,
                    original_artifacts=original_artifacts,
                    generated_artifacts=generated_artifacts,
                    presentation_order=presentation_order,
                    evaluated_at=_now_utc(),
                )
                session.add(sample)
            await session.flush()
            return sample

    async def get_samples_by_validator(
        self, validator_hotkey: str, limit: int = 100
    ) -> List[ValidatorSample]:
        async with get_session() as session:
            q = (
                select(ValidatorSample)
                .where(ValidatorSample.validator_hotkey == validator_hotkey)
                .order_by(ValidatorSample.evaluated_at.desc())
                .limit(limit)
            )
            r = await session.execute(q)
            return list(r.scalars().all())

    async def get_samples_by_miner(
        self, miner_hotkey: str, limit: int = 100
    ) -> List[ValidatorSample]:
        async with get_session() as session:
            q = (
                select(ValidatorSample)
                .where(ValidatorSample.miner_hotkey == miner_hotkey)
                .order_by(ValidatorSample.evaluated_at.desc())
                .limit(limit)
            )
            r = await session.execute(q)
            return list(r.scalars().all())

    async def get_miner_stats_by_validator(
        self, validator_hotkey: str
    ) -> Dict[str, Dict[str, Any]]:
        async with get_session() as session:
            q = (
                select(
                    ValidatorSample.miner_hotkey,
                    func.count(ValidatorSample.id).label("total"),
                    func.sum(func.cast(ValidatorSample.passed, Integer)).label("passed_count"),
                )
                .where(ValidatorSample.validator_hotkey == validator_hotkey)
                .group_by(ValidatorSample.miner_hotkey)
            )
            r = await session.execute(q)
            return {row.miner_hotkey: self._stats_from_row(row) for row in r.all()}

    async def get_all_miner_stats(self) -> Dict[str, Dict[str, Any]]:
        async with get_session() as session:
            q = (
                select(
                    ValidatorSample.miner_hotkey,
                    func.count(ValidatorSample.id).label("total"),
                    func.sum(func.cast(ValidatorSample.passed, Integer)).label("passed_count"),
                    func.count(func.distinct(ValidatorSample.validator_hotkey)).label("validator_count"),
                )
                .group_by(ValidatorSample.miner_hotkey)
            )
            r = await session.execute(q)
            return {
                row.miner_hotkey: {**self._stats_from_row(row), "validator_count": row.validator_count}
                for row in r.all()
            }

    async def get_sample_count_by_validator(self, validator_hotkey: str) -> int:
        async with get_session() as session:
            r = await session.execute(
                select(func.count(ValidatorSample.id)).where(
                    ValidatorSample.validator_hotkey == validator_hotkey
                )
            )
            return r.scalar_one()

    async def get_total_sample_count(self) -> int:
        async with get_session() as session:
            r = await session.execute(select(func.count(ValidatorSample.id)))
            return r.scalar_one()

    async def get_recent_samples(self, limit: int = 200) -> List[ValidatorSample]:
        async with get_session() as session:
            q = (
                select(ValidatorSample)
                .order_by(ValidatorSample.evaluated_at.desc().nullslast())
                .limit(limit)
            )
            r = await session.execute(q)
            return list(r.scalars().all())

    async def get_samples_by_validator_and_task_id(
        self, validator_hotkey: str, task_id: int
    ) -> List[ValidatorSample]:
        async with get_session() as session:
            q = (
                select(ValidatorSample)
                .where(
                    ValidatorSample.validator_hotkey == validator_hotkey,
                    ValidatorSample.task_id == task_id,
                )
                .order_by(ValidatorSample.miner_hotkey.asc())
            )
            r = await session.execute(q)
            return list(r.scalars().all())

    async def get_samples_by_task_id(self, task_id: int) -> List[ValidatorSample]:
        async with get_session() as session:
            q = (
                select(ValidatorSample)
                .where(ValidatorSample.task_id == task_id)
                .order_by(ValidatorSample.miner_hotkey.asc(), ValidatorSample.evaluated_at.asc())
            )
            r = await session.execute(q)
            return list(r.scalars().all())

    async def get_latest_evaluated_task_ids(self, limit: int = 100) -> List[int]:
        async with get_session() as session:
            q = (
                select(distinct(ValidatorSample.task_id))
                .where(ValidatorSample.task_id.isnot(None))
                .order_by(ValidatorSample.task_id.desc())
                .limit(limit)
            )
            r = await session.execute(q)
            return [x[0] for x in r.all() if x[0] is not None]

    async def get_samples_in_task_window(self, task_ids: List[int]) -> List[ValidatorSample]:
        if not task_ids:
            return []
        async with get_session() as session:
            q = (
                select(ValidatorSample)
                .where(ValidatorSample.task_id.in_(task_ids))
                .order_by(ValidatorSample.task_id.desc(), ValidatorSample.miner_hotkey.asc())
            )
            r = await session.execute(q)
            return list(r.scalars().all())

    async def get_samples_by_miner_and_task_ids(
        self, miner_hotkey: str, task_ids: Optional[List[int]] = None
    ) -> List[ValidatorSample]:
        async with get_session() as session:
            q = (
                select(ValidatorSample)
                .where(ValidatorSample.miner_hotkey == miner_hotkey)
                .where(ValidatorSample.task_id.isnot(None))
            )
            if task_ids:
                q = q.where(ValidatorSample.task_id.in_(task_ids))
            q = q.order_by(
                ValidatorSample.task_id.desc().nullslast(),
                ValidatorSample.evaluated_at.desc(),
            )
            r = await session.execute(q)
            return list(r.scalars().all())

    async def get_samples_by_task_and_miner(
        self, task_id: int, miner_hotkey: str
    ) -> List[ValidatorSample]:
        async with get_session() as session:
            q = (
                select(ValidatorSample)
                .where(
                    ValidatorSample.task_id == task_id,
                    ValidatorSample.miner_hotkey == miner_hotkey,
                )
                .order_by(ValidatorSample.evaluated_at.asc())
            )
            r = await session.execute(q)
            return list(r.scalars().all())

    async def delete_samples_by_validator(self, validator_hotkey: str) -> int:
        async with get_session() as session:
            stmt = delete(ValidatorSample).where(
                ValidatorSample.validator_hotkey == validator_hotkey
            )
            result = await session.execute(stmt)
            if result.rowcount > 0:
                emit_log(f"Deleted {result.rowcount} samples from validator {validator_hotkey[:8]}...", "info")
            return result.rowcount

    async def delete_samples_by_miner(self, miner_hotkey: str) -> int:
        async with get_session() as session:
            stmt = delete(ValidatorSample).where(ValidatorSample.miner_hotkey == miner_hotkey)
            result = await session.execute(stmt)
            return result.rowcount
