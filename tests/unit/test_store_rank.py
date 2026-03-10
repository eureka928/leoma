"""
Unit tests for RankStore.

Tests score storage and retrieval operations using SQLite in-memory database.
"""

from leoma.infra.db.stores.store_rank import RankStore
from leoma.infra.db.tables import RankScore


class TestRankStoreSaveScore:
    """Tests for save_score method."""

    async def test_save_score_creates_record(
        self,
        rank_store: RankStore,
        test_hotkeys: list[str],
    ):
        """Test that save_score creates a new score record."""
        score = await rank_store.save_score(
            miner_hotkey=test_hotkeys[0],
            validator_hotkey=test_hotkeys[1],
            score=0.75,
            total_samples=20,
            total_passed=15,
            pass_rate=0.75,
        )

        assert score is not None
        assert score.miner_hotkey == test_hotkeys[0]
        assert score.validator_hotkey == test_hotkeys[1]
        assert score.score == 0.75
        assert score.total_samples == 20
        assert score.total_passed == 15
        assert score.pass_rate == 0.75

    async def test_save_score_upserts_existing(
        self,
        rank_store: RankStore,
        test_hotkeys: list[str],
    ):
        """Test that save_score updates existing record."""
        # Create initial score
        await rank_store.save_score(
            miner_hotkey=test_hotkeys[0],
            validator_hotkey=test_hotkeys[1],
            score=0.5,
            total_samples=10,
            total_passed=5,
            pass_rate=0.5,
        )

        # Update with new values
        updated = await rank_store.save_score(
            miner_hotkey=test_hotkeys[0],
            validator_hotkey=test_hotkeys[1],
            score=0.8,
            total_samples=20,
            total_passed=16,
            pass_rate=0.8,
        )

        assert updated.score == 0.8
        assert updated.total_samples == 20
        assert updated.total_passed == 16
        assert updated.pass_rate == 0.8

        # Verify only one record exists
        scores = await rank_store.get_scores_by_miner(test_hotkeys[0])
        assert len(scores) == 1

    async def test_save_score_default_values(
        self,
        rank_store: RankStore,
        test_hotkeys: list[str],
    ):
        """Test saving score with only required fields uses defaults."""
        score = await rank_store.save_score(
            miner_hotkey=test_hotkeys[0],
            validator_hotkey=test_hotkeys[1],
            score=0.6,
        )

        assert score.total_samples == 0
        assert score.total_passed == 0
        assert score.pass_rate == 0.0


class TestRankStoreBatchSaveScores:
    """Tests for batch_save_scores method."""

    async def test_batch_save_scores(
        self,
        rank_store: RankStore,
        test_hotkeys: list[str],
    ):
        """Test batch saving scores for a validator."""
        validator_hotkey = test_hotkeys[0]
        scores_data = {
            test_hotkeys[1]: {
                "score": 0.75,
                "total_samples": 20,
                "total_passed": 15,
                "pass_rate": 0.75,
            },
            test_hotkeys[2]: {
                "score": 0.6,
                "total_samples": 20,
                "total_passed": 12,
                "pass_rate": 0.6,
            },
        }

        count = await rank_store.batch_save_scores(validator_hotkey, scores_data)

        assert count == 2

        # Verify scores were saved
        saved_scores = await rank_store.get_scores_by_validator(validator_hotkey)
        assert len(saved_scores) == 2

    async def test_batch_save_scores_updates_existing(
        self,
        rank_store: RankStore,
        test_hotkeys: list[str],
    ):
        """Test that batch save updates existing scores."""
        validator_hotkey = test_hotkeys[0]
        miner_hotkey = test_hotkeys[1]

        # Create initial score
        await rank_store.save_score(
            miner_hotkey=miner_hotkey,
            validator_hotkey=validator_hotkey,
            score=0.5,
            total_samples=10,
            total_passed=5,
            pass_rate=0.5,
        )

        # Batch update
        scores_data = {
            miner_hotkey: {
                "score": 0.8,
                "total_samples": 20,
                "total_passed": 16,
                "pass_rate": 0.8,
            },
        }

        count = await rank_store.batch_save_scores(validator_hotkey, scores_data)
        assert count == 1

        # Verify update
        scores = await rank_store.get_scores_by_validator(validator_hotkey)
        assert len(scores) == 1
        assert scores[0].score == 0.8

    async def test_batch_save_scores_empty(
        self,
        rank_store: RankStore,
        test_hotkeys: list[str],
    ):
        """Test batch save with empty dict returns 0."""
        count = await rank_store.batch_save_scores(test_hotkeys[0], {})

        assert count == 0


