from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from autoammonia.processing.conversions import corrected_current_a
from autoammonia.processing.experiment_metadata import (
    effective_aliquot_times,
    load_aliquot_volume_mL,
    load_reaction_catholyte_volume_mL,
    load_reaction_time_s,
    load_reactor_volume_L,
)
from autoammonia.processing.processing_config import ProcessingConfig, get_processing_config
from autoammonia.processing.uvvis_gaussian_fit_plot import get_gaussian_amplitude


MOLS_ELECTRONS_PER_NH3 = 8.0
FARADAY_CONSTANT_C_MOL = 96485.0
MOLAR_MASS_N_G_MOL = 14.0067


@dataclass(frozen=True)
class UvvisAliquot:
    """UV-Vis aliquot data.

    Attributes:
        experiment_id (int): Experiment ID.
        reaction_time_s (float): Reaction time in seconds from filename.
        vial (int | None): Vial number.
        path (Path): Source CSV path.
        absorbance_corrected (float): Peak-corrected absorbance.
        gaussian_amplitude (float): Gaussian-fit amplitude.
    """

    experiment_id: int
    reaction_time_s: float
    vial: int | None
    path: Path
    absorbance_corrected: float
    gaussian_amplitude: float


@dataclass(frozen=True)
class FeIntervalBreakdown:
    """Interval FE breakdown for one UV-Vis aliquot.

    Attributes:
        experiment_id (int): Experiment ID.
        reaction_time_s (float): Effective reaction time in seconds.
        delta_absorbance_corrected (float): Interval absorbance change.
        fe_nh3_pct (float): Interval Faradaic efficiency in percent.
    """

    experiment_id: int
    reaction_time_s: float
    delta_absorbance_corrected: float
    fe_nh3_pct: float


@dataclass(frozen=True)
class FeCumulativeBreakdown:
    """Cumulative FE breakdown for one UV-Vis aliquot.

    Attributes:
        experiment_id (int): Experiment ID.
        reaction_time_s (float): Effective reaction time in seconds.
        n_total_mg (float): Cumulative nitrogen mass in mg.
        fe_cumulative_pct (float): Cumulative Faradaic efficiency in percent.
    """

    experiment_id: int
    reaction_time_s: float
    n_total_mg: float
    fe_cumulative_pct: float


def parse_uvvis_filename(path: Path) -> tuple[int, float, int | None] | None:
    """Parse experiment ID, reaction time, and vial from a UV-Vis filename.

    Args:
        path (Path): UV-Vis CSV path.

    Returns:
        tuple[int, float, int | None] | None: Parsed values or None if unmatched.
    """
    match = re.match(
        r"ID(?P<experiment_id>\d+)_RXT(?P<reaction_time_s>[\d.]+)_VIALvial(?P<vial>\d+)",
        path.name,
    )
    if match is None:
        return None
    return (
        int(match.group("experiment_id")),
        float(match.group("reaction_time_s")),
        int(match.group("vial")),
    )


def calculate_absorbance_steps(
    df_uv: pd.DataFrame,
    rolling_window: int = 10,
) -> pd.DataFrame:
    """Calculate intermediate absorbance columns used for FE.

    Args:
        df_uv (pd.DataFrame): UV-Vis dataframe containing wavelength and absorption columns.
        rolling_window (int, optional): Rolling mean window. Defaults to 10.

    Returns:
        pd.DataFrame: Dataframe with absorbance processing columns.
    """
    df = df_uv.copy()
    df["Wavelength (nm)"] = pd.to_numeric(df["Wavelength (nm)"], errors="coerce")
    df["Absorption"] = pd.to_numeric(df["Absorption"], errors="coerce")
    background_absorbance = float(df["Absorption"].dropna().iloc[-1])
    df["Abs_zero"] = df["Absorption"] - background_absorbance
    df["Abs_zero_filtered"] = (
        df["Abs_zero"].rolling(window=rolling_window, min_periods=1, center=True).mean()
    )
    return df.dropna(subset=["Wavelength (nm)", "Absorption", "Abs_zero", "Abs_zero_filtered"])


