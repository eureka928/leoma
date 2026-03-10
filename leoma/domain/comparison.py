"""
Evaluation and comparison result types.
"""

from typing import List

from pydantic import BaseModel, Field


class EvaluationResult(BaseModel):
    """
    Evaluation result.

    Attributes
    ----------
    passed : bool
    confidence : int
        Between 0 and 100.
    reasoning : str
    original_artifacts : List[str]
    generated_artifacts : List[str]
    presentation_order : str
    """

    passed: bool
    confidence: int = Field(ge=0, le=100)
    reasoning: str
    original_artifacts: List[str] = Field(default_factory=list)
    generated_artifacts: List[str] = Field(default_factory=list)
    presentation_order: str
