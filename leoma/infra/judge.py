"""
GPT-4o evaluation: benchmark prompt generation and video scoring.
"""
import json
from typing import Any, Dict, List
from leoma.bootstrap import emit_log as log
from openai import AsyncOpenAI

DESCRIPTION_PROMPT = """You are writing a benchmark prompt for first-frame-conditioned video generation.

Use the provided sequential frames from a 5-second one-shot clip.
Write a single high-precision prompt that includes:
- Main subject identity, appearance, and spatial layout
- Scene/environment details and background elements
- Temporal action sequence across the clip
- Camera behavior (static, pan, tilt, dolly, zoom) and framing
- Lighting, color, texture, and mood
- Consistency constraints (what must remain stable over time)

Output requirements:
- Plain text only (no bullets, no markdown)
- 70-130 words
- Concrete and specific wording suitable for benchmark generation
"""

ASPECT_KEYS = (
    "first_frame_fidelity",
    "prompt_adherence",
    "motion_quality",
    "temporal_consistency",
    "visual_quality",
    "camera_composition",
)
ASPECT_WEIGHTS = {
    "first_frame_fidelity": 0.25,
    "prompt_adherence": 0.25,
    "motion_quality": 0.15,
    "temporal_consistency": 0.20,
    "visual_quality": 0.10,
    "camera_composition": 0.05,
}


def _strip_json_fence(content: str) -> str:
    text = content.strip()
    if "```" not in text:
        return text
    fenced = text.split("```")[1]
    return fenced[4:] if fenced.startswith("json") else fenced


def _clamp_score(value: Any, default: int = 0) -> int:
    try:
        parsed = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(0, min(100, parsed))


def _normalize_aspect_scores(raw: Any) -> Dict[str, int]:
    source = raw if isinstance(raw, dict) else {}
    return {key: _clamp_score(source.get(key), default=0) for key in ASPECT_KEYS}


def _weighted_overall_score(aspect_scores: Dict[str, int]) -> int:
    weighted = 0.0
    for key, weight in ASPECT_WEIGHTS.items():
        weighted += aspect_scores.get(key, 0) * weight
    return _clamp_score(weighted)


def _normalize_generated_eval_result(
    result: Dict[str, Any],
    *,
    pass_threshold: int,
    critical_threshold: int,
) -> Dict[str, Any]:
    aspect_scores = _normalize_aspect_scores(result.get("aspect_scores"))
    log(f"Aspect scores: {aspect_scores}")
    log(f"Pass threshold: {pass_threshold}")
    log(f"Critical threshold: {critical_threshold}")
    overall_score = _clamp_score(
        result.get("overall_score"),
        default=_weighted_overall_score(aspect_scores),
    )
    log(f"Overall score: {overall_score}")
    critical_floor = min(
        aspect_scores.get("first_frame_fidelity", 0),
        aspect_scores.get("prompt_adherence", 0),
        aspect_scores.get("temporal_consistency", 0),
    )
    passes = overall_score >= pass_threshold and critical_floor >= critical_threshold

    major_issues = result.get("major_issues")
    if not isinstance(major_issues, list):
        major_issues = []
    strengths = result.get("strengths")
    if not isinstance(strengths, list):
        strengths = []

    return {
        "passed": passes,
        "confidence": _clamp_score(result.get("confidence"), default=0),
        "original_artifacts": [],
        "generated_artifacts": [str(issue) for issue in major_issues][:20],
        "reasoning": str(result.get("reasoning") or "").strip(),
        "presentation_order": "single-video benchmark",
        "overall_score": overall_score,
        "aspect_scores": aspect_scores,
        "major_issues": [str(issue) for issue in major_issues][:20],
        "strengths": [str(item) for item in strengths][:20],
    }


def _parse_generated_eval_error(raw_text: str) -> Dict[str, Any]:
    aspect_scores = {key: 0 for key in ASPECT_KEYS}
    return {
        "passed": False,
        "confidence": 0,
        "original_artifacts": [],
        "generated_artifacts": [],
        "reasoning": f"Parse error: {raw_text[:100]}",
        "presentation_order": "single-video benchmark",
        "overall_score": 0,
        "aspect_scores": aspect_scores,
        "major_issues": [],
        "strengths": [],
    }


async def get_description_async(openai_client: AsyncOpenAI, frames: List[Dict[str, Any]]) -> str:
    content = [{"type": "text", "text": DESCRIPTION_PROMPT}] + frames
    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": content}],
        max_tokens=220,
    )
    return response.choices[0].message.content.strip()


async def evaluate_generated_video_async(
    openai_client: AsyncOpenAI,
    first_frame: List[Dict[str, Any]],
    generated_frames: List[Dict[str, Any]],
    prompt: str,
    *,
    pass_threshold: int = 70,
    critical_threshold: int = 50,
) -> Dict[str, Any]:
    content = [
        {
            "type": "text",
            "text": f"""You are a strict benchmark evaluator for first-frame-conditioned video generation.

Given:
1) A conditioning first frame
2) The benchmark generation prompt
3) Sequential frames from a generated video

Benchmark prompt:
"{prompt}"

Score this generated video from 0-100 across these aspects:
- first_frame_fidelity
- prompt_adherence
- motion_quality
- temporal_consistency
- visual_quality
- camera_composition

Evaluation rules:
- Penalize identity drift, geometry instability, flicker, temporal jumps, and prompt mismatch.
- Be strict about whether the opening generated frame respects the conditioning frame.
- Identify concrete failure artifacts.
- No ties, no ambiguity.

Respond with ONLY JSON using this schema:
{{
  "overall_score": 0-100,
  "confidence": 0-100,
  "aspect_scores": {{
    "first_frame_fidelity": 0-100,
    "prompt_adherence": 0-100,
    "motion_quality": 0-100,
    "temporal_consistency": 0-100,
    "visual_quality": 0-100,
    "camera_composition": 0-100
  }},
  "major_issues": ["issue 1", "issue 2"],
  "strengths": ["strength 1", "strength 2"],
  "reasoning": "1-2 sentences"
}}""",
        },
        {"type": "text", "text": "CONDITIONING FIRST FRAME:"},
    ] + first_frame + [
        {"type": "text", "text": "GENERATED VIDEO FRAMES (chronological):"},
    ] + generated_frames

    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": content}],
        max_tokens=450,
    )
    text = _strip_json_fence(response.choices[0].message.content)
    try:
        result = json.loads(text)
        return _normalize_generated_eval_result(
            result,
            pass_threshold=pass_threshold,
            critical_threshold=critical_threshold,
        )
    except json.JSONDecodeError:
        return _parse_generated_eval_error(text)
