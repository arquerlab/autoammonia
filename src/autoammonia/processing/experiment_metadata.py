from __future__ import annotations

import numpy as np

from autoammonia.db.db import Session
from autoammonia.db.models import Experiment
from autoammonia.processing.processing_config import expand_data_path


def _format_composition(items: list[tuple[str, float]]) -> str:
    """Format non-zero composition tuples as a compact comma-separated string.

    Args:
        items (list[tuple[str, float]]): Name/proportion pairs.

    Returns:
        str: Formatted composition string.
    """
    non_zero_items = [(name, value) for name, value in items if not np.isclose(value, 0.0)]
    if not non_zero_items:
        return "N/A"
    return ", ".join(f"{name}: {value:.3f}" for name, value in non_zero_items)


def _get_experiment(experiment_id: int) -> Experiment:
    """Load one experiment row or raise if unavailable.

    Args:
        experiment_id (int): Experiment ID.

    Returns:
        Experiment: Loaded experiment.

    Raises:
        ValueError: If the experiment does not exist.
    """
    session = Session()
    try:
        experiment = session.query(Experiment).filter(Experiment.id == int(experiment_id)).first()
        if experiment is None:
            raise ValueError(f"Experiment {experiment_id} not found in database.")
        session.expunge(experiment)
        return experiment
    finally:
        session.close()


def load_experiment_run_config(experiment_id: int) -> dict:
    """Load the merged run configuration snapshot for one experiment.

    Args:
        experiment_id (int): Experiment ID.

    Returns:
        dict: Configuration snapshot stored in configs.config_json.

    Raises:
        ValueError: If the experiment has no linked configuration snapshot.
    """
    session = Session()
    try:
        experiment = session.query(Experiment).filter(Experiment.id == int(experiment_id)).first()
        if experiment is None:
            raise ValueError(f"Experiment {experiment_id} not found in database.")
        if not experiment.configs:
            raise ValueError(
                f"Experiment {experiment_id} has no linked configuration snapshot in experiment_config."
            )
        config_json = experiment.configs[0].config.config_json
        if not isinstance(config_json, dict):
            raise ValueError(f"Experiment {experiment_id} configuration snapshot is invalid.")
        return config_json
    finally:
        session.close()


def _require_config_key(run_config: dict, key: str, experiment_id: int) -> float:
    """Return a numeric config value or raise if missing.

    Args:
        run_config (dict): Experiment configuration snapshot.
        key (str): Configuration key.
        experiment_id (int): Experiment ID for error messages.

    Returns:
        float: Parsed numeric value.

    Raises:
        ValueError: If the key is missing or not numeric.
    """
    if key not in run_config:
        raise ValueError(
            f"Experiment {experiment_id} configuration snapshot is missing required key '{key}'."
        )
    try:
        return float(run_config[key])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Experiment {experiment_id} configuration key '{key}' is not numeric."
        ) from exc


def load_reaction_catholyte_volume_mL(experiment_id: int) -> float:
    """Load reactor catholyte volume from the experiment configuration snapshot.

    Args:
        experiment_id (int): Experiment ID.

    Returns:
        float: Catholyte volume in mL.
    """
    run_config = load_experiment_run_config(experiment_id)
    return _require_config_key(run_config, "reaction_catholyte_volume", experiment_id)


def load_reactor_volume_L(experiment_id: int) -> float:
    """Load reactor volume in liters from reaction_catholyte_volume.

    Args:
        experiment_id (int): Experiment ID.

    Returns:
        float: Reactor volume in L.
    """
    return load_reaction_catholyte_volume_mL(experiment_id) / 1000.0


def load_reaction_time_s(experiment_id: int) -> float:
    """Load reaction duration from the experiment configuration snapshot.

    Args:
        experiment_id (int): Experiment ID.

    Returns:
        float: Reaction time in seconds.
    """
    run_config = load_experiment_run_config(experiment_id)
    return _require_config_key(run_config, "reaction_time", experiment_id)


def load_aliquot_volume_mL(experiment_id: int) -> float:
    """Load aliquot volume from the experiment configuration snapshot.

    Args:
        experiment_id (int): Experiment ID.

    Returns:
        float: Aliquot volume in mL.
    """
    run_config = load_experiment_run_config(experiment_id)
    return _require_config_key(run_config, "aliquot_volume", experiment_id)


def load_reaction_current_ma(experiment_id: int) -> float:
    """Load reaction setpoint current from the experiment configuration snapshot.

    Args:
        experiment_id (int): Experiment ID.

    Returns:
        float: Reaction current in mA.
    """
    run_config = load_experiment_run_config(experiment_id)
    return _require_config_key(run_config, "reaction_current", experiment_id)


