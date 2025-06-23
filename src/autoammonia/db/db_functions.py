from typing import List, Tuple, Optional
from decimal import Decimal
from prefect import task
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from .db import Session
from .models import Precursor, Electrolyte, Experiment, CatalystComposition, ElectrolyteComposition, Result
from ..utils.elytes_precursors import get_valid_electrolytes, get_valid_precursors

@task
def add_valid_electrolytes_and_metals_to_db() -> None:
    """
    Adds all valid electrolytes and metals from CONNECTIONS_INFO to the database,
    skipping those that already exist.

    Returns:
        None
    """
    # Get lists from your existing functions
    valid_electrolytes = get_valid_electrolytes()
    valid_precursors = get_valid_precursors()

    session = Session()
    try:
        if valid_precursors:
            stmt_m = insert(Precursor).values([{"name": m} for m, port in valid_precursors]).on_conflict_do_nothing(index_elements=["name"])
            session.execute(stmt_m)
        if valid_electrolytes:
            stmt_e = insert(Electrolyte).values([{"name": e} for e, port in valid_electrolytes]).on_conflict_do_nothing(index_elements=["name"])
            session.execute(stmt_e)
        session.commit()
    finally:
        session.close()
        
@task
def add_experiment_to_db(
    precursor_ratios: List[Tuple[str, float]],
    electrolyte_ratios: List[Tuple[str, float]],
    notes: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> int:
    """
    Adds a new experiment to the database, including its catalyst and electrolyte compositions.

    Args:
        precursor_ratios (List[Tuple[str, float]]): List of (precursor name, proportion) tuples.
        electrolyte_ratios (List[Tuple[str, float]]): List of (electrolyte name, proportion) tuples.
        notes (Optional[str], optional): Notes about the experiment.
        metadata (Optional[dict], optional): Metadata for the experiment.

    Returns:
        None

    Raises:
        ValueError: If any precursor or electrolyte is not found in the database.
    """
    session = Session()
    try:
        # Create and add a new Experiment record
        experiment = Experiment(notes=notes, exp_metadata=metadata or {})
        session.add(experiment)
        session.flush()  # Ensure experiment.id is available

        # Link precursors to experiment with proportions
        for precursor_name, proportion in precursor_ratios:
            precursor = session.query(Precursor).filter_by(name=precursor_name).first()
            if precursor is None:
                raise ValueError(f"Precursor '{precursor_name}' not found in database.")
            catalyst_comp = CatalystComposition(
                experiment_id=experiment.id,
                precursor_id=precursor.id,
                proportion=Decimal(str(proportion))
            )
            session.add(catalyst_comp)

        # Link electrolytes to experiment with proportions
        for electrolyte_name, proportion in electrolyte_ratios:
            electrolyte = session.query(Electrolyte).filter_by(name=electrolyte_name).first()
            if electrolyte is None:
                raise ValueError(f"Electrolyte '{electrolyte_name}' not found in database.")
            electrolyte_comp = ElectrolyteComposition(
                experiment_id=experiment.id,
                electrolyte_id=electrolyte.id,
                proportion=Decimal(str(proportion))
            )
            session.add(electrolyte_comp)

        session.commit()
        return experiment.id
    except (SQLAlchemyError, ValueError) as e:
        session.rollback()
        print(f"Error adding experiment: {e}")
    finally:
        session.close()
        
@task
def add_results_to_db(
        experiment_id: int,
        result_type: str,
        result_role: str,
        file_path: str,
        description: str | None = None,
        metadata: dict | None = None,
) -> None:
    """
    Adds a result file to the database associated with a specific experiment.

    Args:
        experiment_id (int): The ID of the experiment to which the result belongs.
        result_type (str): The type of the result (e.g., 'spectrum', 'image').
        result_role (str): The role of the result (e.g., 'raw', 'processed').
        file_path (str): The path to the result file.
        description (str | None, optional): A description of the result. Defaults to None.
        metadata (dict | None, optional): Additional metadata for the result. Defaults to None.

    Returns:
        None
    """
    session = Session()
    try:
        # Create and add a new Result record
        result = Result(
            experiment_id=experiment_id,
            type=result_type,
            role=result_role,
            file_path=file_path,
            description=description,
            metadata=metadata or {}
        )
        session.add(result)
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        print(f"Error adding result: {e}")
    finally:
        session.close()
