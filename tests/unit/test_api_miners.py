"""Unit tests for miner API routes."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from leoma.delivery.http.routes.miners import router
from leoma.infra.db.tables import ValidMiner


# Module-local SS58-like identities for route tests.
VALIDATOR_ROUTE_HOTKEY = "5C62W7ELLAAfjCQeBU3me9nTXXqjVwN4kQY8w8gM9nJ8K4pL"
MINER_ROUTE_HOTKEY = "5D9KxqM4nTa8cJrL2WvY6hP3sFzU1bN7eQmR5tHkC8yLpXaZ"


@pytest.fixture
def app():
    """Create a test FastAPI application with miners router."""
    test_app = FastAPI()
    test_app.include_router(router, prefix="/miners")
    return test_app


@pytest.fixture
def mock_auth(app):
    """Mock the authentication dependency to always succeed."""
    from leoma.delivery.http.verifier import verify_signature
    
    async def _mock_verify_signature():
        return VALIDATOR_ROUTE_HOTKEY

    app.dependency_overrides[verify_signature] = _mock_verify_signature
    yield VALIDATOR_ROUTE_HOTKEY
    app.dependency_overrides.clear()


@pytest.fixture
def miner_record():
    """Create one miner record for response tests."""
    return ValidMiner(
        uid=0,
        miner_hotkey=MINER_ROUTE_HOTKEY,
        block=1000000,
        model_name="leoma/video-generator",
        model_revision="rev-2026-03-10",
        model_hash="hash-20260310",
        chute_id="miner-chute-0",
        chute_slug="leoma-video-generator",
        is_valid=True,
        invalid_reason=None,
        last_validated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def miner_records(test_hotkeys):
    """Create a list of miner records for list endpoints."""
    miners = []
    for i, hotkey in enumerate(test_hotkeys):
        miners.append(ValidMiner(
            uid=i,
            miner_hotkey=hotkey,
            block=1000000 + i,
            model_name=f"user/model-{i}",
            model_revision=f"rev{i}",
            model_hash=f"hash{i}",
            chute_id=f"chute-id-{i}",
            chute_slug=f"chute-slug-{i}",
            is_valid=(i % 2 == 0),  # Even UIDs are valid
            invalid_reason=None if (i % 2 == 0) else "Healthcheck request failed",
            last_validated_at=datetime.now(timezone.utc),
        ))
    return miners


class TestGetValidMiners:
    """Tests for GET /miners/valid endpoint."""

    async def test_get_valid_miners_success(
        self,
        app: FastAPI,
        mock_auth,
        miner_records: list[ValidMiner],
        monkeypatch,
    ):
        """Test successful retrieval of valid miners."""
        valid_miners = [m for m in miner_records if m.is_valid]

        # Mock the DAO
        mock_dao = MagicMock()
        mock_dao.get_valid_miners = AsyncMock(return_value=valid_miners)
        mock_dao.get_all_miners = AsyncMock(return_value=miner_records)
        monkeypatch.setattr("leoma.delivery.http.routes.miners.valid_miners_dao", mock_dao)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/miners/valid")

        assert response.status_code == 200
        data = response.json()
        assert "miners" in data
        assert data["total"] == len(miner_records)
        assert data["valid_count"] == len(valid_miners)
        assert len(data["miners"]) == len(valid_miners)

    async def test_get_valid_miners_empty(
        self,
        app: FastAPI,
        mock_auth,
        monkeypatch,
    ):
        """Test retrieval when no valid miners exist."""
        mock_dao = MagicMock()
        mock_dao.get_valid_miners = AsyncMock(return_value=[])
        mock_dao.get_all_miners = AsyncMock(return_value=[])
        monkeypatch.setattr("leoma.delivery.http.routes.miners.valid_miners_dao", mock_dao)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/miners/valid")

        assert response.status_code == 200
        data = response.json()
        assert data["miners"] == []
        assert data["total"] == 0
        assert data["valid_count"] == 0

    async def test_get_valid_miners_response_structure(
        self,
        app: FastAPI,
        mock_auth,
        miner_record: ValidMiner,
        monkeypatch,
    ):
        """Test response contains expected miner fields."""
        mock_dao = MagicMock()
        mock_dao.get_valid_miners = AsyncMock(return_value=[miner_record])
        mock_dao.get_all_miners = AsyncMock(return_value=[miner_record])
        monkeypatch.setattr("leoma.delivery.http.routes.miners.valid_miners_dao", mock_dao)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/miners/valid")

        assert response.status_code == 200
        miner_data = response.json()["miners"][0]

        # Verify all expected fields are present
        assert miner_data["uid"] == miner_record.uid
        assert miner_data["hotkey"] == miner_record.miner_hotkey
        assert miner_data["model_name"] == miner_record.model_name
        assert miner_data["model_revision"] == miner_record.model_revision
        assert miner_data["model_hash"] == miner_record.model_hash
        assert miner_data["chute_id"] == miner_record.chute_id
        assert miner_data["chute_slug"] == miner_record.chute_slug
        assert miner_data["is_valid"] == miner_record.is_valid
        assert miner_data["block"] == miner_record.block


class TestGetAllMiners:
    """Tests for GET /miners/all endpoint."""

    async def test_get_all_miners_success(
        self,
        app: FastAPI,
        mock_auth,
        miner_records: list[ValidMiner],
        monkeypatch,
    ):
        """Test successful retrieval of all miners."""
        valid_count = len([m for m in miner_records if m.is_valid])

        mock_dao = MagicMock()
        mock_dao.get_all_miners = AsyncMock(return_value=miner_records)
        mock_dao.get_valid_count = AsyncMock(return_value=valid_count)
        monkeypatch.setattr("leoma.delivery.http.routes.miners.valid_miners_dao", mock_dao)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/miners/all")

        assert response.status_code == 200
        data = response.json()
        assert len(data["miners"]) == len(miner_records)
        assert data["total"] == len(miner_records)
        assert data["valid_count"] == valid_count

    async def test_get_all_miners_includes_invalid(
        self,
        app: FastAPI,
        mock_auth,
        miner_records: list[ValidMiner],
        monkeypatch,
    ):
        """Test that all miners includes both valid and invalid."""
        mock_dao = MagicMock()
        mock_dao.get_all_miners = AsyncMock(return_value=miner_records)
        mock_dao.get_valid_count = AsyncMock(return_value=3)
        monkeypatch.setattr("leoma.delivery.http.routes.miners.valid_miners_dao", mock_dao)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/miners/all")

        assert response.status_code == 200
        miners = response.json()["miners"]

        # Check we have both valid and invalid miners
        valid_statuses = [m["is_valid"] for m in miners]
        assert True in valid_statuses
        assert False in valid_statuses


class TestGetMiner:
    """Tests for GET /miners/{miner_hotkey} endpoint."""

    async def test_get_miner_success(
        self,
        app: FastAPI,
        mock_auth,
        miner_record: ValidMiner,
        monkeypatch,
    ):
        """Test successful retrieval of a single miner."""
        mock_dao = MagicMock()
        mock_dao.get_miner_by_hotkey = AsyncMock(return_value=miner_record)
        monkeypatch.setattr("leoma.delivery.http.routes.miners.valid_miners_dao", mock_dao)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/miners/{miner_record.miner_hotkey}")

        assert response.status_code == 200
        data = response.json()
        assert data["uid"] == miner_record.uid
        assert data["hotkey"] == miner_record.miner_hotkey
        assert data["is_valid"] == miner_record.is_valid

    async def test_get_miner_not_found(
        self,
        app: FastAPI,
        mock_auth,
        monkeypatch,
    ):
        """Test 404 when miner not found (valid SS58 hotkey but not in DB)."""
        mock_dao = MagicMock()
        mock_dao.get_miner_by_hotkey = AsyncMock(return_value=None)
        monkeypatch.setattr("leoma.delivery.http.routes.miners.valid_miners_dao", mock_dao)

        # Use valid SS58 format so validation passes; DAO returns None -> 404
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/miners/{MINER_ROUTE_HOTKEY}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_get_miner_with_invalid_status(
        self,
        app: FastAPI,
        mock_auth,
        test_hotkeys: list[str],
        monkeypatch,
    ):
        """Test retrieving an invalid miner shows invalid reason."""
        invalid_miner = ValidMiner(
            uid=0,
            miner_hotkey=test_hotkeys[0],
            is_valid=False,
            invalid_reason="Chute endpoint unreachable",
        )

        mock_dao = MagicMock()
        mock_dao.get_miner_by_hotkey = AsyncMock(return_value=invalid_miner)
        monkeypatch.setattr("leoma.delivery.http.routes.miners.valid_miners_dao", mock_dao)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/miners/{test_hotkeys[0]}")

        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is False
        assert data["invalid_reason"] == "Chute endpoint unreachable"


class TestAuthenticationRequired:
    """Tests for authentication requirement on miners endpoints."""

    async def test_valid_miners_requires_auth(
        self,
        app: FastAPI,
    ):
        """Test /miners/valid requires authentication."""
        from fastapi import HTTPException
        from leoma.delivery.http.verifier import verify_signature

        async def _mock_verify_fail():
            raise HTTPException(status_code=401, detail="Authentication failed")

        app.dependency_overrides[verify_signature] = _mock_verify_fail

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/miners/valid")

            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()

    async def test_all_miners_requires_auth(
        self,
        app: FastAPI,
    ):
        """Test /miners/all requires authentication."""
        from fastapi import HTTPException
        from leoma.delivery.http.verifier import verify_signature

        async def _mock_verify_fail():
            raise HTTPException(status_code=401, detail="Authentication failed")

        app.dependency_overrides[verify_signature] = _mock_verify_fail

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/miners/all")

            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()

    async def test_get_miner_requires_auth(
        self,
        app: FastAPI,
    ):
        """Test /miners/{hotkey} requires authentication."""
        from fastapi import HTTPException
        from leoma.delivery.http.verifier import verify_signature

        async def _mock_verify_fail():
            raise HTTPException(status_code=401, detail="Authentication failed")

        app.dependency_overrides[verify_signature] = _mock_verify_fail

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(f"/miners/{MINER_ROUTE_HOTKEY}")

            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()
