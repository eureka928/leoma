"""
Unit tests for ParticipantStore.

Tests CRUD operations for participant records using SQLite in-memory database.
"""

from leoma.infra.db.stores.store_participant import ParticipantStore
from leoma.infra.db.tables import ValidMiner


class TestParticipantStoreSaveMiner:
    """Tests for save_miner method."""

    async def test_save_miner_creates_record(
        self,
        participant_store: ParticipantStore,
        test_hotkeys: list[str],
    ):
        """Test that save_miner creates a new miner record."""
        miner = await participant_store.save_miner(
            uid=0,
            miner_hotkey=test_hotkeys[0],
            model_name="user/video-generation-model",
            model_revision="abc123def456",
            model_hash="hash123",
            chute_id="3182321e-3e58-55da-ba44-051686ddbfe5",
            chute_slug="chutes-video-generation-model",
            block=1000000,
            is_valid=True,
        )

        assert miner is not None
        assert miner.uid == 0
        assert miner.miner_hotkey == test_hotkeys[0]
        assert miner.model_name == "user/video-generation-model"
        assert miner.model_revision == "abc123def456"
        assert miner.model_hash == "hash123"
        assert miner.chute_id == "3182321e-3e58-55da-ba44-051686ddbfe5"
        assert miner.chute_slug == "chutes-video-generation-model"
        assert miner.is_valid is True

    async def test_save_miner_updates_existing(
        self,
        participant_store: ParticipantStore,
        test_hotkeys: list[str],
    ):
        """Test that save_miner updates existing miner record."""
        # Create initial miner
        await participant_store.save_miner(
            uid=0,
            miner_hotkey=test_hotkeys[0],
            is_valid=False,
        )

        # Update the miner
        updated = await participant_store.save_miner(
            uid=0,
            miner_hotkey=test_hotkeys[0],
            model_name="user/updated-model",
            model_revision="newrev123",
            chute_id="11111111-2222-3333-4444-555555555555",
            chute_slug="chutes-updated-model",
            is_valid=True,
        )

        assert updated.uid == 0
        assert updated.model_name == "user/updated-model"
        assert updated.model_revision == "newrev123"
        assert updated.chute_id == "11111111-2222-3333-4444-555555555555"
        assert updated.chute_slug == "chutes-updated-model"
        assert updated.is_valid is True

    async def test_save_miner_with_invalid_reason(
        self,
        participant_store: ParticipantStore,
        test_hotkeys: list[str],
    ):
        """Test saving miner with invalid status and reason."""
        miner = await participant_store.save_miner(
            uid=0,
            miner_hotkey=test_hotkeys[0],
            is_valid=False,
            invalid_reason="Chute endpoint unreachable",
        )

        assert miner.is_valid is False
        assert miner.invalid_reason == "Chute endpoint unreachable"


class TestParticipantStoreGetMiner:
    """Tests for get_miner_by_uid and get_miner_by_hotkey methods."""

    async def test_get_miner_by_uid(
        self,
        participant_store: ParticipantStore,
        db_with_valid_miners: list[ValidMiner],
    ):
        """Test retrieving miner by UID."""
        miner = await participant_store.get_miner_by_uid(0)

        assert miner is not None
        assert miner.uid == 0

    async def test_get_miner_by_uid_not_found(
        self,
        participant_store: ParticipantStore,
    ):
        """Test get_miner_by_uid returns None for non-existent UID."""
        miner = await participant_store.get_miner_by_uid(999)

        assert miner is None

    async def test_get_miner_by_hotkey(
        self,
        participant_store: ParticipantStore,
        db_with_valid_miners: list[ValidMiner],
    ):
        """Test retrieving miner by hotkey."""
        expected_hotkey = db_with_valid_miners[0].miner_hotkey
        miner = await participant_store.get_miner_by_hotkey(expected_hotkey)

        assert miner is not None
        assert miner.miner_hotkey == expected_hotkey

    async def test_get_miner_by_hotkey_not_found(
        self,
        participant_store: ParticipantStore,
    ):
        """Test get_miner_by_hotkey returns None for unknown hotkey."""
        miner = await participant_store.get_miner_by_hotkey("unknown-hotkey")

        assert miner is None


class TestParticipantStoreGetValidMiners:
    """Tests for get_valid_miners method."""

    async def test_get_valid_miners_filters_correctly(
        self,
        participant_store: ParticipantStore,
        db_with_valid_miners: list[ValidMiner],
    ):
        """Test that get_valid_miners only returns valid miners."""
        valid_miners = await participant_store.get_valid_miners()

        assert all(m.is_valid for m in valid_miners)
        # db_with_valid_miners sets even UIDs as valid
        expected_valid = [m for m in db_with_valid_miners if m.is_valid]
        assert len(valid_miners) == len(expected_valid)

    async def test_get_all_miners(
        self,
        participant_store: ParticipantStore,
        db_with_valid_miners: list[ValidMiner],
    ):
        """Test that get_all_miners returns all miners."""
        all_miners = await participant_store.get_all_miners()

        assert len(all_miners) == len(db_with_valid_miners)


