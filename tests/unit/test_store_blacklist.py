"""
Unit tests for BlacklistStore.

Tests CRUD operations for blacklist records using SQLite in-memory database.
"""

from leoma.infra.db.stores.store_blacklist import BlacklistStore
from leoma.infra.db.tables import Blacklist


class TestBlacklistStoreAdd:
    """Tests for add method."""

    async def test_add_creates_blacklist_entry(
        self,
        blacklist_store: BlacklistStore,
        test_hotkeys: list[str],
    ):
        """Test that add creates a new blacklist entry."""
        entry = await blacklist_store.add(
            hotkey=test_hotkeys[0],
            reason="Malicious behavior detected",
            added_by=test_hotkeys[1],
        )

        assert entry is not None
        assert entry.hotkey == test_hotkeys[0]
        assert entry.reason == "Malicious behavior detected"
        assert entry.added_by == test_hotkeys[1]

    async def test_add_updates_existing_entry(
        self,
        blacklist_store: BlacklistStore,
        test_hotkeys: list[str],
    ):
        """Test that add updates an existing blacklist entry."""
        # Create initial entry
        await blacklist_store.add(
            hotkey=test_hotkeys[0],
            reason="Initial reason",
            added_by=test_hotkeys[1],
        )

        # Update the entry
        updated = await blacklist_store.add(
            hotkey=test_hotkeys[0],
            reason="Updated reason",
            added_by=test_hotkeys[2],
        )

        assert updated.hotkey == test_hotkeys[0]
        assert updated.reason == "Updated reason"
        assert updated.added_by == test_hotkeys[2]

    async def test_add_with_no_reason(
        self,
        blacklist_store: BlacklistStore,
        test_hotkeys: list[str],
    ):
        """Test adding to blacklist without a reason."""
        entry = await blacklist_store.add(
            hotkey=test_hotkeys[0],
        )

        assert entry is not None
        assert entry.hotkey == test_hotkeys[0]
        assert entry.reason is None
        assert entry.added_by is None


class TestBlacklistStoreRemove:
    """Tests for remove method."""

    async def test_remove_existing_entry(
        self,
        blacklist_store: BlacklistStore,
        test_hotkeys: list[str],
    ):
        """Test removing an existing blacklist entry."""
        # Add entry first
        await blacklist_store.add(
            hotkey=test_hotkeys[0],
            reason="Manual moderation review",
        )

        # Remove it
        result = await blacklist_store.remove(test_hotkeys[0])

        assert result is True

        # Verify it's removed
        entry = await blacklist_store.get(test_hotkeys[0])
        assert entry is None

    async def test_remove_nonexistent_entry(
        self,
        blacklist_store: BlacklistStore,
        test_hotkeys: list[str],
    ):
        """Test removing a non-existent entry returns False."""
        result = await blacklist_store.remove(test_hotkeys[0])

        assert result is False


class TestBlacklistStoreIsBlacklisted:
    """Tests for is_blacklisted method."""

    async def test_is_blacklisted_returns_true_for_blacklisted(
        self,
        blacklist_store: BlacklistStore,
        test_hotkeys: list[str],
    ):
        """Test is_blacklisted returns True for blacklisted hotkey."""
        await blacklist_store.add(
            hotkey=test_hotkeys[0],
            reason="Manual moderation review",
        )

        result = await blacklist_store.is_blacklisted(test_hotkeys[0])

        assert result is True

    async def test_is_blacklisted_returns_false_for_non_blacklisted(
        self,
        blacklist_store: BlacklistStore,
        test_hotkeys: list[str],
    ):
        """Test is_blacklisted returns False for non-blacklisted hotkey."""
        result = await blacklist_store.is_blacklisted(test_hotkeys[0])

        assert result is False


class TestBlacklistStoreGet:
    """Tests for get method."""

    async def test_get_existing_entry(
        self,
        blacklist_store: BlacklistStore,
        test_hotkeys: list[str],
    ):
        """Test getting an existing blacklist entry."""
        await blacklist_store.add(
            hotkey=test_hotkeys[0],
            reason="Manual moderation review",
            added_by=test_hotkeys[1],
        )

        entry = await blacklist_store.get(test_hotkeys[0])

        assert entry is not None
        assert entry.hotkey == test_hotkeys[0]
        assert entry.reason == "Manual moderation review"
        assert entry.added_by == test_hotkeys[1]

    async def test_get_nonexistent_entry(
        self,
        blacklist_store: BlacklistStore,
        test_hotkeys: list[str],
    ):
        """Test getting a non-existent entry returns None."""
        entry = await blacklist_store.get(test_hotkeys[0])

        assert entry is None


class TestBlacklistStoreGetAll:
    """Tests for get_all method."""

    async def test_get_all_returns_all_entries(
        self,
        blacklist_store: BlacklistStore,
        test_hotkeys: list[str],
    ):
        """Test get_all returns all blacklisted entries."""
        # Add multiple entries
        for i, hotkey in enumerate(test_hotkeys[:3]):
            await blacklist_store.add(
                hotkey=hotkey,
                reason=f"Reason {i}",
            )

        entries = await blacklist_store.get_all()

        assert len(entries) == 3
        hotkeys = {e.hotkey for e in entries}
        assert test_hotkeys[0] in hotkeys
        assert test_hotkeys[1] in hotkeys
        assert test_hotkeys[2] in hotkeys

    async def test_get_all_returns_empty_list_when_no_entries(
        self,
        blacklist_store: BlacklistStore,
    ):
        """Test get_all returns empty list when no entries exist."""
        entries = await blacklist_store.get_all()

        assert entries == []


class TestBlacklistStoreGetHotkeys:
    """Tests for get_hotkeys method."""

    async def test_get_hotkeys_returns_list_of_hotkeys(
        self,
        blacklist_store: BlacklistStore,
        test_hotkeys: list[str],
    ):
        """Test get_hotkeys returns list of blacklisted hotkeys."""
        # Add multiple entries
        for hotkey in test_hotkeys[:3]:
            await blacklist_store.add(hotkey=hotkey)

        hotkeys = await blacklist_store.get_hotkeys()

        assert len(hotkeys) == 3
        assert test_hotkeys[0] in hotkeys
        assert test_hotkeys[1] in hotkeys
        assert test_hotkeys[2] in hotkeys

    async def test_get_hotkeys_returns_empty_list_when_no_entries(
        self,
        blacklist_store: BlacklistStore,
    ):
        """Test get_hotkeys returns empty list when no entries exist."""
        hotkeys = await blacklist_store.get_hotkeys()

        assert hotkeys == []


class TestBlacklistStoreWithPrePopulatedData:
    """Tests using pre-populated blacklist fixture."""

    async def test_get_all_with_fixture(
        self,
        blacklist_store: BlacklistStore,
        db_with_blacklist: list[Blacklist],
    ):
        """Test get_all with pre-populated data."""
        entries = await blacklist_store.get_all()

        assert len(entries) == len(db_with_blacklist)

    async def test_is_blacklisted_with_fixture(
        self,
        blacklist_store: BlacklistStore,
        db_with_blacklist: list[Blacklist],
    ):
        """Test is_blacklisted with pre-populated data."""
        # First entry should be blacklisted
        result = await blacklist_store.is_blacklisted(db_with_blacklist[0].hotkey)
        assert result is True

        # Random hotkey should not be blacklisted
        result = await blacklist_store.is_blacklisted("5XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
        assert result is False
