"""
Sample and submission metadata.

SampleMetadata and validator-sample / prompt / generation payloads.
"""

from typing import Dict, List

from pydantic import BaseModel

from leoma.domain.participant import MinerResult
from leoma.domain.source import GenerationInfo, PromptInfo, VideoSource


class SampleMetadata(BaseModel):
    """
    Full sample metadata.

    Attributes
    ----------
    task_id : int
    created_at : str
    source : VideoSource
    prompt : PromptInfo
    generation : GenerationInfo
    miners : Dict[str, MinerResult]
    files : List[str]
    """

    task_id: int
    created_at: str
    source: VideoSource
    prompt: PromptInfo
    generation: GenerationInfo
    miners: Dict[str, MinerResult]
    files: List[str]
