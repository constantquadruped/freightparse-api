"""Tests for authentication and rate limiting."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.mark.anyio
async def test_no_auth_returns_401(client):
    resp = await client.post("/parse-bol", json={"text": "x" * 25})
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_invalid_api_key_returns_401(client):
    resp = await client.post(
        "/parse-bol",
        json={"text": "x" * 25},
        headers={"X-API-Key": "wrong-key"},
    )
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_valid_direct_key(client, auth_headers):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text='{"confidence": 0.5}')]

    with patch("main.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_msg)
        mock_get.return_value = mock_client

        resp = await client.post("/parse-bol", json={"text": "x" * 25}, headers=auth_headers)
        assert resp.status_code == 200


@pytest.mark.anyio
async def test_rate_limit_returns_429(client, auth_headers):
    import main
    main.rate_store.clear()  # Reset from prior tests

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text='{"confidence": 0.5}')]

    with patch("main.get_client") as mock_get, \
         patch("main.RATE_LIMIT", 2):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_msg)
        mock_get.return_value = mock_client

        # First two should succeed
        for _ in range(2):
            resp = await client.post("/parse-bol", json={"text": "x" * 25}, headers=auth_headers)
            assert resp.status_code == 200

        # Third should be rate limited
        resp = await client.post("/parse-bol", json={"text": "x" * 25}, headers=auth_headers)
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers


@pytest.mark.anyio
async def test_rate_limit_isolated_per_direct_key(client):
    import main
    main.rate_store.clear()

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text='{"confidence": 0.5}')]

    with patch("main.get_client") as mock_get, patch("main.RATE_LIMIT", 1):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_msg)
        mock_get.return_value = mock_client

        first_key = {"X-API-Key": "test-key-1", "Content-Type": "application/json"}
        second_key = {"X-API-Key": "test-key-2", "Content-Type": "application/json"}

        resp = await client.post("/parse-bol", json={"text": "x" * 25}, headers=first_key)
        assert resp.status_code == 200

        resp = await client.post("/parse-bol", json={"text": "x" * 25}, headers=second_key)
        assert resp.status_code == 200

        resp = await client.post("/parse-bol", json={"text": "x" * 25}, headers=first_key)
        assert resp.status_code == 429
