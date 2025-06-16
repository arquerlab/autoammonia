from autoammonia.db.models import Base
from autoammonia.db.db import Session

def main():
    """
    Drops all tables in the database using SQLAlchemy metadata.

    Raises:
        Exception: If the database engine or tables cannot be dropped.
    """
    engine = Session.bind
    print(f"Dropping all tables on database: {engine.url}")
    Base.metadata.drop_all(engine)
    print("All tables dropped successfully.")

if __name__ == "__main__":
    main()