def get_absorbance_corrected(
    df_uv: pd.DataFrame,
    peak_min_nm: float,
    peak_max_nm: float,
    rolling_window: int = 10,
) -> float:
    """Calculate smoothed background-corrected absorbance peak.

    Args:
        df_uv (pd.DataFrame): UV-Vis dataframe.
        peak_min_nm (float): Peak band minimum wavelength in nm.
        peak_max_nm (float): Peak band maximum wavelength in nm.
        rolling_window (int, optional): Rolling mean window. Defaults to 10.

    Returns:
        float: Maximum smoothed absorbance in the peak band.
    """
    df = calculate_absorbance_steps(df_uv, rolling_window=rolling_window)
    peak_region = df[df["Wavelength (nm)"].between(peak_min_nm, peak_max_nm)]
    return float(peak_region["Abs_zero_filtered"].max())


def get_aliquot_absorbance(
    aliquot: UvvisAliquot,
    config: ProcessingConfig,
    df_uv: pd.DataFrame | None = None,
) -> float:
    """Return the configured absorbance metric for one aliquot.

    Args:
        aliquot (UvvisAliquot): Loaded aliquot.
        config (ProcessingConfig): Processing configuration.
        df_uv (pd.DataFrame | None, optional): Optional preloaded UV-Vis dataframe.

    Returns:
        float: Absorbance metric value.
    """
    if config.absorbance_metric == "gaussian":
        if df_uv is None:
            df_uv = pd.read_csv(aliquot.path)
        return float(get_gaussian_amplitude(df_uv))
    return aliquot.absorbance_corrected


def load_uvvis_aliquots(
    experiment_id: int,
    folder_uvvis: Path,
    config: ProcessingConfig | None = None,
) -> list[UvvisAliquot]:
    """Load UV-Vis aliquots and calculate absorbance values.

    Args:
        experiment_id (int): Experiment ID.
        folder_uvvis (Path): Folder containing UV-Vis CSV files.
        config (ProcessingConfig | None, optional): Processing config. Defaults to loaded config.

    Returns:
        list[UvvisAliquot]: Aliquots sorted by reaction time.
    """
    config = config or get_processing_config()
    aliquots: list[UvvisAliquot] = []
    for path in sorted(folder_uvvis.glob(f"ID{experiment_id}_RXT*_VIAL*.csv")):
        parsed = parse_uvvis_filename(path)
        if parsed is None:
            print(f"Skipping UV-Vis file with unrecognized name: {path.name}")
            continue

        parsed_experiment_id, reaction_time_s, vial = parsed
        df_uv = pd.read_csv(path)
        aliquots.append(
            UvvisAliquot(
                experiment_id=parsed_experiment_id,
                reaction_time_s=reaction_time_s,
                vial=vial,
                path=path,
                absorbance_corrected=get_absorbance_corrected(
                    df_uv,
                    peak_min_nm=config.absorbance_peak_min_nm,
                    peak_max_nm=config.absorbance_peak_max_nm,
                    rolling_window=config.absorbance_rolling_window,
                ),
                gaussian_amplitude=float(get_gaussian_amplitude(df_uv)),
            )
        )
    return sorted(aliquots, key=lambda aliquot: aliquot.reaction_time_s)


def load_cp_data(
    experiment_id: int,
    folder_electrosynthesis: Path,
) -> tuple[Path, pd.DataFrame] | None:
    """Load electrosynthesis CP data for one experiment.

    Args:
        experiment_id (int): Experiment ID.
        folder_electrosynthesis (Path): Electrosynthesis folder.

    Returns:
        tuple[Path, pd.DataFrame] | None: CP path and dataframe, or None if unavailable.
    """
    matches = sorted(folder_electrosynthesis.glob(f"{experiment_id}_cell*_method_CP*.csv"))
    if not matches:
        return None

    required_columns = ["Time (s)", "Current (A)"]
    for path in matches:
        try:
            df = pd.read_csv(path, usecols=required_columns)
        except Exception as exc:
            print(f"Skipping CP file {path.name}: {exc}")
            continue

        for column in required_columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
        df = df.dropna(subset=required_columns).sort_values("Time (s)").reset_index(drop=True)
        if not df.empty:
            return path, df
    return None


