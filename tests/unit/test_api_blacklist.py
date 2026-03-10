"""Unit tests for blacklist API routes."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from leoma.delivery.http.routes.blacklist import router
from leoma.infra.db.tables import Blacklist


# Module-local SS58-like identities for blacklist route tests.
BLACKLIST_ADMIN_HOTKEY = "5C62W7ELLAAfjCQeBU3me9nTXXqjVwN4kQY8w8gM9nJ8K4pL"
BLACKLIST_TARGET_HOTKEY = "5D9KxqM4nTa8cJrL2WvY6hP3sFzU1bN7eQmR5tHkC8yLpXaZ"


@pytest.fixture
def app():
    """Create a test FastAPI application with blacklist router."""
    test_app = FastAPI()
    test_app.include_router(router, prefix="/blacklist")
    return test_app


@pytest.fixture
def mock_admin_auth(app):
    """Mock the admin authentication dependency to always succeed."""
    from leoma.delivery.http.verifier import verify_admin_signature
    
    async def _mock_verify_admin_signature():
        return BLACKLIST_ADMIN_HOTKEY

    app.dependency_overrides[verify_admin_signature] = _mock_verify_admin_signature
    yield BLACKLIST_ADMIN_HOTKEY
    app.dependency_overrides.clear()


@pytest.fixture
def blacklist_entry_record():
    """Create one blacklist record for API response tests."""
    return Blacklist(
        id=1,
        hotkey=BLACKLIST_TARGET_HOTKEY,
        reason="Repeated protocol violations",
        added_by=BLACKLIST_ADMIN_HOTKEY,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def blacklist_records(test_hotkeys):
    """Create a list of blacklist records for listing endpoints."""
    entries = []
    for i, hotkey in enumerate(test_hotkeys[:3]):
        entries.append(Blacklist(
            id=i + 1,
            hotkey=hotkey,
            reason=f"Violation category {i}",
            added_by=BLACKLIST_ADMIN_HOTKEY,
            created_at=datetime.now(timezone.utc),
        ))
    return entries


class TestGetBlacklist:
    """Tests for GET /blacklist endpoint (public)."""

    async def test_get_blacklist_success(
        self,
        app: FastAPI,
        blacklist_records: list[Blacklist],
        monkeypatch,
    ):
        """Test successful retrieval of all blacklisted miners."""
        mock_dao = MagicMock()
        mock_dao.get_all = AsyncMock(return_value=blacklist_records)
        monkeypatch.setattr("leoma.delivery.http.routes.blacklist.blacklist_dao", mock_dao)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/blacklist")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == len(blacklist_records)

    async def test_get_blacklist_empty(
        self,
        app: FastAPI,
        monkeypatch,
    ):
        """Test retrieval when no entries exist."""
        mock_dao = MagicMock()
        mock_dao.get_all = AsyncMock(return_value=[])
        monkeypatch.setattr("leoma.delivery.http.routes.blacklist.blacklist_dao", mock_dao)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/blacklist")

        assert response.status_code == 200
        assert response.json() == []

    async def test_get_blacklist_response_structure(
        self,
        app: FastAPI,
        blacklist_entry_record: Blacklist,
        monkeypatch,
    ):
        """Test response contains expected blacklist fields."""
        mock_dao = MagicMock()
        mock_dao.get_all = AsyncMock(return_value=[blacklist_entry_record])
        monkeypatch.setattr("leoma.delivery.http.routes.blacklist.blacklist_dao", mock_dao)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/blacklist")

        assert response.status_code == 200
        entry_data = response.json()[0]

        # Verify all expected fields
        assert entry_data["hotkey"] == blacklist_entry_record.hotkey
        assert entry_data["reason"] == blacklist_entry_record.reason
        assert entry_data["added_by"] == blacklist_entry_record.added_by

    async def test_get_blacklist_no_auth_required(
        self,
        app: FastAPI,
        monkeypatch,
    ):
        """Test GET /blacklist is public (no auth required)."""
        mock_dao = MagicMock()
        mock_dao.get_all = AsyncMock(return_value=[])
        monkeypatch.setattr("leoma.delivery.http.routes.blacklist.blacklist_dao", mock_dao)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # No auth headers provided
            response = await client.get("/blacklist")

        # Should succeed without auth
        assert response.status_code == 200


class TestGetBlacklistedMiners:
    """Tests for GET /blacklist/miners endpoint (public)."""

    async def test_get_blacklisted_miners_success(
        self,
        app: FastAPI,
        blacklist_records: list[Blacklist],
        monkeypatch,
    ):
        """Test successful retrieval of blacklisted hotkeys."""
        hotkeys = [e.hotkey for e in blacklist_records]

        mock_dao = MagicMock()
        mock_dao.get_hotkeys = AsyncMock(return_value=hotkeys)
        monkeypatch.setattr("leoma.delivery.http.routes.blacklist.blacklist_dao", mock_dao)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/blacklist/miners")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == len(hotkeys)
        assert all(hotkey in data for hotkey in hotkeys)

    async def test_get_blacklisted_miners_empty(
        self,
        app: FastAPI,
        monkeypatch,
    ):
        """Test retrieval when no miners are blacklisted."""
        mock_dao = MagicMock()
        mock_dao.get_hotkeys = AsyncMock(return_value=[])
        monkeypatch.setattr("leoma.delivery.http.routes.blacklist.blacklist_dao", mock_dao)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/blacklist/miners")

        assert response.status_code == 200
        assert response.json() == []

    async def test_get_blacklisted_miners_no_auth_required(
        self,
        app: FastAPI,
        monkeypatch,
    ):
        """Test GET /blacklist/miners is public (no auth required)."""
        mock_dao = MagicMock()
        mock_dao.get_hotkeys = AsyncMock(return_value=[])
        monkeypatch.setattr("leoma.delivery.http.routes.blacklist.blacklist_dao", mock_dao)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/blacklist/miners")

        assert response.status_code == 200


class TestGetBlacklistEntry:
    """Tests for GET /blacklist/{hotkey} endpoint (public)."""

    async def test_get_blacklist_entry_success(
        self,
        app: FastAPI,
        blacklist_entry_record: Blacklist,
        monkeypatch,
    ):
        """Test successful retrieval of single blacklist entry."""
        mock_dao = MagicMock()
        mock_dao.get = AsyncMock(return_value=blacklist_entry_record)
        monkeypatch.setattr("leoma.delivery.http.routes.blacklist.blacklist_dao", mock_dao)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/blacklist/{blacklist_entry_record.hotkey}")

        assert response.status_code == 200
        data = response.json()
        assert data["hotkey"] == blacklist_entry_record.hotkey
        assert data["reason"] == blacklist_entry_record.reason

    async def test_get_blacklist_entry_not_found(
        self,
        app: FastAPI,
        monkeypatch,
    ):
        """Test 404 when entry not found."""
        mock_dao = MagicMock()
        mock_dao.get = AsyncMock(return_value=None)
        monkeypatch.setattr("leoma.delivery.http.routes.blacklist.blacklist_dao", mock_dao)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/blacklist/{BLACKLIST_TARGET_HOTKEY}")

        assert response.status_code == 404
        assert "not blacklisted" in response.json()["detail"].lower()

    async def test_get_blacklist_entry_no_auth_required(
        self,
        app: FastAPI,
        blacklist_entry_record: Blacklist,
        monkeypatch,
    ):
        """Test GET /blacklist/{hotkey} is public (no auth required)."""
        mock_dao = MagicMock()
        mock_dao.get = AsyncMock(return_value=blacklist_entry_record)
        monkeypatch.setattr("leoma.delivery.http.routes.blacklist.blacklist_dao", mock_dao)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/blacklist/{blacklist_entry_record.hotkey}")

        assert response.status_code == 200


class TestAddToBlacklist:
    """Tests for POST /blacklist endpoint (admin only)."""

    async def test_add_to_blacklist_success(
        self,
        app: FastAPI,
        mock_admin_auth,
        blacklist_entry_record: Blacklist,
        monkeypatch,
    ):
        """Test successful addition to blacklist."""
        mock_dao = MagicMock()
        mock_dao.add = AsyncMock(return_value=blacklist_entry_record)
        monkeypatch.setattr("leoma.delivery.http.routes.blacklist.blacklist_dao", mock_dao)

        payload = {
            "hotkey": BLACKLIST_TARGET_HOTKEY,
            "reason": "Repeated protocol violations",
        }

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/blacklist", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["hotkey"] == blacklist_entry_record.hotkey
        assert data["reason"] == blacklist_entry_record.reason

    async def test_add_to_blacklist_calls_dao_correctly(
        self,
        app: FastAPI,
        mock_admin_auth,
        blacklist_entry_record: Blacklist,
        monkeypatch,
    ):
        """Test that add to blacklist calls DAO with correct parameters."""
        mock_dao = MagicMock()
        mock_dao.add = AsyncMock(return_value=blacklist_entry_record)
        monkeypatch.setattr("leoma.delivery.http.routes.blacklist.blacklist_dao", mock_dao)

        payload = {
            "hotkey": BLACKLIST_TARGET_HOTKEY,
            "reason": "Manual review requested",
        }

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            await client.post("/blacklist", json=payload)

        mock_dao.add.assert_called_once_with(
            hotkey=BLACKLIST_TARGET_HOTKEY,
            reason="Manual review requested",
            added_by=BLACKLIST_ADMIN_HOTKEY,
        )

    async def test_add_to_blacklist_without_reason(
        self,
        app: FastAPI,
        mock_admin_auth,
        monkeypatch,
    ):
        """Test adding to blacklist without a reason."""
        entry = Blacklist(
            id=1,
            hotkey=BLACKLIST_TARGET_HOTKEY,
            reason=None,
            added_by=BLACKLIST_ADMIN_HOTKEY,
            created_at=datetime.now(timezone.utc),
        )

        mock_dao = MagicMock()
        mock_dao.add = AsyncMock(return_value=entry)
        monkeypatch.setattr("leoma.delivery.http.routes.blacklist.blacklist_dao", mock_dao)

        payload = {
            "hotkey": BLACKLIST_TARGET_HOTKEY,
        }

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/blacklist", json=payload)

        assert response.status_code == 200

    async def test_add_to_blacklist_invalid_hotkey_format(
        self,
        app: FastAPI,
        mock_admin_auth,
    ):
        """Test adding with invalid hotkey format."""
        payload = {
            "hotkey": "invalid-hotkey",
            "reason": "Manual review requested",
        }

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/blacklist", json=payload)

        assert response.status_code == 422  # Validation error

    async def test_add_to_blacklist_requires_admin(
        self,
        app: FastAPI,
    ):
        """Test POST /blacklist requires admin authentication."""
        from fastapi import HTTPException
        from leoma.delivery.http.verifier import verify_admin_signature

        async def _mock_verify_fail():
            raise HTTPException(status_code=403, detail="Admin access required")

        app.dependency_overrides[verify_admin_signature] = _mock_verify_fail

        try:
            payload = {
                "hotkey": BLACKLIST_TARGET_HOTKEY,
                "reason": "Manual review requested",
            }

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post("/blacklist", json=payload)

            assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()


class TestRemoveFromBlacklist:
    """Tests for DELETE /blacklist/{hotkey} endpoint (admin only)."""

    async def test_remove_from_blacklist_success(
        self,
        app: FastAPI,
        mock_admin_auth,
        monkeypatch,
    ):
        """Test successful removal from blacklist."""
        mock_dao = MagicMock()
        mock_dao.remove = AsyncMock(return_value=True)
        monkeypatch.setattr("leoma.delivery.http.routes.blacklist.blacklist_dao", mock_dao)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete(f"/blacklist/{BLACKLIST_TARGET_HOTKEY}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["removed_by"] == BLACKLIST_ADMIN_HOTKEY

    async def test_remove_from_blacklist_not_found(
        self,
        app: FastAPI,
        mock_admin_auth,
        monkeypatch,
    ):
        """Test 404 when trying to remove non-existent entry."""
        mock_dao = MagicMock()
        mock_dao.remove = AsyncMock(return_value=False)
        monkeypatch.setattr("leoma.delivery.http.routes.blacklist.blacklist_dao", mock_dao)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete(f"/blacklist/{BLACKLIST_TARGET_HOTKEY}")

        assert response.status_code == 404
        assert "not blacklisted" in response.json()["detail"].lower()

    async def test_remove_from_blacklist_requires_admin(
        self,
        app: FastAPI,
    ):
        """Test DELETE /blacklist/{hotkey} requires admin authentication."""
        from fastapi import HTTPException
        from leoma.delivery.http.verifier import verify_admin_signature

        async def _mock_verify_fail():
            raise HTTPException(status_code=403, detail="Admin access required")

        app.dependency_overrides[verify_admin_signature] = _mock_verify_fail

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.delete(f"/blacklist/{BLACKLIST_TARGET_HOTKEY}")

            assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()


class TestAuthenticationLevels:
    """Tests verifying correct authentication levels for all endpoints."""

    async def test_public_endpoints_no_auth(
        self,
        app: FastAPI,
        monkeypatch,
    ):
        """Test that public endpoints don't require authentication."""
        mock_dao = MagicMock()
        mock_dao.get_all = AsyncMock(return_value=[])
        mock_dao.get_hotkeys = AsyncMock(return_value=[])
        mock_dao.get = AsyncMock(return_value=None)
        monkeypatch.setattr("leoma.delivery.http.routes.blacklist.blacklist_dao", mock_dao)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # All these should work without auth
            r1 = await client.get("/blacklist")
            r2 = await client.get("/blacklist/miners")
            r3 = await client.get(f"/blacklist/{BLACKLIST_TARGET_HOTKEY}")

        # GET endpoints should succeed
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 404  # Not found, but not auth error

    async def test_admin_endpoints_require_admin(
        self,
        app: FastAPI,
    ):
        """Test that admin endpoints require admin authentication."""
        from fastapi import HTTPException
        from leoma.delivery.http.verifier import verify_admin_signature

        async def _mock_verify_fail():
            raise HTTPException(status_code=403, detail="Admin access required")

        app.dependency_overrides[verify_admin_signature] = _mock_verify_fail

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                r1 = await client.post("/blacklist", json={"hotkey": BLACKLIST_TARGET_HOTKEY})
                r2 = await client.delete(f"/blacklist/{BLACKLIST_TARGET_HOTKEY}")

            # Both should require admin
            assert r1.status_code == 403
            assert r2.status_code == 403
        finally:
            app.dependency_overrides.clear()
