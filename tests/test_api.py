"""
test_api.py — API integration tests (using TestClient with mock state).
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone

# We test routes in isolation by patching DB/ES
from api.main import app


def _make_app_with_mocks(pg_rows=None, es_hits=None, es_total=0, health_pg="ok", health_es="green"):
    """Return a TestClient with mocked state."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    if pg_rows is not None:
        mock_conn.fetch = AsyncMock(return_value=pg_rows)
        mock_conn.fetchval = AsyncMock(return_value=1)
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_es = AsyncMock()
    mock_es.cluster.health = AsyncMock(return_value={"status": health_es})
    if es_hits is not None:
        mock_es.search = AsyncMock(return_value={
            "hits": {
                "total": {"value": es_total},
                "hits": es_hits,
            }
        })

    app.state.pg = mock_pool
    app.state.es = mock_es
    return TestClient(app, raise_server_exceptions=True)


def _make_log_row():
    """Return a mock asyncpg Record-like dict for a log entry."""
    import uuid
    return {
        "id": 1,
        "doc_id": uuid.uuid4(),
        "ts": datetime(2026, 10, 26, 10, 15, 32, tzinfo=timezone.utc),
        "severity": "ERROR",
        "service": "payments",
        "host": "host-03",
        "trace_id": "ab12cd34",
        "message": "Payment gateway timeout after 3 retries",
    }


class TestHealthEndpoint:
    def test_health_ok(self):
        client = _make_app_with_mocks()
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "postgres" in data
        assert "elasticsearch" in data

    def test_health_returns_json(self):
        client = _make_app_with_mocks()
        resp = client.get("/health")
        assert resp.headers["content-type"].startswith("application/json")


class TestLogsEndpoint:
    def _row_as_mapping(self):
        row = _make_log_row()
        m = MagicMock()
        m.__getitem__ = lambda self_, k: row[k]
        m.keys = lambda: row.keys()
        # Make dict(r) work
        m.__iter__ = lambda self_: iter(row)
        return m

    def test_logs_returns_200(self):
        """GET /logs returns 200 even with empty result."""
        client = _make_app_with_mocks(pg_rows=[])
        resp = client.get("/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert data["total_returned"] == 0

    def test_logs_limit_validation(self):
        client = _make_app_with_mocks(pg_rows=[])
        resp = client.get("/logs?limit=0")
        assert resp.status_code == 422

    def test_logs_limit_max(self):
        client = _make_app_with_mocks(pg_rows=[])
        resp = client.get("/logs?limit=1001")
        assert resp.status_code == 422


class TestAnomaliesEndpoint:
    def test_anomalies_empty(self):
        client = _make_app_with_mocks(pg_rows=[])
        resp = client.get("/anomalies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] == []


class TestStatsEndpoint:
    def test_error_rate_valid_intervals(self):
        client = _make_app_with_mocks(pg_rows=[])
        for interval in ("1m", "5m", "1h"):
            resp = client.get(f"/stats/error-rate?interval={interval}")
            assert resp.status_code == 200, f"Failed for interval={interval}"

    def test_error_rate_invalid_interval(self):
        client = _make_app_with_mocks(pg_rows=[])
        resp = client.get("/stats/error-rate?interval=2m")
        assert resp.status_code == 422

    def test_top_hosts_returns_200(self):
        client = _make_app_with_mocks(pg_rows=[])
        resp = client.get("/stats/top-hosts")
        assert resp.status_code == 200


class TestTraceEndpoint:
    def test_trace_returns_200(self):
        client = _make_app_with_mocks(pg_rows=[])
        resp = client.get("/trace/ab12cd34")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
