# Domain: shared data shapes (no I/O).

from leoma.domain.comparison import EvaluationResult
from leoma.domain.participant import (
    MinerCommitment,
    MinerInfo,
    MinerResult,
    MinerScore,
)
from leoma.domain.source import (
    DEFAULT_GENERATION_FPS,
    DEFAULT_GENERATION_FRAMES,
    DEFAULT_GENERATION_RESOLUTION,
    DEFAULT_PROMPT_MODEL,
    GenerationInfo,
    GenerationParams,
    PromptInfo,
    VideoSource,
)
from leoma.domain.submission import SampleMetadata

__all__ = [
    "DEFAULT_GENERATION_FPS",
    "DEFAULT_GENERATION_FRAMES",
    "DEFAULT_GENERATION_RESOLUTION",
    "DEFAULT_PROMPT_MODEL",
    "EvaluationResult",
    "GenerationInfo",
    "GenerationParams",
    "MinerCommitment",
    "MinerInfo",
    "MinerResult",
    "MinerScore",
    "PromptInfo",
    "SampleMetadata",
    "VideoSource",
]
