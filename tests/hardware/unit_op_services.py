"""
Unit operation tests for service components (Redis, DB, Prefect, queue).

These helpers return simple (name, status, details) tuples so they can be
used both from scripts and pytest tests.
"""

from typing import Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from autoammonia.db.db import Session
from autoammonia.db.db_functions import add_experiment_to_db, add_valid_electrolytes_and_metals_to_db
from autoammonia.db.models import (
    Base,
    Precursor,
    Electrolyte,
    CatalystComposition,
    ElectrolyteComposition,
    Experiment,
    Result,
)
from autoammonia.utils.redis_client import client, create_redis_client
from autoammonia.utils.prefect import create_work_pool_if_not_exists
from autoammonia.experiment_queue import enqueue_experiment


def redis_unit_op() -> Tuple[str, str, Optional[str]]:
    """
    Run a basic test on the Redis service.

    Returns:
        tuple[str, str, Optional[str]]: ("redis", "OK" | "FAILED", error message or None)
    """
    try:
        # Low-level ping via a fresh client to avoid cached state issues.
        redis_client = create_redis_client()
        redis_client.ping()

        # Basic write/read using the proxied client used by the codebase.
        test_key = "unit_op_redis_test_key"
        test_value = "42"
        client.set(test_key, test_value)
        value = client.get(test_key)

        if value != test_value:
            return ("redis", "FAILED", f"Round-trip mismatch: expected {test_value}, got {value}")

        return ("redis", "OK", None)
    except Exception as exc:  # pragma: no cover - depends on external service
        return ("redis", "FAILED", str(exc))


def db_unit_op() -> Tuple[str, str, Optional[str]]:
    """
    Run a basic end‑to‑end test on the real database using existing helpers.

    Behavior:
        - Ensures valid precursors/electrolytes are present using
          `add_valid_electrolytes_and_metals_to_db`.
        - Creates a temporary experiment via `add_experiment_to_db`.
        - Verifies the experiment exists.
        - Cleans up by deleting the experiment and related rows.

    Returns:
        tuple[str, str, Optional[str]]: ("db", "OK" | "FAILED", error message or None)
    """
    session = Session()
    experiment_id: Optional[int] = None
    try:
        # Ensure base tables/models are in place – safe no‑op if already created
        engine = session.bind
        if engine is not None:
            Base.metadata.create_all(engine)

        # Ensure valid precursors/electrolytes exist
        add_valid_electrolytes_and_metals_to_db()

        # Pick any existing precursor / electrolyte that were just inserted
        precursor = session.query(Precursor).first()
        electrolyte = session.query(Electrolyte).first()
        if precursor is None or electrolyte is None:
            session.rollback()
            return (
                "db",
                "FAILED",
                "No precursors or electrolytes found after seeding database.",
            )

        # Create a temporary experiment using those names
        experiment_id = add_experiment_to_db(
            precursor_ratios=[(precursor.name, 0.5)],
            electrolyte_ratios=[(electrolyte.name, 0.5)],
            notes="unit_op_db_test",
            metadata={"unit_op": True},
        )

        experiment = session.query(Experiment).filter_by(id=experiment_id).first()
        if experiment is None:
            session.rollback()
            return ("db", "FAILED", f"Experiment {experiment_id} not found after insertion")

        # Clean up: delete dependent rows first, then experiment
        session.query(Result).filter_by(experiment_id=experiment_id).delete()
        session.query(CatalystComposition).filter_by(experiment_id=experiment_id).delete()
        session.query(ElectrolyteComposition).filter_by(experiment_id=experiment_id).delete()
        session.query(Experiment).filter_by(id=experiment_id).delete()
        session.commit()

        return ("db", "OK", None)
    except Exception as exc:
        session.rollback()
        return ("db", "FAILED", str(exc))
    finally:
        session.close()


async def prefect_unit_op(pool_name: str = "autoammonia-unit-op") -> Tuple[str, str, Optional[str]]:
    """
    Run a basic test on the Prefect orchestration service.

    This attempts to create (or verify) a small work pool using the Prefect API.

    Args:
        pool_name (str): Name of the work pool to create or verify.

    Returns:
        tuple[str, str, Optional[str]]: ("prefect", "OK" | "FAILED", error message or None)
    """
    try:
        await create_work_pool_if_not_exists(pool_name=pool_name)
        return ("prefect", "OK", None)
    except Exception as exc:  # pragma: no cover - depends on external Prefect server
        return ("prefect", "FAILED", str(exc))


def queue_unit_op(list_name: str = "unit_op_queue") -> Tuple[str, str, Optional[str]]:
    """
    Run a basic test on the experiment queue in Redis.

    Args:
        list_name (str): Name of the Redis list to use as a test queue.

    Returns:
        tuple[str, str, Optional[str]]: ("queue", "OK" | "FAILED", error message or None)
    """
    try:
        # Enqueue a minimal dummy experiment
        dummy_experiment = {"type": "unit_op", "value": 1}
        enqueue_experiment(list_name=list_name, data=dummy_experiment)

        raw_items = client.lrange(list_name, 0, -1)
        if not raw_items:
            return ("queue", "FAILED", "No items found in queue after enqueue")

        return ("queue", "OK", None)
    except Exception as exc:  # pragma: no cover - depends on external Redis
        return ("queue", "FAILED", str(exc))
