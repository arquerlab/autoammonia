"""Database session singleton for thread-safe experiment management.

This module provides a globally available, thread-safe SQLAlchemy session factory.
"""
from .session import get_scoped_session

DB_URL = "postgresql://dummy:dummy@127.0.0.1:5432/autoammonia_db"

# Module-level cache for the Session (lazy initialization)
_cached_session = None

def get_session():
    """
    Get database session, creating it only when first needed.
    
    Returns:
        scoped_session: The SQLAlchemy scoped session factory.
    """
    global _cached_session
    if _cached_session is None:
        _cached_session = get_scoped_session(DB_URL)
    return _cached_session

class _SessionProxy:
    """Proxy class to delegate attribute access and calls to the Session."""
    def __getattr__(self, name):
        """Delegate attribute access to the Session."""
        real_session = get_session()
        import sys
        sys.modules[__name__]._cached_session = real_session
        return getattr(real_session, name)
    
    def __call__(self, *args, **kwargs):
        """Allow Session() to be called directly to get a session instance."""
        return get_session()(*args, **kwargs)

Session = _SessionProxy()
