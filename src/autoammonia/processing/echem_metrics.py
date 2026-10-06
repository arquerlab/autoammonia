from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from autoammonia.processing.conversions import current_density_ma_cm2, potential_agagcl_3m_to_rhe
from autoammonia.processing.echem_traces import EchemTrace, safe_read_csv
from autoammonia.processing.plot_style import format_value
from autoammonia.processing.processing_config import ProcessingConfig, get_processing_config


def parse_scan_rate_mv_s(path: Path) -> float | None:
    """Parse CV scan rate from the characterization filename.

    Args:
        path (Path): CV file path.

    Returns:
        float | None: Scan rate in mV/s, or None if unavailable.
    """
    match = re.search(r"ECSA_rate_([0-9]+(?:\.[0-9]+)?)", path.name)
    if not match:
        return None
    return float(match.group(1))


def capacitive_current_density_ma_cm2(
    df: pd.DataFrame,
    config: ProcessingConfig,
) -> float | None:
    """Estimate capacitive current density from one CV trace.

    Args:
        df (pd.DataFrame): CV dataframe.
        config (ProcessingConfig): Processing configuration.

    Returns:
        float | None: Half of anodic/cathodic current-density separation in mA/cm^2.
    """
    potential = df["Potential (V)"].to_numpy(dtype=float)
    current_density = current_density_ma_cm2(
        df["Current (A)"].to_numpy(dtype=float),
        config.electrode_area_cm2,
        config.current_correction_factor,
    )
    finite = np.isfinite(potential) & np.isfinite(current_density)
    potential = potential[finite]
    current_density = current_density[finite]
    if potential.size < 10:
        return None

    target_potential = float(np.nanmedian(potential))
    window = 0.01
    in_window = np.abs(potential - target_potential) <= window
    if np.count_nonzero(in_window) < 4:
        nearest_indices = np.argsort(np.abs(potential - target_potential))[: min(20, potential.size)]
        selected = current_density[nearest_indices]
    else:
        selected = current_density[in_window]

    if selected.size < 2:
        return None
    high = float(np.nanpercentile(selected, 90))
    low = float(np.nanpercentile(selected, 10))
    return abs(high - low) / 2.0


def calculate_dlc_slope(
    experiment_id: int,
    folder: Path,
    stage: str,
    config: ProcessingConfig | None = None,
) -> float | None:
    """Calculate DLC from CV current-density slope vs scan rate.

    Args:
        experiment_id (int): Experiment ID.
        folder (Path): Electrosynthesis data folder.
        stage (str): `prerx` or `postrx`.
        config (ProcessingConfig | None, optional): Processing config.

    Returns:
        float | None: DLC in mF/cm^2, or None if insufficient data are available.
    """
    config = config or get_processing_config()
    points: list[tuple[float, float]] = []
    required_columns = {"Potential (V)", "Current (A)"}

    for path in sorted(folder.glob(f"{experiment_id}_cell*_method_CV_{stage}_ECSA_rate_*.csv")):
        rate_mv_s = parse_scan_rate_mv_s(path)
        if rate_mv_s is None:
            continue
        df = safe_read_csv(path, required_columns)
        if df is None or df.empty:
            continue
        cap_current = capacitive_current_density_ma_cm2(df, config)
        if cap_current is None:
            continue
        points.append((rate_mv_s / 1000.0, cap_current))

    if len(points) < 2:
        return None

    scan_rates_v_s = np.asarray([point[0] for point in points], dtype=float)
    cap_currents_ma_cm2 = np.asarray([point[1] for point in points], dtype=float)
    slope, _intercept = np.polyfit(scan_rates_v_s, cap_currents_ma_cm2, deg=1)
    return abs(float(slope))


def ocp_value_v(
    trace: EchemTrace | None,
    ph: float | None = None,
    ref_offset_v: float | None = None,
) -> float | None:
    """Return a stable final OCP value from the last part of a trace.

    Args:
        trace (EchemTrace | None): OCP trace.
        ph (float | None, optional): Electrolyte pH for RHE conversion. When provided with
            ref_offset_v, returns potential vs RHE.
        ref_offset_v (float | None, optional): Ag/AgCl reference offset in volts.

    Returns:
        float | None: Median potential from the last 20% of the trace, or None.
    """
    if trace is None or trace.data.empty or "Potential (V)" not in trace.data.columns:
        return None

    potential = trace.data["Potential (V)"].to_numpy(dtype=float)
    potential = potential[np.isfinite(potential)]
    if potential.size == 0:
        return None

    start = max(0, int(np.floor(potential.size * 0.8)))
    ocp_v = float(np.nanmedian(potential[start:]))
    if ph is None or ref_offset_v is None:
        return ocp_v
    return float(
        potential_agagcl_3m_to_rhe(np.asarray([ocp_v]), ph=ph, ref_offset_v=ref_offset_v)[0]
    )


