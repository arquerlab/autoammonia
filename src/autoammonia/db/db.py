"""Database session singleton for thread-safe experiment management.

This module provides a globally available, thread-safe SQLAlchemy session factory.
"""
from .session import get_scoped_session

DB_URL = "postgresql://dummy:dummy@127.0.0.1:5432/autoammonia_db"
Session = get_scoped_session(DB_URL)