class TestRankStoreGetScores:
    """Tests for score retrieval methods."""

    async def test_get_scores_by_validator(
        self,
        rank_store: RankStore,
        db_with_rank_scores: list[RankScore],
    ):
        """Test retrieving scores by validator hotkey."""
        validator_hotkey = db_with_rank_scores[0].validator_hotkey
        scores = await rank_store.get_scores_by_validator(validator_hotkey)

        assert len(scores) == len(db_with_rank_scores)
        assert all(s.validator_hotkey == validator_hotkey for s in scores)

    async def test_get_scores_by_validator_empty(
        self,
        rank_store: RankStore,
    ):
        """Test get_scores_by_validator returns empty list for unknown validator."""
        scores = await rank_store.get_scores_by_validator("unknown-validator")

        assert scores == []

    async def test_get_scores_by_miner(
        self,
        rank_store: RankStore,
        db_with_rank_scores: list[RankScore],
    ):
        """Test retrieving scores by miner hotkey."""
        miner_hotkey = db_with_rank_scores[0].miner_hotkey
        scores = await rank_store.get_scores_by_miner(miner_hotkey)

        assert len(scores) >= 1
        assert all(s.miner_hotkey == miner_hotkey for s in scores)

    async def test_get_scores_by_miner_empty(
        self,
        rank_store: RankStore,
    ):
        """Test get_scores_by_miner returns empty list for unknown miner."""
        scores = await rank_store.get_scores_by_miner("unknown-miner")

        assert scores == []

    async def test_get_all_scores(
        self,
        rank_store: RankStore,
        db_with_rank_scores: list[RankScore],
    ):
        """Test retrieving all scores."""
        scores = await rank_store.get_all_scores()

        assert len(scores) == len(db_with_rank_scores)


class TestRankStoreGetAggregatedScores:
    """Tests for get_aggregated_scores method."""

    async def test_get_aggregated_scores(
        self,
        rank_store: RankStore,
        db_with_rank_scores: list[RankScore],
    ):
        """Test getting aggregated scores across validators."""
        aggregated = await rank_store.get_aggregated_scores()

        # Should have entry for each unique miner
        miner_hotkeys = {s.miner_hotkey for s in db_with_rank_scores}
        assert len(aggregated) == len(miner_hotkeys)

        for miner_hotkey, stats in aggregated.items():
            assert "avg_score" in stats
            assert "total_samples" in stats
            assert "total_passed" in stats
            assert "pass_rate" in stats
            assert "validator_count" in stats
            assert stats["validator_count"] >= 1

    async def test_get_aggregated_scores_multiple_validators(
        self,
        rank_store: RankStore,
        test_hotkeys: list[str],
    ):
        """Test aggregation when miner has scores from multiple validators."""
        miner_hotkey = test_hotkeys[0]
        
        # Create scores from two validators
        await rank_store.save_score(
            miner_hotkey=miner_hotkey,
            validator_hotkey=test_hotkeys[1],
            score=0.6,
            total_samples=10,
            total_passed=6,
            pass_rate=0.6,
        )
        await rank_store.save_score(
            miner_hotkey=miner_hotkey,
            validator_hotkey=test_hotkeys[2],
            score=0.8,
            total_samples=10,
            total_passed=8,
            pass_rate=0.8,
        )

        aggregated = await rank_store.get_aggregated_scores()

        assert miner_hotkey in aggregated
        stats = aggregated[miner_hotkey]
        
        assert stats["validator_count"] == 2
        assert stats["avg_score"] == 0.7  # (0.6 + 0.8) / 2
        assert stats["total_samples"] == 20
        assert stats["total_passed"] == 14
        assert stats["pass_rate"] == 0.7  # 14 / 20

    async def test_get_aggregated_scores_empty(
        self,
        rank_store: RankStore,
    ):
        """Test aggregated scores on empty database."""
        aggregated = await rank_store.get_aggregated_scores()

        assert aggregated == {}


