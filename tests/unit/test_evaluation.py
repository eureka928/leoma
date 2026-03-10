"""
Unit tests for evaluation utilities.

Tests GPT-4o evaluation prompt building and response parsing.
"""

import json
from unittest.mock import MagicMock


def _pass_rate(passed_count: int, total: int) -> float:
    """Compute pass rate with zero-total guard."""
    return passed_count / total if total > 0 else 0.0


class TestGetDescriptionAsync:
    """Tests for get_description_async function."""

    async def test_get_description_returns_text(self, mock_openai_client):
        """Test that get_description_async returns description text."""
        from leoma.infra.judge import get_description_async

        mock_openai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="A skateboarder crossing a quiet plaza."))]
        )

        frames = [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,abc123"}}]
        result = await get_description_async(mock_openai_client, frames)

        assert result == "A skateboarder crossing a quiet plaza."

    async def test_get_description_strips_whitespace(self, mock_openai_client):
        """Test that description is stripped of whitespace."""
        from leoma.infra.judge import get_description_async

        mock_openai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="  Trimmed text  \n"))]
        )

        frames = []
        result = await get_description_async(mock_openai_client, frames)

        assert result == "Trimmed text"

    async def test_get_description_builds_correct_prompt(self, mock_openai_client):
        """Test that the prompt is correctly constructed."""
        from leoma.infra.judge import get_description_async

        mock_openai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Description"))]
        )

        frames = [
            {"type": "image_url", "image_url": {"url": "frame1"}},
            {"type": "image_url", "image_url": {"url": "frame2"}},
        ]

        await get_description_async(mock_openai_client, frames)

        # Verify the API was called
        mock_openai_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs

        assert call_kwargs["model"] == "gpt-4o"
        assert call_kwargs["max_tokens"] == 220

        # Content should include text prompt + frames
        content = call_kwargs["messages"][0]["content"]
        assert len(content) == 3  # 1 text + 2 frames


class TestCalculatePassRate:
    """Tests for pass rate calculation logic."""

    def test_calculate_pass_rate_basic(self):
        """Test basic pass rate calculation."""
        # This is inline in the DAO, but we test the logic here
        total = 20
        passed_count = 15
        pass_rate = _pass_rate(passed_count, total)

        assert pass_rate == 0.75

    def test_calculate_pass_rate_zero_total(self):
        """Test pass rate with zero total samples."""
        total = 0
        passed_count = 0
        pass_rate = _pass_rate(passed_count, total)

        assert pass_rate == 0.0

    def test_calculate_pass_rate_all_passes(self):
        """Test pass rate with all passes."""
        total = 10
        passed_count = 10
        pass_rate = _pass_rate(passed_count, total)

        assert pass_rate == 1.0

    def test_calculate_pass_rate_no_passes(self):
        """Test pass rate with no passes."""
        total = 10
        passed_count = 0
        pass_rate = _pass_rate(passed_count, total)

        assert pass_rate == 0.0


class TestEvaluateGeneratedVideoAsync:
    """Tests for single-video benchmark evaluation."""

    async def test_evaluate_generated_video_passes(self, mock_openai_client):
        """High aspect scores should pass benchmark threshold."""
        from leoma.infra.judge import evaluate_generated_video_async

        response_json = {
            "overall_score": 86,
            "confidence": 89,
            "aspect_scores": {
                "first_frame_fidelity": 88,
                "prompt_adherence": 84,
                "motion_quality": 82,
                "temporal_consistency": 85,
                "visual_quality": 87,
                "camera_composition": 80,
            },
            "major_issues": ["minor blur"],
            "strengths": ["good temporal coherence"],
            "reasoning": "Strong adherence to prompt and stable motion.",
        }
        mock_openai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(response_json)))]
        )

        result = await evaluate_generated_video_async(
            mock_openai_client,
            first_frame=[{"type": "image_url", "image_url": {"url": "frame"}}],
            generated_frames=[{"type": "image_url", "image_url": {"url": "gen"}}],
            prompt="A person jogging in a city park at sunrise",
        )

        assert result["passed"] is True
        assert result["passed"] is True
        assert result["overall_score"] == 86
        assert result["confidence"] == 89

    async def test_evaluate_generated_video_fails_on_critical_floor(self, mock_openai_client):
        """Low critical aspect should fail even with decent overall score."""
        from leoma.infra.judge import evaluate_generated_video_async

        response_json = {
            "overall_score": 78,
            "confidence": 80,
            "aspect_scores": {
                "first_frame_fidelity": 42,
                "prompt_adherence": 84,
                "motion_quality": 82,
                "temporal_consistency": 85,
                "visual_quality": 87,
                "camera_composition": 80,
            },
            "major_issues": ["identity drift from conditioning frame"],
            "strengths": [],
            "reasoning": "Good quality overall but misses conditioning constraints.",
        }
        mock_openai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(response_json)))]
        )

        result = await evaluate_generated_video_async(
            mock_openai_client,
            first_frame=[],
            generated_frames=[],
            prompt="Test prompt",
        )

        assert result["passed"] is False
        assert result["passed"] is False
        assert result["overall_score"] == 78

    async def test_evaluate_generated_video_handles_parse_error(self, mock_openai_client):
        """Invalid JSON should return fail-safe output."""
        from leoma.infra.judge import evaluate_generated_video_async

        mock_openai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="not-json"))]
        )

        result = await evaluate_generated_video_async(
            mock_openai_client,
            first_frame=[],
            generated_frames=[],
            prompt="Test prompt",
        )

        assert result["passed"] is False
        assert result["passed"] is False
        assert result["overall_score"] == 0
        assert "Parse error" in result["reasoning"]
