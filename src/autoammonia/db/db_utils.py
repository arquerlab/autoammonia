import os
from urllib.parse import urlparse

def get_database_url():
    """
    Get the database URL from the environment or use a default.

    Returns:
        str: The database URL.
    """
    return os.getenv("DATABASE_URL", "postgresql://myuser:mypassword@localhost/mydatabase")

def parse_db_url(db_url):
    """
    Parse the database URL and extract credentials.

    Args:
        db_url (str): The database URL.

    Returns:
        dict: Components for pg_dump/pg_restore.
    """
    parsed = urlparse(db_url)
    return {
        'user': parsed.username,
        'password': parsed.password,
        'host': parsed.hostname or 'localhost',
        'port': str(parsed.port) if parsed.port else '5432',
        'database': parsed.path.lstrip('/')
    }

def prepare_pg_env(password):
    """
    Prepare a copy of the current environment with PGPASSWORD set.

    Args:
        password (str): The database user's password.

    Returns:
        dict: Modified environment dictionary.
    """
    env = os.environ.copy()
    if password:
        env['PGPASSWORD'] = password
    return env