"""
Unit tests for ranking (dominance) logic.

Tests find_dominant_winner and compute_rank_from_miner_stats with mock data:
miners with different passed_count and commit block; determines who is top by
block order + threshold (e.g. 5%).
"""

import random

import pytest

from leoma.infra.rank import find_dominant_winner, compute_rank_from_miner_stats


def _mock_miner(hotkey: str, passed_count: int, pass_rate: float, block: int):
    """(hotkey, passed_count, pass_rate, block) for miner_stats."""
    return (hotkey, passed_count, pass_rate, block)


class TestFindDominantWinner:
    """Tests for find_dominant_winner (block order + threshold)."""

    def test_empty_returns_none(self):
        assert find_dominant_winner([], 0.05) is None

    def test_single_miner_is_top_ranked(self):
        stats = [_mock_miner("hotkey1", 50, 0.5, 1000)]
        assert find_dominant_winner(stats, 0.05) == "hotkey1"

    def test_latest_dominates_when_above_threshold(self):
        # Block 1000: 70%, block 1001: 80% -> 80 >= 70+5, so 1001 is top-ranked
        stats = [
            _mock_miner("early", 70, 0.70, 1000),
            _mock_miner("late", 80, 0.80, 1001),
        ]
        assert find_dominant_winner(stats, 0.05) == "late"

    def test_latest_does_not_dominate_within_threshold(self):
        # Block 1000: 70%, block 1001: 74% -> late doesn't beat early+5%; earliest stays top-ranked
        stats = [
            _mock_miner("early", 70, 0.70, 1000),
            _mock_miner("late", 74, 0.74, 1001),
        ]
        assert find_dominant_winner(stats, 0.05) == "early"

    def test_earliest_can_win_if_later_none_dominate(self):
        # 1000: 90%, 1001: 80%, 1002: 85% -> walking back: 1002 doesn't beat 90+5, 1001 doesn't; 1000 dominates all (no predecessors)
        stats = [
            _mock_miner("a", 90, 0.90, 1000),
            _mock_miner("b", 80, 0.80, 1001),
            _mock_miner("c", 85, 0.85, 1002),
        ]
        assert find_dominant_winner(stats, 0.05) == "a"


class TestComputeRankFromMinerStats:
    """Tests for compute_rank_from_miner_stats (top-ranked miner + full rank list)."""

    def test_empty_returns_none_and_empty_list(self):
        winner, entries = compute_rank_from_miner_stats([], 0.05)
        assert winner is None
        assert entries == []

    def test_rank_one_is_top_ranked_rest_by_passed_count(self):
        stats = [
            _mock_miner("low", 10, 0.10, 1000),
            _mock_miner("mid", 50, 0.50, 1001),
            _mock_miner("high", 90, 0.90, 1002),  # dominates (90 >= 50+5, 10+5)
        ]
        winner, entries = compute_rank_from_miner_stats(stats, 0.05)
        assert winner == "high"
        assert len(entries) == 3
        assert entries[0]["rank"] == 1 and entries[0]["miner_hotkey"] == "high"
        assert entries[0]["passed_count"] == 90 and entries[0]["pass_rate"] == 0.90
        # Ranks 2, 3 by passed_count desc
        assert entries[1]["rank"] == 2 and entries[1]["passed_count"] == 50
        assert entries[2]["rank"] == 3 and entries[2]["passed_count"] == 10

    def test_no_late_dominator_earliest_stays_rank_one(self):
        # Late (b) doesn't beat early (a) by 5%; earliest dominates (no predecessors) so it stays rank 1
        stats = [
            _mock_miner("a", 70, 0.70, 1000),
            _mock_miner("b", 74, 0.74, 1001),
        ]
        winner, entries = compute_rank_from_miner_stats(stats, 0.05)
        assert winner == "a"
        assert len(entries) == 2
        assert entries[0]["rank"] == 1 and entries[0]["miner_hotkey"] == "a"
        assert entries[1]["rank"] == 2 and entries[1]["miner_hotkey"] == "b"


class TestRankWith100MockMiners:
    """Test dominance and full rank with 100 miners (different passed_count, block)."""

    @pytest.fixture
    def hundred_miners_dominant_last(self):
        """100 miners; last (highest block) has 90% pass rate, others <= 84%."""
        base_block = 1000
        total_samples = 100
        random.seed(42)
        stats = []
        for i in range(100):
            hotkey = f"5MockHotkey{i:03d}{'x' * 48}"
            if i == 99:
                passed_count, pass_rate = 90, 0.90
            else:
                passed_count = random.randint(5, 84)
                pass_rate = passed_count / total_samples
            block = base_block + i
            stats.append((hotkey, passed_count, pass_rate, block))
        return stats

    def test_top_ranked_is_last_miner_when_dominant_last(self, hundred_miners_dominant_last):
        winner = find_dominant_winner(hundred_miners_dominant_last, 0.05)
        assert winner is not None
        assert winner == "5MockHotkey099" + "x" * 48

    def test_compute_rank_100_miners_dominant_last(self, hundred_miners_dominant_last):
        winner, entries = compute_rank_from_miner_stats(hundred_miners_dominant_last, 0.05)
        assert winner == "5MockHotkey099" + "x" * 48
        assert len(entries) == 100
        assert entries[0]["rank"] == 1
        assert entries[0]["miner_hotkey"] == winner
        assert entries[0]["block"] == 1099
        assert entries[0]["passed_count"] == 90
        assert entries[0]["pass_rate"] == 0.90
        # Ranks 2+ by passed_count descending
        for i in range(1, len(entries)):
            assert entries[i]["rank"] == i + 1
            assert entries[i]["passed_count"] <= entries[i - 1]["passed_count"]

    @pytest.fixture
    def hundred_miners_random(self):
        """100 miners; fully random passed_count (0..95), no forced dominant last."""
        base_block = 1000
        total_samples = 100
        random.seed(42)
        stats = []
        for i in range(100):
            hotkey = f"5MockHotkey{i:03d}{'x' * 48}"
            passed_count = random.randint(0, 95)
            pass_rate = passed_count / total_samples if total_samples else 0.0
            block = base_block + i
            stats.append((hotkey, passed_count, pass_rate, block))
        return stats

    def test_compute_rank_100_miners_random_determines_top(self, hundred_miners_random):
        winner, entries = compute_rank_from_miner_stats(hundred_miners_random, 0.05)
        assert len(entries) == 100
        if winner is not None:
            rank1 = next(e for e in entries if e["miner_hotkey"] == winner)
            assert rank1["rank"] == 1
        # Rank list is complete and ordered: rank 1 then by passed_count desc
        ranks = [e["rank"] for e in entries]
        assert set(ranks) == set(range(1, 101))
        for i in range(1, len(entries)):
            assert entries[i]["passed_count"] <= entries[i - 1]["passed_count"]
