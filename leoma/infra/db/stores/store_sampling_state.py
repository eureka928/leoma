"""Sampling state store."""
from leoma.infra.db.pool import get_session
from leoma.infra.db.tables import SamplingState
from sqlalchemy import select


KEY_LATEST_TASK_ID = "latest_task_id"


class SamplingStateStore:
    """Access layer for sampling_state."""

    async def get_value(self, key: str) -> str | None:
        async with get_session() as session:
            r = await session.execute(select(SamplingState).where(SamplingState.key == key))
            row = r.scalar_one_or_none()
            return row.value if row else None

    async def set_value(self, key: str, value: str) -> None:
        async with get_session() as session:
            r = await session.execute(select(SamplingState).where(SamplingState.key == key))
            row = r.scalar_one_or_none()
            if row:
                row.value = value
            else:
                session.add(SamplingState(key=key, value=value))

    async def get_latest_task_id(self) -> int | None:
        raw = await self.get_value(KEY_LATEST_TASK_ID)
        if raw is None:
            return None
        try:
            return int(raw)
        except (ValueError, TypeError):
            return None

    async def set_latest_task_id(self, task_id: int) -> None:
        await self.set_value(KEY_LATEST_TASK_ID, str(task_id))

    async def ensure_next_task_id_synced(self) -> None:
        latest = await self.get_latest_task_id()
        if latest is None:
            return
        async with get_session() as session:
            r = await session.execute(
                select(SamplingState).where(SamplingState.key == "next_task_id")
            )
            row = r.scalar_one_or_none()
            if row is None:
                session.add(SamplingState(key="next_task_id", value=str(latest + 1)))

    async def get_and_increment_next_task_id(self) -> int:
        async with get_session() as session:
            r = await session.execute(
                select(SamplingState).where(SamplingState.key == "next_task_id")
            )
            row = r.scalar_one_or_none()
            if row is None:
                next_id = 1
                session.add(SamplingState(key="next_task_id", value="2"))
            else:
                next_id = int(row.value)
                row.value = str(next_id + 1)
            await session.flush()
            return next_id
