# Database Guide

This guide explains how to set up and manage the database for this project.  
It covers installing PostgreSQL, creating the database, configuring the connection, and using developer scripts for table setup and data initialization.

---

## Table of Contents

- [Overview](#overview)
- [Setup (from scratch)](#setup-from-scratch)
- [Developer Scripts](#developer-scripts)
- [Model Structure](#model-structure)
- [Troubleshooting](#troubleshooting)
- [More Information](#more-information)

---

## Overview

This project uses **SQLAlchemy ORM** for database access.  
Session and connection management are handled in `db.py` and `session.py`.  
All table models are defined in `models.py` (see docstrings for details).

---

## Setup (from scratch)

### 1. Install PostgreSQL

- **Linux:**
  ```bash
  sudo apt update
  sudo apt install postgresql postgresql-contrib
  ```
- **macOS (Homebrew):**
  ```bash
  brew install postgresql
  brew services start postgresql
  ```
- **Windows:**
  Download and run the [PostgreSQL installer](https://www.postgresql.org/download/windows/).

### 2. Create Database and User

Open the PostgreSQL shell using one of the following:

- **Default system user:**
  ```bash
  psql
  ```
- **Switch user (if you know the password):**
  ```bash
  su - postgres
  psql
  ```
- **Connect directly with credentials:**
  ```bash
  psql -U myuser -h localhost -d postgres
  ```
- **Docker:**
  ```bash
  docker exec -it <container_name> psql -U postgres
  ```

Then in the psql shell, run:
```sql
CREATE DATABASE mydatabase;
CREATE USER myuser WITH PASSWORD 'mypassword';
GRANT ALL PRIVILEGES ON DATABASE mydatabase TO myuser;
```

### 3. Configure the Database URL

Update the `DB_URL` variable in `db.py`:

```python
DB_URL = "postgresql://user:password@host/dbname"
```

Test connectivity using the `test_db_connection.py` script:

```bash
python -m autoammonia.db.test_db_connection
```

### 4. Create and Manage Tables

- **Create tables:**  
  ```bash
  python -m autoammonia.db.create_tables
  ```
- **Seed tables with initial data:**  
  ```bash
  python -m autoammonia.db.seed_db
  ```
- **Drop all tables:**  
  ```bash
  python -m autoammonia.db.drop_tables
  ```

---

## Developer Scripts

- `create_tables.py`: Creates all tables defined in `models.py`.  
  **Usage:** `python -m autoammonia.db.create_tables`
- `drop_tables.py`: Drops all tables from the database.  
  **Usage:** `python -m autoammonia.db.drop_tables`
- `seed_db.py`: Populates tables with initial/default data.  
  **Usage:** `python -m autoammonia.db.seed_db`
- `test_db_connection.py`: Tests database connectivity and prints status.  
  **Usage:** `python -m autoammonia.db.test_db_connection`

---

## Model Structure

All models are defined in `models.py`.  
Check the Google-style docstrings in `models.py` for details of fields and relationships.

**Key Tables:**
- `Experiment`: Main experimental record (notes, metadata, timestamp).
- `Precursor`: Reference table for metals.
- `Electrolyte`: Reference table for electrolytes.
- `CatalystComposition`: Links experiments to precursors/metals, with proportions.
- `ElectrolyteComposition`: Links experiments to electrolytes, with proportions.
- `Result`: Stores result files and output data for experiments.
- `Config`: Stores versioned configuration objects.
- `ExperimentConfig`: Links experiment to its configuration.

---

## Troubleshooting

- **Database URL:** Double-check your connection string in `db.py` or your environment variable.
- **PostgreSQL Access:** If `sudo -u postgres psql` fails, try:
    - `psql` (if your user has access)
    - `psql -U myuser -d mydatabase`
    - `su - postgres; psql`
    - Docker exec, if running in a container
- **Session Errors:** Ensure sessions are closed and check for typos in your connection string.
- **Dependencies:** Install all Python dependencies listed in the main project requirements.

---

## More Information

- See model and function docstrings in `models.py` and `db_functions.py`.
- For advanced usage, see [SQLAlchemy documentation](https://docs.sqlalchemy.org/).
- For workflow orchestration, see [Prefect documentation](https://docs.prefect.io/).

---