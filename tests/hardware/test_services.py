"""
Pytest wrappers for service unit-op checks (Redis, DB, queue, Prefect).

These tests use the unit-op helpers in `unit_op_services.py` and assert that
each service is reachable. Failures are also appended to `hardware_summary`
so you get a compact summary at the end of the run.
"""

from __future__ import annotations

import asyncio
from typing import Dict, List

import pytest

from . import unit_op_services as svc


@pytest.mark.integration
def test_redis_service(hardware_summary: List[Dict[str, str]]) -> None:
    """Check that Redis is reachable and basic read/write works."""
    name, status, error = svc.redis_unit_op()
    hardware_summary.append({"kind": "redis", "name": name, "status": status, "error": error})
    assert status == "OK", f"Redis service test failed: {error}"


@pytest.mark.integration
def test_db_service(hardware_summary: List[Dict[str, str]]) -> None:
    """Check that the database is reachable and can execute a simple query."""
    name, status, error = svc.db_unit_op()
    hardware_summary.append({"kind": "db", "name": name, "status": status, "error": error})
    assert status == "OK", f"DB service test failed: {error}"


@pytest.mark.integration
def test_queue_service(hardware_summary: List[Dict[str, str]]) -> None:
    """Check that the Redis experiment queue can accept an item."""
    name, status, error = svc.queue_unit_op()
    hardware_summary.append({"kind": "queue", "name": name, "status": status, "error": error})
    assert status == "OK", f"Queue service test failed: {error}"


@pytest.mark.integration
def test_prefect_service(hardware_summary: List[Dict[str, str]]) -> None:
    """Check that Prefect API is reachable by creating/verifying a work pool."""
    name, status, error = asyncio.run(svc.prefect_unit_op())
    hardware_summary.append({"kind": "prefect", "name": name, "status": status, "error": error})
    assert status == "OK", f"Prefect service test failed: {error}"