def eta_at_current_density(
    df: pd.DataFrame,
    ph: float,
    ref_offset_v: float,
    config: ProcessingConfig,
) -> float | None:
    """Calculate absolute overpotential where LSV reaches target current density.

    Args:
        df (pd.DataFrame): LSV dataframe.
        ph (float): Electrolyte pH for RHE conversion.
        ref_offset_v (float): Ag/AgCl reference offset in volts.
        config (ProcessingConfig): Processing configuration.

    Returns:
        float | None: Absolute potential vs RHE at target current density, or None.
    """
    target_ma_cm2 = config.target_current_density_ma_cm2
    potential_rhe = np.asarray(
        potential_agagcl_3m_to_rhe(df["Potential (V)"], ph=ph, ref_offset_v=ref_offset_v),
        dtype=float,
    )
    current_density_ma_cm2_values = current_density_ma_cm2(
        df["Current (A)"].to_numpy(dtype=float),
        config.electrode_area_cm2,
        config.current_correction_factor,
    )

    finite = np.isfinite(potential_rhe) & np.isfinite(current_density_ma_cm2_values)
    potential_rhe = potential_rhe[finite]
    abs_current_density = np.abs(current_density_ma_cm2_values[finite])
    if potential_rhe.size < 2 or np.nanmax(abs_current_density) < target_ma_cm2:
        return None

    centered = abs_current_density - target_ma_cm2
    crossing_indices = np.where(centered[:-1] * centered[1:] <= 0)[0]
    if crossing_indices.size:
        index = int(crossing_indices[0])
        x0 = abs_current_density[index]
        x1 = abs_current_density[index + 1]
        y0 = potential_rhe[index]
        y1 = potential_rhe[index + 1]
        if np.isclose(x0, x1):
            return abs(float(y0))
        x_pair = np.asarray([x0, x1], dtype=float)
        y_pair = np.asarray([y0, y1], dtype=float)
        order = np.argsort(x_pair)
        potential_at_target = np.interp(target_ma_cm2, x_pair[order], y_pair[order])
        return abs(float(potential_at_target))

    order = np.argsort(abs_current_density)
    current_sorted = abs_current_density[order]
    potential_sorted = potential_rhe[order]
    unique_current, unique_indices = np.unique(current_sorted, return_index=True)
    if unique_current.size < 2:
        return None
    potential_at_target = np.interp(target_ma_cm2, unique_current, potential_sorted[unique_indices])
    return abs(float(potential_at_target))


def build_lsv_metric_rows(
    experiment_id: int,
    lsv_traces: dict[str, EchemTrace],
    electrosynthesis_folder: Path,
    prerx_ocp: EchemTrace | None,
    postrx_ocp: EchemTrace | None,
    ph: float,
    ref_offset_v: float,
    config: ProcessingConfig | None = None,
) -> list[list[str]]:
    """Build rows for the LSV/DLC before-after table.

    Args:
        experiment_id (int): Experiment ID.
        lsv_traces (dict[str, EchemTrace]): Loaded LSV traces.
        electrosynthesis_folder (Path): Electrosynthesis data folder.
        prerx_ocp (EchemTrace | None): Before-reaction OCP trace.
        postrx_ocp (EchemTrace | None): After-reaction OCP trace.
        ph (float): Electrolyte pH.
        ref_offset_v (float): Ag/AgCl reference offset in volts.
        config (ProcessingConfig | None, optional): Processing config.

    Returns:
        list[list[str]]: Table rows.
    """
    config = config or get_processing_config()
    eta_pre = (
        eta_at_current_density(lsv_traces["prerx"].data, ph, ref_offset_v, config)
        if "prerx" in lsv_traces
        else None
    )
    eta_post = (
        eta_at_current_density(lsv_traces["postrx"].data, ph, ref_offset_v, config)
        if "postrx" in lsv_traces
        else None
    )
    dlc_pre = calculate_dlc_slope(experiment_id, electrosynthesis_folder, "prerx", config)
    dlc_post = calculate_dlc_slope(experiment_id, electrosynthesis_folder, "postrx", config)
    ocp_pre = ocp_value_v(prerx_ocp, ph=ph, ref_offset_v=ref_offset_v)
    ocp_post = ocp_value_v(postrx_ocp, ph=ph, ref_offset_v=ref_offset_v)

    return [
        [r"V$_{OC}$", "V vs RHE", format_value(ocp_pre, 3), format_value(ocp_post, 3)],
        [
            r"$\eta$ @ 10 mA/cm$^2$",
            "V vs RHE",
            format_value(eta_pre, 3),
            format_value(eta_post, 3),
        ],
        [r"C$_{DL}$", r"mF/cm$^2$", format_value(dlc_pre, 3), format_value(dlc_post, 3)],
    ]


def empty_metric_rows() -> list[list[str]]:
    """Return placeholder rows for the LSV and C_DL table.

    Returns:
        list[list[str]]: Table rows filled with `N/A` values.
    """
    return [
        [r"V$_{OC}$", "V vs RHE", "N/A", "N/A"],
        [r"$\eta$ @ 10 mA/cm$^2$", "V vs RHE", "N/A", "N/A"],
        [r"C$_{DL}$", r"mF/cm$^2$", "N/A", "N/A"],
    ]
