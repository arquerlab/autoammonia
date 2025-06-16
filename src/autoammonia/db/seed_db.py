from autoammonia.db.db_functions import add_valid_electrolytes_and_metals_to_db

def main():
    """
    Seeds the database with valid electrolytes and precursors.
    """
    print("Seeding database with reference data...")
    add_valid_electrolytes_and_metals_to_db.run()
    print("Database seeded successfully.")

if __name__ == "__main__":
    main()