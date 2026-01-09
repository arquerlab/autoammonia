"""
Shared pytest fixtures for autoammonia tests.

Provides mocks for Redis, database, and environment variable configuration
to enable testing without external dependencies.
"""
import os
import sys
import logging

# Prefect settings to allow ephemeral mode and suppress noisy logs
os.environ["PREFECT_UNIT_TEST_MODE"] = "True"
os.environ["PREFECT_SERVER_ALLOW_EPHEMERAL_MODE"] = "True"
os.environ["PREFECT_LOGGING_LEVEL"] = "CRITICAL"
os.environ["PREFECT_SERVER_ANALYTICS_ENABLED"] = "False"

# Suppress loggers early
for logger_name in ["prefect", "prefect.server", "prefect.logging", "prefect.client"]:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from autoammonia.db.models import Precursor, Electrolyte

@pytest.fixture(scope="session", autouse=True)
def prefect_test_harness_fixture():
    """
    Use Prefect's test harness to provide a clean, isolated environment for all tests.
    This handles ephemeral server lifecycle correctly.
    """
    try:
        from prefect.testing.utilities import prefect_test_harness
        with prefect_test_harness():
            yield
    except ImportError:
        # Fallback if harness is not available
        yield

@pytest.fixture(scope="session", autouse=True)
def silence_prefect_logging():
    """
    Deeply silence Prefect and Rich to avoid "I/O operation on closed file"
    and other teardown noise.
    """
    # Disable rich markup and colors
    os.environ["PREFECT_LOGGING_MARKUP"] = "False"
    os.environ["PREFECT_LOGGING_COLORS"] = "False"
    
    # Patch subprocess_server_logger if possible
    try:
        from prefect.server.api import server
        server.subprocess_server_logger.disabled = True
    except (ImportError, AttributeError):
        pass

    # Suppress all prefect loggers and their handlers
    all_loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
    all_loggers.append(logging.getLogger("prefect"))
    
    for logger in all_loggers:
        if logger.name.startswith("prefect"):
            logger.setLevel(logging.CRITICAL)
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
            logger.addHandler(logging.NullHandler())
            logger.propagate = False

    yield

# Try to import fakeredis for better Redis mocking, fallback to manual mock
try:
    import fakeredis
    HAS_FAKEREDIS = True
except ImportError:
    HAS_FAKEREDIS = False


@pytest.fixture(scope="function", autouse=True)
def reset_component_instances():
    """
    Clear the cached component instances in decorators.py before each test.
    
    This ensures that each test creates its own instances based on the
    active configuration (simulation vs real hardware).
    """
    from autoammonia.utils import decorators
    decorators._component_instances.clear()
    yield
    decorators._component_instances.clear()


@pytest.fixture(scope="function", autouse=True)
def simulation_mode(request):
    """
    Automatically enable simulation mode for all tests except hardware tests.
    
    This fixture sets AUTOAMMONIA_SIMULATION=true and AUTOAMMONIA_MOCK_CONFIG=true
    for unit and integration tests, ensuring they use mocked hardware and fast timings.
    Hardware tests marked with @pytest.mark.hardware will have this disabled by
    the hardware_test_mode fixture.
    """
    # Check if this is a hardware test - if so, don't auto-enable simulation
    if "hardware" in request.keywords:
        yield
        return
    
    # Store original values
    original_sim = os.environ.get("AUTOAMMONIA_SIMULATION")
    original_mock = os.environ.get("AUTOAMMONIA_MOCK_CONFIG")
    
    # Set simulation mode for non-hardware tests
    os.environ["AUTOAMMONIA_SIMULATION"] = "true"
    os.environ["AUTOAMMONIA_MOCK_CONFIG"] = "true"
    
    # Reload config modules to pick up the new environment variables
    import importlib
    from autoammonia import config
    importlib.reload(config.config)
    importlib.reload(config.components_config)
    
    yield
    
    # Restore original values
    if original_sim is None:
        os.environ.pop("AUTOAMMONIA_SIMULATION", None)
    else:
        os.environ["AUTOAMMONIA_SIMULATION"] = original_sim
    
    if original_mock is None:
        os.environ.pop("AUTOAMMONIA_MOCK_CONFIG", None)
    else:
        os.environ["AUTOAMMONIA_MOCK_CONFIG"] = original_mock

    # Reload config again to restore original state for other tests
    importlib.reload(config.config)
    importlib.reload(config.components_config)


