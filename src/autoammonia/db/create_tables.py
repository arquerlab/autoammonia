from autoammonia.db.models import Base
from autoammonia.db.db import Session

def main():
    """
    Creates all tables in the database using SQLAlchemy metadata.

    Raises:
        Exception: If the database engine or tables cannot be created.
    """
    engine = Session.bind
    print(f"Creating tables on database: {engine.url}")
    Base.metadata.create_all(engine)
    print("All tables created successfully.")

if __name__ == "__main__":
    main()