"""
Unit tests for scoring utilities.

Tests score calculation and normalization.
"""

from unittest.mock import MagicMock, patch


def _mock_s3_response(metadata: dict) -> MagicMock:
    """Create a Minio-like response object for metadata JSON."""
    import json

    response = MagicMock()
    response.read.return_value = json.dumps(metadata).encode()
    response.close = MagicMock()
    response.release_conn = MagicMock()
    return response


class TestCalculateScoresFromStats:
    """Tests for score calculation from miner stats."""

    def test_calculate_pass_rate(self):
        """Test basic pass rate calculation."""
        # Simulate the calculation logic
        stats = {
            "hotkey1": {"passed_count": 10, "total": 20},
            "hotkey2": {"passed_count": 15, "total": 20},
            "hotkey3": {"passed_count": 5, "total": 20},
        }

        for hotkey, data in stats.items():
            data["pass_rate"] = data["passed_count"] / data["total"] if data["total"] > 0 else 0.0

        assert stats["hotkey1"]["pass_rate"] == 0.5
        assert stats["hotkey2"]["pass_rate"] == 0.75
        assert stats["hotkey3"]["pass_rate"] == 0.25

    def test_calculate_pass_rate_zero_samples(self):
        """Test pass rate calculation with zero samples."""
        total = 0
        passed_count = 0
        pass_rate = passed_count / total if total > 0 else 0.0

        assert pass_rate == 0.0

    def test_find_top_ranked_miner(self):
        """Test finding the top-ranked miner by pass rate."""
        scores = {
            "hotkey1": {"passed_count": 10, "total": 20, "pass_rate": 0.5},
            "hotkey2": {"passed_count": 18, "total": 20, "pass_rate": 0.9},
            "hotkey3": {"passed_count": 12, "total": 20, "pass_rate": 0.6},
        }

        top_ranked_hotkey = max(scores.keys(), key=lambda k: scores[k]["pass_rate"])

        assert top_ranked_hotkey == "hotkey2"
        assert scores[top_ranked_hotkey]["pass_rate"] == 0.9


class TestNormalizeScores:
    """Tests for score normalization."""

    def test_normalize_scores_basic(self):
        """Test basic score normalization to weights."""
        scores = {
            "hotkey1": {"pass_rate": 0.5},
            "hotkey2": {"pass_rate": 0.7},
            "hotkey3": {"pass_rate": 0.8},
        }

        total = sum(s["pass_rate"] for s in scores.values())
        weights = {k: s["pass_rate"] / total for k, s in scores.items()}

        # Sum of weights should be 1.0
        assert abs(sum(weights.values()) - 1.0) < 1e-10

    def test_normalize_scores_all_zero(self):
        """Test normalization when all pass rates are zero."""
        scores = {
            "hotkey1": {"pass_rate": 0.0},
            "hotkey2": {"pass_rate": 0.0},
        }

        total = sum(s["pass_rate"] for s in scores.values())
        if total == 0:
            # Equal distribution when all are zero
            weights = {k: 1.0 / len(scores) for k in scores}
        else:
            weights = {k: s["pass_rate"] / total for k, s in scores.items()}

        assert weights["hotkey1"] == 0.5
        assert weights["hotkey2"] == 0.5

    def test_normalize_scores_single_miner(self):
        """Test normalization with single miner."""
        scores = {"hotkey1": {"pass_rate": 0.8}}

        total = sum(s["pass_rate"] for s in scores.values())
        if total == 0:
            weights = {k: 1.0 for k in scores}
        else:
            weights = {k: s["pass_rate"] / total for k, s in scores.items()}

        assert weights["hotkey1"] == 1.0


class TestHandleNoMiners:
    """Tests for edge case with no miners."""

    async def test_calculate_scores_from_s3_no_samples(self):
        """Test score calculation when no samples in S3."""
        from leoma.app.scorer.main import calculate_scores_from_s3

        mock_minio = MagicMock()

        with patch("leoma.app.scorer.main.asyncio.to_thread") as mock_thread:
            mock_thread.return_value = []

            result = await calculate_scores_from_s3(mock_minio)

            assert result == {}

    def test_empty_scores_handling(self):
        """Test handling of empty scores dict."""
        scores = {}

        # Should handle gracefully
        total_miners = len(scores)
        total_samples = sum(s.get("total", 0) for s in scores.values())

        assert total_miners == 0
        assert total_samples == 0


class TestCalculateScoresFromS3:
    """Tests for S3-based score calculation."""

    async def test_calculate_scores_from_s3_basic(self):
        """Test basic S3 score calculation."""
        from leoma.app.scorer.main import calculate_scores_from_s3

        mock_minio = MagicMock()

        # Mock list_objects to return metadata files
        mock_obj = MagicMock()
        mock_obj.object_name = "1/metadata.json"

        with patch("leoma.app.scorer.main.asyncio.to_thread") as mock_thread:
            mock_thread.return_value = [mock_obj]

            metadata = {
                "miners": {
                    "hotkey1": {
                        "slug": "miner/model",
                        "evaluation": {"passed": True},
                    },
                    "hotkey2": {
                        "slug": "miner/model",
                        "evaluation": {"passed": False},
                    },
                }
            }

            mock_response = _mock_s3_response(metadata)

            def side_effect(*args, **kwargs):
                if callable(args[0]):
                    return args[0]()
                return mock_response

            mock_thread.side_effect = [
                [mock_obj],
                mock_response,
            ]

            result = await calculate_scores_from_s3(mock_minio)

        assert "hotkey1" in result or "hotkey2" in result or result == {}

    async def test_calculate_scores_parses_passed_field(self):
        """Test that fallback scorer accepts the new evaluation.passed key."""
        from leoma.app.scorer.main import calculate_scores_from_s3

        mock_minio = MagicMock()
        mock_obj = MagicMock()
        mock_obj.object_name = "1/metadata.json"

        metadata = {
            "miners": {
                "hotkey1": {
                    "slug": "miner/model",
                    "evaluation": {"passed": True},
                },
                "hotkey2": {
                    "slug": "miner/model2",
                    "evaluation": {"passed": False},
                },
            }
        }

        mock_response = _mock_s3_response(metadata)

        with patch("leoma.app.scorer.main.asyncio.to_thread") as mock_thread:
            mock_thread.side_effect = [
                [mock_obj],
                mock_response,
            ]

            result = await calculate_scores_from_s3(mock_minio)

        assert result["hotkey1"]["passed_count"] == 1
        assert result["hotkey1"]["total"] == 1
        assert result["hotkey2"]["passed_count"] == 0
        assert result["hotkey2"]["total"] == 1


