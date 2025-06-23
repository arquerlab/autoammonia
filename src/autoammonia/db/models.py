from sqlalchemy import (
    Column, Integer, Text, DateTime, ForeignKey, Numeric, JSON, String
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import datetime

Base = declarative_base()

class Experiment(Base):
    """Database model for storing experiment data and metadata.

    Represents a single experimental run. Stores only an ID, a timestamp, 
    optional notes, and arbitrary metadata as JSON.

    Attributes:
        id (int): Primary key.
        date (datetime): Timestamp for when the experiment took place.
        notes (str): Freeform notes about the experiment.
        metadata (dict): JSON object storing arbitrary experiment parameters.
        catalyst_compositions (list[CatalystComposition]): List of catalyst composition objects.
        electrolyte_compositions (list[ElectrolyteComposition]): List of electrolyte composition objects.
        results (list[Result]): List of result objects (output files).
        configs (list[ExperimentConfig]): Experiment-to-config link object(s).
    """
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, default=datetime.datetime.now)
    notes = Column(Text)
    exp_metadata = Column(JSON)

    catalyst_compositions = relationship("CatalystComposition", back_populates="experiment")
    electrolyte_compositions = relationship("ElectrolyteComposition", back_populates="experiment")
    results = relationship("Result", back_populates="experiment")
    configs = relationship("ExperimentConfig", back_populates="experiment")


class Precursor(Base):
    """Reference table for metal precursors for catalyst fabrication.

    Attributes:
        id (int): Primary key.
        name (str): Unique name for the metal.
        properties (dict): Optional JSON metadata for the metal (e.g., formula, supplier).
    """
    __tablename__ = "precursors"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    properties = Column(JSON)


class Electrolyte(Base):
    """Reference table for electrolytes.

    Attributes:
        id (int): Primary key.
        name (str): Unique name for the electrolyte.
        properties (dict): Optional JSON metadata for the electrolyte (e.g., formula, supplier).
    """
    __tablename__ = "electrolytes"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    properties = Column(JSON)


class CatalystComposition(Base):
    """Links experiments to precursors and proportions.

    Represents a single metal's proportion in an experiment's catalyst.

    Attributes:
        id (int): Primary key.
        experiment_id (int): Foreign key to experiments.id.
        precursor_id (int): Foreign key to precursor.id.
        proportion (Decimal): Proportion of this metal in the catalyst.
        experiment (Experiment): Related experiment.
        precursor (Precursor): Related precursor.
    """
    __tablename__ = "catalyst_compositions"
    id = Column(Integer, primary_key=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    precursor_id = Column(Integer, ForeignKey("precursors.id"), nullable=False)
    proportion = Column(Numeric(6,3), nullable=False)

    experiment = relationship("Experiment", back_populates="catalyst_compositions")
    precursor = relationship("Precursor")

    __table_args__ = (
        # Ensure no duplicate precursors per experiment
        {'sqlite_autoincrement': True},
        # Enforce experiment_id and precursor_id unique together
        # (You may prefer explicit UniqueConstraint for more portability)
    )


class ElectrolyteComposition(Base):
    """Links experiments to electrolytes and proportions.

    Represents a single electrolyte's proportion in an experiment's electrolyte mixture.

    Attributes:
        id (int): Primary key.
        experiment_id (int): Foreign key to experiments.id.
        electrolyte_id (int): Foreign key to electrolytes.id.
        proportion (Decimal): Proportion of this electrolyte in the mixture.
        experiment (Experiment): Related experiment.
        electrolyte (Electrolyte): Related electrolyte.
    """
    __tablename__ = "electrolyte_compositions"
    id = Column(Integer, primary_key=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    electrolyte_id = Column(Integer, ForeignKey("electrolytes.id"), nullable=False)
    proportion = Column(Numeric(6,3), nullable=False)

    experiment = relationship("Experiment", back_populates="electrolyte_compositions")
    electrolyte = relationship("Electrolyte")

    __table_args__ = (
        # Ensure no duplicate electrolyte per experiment
        {'sqlite_autoincrement': True},
        # Enforce experiment_id and electrolyte_id unique together
        # (You may prefer explicit UniqueConstraint for more portability)
    )


class Config(Base):
    """Stores versioned configuration objects.

    Attributes:
        id (int): Primary key.
        created_at (datetime): Timestamp of creation.
        version (str): Config version string or number.
        config_json (dict): JSON storing configuration parameters.
        notes (str): Additional notes.
    """
    __tablename__ = "configs"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime.now)
    version = Column(String(20))
    config_json = Column(JSON, nullable=False)
    notes = Column(Text)


class ExperimentConfig(Base):
    """Links experiments to the specific configuration used.

    Attributes:
        experiment_id (int): Foreign key to experiments.id.
        config_id (int): Foreign key to configs.id.
        experiment (Experiment): Related experiment.
        config (Config): Related configuration.
    """
    __tablename__ = "experiment_config"

    experiment_id = Column(Integer, ForeignKey("experiments.id"), primary_key=True)
    config_id = Column(Integer, ForeignKey("configs.id"), nullable=False)
    experiment = relationship("Experiment", back_populates="configs")
    config = relationship("Config")


class Result(Base):
    """Stores output files and processed results for each experiment.

    Attributes:
        id (int): Primary key.
        experiment_id (int): Foreign key to experiments.id.
        result_type (str): General type (e.g., 'uv-vis', 'potentiostat', 'processed').
        result_role (str): Specific context or step (e.g., 'pre-reaction', 'analysis').
        file_path (str): Path or URI to the output file.
        description (str): Free-text description.
        metadata (dict): Optional JSON with extra properties.
        created_at (datetime): Timestamp of result creation.
        experiment (Experiment): Related experiment.
    """
    __tablename__ = "results"
    id = Column(Integer, primary_key=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    result_type = Column(String(50), nullable=False)
    result_role = Column(String(50))  # e.g., 'reaction', 'post-reaction', 'analysis'
    file_path = Column(Text, nullable=False)
    description = Column(Text)
    results_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.datetime.now)

    experiment = relationship("Experiment", back_populates="results")