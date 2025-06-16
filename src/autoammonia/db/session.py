from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, scoped_session as ScopedSessionType

def get_scoped_session(db_url: str) -> ScopedSessionType:
    """Create a scoped session factory for the given database URL. This is thread-safe approach
    to manage the database, in case different modules (reaction and analysis) need to acces the 
    database concurrently.

    Args:
        db_url (str): SQLAlchemy database URL.

    Returns:
        scoped_session: A thread-safe session factory suitable for multi-threaded use.
    """
    engine = create_engine(db_url)
    session_factory = sessionmaker(bind=engine)
    return scoped_session(session_factory)