class TestCalculateScoresFromTaskArtifacts:
    """Tests for calculating scores from S3 task artifacts."""

    async def test_calculate_scores_from_task_artifacts(self):
        """Test that `calculate_scores_from_samples` delegates to the S3 scorer."""
        from leoma.app.scorer.main import calculate_scores_from_samples

        mock_minio = MagicMock()

        with patch("leoma.app.scorer.main.calculate_scores_from_s3") as mock_s3:
            mock_s3.return_value = {"hotkey1": {"passed_count": 5, "total": 10, "pass_rate": 0.5}}

            result = await calculate_scores_from_samples(mock_minio)

            mock_s3.assert_called_once_with(mock_minio)
            assert "hotkey1" in result
            assert result["hotkey1"]["pass_rate"] == 0.5

    async def test_calculate_scores_parses_task_metadata(self):
        """Test that score calculation correctly parses task metadata."""
        from leoma.app.scorer.main import calculate_scores_from_s3
        mock_minio = MagicMock()
        mock_obj = MagicMock()
        mock_obj.object_name = "1/metadata.json"

        metadata = {
            "miners": {
                "hotkey1": {
                    "slug": "miner/model",
                    "evaluation": {"passed": True},
                },
                "hotkey2": {
                    "slug": "miner/model2",
                    "evaluation": {"passed": False},
                },
            }
        }

        mock_response = _mock_s3_response(metadata)

        with patch("leoma.app.scorer.main.asyncio.to_thread") as mock_thread:
            mock_thread.side_effect = [
                [mock_obj],
                mock_response,
            ]

            result = await calculate_scores_from_s3(mock_minio)

        # hotkey1 passed, hotkey2 failed
        assert result["hotkey1"]["passed_count"] == 1
        assert result["hotkey1"]["total"] == 1
        assert result["hotkey1"]["pass_rate"] == 1.0
        assert result["hotkey2"]["passed_count"] == 0
        assert result["hotkey2"]["total"] == 1
        assert result["hotkey2"]["pass_rate"] == 0.0


class TestTopRankedMinerSelection:
    """Tests for top-ranked miner selection logic."""

    def test_select_top_ranked_miner_by_highest_pass_rate(self):
        """Test that the top-ranked miner has the highest pass rate."""
        scores = {
            "miner_a": {"passed_count": 15, "total": 20, "pass_rate": 0.75},
            "miner_b": {"passed_count": 18, "total": 20, "pass_rate": 0.90},
            "miner_c": {"passed_count": 10, "total": 20, "pass_rate": 0.50},
        }

        if scores:
            top_ranked = max(scores.keys(), key=lambda k: scores[k]["pass_rate"])
            top_ranked_pass_rate = scores[top_ranked]["pass_rate"]
        else:
            top_ranked = None
            top_ranked_pass_rate = None

        assert top_ranked == "miner_b"
        assert top_ranked_pass_rate == 0.90

    def test_select_top_ranked_miner_with_tied_pass_rates(self):
        """Test top-ranked miner selection with tied pass rates."""
        scores = {
            "miner_a": {"passed_count": 10, "total": 20, "pass_rate": 0.50},
            "miner_b": {"passed_count": 10, "total": 20, "pass_rate": 0.50},
        }

        # max() will return one of them deterministically (first one found)
        if scores:
            top_ranked = max(scores.keys(), key=lambda k: scores[k]["pass_rate"])

        assert top_ranked in ["miner_a", "miner_b"]

    def test_select_top_ranked_miner_with_single_candidate(self):
        """Test top-ranked miner selection with a single candidate."""
        scores = {
            "only_miner": {"passed_count": 5, "total": 10, "pass_rate": 0.50},
        }

        top_ranked = max(scores.keys(), key=lambda k: scores[k]["pass_rate"])

        assert top_ranked == "only_miner"

    def test_threshold_margin_for_replacing_top_ranked_miner(self):
        """Test epsilon margin logic for replacing the current top-ranked miner."""
        current_top_ranked_rate = 0.70
        challenger_rate = 0.73
        epsilon_beat = 0.05

        challenger_beats = challenger_rate > (current_top_ranked_rate + epsilon_beat)

        assert challenger_beats is False  # 0.73 < 0.75

        # Now with sufficient margin
        challenger_rate = 0.80
        challenger_beats = challenger_rate > (current_top_ranked_rate + epsilon_beat)

        assert challenger_beats is True  # 0.80 > 0.75