def load_electrodeposition_current_ma(experiment_id: int) -> float:
    """Load electrodeposition setpoint current from the experiment configuration snapshot.

    Args:
        experiment_id (int): Experiment ID.

    Returns:
        float: Electrodeposition current in mA.
    """
    run_config = load_experiment_run_config(experiment_id)
    return _require_config_key(run_config, "electrodeposition_current", experiment_id)


def resolve_data_path_for_experiment(experiment_id: int):
    """Resolve the data root path for one experiment from its configuration snapshot.

    Args:
        experiment_id (int): Experiment ID.

    Returns:
        Path: Expanded data path.
    """
    from pathlib import Path

    run_config = load_experiment_run_config(experiment_id)
    if "data_path" not in run_config:
        raise ValueError(
            f"Experiment {experiment_id} configuration snapshot is missing required key 'data_path'."
        )
    return expand_data_path(Path(run_config["data_path"]))


def load_experiment_compositions(experiment_id: int) -> tuple[str, str]:
    """Load catalyst and electrolyte compositions from the experiment database.

    Args:
        experiment_id (int): Experiment ID.

    Returns:
        tuple[str, str]: Catalyst composition text and electrolyte composition text.

    Raises:
        ValueError: If the experiment cannot be loaded from the database.
    """
    session = Session()
    try:
        experiment = session.query(Experiment).filter(Experiment.id == int(experiment_id)).first()
        if experiment is None:
            raise ValueError(f"Experiment {experiment_id} not found in database.")

        catalyst_items = [
            (composition.precursor.name, float(composition.proportion))
            for composition in experiment.catalyst_compositions
        ]
        electrolyte_items = [
            (composition.electrolyte.name, float(composition.proportion))
            for composition in experiment.electrolyte_compositions
        ]
        return _format_composition(catalyst_items), _format_composition(electrolyte_items)
    finally:
        session.close()


def effective_aliquot_times(reaction_times_s: list[float], reaction_time_s: float) -> list[float]:
    """Replace the last aliquot time with the configured reaction end time.

    Args:
        reaction_times_s (list[float]): Parsed aliquot times from filenames.
        reaction_time_s (float): Reaction duration from configuration snapshot.

    Returns:
        list[float]: Effective aliquot times in seconds.
    """
    if not reaction_times_s:
        return []
    effective = list(reaction_times_s)
    effective[-1] = float(reaction_time_s)
    return effective


def repair_snapshot_data_paths(
    wrong_path: str = "~/autoammonia_data",
    correct_path: str = "~/ammonia_data",
) -> int:
    """Update stored experiment config snapshots that point at the wrong data root.

    Args:
        wrong_path (str, optional): Incorrect data_path value to replace.
        correct_path (str, optional): Correct data_path value.

    Returns:
        int: Number of config rows updated.
    """
    from autoammonia.db.models import Config

    session = Session()
    updated = 0
    try:
        for config_row in session.query(Config).all():
            config_json = config_row.config_json
            if not isinstance(config_json, dict):
                continue
            if config_json.get("data_path") != wrong_path:
                continue
            repaired = dict(config_json)
            repaired["data_path"] = correct_path
            if repaired.get("calibration_path") == f"{wrong_path}/calibration":
                repaired["calibration_path"] = f"{correct_path}/calibration"
            config_row.config_json = repaired
            updated += 1
        if updated:
            session.commit()
        return updated
    finally:
        session.close()


def backfill_experiment_config_snapshot(
    experiment_id: int,
    config_snapshot: dict | None = None,
) -> dict:
    """Attach a configuration snapshot to a legacy experiment if missing.

    Args:
        experiment_id (int): Experiment ID.
        config_snapshot (dict | None, optional): Snapshot to store. When None, uses
            the active DEFAULT_CONFIG merged with any experiment exp_metadata cell value.

    Returns:
        dict: Stored configuration snapshot.

    Raises:
        ValueError: If the experiment does not exist.
    """
    from autoammonia.config.config import ACTIVE_SETUP, DEFAULT_CONFIG
    from autoammonia.db.models import Config, ExperimentConfig

    session = Session()
    try:
        experiment = session.query(Experiment).filter(Experiment.id == int(experiment_id)).first()
        if experiment is None:
            raise ValueError(f"Experiment {experiment_id} not found in database.")
        if experiment.configs:
            return experiment.configs[0].config.config_json

        snapshot = dict(config_snapshot or DEFAULT_CONFIG)
        snapshot.setdefault("setup", ACTIVE_SETUP)
        if isinstance(experiment.exp_metadata, dict) and "cell" in experiment.exp_metadata:
            snapshot["cell"] = experiment.exp_metadata["cell"]

        config_row = Config(
            version=str(snapshot.get("setup", ACTIVE_SETUP)),
            config_json=snapshot,
            notes=f"Backfilled snapshot for experiment {experiment_id}",
        )
        session.add(config_row)
        session.flush()
        session.add(ExperimentConfig(experiment_id=experiment.id, config_id=config_row.id))
        session.commit()
        return snapshot
    finally:
        session.close()
