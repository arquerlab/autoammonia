"""
Unit tests for database functions.

Tests experiment creation, result storage, and database operations.
"""
import pytest
from decimal import Decimal
from unittest.mock import patch
from sqlalchemy.exc import SQLAlchemyError

from autoammonia.db.db_functions import (
    add_experiment_to_db,
    add_results_to_db,
)
from autoammonia.db.models import (
    Experiment,
    Precursor,
    Electrolyte,
    CatalystComposition,
    ElectrolyteComposition,
    Result,
)


@pytest.fixture(autouse=True)
def mock_prefect_logger():
    """Mock Prefect logger for all tests."""
    with patch('autoammonia.db.db_functions.get_run_logger') as mock_logger:
        mock_logger.return_value.info = lambda x: None
        mock_logger.return_value.error = lambda x: None
        yield mock_logger


class TestAddExperimentToDb:
    """Tests for add_experiment_to_db function."""

    def test_add_experiment_with_valid_data(self, temp_db):
        """Test adding an experiment with valid precursors and electrolytes."""
        session = temp_db()
        
        # First, create precursors and electrolytes in the database
        precursor1 = Precursor(name="Cu")
        precursor2 = Precursor(name="Ni")
        electrolyte1 = Electrolyte(name="KOH")
        electrolyte2 = Electrolyte(name="NaOH")
        
        session.add_all([precursor1, precursor2, electrolyte1, electrolyte2])
        session.commit()
        
        # Now add an experiment
        experiment_id = add_experiment_to_db(
            precursor_ratios=[("Cu", 0.5), ("Ni", 0.5)],
            electrolyte_ratios=[("KOH", 0.6), ("NaOH", 0.4)],
            notes="Test experiment",
            metadata={"test": True}
        )
        
        # Verify experiment was created
        experiment = session.query(Experiment).filter_by(id=experiment_id).first()
        assert experiment is not None
        assert experiment.notes == "Test experiment"
        assert experiment.exp_metadata == {"test": True}
        
        # Verify catalyst compositions
        catalyst_comps = session.query(CatalystComposition).filter_by(
            experiment_id=experiment_id
        ).all()
        assert len(catalyst_comps) == 2
        precursor_names = {comp.precursor.name for comp in catalyst_comps}
        assert precursor_names == {"Cu", "Ni"}
        
        # Verify electrolyte compositions
        electrolyte_comps = session.query(ElectrolyteComposition).filter_by(
            experiment_id=experiment_id
        ).all()
        assert len(electrolyte_comps) == 2
        electrolyte_names = {comp.electrolyte.name for comp in electrolyte_comps}
        assert electrolyte_names == {"KOH", "NaOH"}

    def test_add_experiment_without_notes_or_metadata(self, temp_db):
        """Test adding an experiment without optional fields."""
        session = temp_db()
        
        # Create required precursors and electrolytes
        precursor = Precursor(name="Cu")
        electrolyte = Electrolyte(name="KOH")
        session.add_all([precursor, electrolyte])
        session.commit()
        
        # Add experiment without notes or metadata
        experiment_id = add_experiment_to_db(
            precursor_ratios=[("Cu", 1.0)],
            electrolyte_ratios=[("KOH", 1.0)]
        )
        
        experiment = session.query(Experiment).filter_by(id=experiment_id).first()
        assert experiment is not None
        assert experiment.notes is None
        assert experiment.exp_metadata == {}

    def test_add_experiment_raises_error_for_missing_precursor(self, temp_db):
        """Test that ValueError is raised when precursor is not found."""
        session = temp_db()
        
        # Create electrolyte but not precursor
        electrolyte = Electrolyte(name="KOH")
        session.add(electrolyte)
        session.commit()
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Precursor 'Cu' not found"):
            add_experiment_to_db(
                precursor_ratios=[("Cu", 1.0)],
                electrolyte_ratios=[("KOH", 1.0)]
            )

    def test_add_experiment_raises_error_for_missing_electrolyte(self, temp_db):
        """Test that ValueError is raised when electrolyte is not found."""
        session = temp_db()
        
        # Create precursor but not electrolyte
        precursor = Precursor(name="Cu")
        session.add(precursor)
        session.commit()
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Electrolyte 'KOH' not found"):
            add_experiment_to_db(
                precursor_ratios=[("Cu", 1.0)],
                electrolyte_ratios=[("KOH", 1.0)]
            )

    def test_add_experiment_proportions_are_stored_correctly(self, temp_db):
        """Test that proportions are stored as Decimal values correctly."""
        session = temp_db()
        
        precursor = Precursor(name="Cu")
        electrolyte = Electrolyte(name="KOH")
        session.add_all([precursor, electrolyte])
        session.commit()
        
        experiment_id = add_experiment_to_db(
            precursor_ratios=[("Cu", 0.333333)],
            electrolyte_ratios=[("KOH", 0.666667)]
        )
        
        # Check proportions are stored correctly
        catalyst_comp = session.query(CatalystComposition).filter_by(
            experiment_id=experiment_id
        ).first()
        assert catalyst_comp.proportion == Decimal("0.333333")
        
        electrolyte_comp = session.query(ElectrolyteComposition).filter_by(
            experiment_id=experiment_id
        ).first()
        assert electrolyte_comp.proportion == Decimal("0.666667")


