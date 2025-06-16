from autoammonia.db.db import Session

def main():
    """
    Tests the database connection by opening and closing a session.
    Prints success or failure.
    """
    try:
        session = Session()
        session.execute("SELECT 1")
        print("Database connection successful.")
    except Exception as e:
        print(f"Database connection failed: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    main()