def integrate_charge_interval(
    df_cp: pd.DataFrame,
    start_time_s: float,
    end_time_s: float,
    current_column: str = "Current (A)",
    current_correction_factor: float = 1.0,
) -> tuple[float, float]:
    """Integrate corrected current magnitude over one reaction interval.

    Args:
        df_cp (pd.DataFrame): CP dataframe.
        start_time_s (float): Interval start in seconds.
        end_time_s (float): Interval end in seconds.
        current_column (str, optional): Current column name. Defaults to "Current (A)".
        current_correction_factor (float, optional): Correction applied once before integration.

    Returns:
        tuple[float, float]: Unsigned integrated charge in C and mean corrected current
            magnitude in A.
    """
    df_rx = df_cp[(df_cp["Time (s)"] >= start_time_s) & (df_cp["Time (s)"] <= end_time_s)]
    if len(df_rx) < 2:
        return float("nan"), float("nan")

    time_s = df_rx["Time (s)"].to_numpy(dtype=float)
    current_a = corrected_current_a(
        df_rx[current_column].to_numpy(dtype=float),
        current_correction_factor,
    )
    charge_c = abs(float(np.trapezoid(current_a, time_s)))
    return charge_c, float(np.nanmean(np.abs(current_a)))


def integrate_charge_to_time(
    df_cp: pd.DataFrame,
    end_time_s: float,
    current_column: str = "Current (A)",
    current_correction_factor: float = 1.0,
) -> float:
    """Integrate corrected current from time zero to an end time.

    Args:
        df_cp (pd.DataFrame): CP dataframe.
        end_time_s (float): End time in seconds.
        current_column (str, optional): Current column name. Defaults to "Current (A)".
        current_correction_factor (float, optional): Correction applied once before integration.

    Returns:
        float: Unsigned integrated charge in C.
    """
    charge_c, _ = integrate_charge_interval(
        df_cp,
        0.0,
        end_time_s,
        current_column=current_column,
        current_correction_factor=current_correction_factor,
    )
    return charge_c


def _n_n_from_delta_absorbance(
    delta_absorbance: float,
    volume_L: float,
    calibration_factor: float,
    molar_mass_n_g_mol: float,
) -> float:
    """Convert an absorbance change to moles of nitrogen produced.

    Args:
        delta_absorbance (float): Absorbance change.
        volume_L (float): Reactor volume in liters.
        calibration_factor (float): Calibration factor.
        molar_mass_n_g_mol (float): Molar mass of nitrogen in g/mol.

    Returns:
        float: Moles of nitrogen.
    """
    m_n_mg_per_mol = molar_mass_n_g_mol * 1000.0
    conc_n_mg_per_l = delta_absorbance / calibration_factor
    return (conc_n_mg_per_l * volume_L) / m_n_mg_per_mol


def fe_percent_from_charge(
    n_n_mol: float,
    charge_c: float,
    mols_electrons_per_nh3: float,
    faraday_constant_c_mol: float,
) -> float:
    """Calculate Faradaic efficiency in percent from nitrogen moles and charge.

    Args:
        n_n_mol (float): Moles of nitrogen produced in the interval.
        charge_c (float): Charge passed in coulombs.
        mols_electrons_per_nh3 (float): Electrons per NH3.
        faraday_constant_c_mol (float): Faraday constant in C/mol.

    Returns:
        float: Faradaic efficiency in percent, or NaN if charge is invalid.
    """
    if not np.isfinite(charge_c) or charge_c <= 0.0 or not np.isfinite(n_n_mol):
        return float("nan")
    q_nh3_c = mols_electrons_per_nh3 * n_n_mol * faraday_constant_c_mol
    return q_nh3_c / charge_c * 100.0


