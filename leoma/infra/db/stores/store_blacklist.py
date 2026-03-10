"""Blacklist store."""
from typing import List, Optional

from sqlalchemy import delete, select

from leoma.bootstrap import emit_log
from leoma.infra.db.pool import get_session
from leoma.infra.db.tables import Blacklist


class BlacklistStore:
    """Access layer for blacklist."""

    @staticmethod
    def _by_hotkey(hotkey: str):
        return select(Blacklist).where(Blacklist.hotkey == hotkey)

    async def _get_entry(self, hotkey: str) -> Optional[Blacklist]:
        async with get_session() as session:
            r = await session.execute(self._by_hotkey(hotkey))
            return r.scalar_one_or_none()

    async def add(
        self,
        hotkey: str,
        reason: Optional[str] = None,
        added_by: Optional[str] = None,
    ) -> Blacklist:
        async with get_session() as session:
            r = await session.execute(self._by_hotkey(hotkey))
            existing = r.scalar_one_or_none()
            if existing:
                existing.reason = reason
                existing.added_by = added_by
                entry = existing
            else:
                entry = Blacklist(hotkey=hotkey, reason=reason, added_by=added_by)
                session.add(entry)
            await session.flush()
        emit_log(f"Added miner {hotkey[:8]}... to blacklist: {reason}", "info")
        return entry

    async def remove(self, hotkey: str) -> bool:
        async with get_session() as session:
            stmt = delete(Blacklist).where(Blacklist.hotkey == hotkey)
            r = await session.execute(stmt)
            if r.rowcount > 0:
                emit_log(f"Removed miner {hotkey[:8]}... from blacklist", "info")
                return True
            return False

    async def is_blacklisted(self, hotkey: str) -> bool:
        return (await self._get_entry(hotkey)) is not None

    async def get(self, hotkey: str) -> Optional[Blacklist]:
        return await self._get_entry(hotkey)

    async def get_all(self) -> List[Blacklist]:
        async with get_session() as session:
            r = await session.execute(select(Blacklist))
            return list(r.scalars().all())

    async def get_hotkeys(self) -> List[str]:
        entries = await self.get_all()
        return [e.hotkey for e in entries]