class TestParticipantStoreSetValidationStatus:
    """Tests for set_validation_status method."""

    async def test_set_validation_status_mark_invalid(
        self,
        participant_store: ParticipantStore,
        db_with_valid_miners: list[ValidMiner],
    ):
        """Test marking a miner as invalid with reason."""
        miner = db_with_valid_miners[0]
        result = await participant_store.set_validation_status(
            uid=miner.uid,
            is_valid=False,
            invalid_reason="Endpoint returned 500 error",
        )

        assert result is True

        updated = await participant_store.get_miner_by_uid(miner.uid)
        assert updated.is_valid is False
        assert updated.invalid_reason == "Endpoint returned 500 error"

    async def test_set_validation_status_mark_valid(
        self,
        participant_store: ParticipantStore,
        test_hotkeys: list[str],
    ):
        """Test marking a previously invalid miner as valid."""
        # Create invalid miner
        await participant_store.save_miner(
            uid=0,
            miner_hotkey=test_hotkeys[0],
            is_valid=False,
            invalid_reason="Initial failure",
        )

        # Mark as valid
        result = await participant_store.set_validation_status(
            uid=0,
            is_valid=True,
            invalid_reason=None,
        )

        assert result is True

        miner = await participant_store.get_miner_by_uid(0)
        assert miner.is_valid is True
        assert miner.invalid_reason is None

    async def test_set_validation_status_unknown_uid(
        self,
        participant_store: ParticipantStore,
    ):
        """Test set_validation_status returns False for unknown UID."""
        result = await participant_store.set_validation_status(
            uid=999,
            is_valid=True,
        )

        assert result is False


class TestParticipantStoreBatchOperations:
    """Tests for batch operations."""

    async def test_batch_upsert_miners(
        self,
        participant_store: ParticipantStore,
        test_hotkeys: list[str],
    ):
        """Test batch upserting miners."""
        miners_data = [
            {
                "uid": 0,
                "miner_hotkey": test_hotkeys[0],
                "model_name": "model1",
                "is_valid": True,
            },
            {
                "uid": 1,
                "miner_hotkey": test_hotkeys[1],
                "model_name": "model2",
                "is_valid": False,
                "invalid_reason": "HTTP healthcheck failed",
            },
        ]

        count = await participant_store.batch_upsert_miners(miners_data)

        assert count == 2

        # Verify both miners exist
        miner0 = await participant_store.get_miner_by_uid(0)
        miner1 = await participant_store.get_miner_by_uid(1)

        assert miner0 is not None
        assert miner0.model_name == "model1"
        assert miner0.is_valid is True

        assert miner1 is not None
        assert miner1.model_name == "model2"
        assert miner1.is_valid is False
        assert miner1.invalid_reason == "HTTP healthcheck failed"

    async def test_batch_upsert_miners_updates_existing(
        self,
        participant_store: ParticipantStore,
        test_hotkeys: list[str],
    ):
        """Test that batch upsert updates existing miners."""
        # Create initial miner
        await participant_store.save_miner(
            uid=0,
            miner_hotkey=test_hotkeys[0],
            model_name="old_model",
            is_valid=False,
        )

        # Batch upsert with updated data
        miners_data = [
            {
                "uid": 0,
                "miner_hotkey": test_hotkeys[0],
                "model_name": "new_model",
                "is_valid": True,
            },
        ]

        count = await participant_store.batch_upsert_miners(miners_data)
        assert count == 1

        # Verify update
        miner = await participant_store.get_miner_by_uid(0)
        assert miner.model_name == "new_model"
        assert miner.is_valid is True


class TestParticipantStoreDeleteStaleMiners:
    """Tests for delete_stale_miners method."""

    async def test_delete_stale_miners(
        self,
        participant_store: ParticipantStore,
        db_with_valid_miners: list[ValidMiner],
    ):
        """Test deleting miners not in active UIDs list."""
        # Keep only first 2 miners
        active_uids = [0, 1]
        deleted = await participant_store.delete_stale_miners(active_uids)

        # Should delete miners with UIDs 2, 3, 4
        assert deleted == len(db_with_valid_miners) - 2

        # Verify remaining
        remaining = await participant_store.get_all_miners()
        assert len(remaining) == 2
        assert all(m.uid in active_uids for m in remaining)

    async def test_delete_stale_miners_empty_list_skips(
        self,
        participant_store: ParticipantStore,
        db_with_valid_miners: list[ValidMiner],
    ):
        """Test that empty active_uids list doesn't delete all miners."""
        deleted = await participant_store.delete_stale_miners([])

        # Should skip deletion as protection against accidental wipe
        assert deleted == 0

        # All miners should still exist
        remaining = await participant_store.get_all_miners()
        assert len(remaining) == len(db_with_valid_miners)


class TestParticipantStoreCount:
    """Tests for count operations."""

    async def test_get_valid_count(
        self,
        participant_store: ParticipantStore,
        db_with_valid_miners: list[ValidMiner],
    ):
        """Test counting valid miners."""
        count = await participant_store.get_valid_count()

        expected_valid = [m for m in db_with_valid_miners if m.is_valid]
        assert count == len(expected_valid)

    async def test_get_total_count(
        self,
        participant_store: ParticipantStore,
        db_with_valid_miners: list[ValidMiner],
    ):
        """Test counting total miners."""
        count = await participant_store.get_total_count()

        assert count == len(db_with_valid_miners)

    async def test_get_total_count_empty(
        self,
        participant_store: ParticipantStore,
    ):
        """Test count on empty database."""
        count = await participant_store.get_total_count()

        assert count == 0