def build_fe_interval_breakdowns(
    experiment_id: int,
    folder_uvvis: Path,
    folder_electrosynthesis: Path,
    config: ProcessingConfig | None = None,
) -> list[FeIntervalBreakdown]:
    """Build interval FE breakdown rows for one experiment.

    Args:
        experiment_id (int): Experiment ID.
        folder_uvvis (Path): UV-Vis folder.
        folder_electrosynthesis (Path): Electrosynthesis folder.
        config (ProcessingConfig | None, optional): Processing config. Defaults to loaded config.

    Returns:
        list[FeIntervalBreakdown]: Interval FE rows sorted by reaction time.
    """
    config = config or get_processing_config()
    aliquots = load_uvvis_aliquots(experiment_id, folder_uvvis, config=config)
    if not aliquots:
        return []

    cp_data = load_cp_data(experiment_id, folder_electrosynthesis)
    if cp_data is None:
        return []
    _cp_path, df_cp = cp_data

    volume_l = load_reactor_volume_L(experiment_id)
    reaction_time_s = load_reaction_time_s(experiment_id)
    effective_times = effective_aliquot_times(
        [aliquot.reaction_time_s for aliquot in aliquots],
        reaction_time_s,
    )

    breakdowns: list[FeIntervalBreakdown] = []
    previous_absorbance: float | None = None
    previous_time_s = 0.0

    for aliquot, effective_time_s in zip(aliquots, effective_times):
        absorbance = get_aliquot_absorbance(aliquot, config)
        if previous_absorbance is None:
            delta_absorbance = absorbance
        else:
            delta_absorbance = absorbance - previous_absorbance

        charge_c, _ = integrate_charge_interval(
            df_cp,
            previous_time_s,
            effective_time_s,
            current_correction_factor=config.current_correction_factor,
        )
        n_n_mol = _n_n_from_delta_absorbance(
            delta_absorbance,
            volume_l,
            config.calibration_factor,
            config.molar_mass_n_g_mol,
        )
        fe_pct = fe_percent_from_charge(
            n_n_mol,
            charge_c,
            config.mols_electrons_per_nh3,
            config.faraday_constant_c_mol,
        )
        breakdowns.append(
            FeIntervalBreakdown(
                experiment_id=experiment_id,
                reaction_time_s=effective_time_s,
                delta_absorbance_corrected=delta_absorbance,
                fe_nh3_pct=fe_pct,
            )
        )
        previous_absorbance = absorbance
        previous_time_s = effective_time_s

    return breakdowns


def build_fe_cumulative_breakdowns(
    experiment_id: int,
    folder_uvvis: Path,
    folder_electrosynthesis: Path,
    config: ProcessingConfig | None = None,
) -> list[FeCumulativeBreakdown]:
    """Build cumulative mass-balance FE breakdown rows for one experiment.

    Args:
        experiment_id (int): Experiment ID.
        folder_uvvis (Path): UV-Vis folder.
        folder_electrosynthesis (Path): Electrosynthesis folder.
        config (ProcessingConfig | None, optional): Processing config. Defaults to loaded config.

    Returns:
        list[FeCumulativeBreakdown]: Cumulative FE rows sorted by reaction time.
    """
    config = config or get_processing_config()
    aliquots = load_uvvis_aliquots(experiment_id, folder_uvvis, config=config)
    if not aliquots:
        return []

    cp_data = load_cp_data(experiment_id, folder_electrosynthesis)
    if cp_data is None:
        return []
    _cp_path, df_cp = cp_data

    initial_volume_ml = load_reaction_catholyte_volume_mL(experiment_id)
    aliquot_volume_ml = load_aliquot_volume_mL(experiment_id)
    reaction_time_s = load_reaction_time_s(experiment_id)
    effective_times = effective_aliquot_times(
        [aliquot.reaction_time_s for aliquot in aliquots],
        reaction_time_s,
    )

    breakdowns: list[FeCumulativeBreakdown] = []
    n_removed_mg = 0.0
    v_remaining_ml = initial_volume_ml

    for index, (aliquot, effective_time_s) in enumerate(zip(aliquots, effective_times)):
        absorbance = get_aliquot_absorbance(aliquot, config)
        conc_n_mg_per_ml = absorbance / config.calibration_factor / 1000.0
        n_in_reactor_mg = conc_n_mg_per_ml * v_remaining_ml
        n_total_mg = n_in_reactor_mg + n_removed_mg

        charge_c = integrate_charge_to_time(
            df_cp,
            effective_time_s,
            current_correction_factor=config.current_correction_factor,
        )
        n_n_mol = (n_total_mg / 1000.0) / config.molar_mass_n_g_mol
        fe_pct = fe_percent_from_charge(
            n_n_mol,
            charge_c,
            config.mols_electrons_per_nh3,
            config.faraday_constant_c_mol,
        )
        breakdowns.append(
            FeCumulativeBreakdown(
                experiment_id=experiment_id,
                reaction_time_s=effective_time_s,
                n_total_mg=n_total_mg,
                fe_cumulative_pct=fe_pct,
            )
        )

        n_removed_mg += conc_n_mg_per_ml * aliquot_volume_ml
        if index < len(aliquots) - 1:
            v_remaining_ml -= aliquot_volume_ml

    return breakdowns


