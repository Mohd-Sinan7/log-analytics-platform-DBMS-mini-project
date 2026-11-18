"""
conftest.py — pytest fixtures for integration tests.

Requires a running Postgres and Elasticsearch (or mocks).
Uses TEST_PG_DSN and TEST_ES_HOST environment variables when set,
otherwise skips integration tests.
"""
from __future__ import annotations

import os
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# Mock app state for unit-level API tests
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_pg_pool():
    """Lightweight mock asyncpg pool for API route unit tests."""
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.fixture
def mock_es():
    """Lightweight mock AsyncElasticsearch client."""
    es = AsyncMock()
    es.cluster.health.return_value = {"status": "green"}
    return es