class TestRankStoreDelete:
    """Tests for delete operations."""

    async def test_delete_scores_by_validator(
        self,
        rank_store: RankStore,
        db_with_rank_scores: list[RankScore],
    ):
        """Test deleting all scores from a validator."""
        validator_hotkey = db_with_rank_scores[0].validator_hotkey
        deleted = await rank_store.delete_scores_by_validator(validator_hotkey)

        assert deleted == len(db_with_rank_scores)

        # Verify deletion
        remaining = await rank_store.get_scores_by_validator(validator_hotkey)
        assert len(remaining) == 0

    async def test_delete_scores_by_validator_not_found(
        self,
        rank_store: RankStore,
    ):
        """Test delete returns 0 for unknown validator."""
        deleted = await rank_store.delete_scores_by_validator("unknown-validator")

        assert deleted == 0

    async def test_delete_scores_by_miner(
        self,
        rank_store: RankStore,
        test_hotkeys: list[str],
    ):
        """Test deleting all scores for a miner."""
        miner_hotkey = test_hotkeys[0]
        
        # Create scores from multiple validators
        for i, validator_hotkey in enumerate(test_hotkeys[1:4]):
            await rank_store.save_score(
                miner_hotkey=miner_hotkey,
                validator_hotkey=validator_hotkey,
                score=0.5 + (i * 0.1),
                total_samples=10,
                total_passed=5 + i,
            )

        deleted = await rank_store.delete_scores_by_miner(miner_hotkey)

        assert deleted == 3

        # Verify deletion
        remaining = await rank_store.get_scores_by_miner(miner_hotkey)
        assert len(remaining) == 0

    async def test_delete_scores_by_miner_not_found(
        self,
        rank_store: RankStore,
    ):
        """Test delete returns 0 for unknown miner."""
        deleted = await rank_store.delete_scores_by_miner("unknown-miner")

        assert deleted == 0


class TestRankStoreEdgeCases:
    """Tests for edge cases."""

    async def test_score_with_zero_samples(
        self,
        rank_store: RankStore,
        test_hotkeys: list[str],
    ):
        """Test handling score with zero samples."""
        score = await rank_store.save_score(
            miner_hotkey=test_hotkeys[0],
            validator_hotkey=test_hotkeys[1],
            score=0.0,
            total_samples=0,
            total_passed=0,
            pass_rate=0.0,
        )

        assert score is not None
        assert score.total_samples == 0
        assert score.pass_rate == 0.0

    async def test_same_miner_multiple_validators(
        self,
        rank_store: RankStore,
        test_hotkeys: list[str],
    ):
        """Test that same miner can have scores from multiple validators."""
        miner_hotkey = test_hotkeys[0]
        
        # Create scores from different validators
        await rank_store.save_score(
            miner_hotkey=miner_hotkey,
            validator_hotkey=test_hotkeys[1],
            score=0.7,
        )
        await rank_store.save_score(
            miner_hotkey=miner_hotkey,
            validator_hotkey=test_hotkeys[2],
            score=0.8,
        )

        miner_scores = await rank_store.get_scores_by_miner(miner_hotkey)
        assert len(miner_scores) == 2
        
        validators = {s.validator_hotkey for s in miner_scores}
        assert len(validators) == 2

    async def test_same_validator_multiple_miners(
        self,
        rank_store: RankStore,
        test_hotkeys: list[str],
    ):
        """Test that same validator can have scores for multiple miners."""
        validator_hotkey = test_hotkeys[0]
        
        # Create scores for different miners
        for i, miner_hotkey in enumerate(test_hotkeys[1:4]):
            await rank_store.save_score(
                miner_hotkey=miner_hotkey,
                validator_hotkey=validator_hotkey,
                score=0.5 + (i * 0.1),
            )

        validator_scores = await rank_store.get_scores_by_validator(validator_hotkey)
        assert len(validator_scores) == 3
        
        miners = {s.miner_hotkey for s in validator_scores}
        assert len(miners) == 3
