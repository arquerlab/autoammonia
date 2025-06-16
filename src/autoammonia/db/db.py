"""Database session singleton for thread-safe experiment management.

This module provides a globally available, thread-safe SQLAlchemy session factory.
"""
from .session import get_scoped_session

DB_URL = "postgresql://user:password@host/dbname"  # Or read from config
Session = get_scoped_session(DB_URL)