class TestAddResultsToDb:
    """Tests for add_results_to_db function."""

    def test_add_result_with_all_fields(self, temp_db):
        """Test adding a result with all fields provided."""
        session = temp_db()
        
        # Create an experiment first
        experiment = Experiment(notes="Test")
        session.add(experiment)
        session.commit()
        
        # Add result
        add_results_to_db(
            experiment_id=experiment.id,
            result_type="spectrum",
            result_role="raw",
            file_path="/path/to/file.csv",
            description="Test spectrum",
            metadata={"wavelength_range": "200-800"}
        )
        
        # Verify result was created
        result = session.query(Result).filter_by(experiment_id=experiment.id).first()
        assert result is not None
        assert result.result_type == "spectrum"
        assert result.result_role == "raw"
        assert result.file_path == "/path/to/file.csv"
        assert result.description == "Test spectrum"
        assert result.results_metadata == {"wavelength_range": "200-800"}

    def test_add_result_without_optional_fields(self, temp_db):
        """Test adding a result without optional description and metadata."""
        session = temp_db()
        
        # Create an experiment
        experiment = Experiment(notes="Test")
        session.add(experiment)
        session.commit()
        
        # Add result without optional fields
        add_results_to_db(
            experiment_id=experiment.id,
            result_type="image",
            result_role="processed",
            file_path="/path/to/image.png"
        )
        
        # Verify result was created with None/empty defaults
        result = session.query(Result).filter_by(experiment_id=experiment.id).first()
        assert result is not None
        assert result.description is None
        assert result.results_metadata == {}

    def test_add_multiple_results_to_same_experiment(self, temp_db):
        """Test adding multiple results to the same experiment."""
        session = temp_db()
        
        # Create an experiment
        experiment = Experiment(notes="Test")
        session.add(experiment)
        session.commit()
        
        # Add multiple results
        add_results_to_db(
            experiment_id=experiment.id,
            result_type="spectrum",
            result_role="raw",
            file_path="/path/to/raw.csv"
        )
        add_results_to_db(
            experiment_id=experiment.id,
            result_type="spectrum",
            result_role="processed",
            file_path="/path/to/processed.csv"
        )
        
        # Verify both results exist
        results = session.query(Result).filter_by(experiment_id=experiment.id).all()
        assert len(results) == 2
        result_types = {r.result_type for r in results}
        result_roles = {r.result_role for r in results}
        assert result_types == {"spectrum"}
        assert result_roles == {"raw", "processed"}