@pytest.fixture
def mock_redis(monkeypatch):
    """
    Provide a mocked Redis client for tests.
    
    Uses fakeredis if available for realistic Redis behavior, otherwise
    provides a minimal mock that supports the operations used by the codebase.
    
    Args:
        monkeypatch: Pytest's monkeypatch fixture.
    
    Returns:
        redis.Redis: A mocked Redis client instance.
    """
    if HAS_FAKEREDIS:
        # Use fakeredis for realistic Redis behavior
        fake_redis = fakeredis.FakeStrictRedis(decode_responses=True)
        
        # Patch the redis_client module's client
        from autoammonia.utils import redis_client
        monkeypatch.setattr(redis_client, "client", fake_redis)
        
        # Also patch create_redis_client to return the fake client
        def mock_create_client():
            return fake_redis
        
        monkeypatch.setattr(redis_client, "create_redis_client", mock_create_client)
        
        return fake_redis
    else:
        # Manual mock for basic operations
        mock_client = MagicMock()
        mock_client._data = {}
        mock_client._lists = {}
        mock_client._locks = {}
        
        # Implement basic Redis operations
        def mock_get(key):
            return mock_client._data.get(key)
        
        def mock_set(key, value):
            mock_client._data[key] = str(value)
            return True
        
        def mock_delete(key):
            return mock_client._data.pop(key, None) is not None
        
        def mock_lpush(key, *values):
            if key not in mock_client._lists:
                mock_client._lists[key] = []
            mock_client._lists[key] = list(values) + mock_client._lists[key]
            return len(mock_client._lists[key])
        
        def mock_lpop(key):
            if key not in mock_client._lists or not mock_client._lists[key]:
                return None
            return mock_client._lists[key].pop(0)
        
        def mock_lrange(key, start, end):
            if key not in mock_client._lists:
                return []
            lst = mock_client._lists[key]
            if end == -1:
                return lst[start:]
            return lst[start:end+1]
        
        def mock_rpush(key, *values):
            if key not in mock_client._lists:
                mock_client._lists[key] = []
            mock_client._lists[key].extend(values)
            return len(mock_client._lists[key])
        
        def mock_ping():
            return True
        
        def mock_lock(name, timeout=None):
            lock = MagicMock()
            lock_name = name
            lock.acquire = MagicMock(return_value=True)
            lock.release = MagicMock()
            lock.extend = MagicMock()
            lock.owned = MagicMock(return_value=True)
            mock_client._locks[lock_name] = lock
            return lock
        
        mock_client.get = mock_get
        mock_client.set = mock_set
        mock_client.delete = mock_delete
        mock_client.lpush = mock_lpush
        mock_client.lpop = mock_lpop
        mock_client.lrange = mock_lrange
        mock_client.rpush = mock_rpush
        mock_client.ping = mock_ping
        mock_client.lock = mock_lock
        
        # Patch the redis_client module
        from autoammonia.utils import redis_client
        monkeypatch.setattr(redis_client, "client", mock_client)
        
        def mock_create_client():
            return mock_client
        
        monkeypatch.setattr(redis_client, "create_redis_client", mock_create_client)
        
        return mock_client


@pytest.fixture
def temp_db(monkeypatch):
    """
    Provide an in-memory SQLite database for testing.
    
    Creates a temporary database with all tables from the models,
    and patches the Session to use this database instead of PostgreSQL.
    
    Args:
        monkeypatch: Pytest's monkeypatch fixture.
    
    Yields:
        scoped_session: A SQLAlchemy session factory for the test database.
    """
    # Create in-memory SQLite database
    test_db_url = "sqlite:///:memory:"
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    
    # Import models to create tables
    from autoammonia.db.models import Base
    Base.metadata.create_all(engine)
    
    # Create scoped session
    session_factory = sessionmaker(bind=engine)
    test_session = scoped_session(session_factory)
    
    # Patch get_session to return the test session (lazy Session pattern)
    from autoammonia.db import db
    monkeypatch.setattr(db, "_cached_session", test_session)
    monkeypatch.setattr(db, "get_session", lambda: test_session)
    
    yield test_session
    
    # Cleanup
    Base.metadata.drop_all(engine)
    test_session.remove()
    engine.dispose()


@pytest.fixture
def hardware_test_mode(monkeypatch):
    """
    Disable simulation mode for hardware tests.
    
    Use this fixture in hardware tests to ensure real hardware is used
    instead of mocks. This overrides the auto-enabled simulation_mode fixture.
    
    Args:
        monkeypatch: Pytest's monkeypatch fixture.
    
    Example:
        @pytest.mark.hardware
        def test_pump(hardware_test_mode):
            # This test will use real hardware
            pass
    """
    # Override the environment variables set by simulation_mode
    monkeypatch.setenv("AUTOAMMONIA_SIMULATION", "false")
    monkeypatch.setenv("AUTOAMMONIA_MOCK_CONFIG", "false")
    
    # Reload config modules to pick up the new environment variables
    import importlib
    from autoammonia import config
    importlib.reload(config.config)
    importlib.reload(config.components_config)
    
    yield
    
    # Cleanup: config will be reloaded by next test's fixtures


@pytest.fixture(autouse=True)
def mock_prefect_logger():
    """
    Mock Prefect logger for tests that use Prefect tasks/flows.
    
    This fixture patches get_run_logger to return a mock logger that
    has info, warning, and error methods that do nothing.
    
    Uses autouse=True so it's automatically applied to all tests.
    """
    # Patch get_run_logger in prefect module (this will affect all imports)
    mock_logger = MagicMock()
    with patch('prefect.get_run_logger', return_value=mock_logger):
        yield mock_logger


@pytest.fixture
def test_precursors_and_electrolytes(temp_db):
    """
    Create standard test precursors and electrolytes in the database.
    
    Creates Cu, Ni precursors and KOH, NaOH electrolytes that are
    commonly used across multiple tests.
    
    Yields:
        dict: Dictionary with 'precursors' and 'electrolytes' lists
    """
    session = temp_db()
    
    precursors = [
        Precursor(name="Cu"),
        Precursor(name="Ni"),
    ]
    electrolytes = [
        Electrolyte(name="KOH"),
        Electrolyte(name="NaOH"),
    ]
    
    session.add_all(precursors + electrolytes)
    session.commit()
    
    yield {
        "precursors": precursors,
        "electrolytes": electrolytes,
    }
    
    session.close()