def build_fe_breakdowns(
    experiment_ids: list[int],
    folder_uvvis: Path,
    folder_electrosynthesis: Path,
    config: ProcessingConfig | None = None,
) -> list[FeIntervalBreakdown]:
    """Build interval FE breakdown rows for multiple experiments.

    Args:
        experiment_ids (list[int]): Experiment IDs.
        folder_uvvis (Path): UV-Vis folder.
        folder_electrosynthesis (Path): Electrosynthesis folder.
        config (ProcessingConfig | None, optional): Processing config. Defaults to loaded config.

    Returns:
        list[FeIntervalBreakdown]: Combined interval FE rows.
    """
    rows: list[FeIntervalBreakdown] = []
    for experiment_id in experiment_ids:
        rows.extend(
            build_fe_interval_breakdowns(
                experiment_id,
                folder_uvvis,
                folder_electrosynthesis,
                config=config,
            )
        )
    return rows


def _format_value(value: float | None, precision: int = 3) -> str:
    """Format a nullable float for compact table display.

    Args:
        value (float | None): Value to format.
        precision (int, optional): Decimal places. Defaults to 3.

    Returns:
        str: Formatted value or `N/A`.
    """
    if value is None or not np.isfinite(value):
        return "N/A"
    return f"{value:.{precision}f}"


def _format_fe_value(value: float | None) -> str:
    """Format FE values with bounded display markers.

    Args:
        value (float | None): FE percent value.

    Returns:
        str: `<0`, `>100`, numeric FE, or `N/A`.
    """
    if value is None or not np.isfinite(value):
        return "N/A"
    if value < 0.0:
        return "<0"
    if value > 100.0:
        return ">100"
    return _format_value(value, 2)


def format_fe_table_rows(
    breakdowns: list[FeIntervalBreakdown],
    max_rows: int = 3,
) -> list[list[str]]:
    """Format interval FE breakdown rows for matplotlib tables.

    Args:
        breakdowns (list[FeIntervalBreakdown]): Interval FE rows.
        max_rows (int, optional): Maximum number of rows to include. Defaults to 3.

    Returns:
        list[list[str]]: Table rows with time, delta absorbance, and FE percent.
    """
    rows: list[list[str]] = []
    for row in sorted(breakdowns, key=lambda item: item.reaction_time_s)[:max_rows]:
        rows.append(
            [
                f"{float(row.reaction_time_s):.0f}",
                _format_value(float(row.delta_absorbance_corrected), 3),
                _format_fe_value(float(row.fe_nh3_pct)),
            ]
        )
    while len(rows) < max_rows:
        rows.append(["N/A", "N/A", "N/A"])
    return rows
