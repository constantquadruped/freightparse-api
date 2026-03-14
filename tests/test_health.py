"""Tests for health and root endpoints."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.mark.anyio
async def test_root_endpoint(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "FreightParse API"
    assert data["version"] == "2.0.0"
    assert len(data["endpoints"]) == 7  # 3 text + 3 upload + batch


@pytest.mark.anyio
async def test_health_when_ai_configured(client):
    with patch("main.get_client") as mock_get:
        mock_get.return_value = object()

        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["ai_service"] == "configured"


@pytest.mark.anyio
async def test_health_when_ai_misconfigured(client):
    with patch("main.get_client") as mock_get:
        mock_get.side_effect = RuntimeError("missing key")

        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["ai_service"] == "misconfigured"


@pytest.mark.anyio
async def test_request_id_header(client, auth_headers):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text='{"confidence": 0.5}')]

    with patch("main.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_msg)
        mock_get.return_value = mock_client

        resp = await client.post("/parse-bol", json={"text": "x" * 25}, headers=auth_headers)
        assert "X-Request-ID" in resp.headers
        assert "X-Response-Time" in resp.headers
