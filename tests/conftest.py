"""
Shared pytest fixtures for the top-level tests package.

Currently provides a session-wide collector for hardware test results so
that a compact summary can be printed once at the end of a test run.
"""

from __future__ import annotations

from typing import Any, Dict, List

import os
import logging

import pytest


@pytest.fixture(scope="session", autouse=True)
def silence_prefect_console_logging() -> None:
    """
    Silence Prefect/Rich console logging to avoid teardown I/O errors.

    Prefect's temporary server uses a Rich console handler that can try to
    write after pytest has closed stdout/stderr, causing "I/O operation on
    closed file" ValueErrors. This fixture disables rich markup/colors and
    suppresses the noisy Prefect loggers.
    """
    os.environ["PREFECT_LOGGING_MARKUP"] = "False"
    os.environ["PREFECT_LOGGING_COLORS"] = "False"

    try:
        from prefect.server.api import server

        # Disable the subprocess server logger if present
        server.subprocess_server_logger.disabled = True
    except (ImportError, AttributeError):
        pass

    # Deeply silence Prefect-related loggers
    for logger_name in list(logging.root.manager.loggerDict.keys()) + ["prefect"]:
        if logger_name.startswith("prefect"):
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.CRITICAL)
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
            logger.addHandler(logging.NullHandler())
            logger.propagate = False

    yield


@pytest.fixture(scope="session")
def hardware_summary() -> List[Dict[str, Any]]:
    """
    Collect results from hardware tests and print a summary at the end.

    Individual hardware tests append a small dict describing their result;
    after the test session finishes this fixture prints a concise overview
    of any failures that occurred.

    Returns:
        list[dict[str, Any]]: Mutable list where tests can append result
        dictionaries with at least keys: 'kind', 'name', 'status', 'error'.
    """
    results: List[Dict[str, Any]] = []
    yield results

    if not results:
        return

    failed = [r for r in results if r.get("status") != "OK"]
    if not failed:
        print("\n=== Hardware summary: all components OK ===")
        return

    print("\n=== Hardware failure summary ===")
    for r in failed:
        kind = r.get("kind", "unknown")
        name = r.get("name", "unknown")
        status = r.get("status", "UNKNOWN")
        error = r.get("error", "")
        print(f"- {kind} '{name}': {status} ({error})")

