"""Evaluation signature store."""
from leoma.infra.db.pool import get_session
from leoma.infra.db.tables import EvaluationSignature
from sqlalchemy import select


class EvaluationSignatureStore:
    """Access layer for evaluation_signatures."""

    async def get_signature(self, task_id: int, validator_hotkey: str) -> str | None:
        async with get_session() as session:
            r = await session.execute(
                select(EvaluationSignature).where(
                    EvaluationSignature.task_id == task_id,
                    EvaluationSignature.validator_hotkey == validator_hotkey,
                )
            )
            row = r.scalar_one_or_none()
            return row.signature if row else None

    async def set_signature(
        self,
        task_id: int,
        validator_hotkey: str,
        signature: str,
    ) -> None:
        async with get_session() as session:
            r = await session.execute(
                select(EvaluationSignature).where(
                    EvaluationSignature.task_id == task_id,
                    EvaluationSignature.validator_hotkey == validator_hotkey,
                )
            )
            row = r.scalar_one_or_none()
            if row:
                row.signature = signature
            else:
                session.add(
                    EvaluationSignature(
                        task_id=task_id,
                        validator_hotkey=validator_hotkey,
                        signature=signature,
                    )
                )
