from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from autoammonia.processing.conversions import current_density_ma_cm2
from autoammonia.processing.echem_metrics import capacitive_current_density_ma_cm2
from autoammonia.processing.plot_style import (
    SMALL_FONT_SIZE,
    TITLE_FONT_SIZE,
    draw_missing,
    safe_plot_panel,
)
from autoammonia.processing.processing_config import ProcessingConfig, get_processing_config


DEFAULT_BASE_DATA_DIR = Path(r"C:\Users\LAB-CO2MAP\ammonia_data")
FONT_FAMILY = "Arial"
BASE_FONT_SIZE = 14
TITLE_FONT_SIZE = 17
SMALL_FONT_SIZE = 12
AXIS_LABEL_FONT_SIZE = 15
TICK_FONT_SIZE = 13

plt.rcParams.update(
    {
        "font.family": FONT_FAMILY,
        "font.size": BASE_FONT_SIZE,
        "axes.titlesize": TITLE_FONT_SIZE,
        "axes.labelsize": AXIS_LABEL_FONT_SIZE,
        "xtick.labelsize": TICK_FONT_SIZE,
        "ytick.labelsize": TICK_FONT_SIZE,
        "legend.fontsize": SMALL_FONT_SIZE,
    }
)


@dataclass(frozen=True)
class CharacterizationTrace:
    """Electrochemical characterization trace loaded from one CSV file.

    Attributes:
        label (str): Trace label used in plots.
        stage (str): Characterization stage, such as `prerx` or `postrx`.
        method (str): Electrochemical method name, such as `CV` or `LSV`.
        path (Path): Source CSV path.
        data (pd.DataFrame): Trace dataframe.
        scan_rate_mv_s (float | None): CV scan rate in mV/s when available.
    """

    label: str
    stage: str
    method: str
    path: Path
    data: pd.DataFrame
    scan_rate_mv_s: float | None = None


@dataclass(frozen=True)
class CapacitanceFit:
    """Linear capacitance fit for one characterization stage.

    Attributes:
        stage (str): Characterization stage used for the fit.
        scan_rates_mv_s (np.ndarray): Scan rates in mV/s.
        capacitive_currents_ma_cm2 (np.ndarray): Capacitive current densities in mA/cm^2.
        slope_mf_cm2 (float): Fitted slope in mF/cm^2.
        intercept_ma_cm2 (float): Fitted intercept in mA/cm^2.
        r_squared (float): Coefficient of determination for the fit.
    """

    stage: str
    scan_rates_mv_s: np.ndarray
    capacitive_currents_ma_cm2: np.ndarray
    slope_mf_cm2: float
    intercept_ma_cm2: float
    r_squared: float


def _safe_read_csv(
    path: Path,
    required_columns: set[str],
    optional_columns: set[str] | None = None,
    max_points: int = 12000,
) -> pd.DataFrame | None:
    """Read an electrochemical CSV and downsample it for plotting.

    Args:
        path (Path): CSV path.
        required_columns (set[str]): Columns required for downstream processing.
        optional_columns (set[str] | None, optional): Extra columns to keep when present.
            Defaults to None.
        max_points (int, optional): Maximum plotted points. Defaults to 12000.

    Returns:
        pd.DataFrame | None: Downsampled dataframe, or None if the file is invalid.
    """
    columns_to_keep = required_columns | (optional_columns or set())
    try:
        df = pd.read_csv(path, usecols=lambda column: column in columns_to_keep)
    except Exception:
        return None

    if not required_columns.issubset(df.columns):
        return None

    for column in columns_to_keep:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(subset=list(required_columns)).reset_index(drop=True)
    if df.empty:
        return None

    if len(df) > max_points:
        positions = np.linspace(0, len(df) - 1, max_points).astype(int)
        df = df.iloc[positions].reset_index(drop=True)

    return df


def _parse_scan_rate_mv_s(path: Path) -> float | None:
    """Parse CV scan rate from a characterization filename.

    Args:
        path (Path): CV file path.

    Returns:
        float | None: Scan rate in mV/s, or None if unavailable.
    """
    match = re.search(r"ECSA_rate_([0-9]+(?:\.[0-9]+)?)", path.name)
    if not match:
        return None
    return float(match.group(1))


def _parse_stage(path: Path, method: str) -> str:
    """Parse characterization stage from a filename.

    Args:
        path (Path): Electrochemical CSV path.
        method (str): Method token to parse after, such as `CV` or `LSV`.

    Returns:
        str: Parsed stage or `unknown`.
    """
    match = re.search(rf"_method_{re.escape(method)}_([^_.]+)", path.name)
    if not match:
        return "unknown"
    return match.group(1)


def _stage_sort_key(stage: str) -> tuple[int, str]:
    """Return a stable sort key for known characterization stages.

    Args:
        stage (str): Stage label.

    Returns:
        tuple[int, str]: Sort key placing `prerx` before `postrx`.
    """
    order = {"prerx": 0, "postrx": 1}
    return order.get(stage, 99), stage


def _stage_label(stage: str) -> str:
    """Return a human-readable stage label.

    Args:
        stage (str): Stage token from a filename.

    Returns:
        str: Human-readable stage label.
    """
    labels = {"prerx": "Before reaction", "postrx": "After reaction"}
    return labels.get(stage, stage)


def _current_density_ma_cm2(
    current_a: pd.Series | np.ndarray,
    config: ProcessingConfig | None = None,
) -> np.ndarray:
    """Convert measured current to corrected current density.

    Args:
        current_a (pd.Series | np.ndarray): Measured current in A.
        config (ProcessingConfig | None, optional): Processing config.

    Returns:
        np.ndarray: Current density in mA/cm^2.
    """
    config = config or get_processing_config()
    return current_density_ma_cm2(
        current_a,
        config.electrode_area_cm2,
        config.current_correction_factor,
    )


def _load_ecsa_cv_traces(
    experiment_id: int,
    folder: Path,
    stage: str | None = None,
) -> list[CharacterizationTrace]:
    """Load ECSA CV traces for one experiment.

    Args:
        experiment_id (int): Experiment ID.
        folder (Path): Electrosynthesis data folder.
        stage (str | None, optional): Optional stage filter such as `prerx` or `postrx`.
            Defaults to None.

    Returns:
        list[CharacterizationTrace]: Loaded CV traces sorted by stage and scan rate.
    """
    stage_pattern = "*" if stage is None else stage
    paths = sorted(folder.glob(f"{experiment_id}_cell*_method_CV_{stage_pattern}_ECSA_rate_*.csv"))
    traces: list[CharacterizationTrace] = []
    required_columns = {"Potential (V)", "Current (A)"}
    optional_columns = {"Time (s)", "Applied potential (V)", "Cycle"}

    for path in paths:
        scan_rate_mv_s = _parse_scan_rate_mv_s(path)
        if scan_rate_mv_s is None:
            continue

        data = _safe_read_csv(path, required_columns, optional_columns=optional_columns)
        if data is None or data.empty:
            continue

        trace_stage = _parse_stage(path, "CV")
        traces.append(
            CharacterizationTrace(
                label=f"{_stage_label(trace_stage)}, {scan_rate_mv_s:g} mV/s",
                stage=trace_stage,
                method="CV",
                path=path,
                data=data,
                scan_rate_mv_s=scan_rate_mv_s,
            )
        )

    return sorted(
        traces,
        key=lambda trace: (
            _stage_sort_key(trace.stage),
            trace.scan_rate_mv_s if trace.scan_rate_mv_s is not None else np.inf,
            trace.path.name,
        ),
    )


def _load_lsv_traces(
    experiment_id: int,
    folder: Path,
    stage: str | None = None,
) -> list[CharacterizationTrace]:
    """Load LSV traces for one experiment.

    Args:
        experiment_id (int): Experiment ID.
        folder (Path): Electrosynthesis data folder.
        stage (str | None, optional): Optional stage filter such as `prerx` or `postrx`.
            Defaults to None.

    Returns:
        list[CharacterizationTrace]: Loaded LSV traces sorted by stage.
    """
    pattern = (
        f"{experiment_id}_cell*_method_LSV_*.csv"
        if stage is None
        else f"{experiment_id}_cell*_method_LSV_{stage}*.csv"
    )
    paths = sorted(folder.glob(pattern))
    traces: list[CharacterizationTrace] = []
    required_columns = {"Time (s)", "Potential (V)", "Current (A)"}
    optional_columns = {"Applied potential (V)"}

    for path in paths:
        data = _safe_read_csv(path, required_columns, optional_columns=optional_columns)
        if data is None or data.empty:
            continue

        trace_stage = _parse_stage(path, "LSV")
        traces.append(
            CharacterizationTrace(
                label=_stage_label(trace_stage),
                stage=trace_stage,
                method="LSV",
                path=path,
                data=data,
            )
        )

    return sorted(traces, key=lambda trace: (_stage_sort_key(trace.stage), trace.path.name))


def _calculate_capacitance_fits(
    traces: list[CharacterizationTrace],
    config: ProcessingConfig | None = None,
) -> list[CapacitanceFit]:
    """Calculate double-layer capacitance fits from ECSA CV traces.

    Args:
        traces (list[CharacterizationTrace]): ECSA CV traces.

    Returns:
        list[CapacitanceFit]: One linear fit per stage with at least two valid points.
    """
    config = config or get_processing_config()
    points_by_stage: dict[str, list[tuple[float, float]]] = {}

    for trace in traces:
        if trace.scan_rate_mv_s is None:
            continue
        capacitive_current = capacitive_current_density_ma_cm2(trace.data, config)
        if capacitive_current is None:
            continue
        points_by_stage.setdefault(trace.stage, []).append((trace.scan_rate_mv_s, capacitive_current))

    fits: list[CapacitanceFit] = []
    for stage, points in sorted(points_by_stage.items(), key=lambda item: _stage_sort_key(item[0])):
        unique_points = sorted(set(points), key=lambda point: point[0])
        if len(unique_points) < 2:
            continue

        scan_rates_mv_s = np.asarray([point[0] for point in unique_points], dtype=float)
        scan_rates_v_s = scan_rates_mv_s / 1000.0
        capacitive_currents = np.asarray([point[1] for point in unique_points], dtype=float)
        slope, intercept = np.polyfit(scan_rates_v_s, capacitive_currents, deg=1)
        predicted = slope * scan_rates_v_s + intercept
        residual_sum = float(np.sum((capacitive_currents - predicted) ** 2))
        total_sum = float(np.sum((capacitive_currents - np.mean(capacitive_currents)) ** 2))
        r_squared = 1.0 - residual_sum / total_sum if total_sum > 0 else 1.0
        fits.append(
            CapacitanceFit(
                stage=stage,
                scan_rates_mv_s=scan_rates_mv_s,
                capacitive_currents_ma_cm2=capacitive_currents,
                slope_mf_cm2=float(slope),
                intercept_ma_cm2=float(intercept),
                r_squared=float(r_squared),
            )
        )

    return fits


def _plot_ecsa_cv_overlay_panel(
    ax: plt.Axes,
    traces: list[CharacterizationTrace],
    config: ProcessingConfig | None = None,
) -> None:
    """Plot overlaid ECSA CV traces.

    Args:
        ax (plt.Axes): Target axes.
        traces (list[CharacterizationTrace]): ECSA CV traces.
    """
    config = config or get_processing_config()
    ax.set_title("ECSA CV overlay", fontsize=TITLE_FONT_SIZE)
    if not traces:
        draw_missing(ax, "No ECSA CV files found")
        return

    stage_styles = {"prerx": "-", "postrx": "--"}
    rates = sorted({trace.scan_rate_mv_s for trace in traces if trace.scan_rate_mv_s is not None})
    cmap = plt.get_cmap("viridis")
    color_by_rate = {
        rate: cmap(index / max(1, len(rates) - 1))
        for index, rate in enumerate(rates)
    }

    for trace in traces:
        potential_v = trace.data["Potential (V)"]
        current_density = _current_density_ma_cm2(trace.data["Current (A)"], config)
        ax.plot(
            potential_v,
            current_density,
            linewidth=1.1,
            alpha=0.9,
            linestyle=stage_styles.get(trace.stage, "-"),
            color=color_by_rate.get(trace.scan_rate_mv_s, "0.35"),
            label=trace.label,
        )

    ax.set_xlabel("Measured potential (V)")
    ax.set_ylabel("Current density (mA/cm$^2$)")
    ax.legend(frameon=False, fontsize=SMALL_FONT_SIZE - 1, ncols=2)


def _plot_capacitance_panel(ax: plt.Axes, fits: list[CapacitanceFit]) -> None:
    """Plot capacitive current density against scan rate.

    Args:
        ax (plt.Axes): Target axes.
        fits (list[CapacitanceFit]): Capacitance fits to plot.
    """
    ax.set_title("ECSA capacitance fit", fontsize=TITLE_FONT_SIZE)
    if not fits:
        draw_missing(ax, "Not enough ECSA CV points")
        return

    colors = {"prerx": plt.get_cmap("Blues")(0.55), "postrx": plt.get_cmap("Oranges")(0.65)}
    for fit in fits:
        color = colors.get(fit.stage, "0.35")
        ax.scatter(
            fit.scan_rates_mv_s,
            fit.capacitive_currents_ma_cm2,
            s=38,
            color=color,
            label=(
                f"{_stage_label(fit.stage)} points"
                f" (C$_{{DL}}$={abs(fit.slope_mf_cm2):.2f} mF/cm$^2$)"
            ),
        )
        x_line = np.linspace(float(np.min(fit.scan_rates_mv_s)), float(np.max(fit.scan_rates_mv_s)), 100)
        y_line = fit.slope_mf_cm2 * (x_line / 1000.0) + fit.intercept_ma_cm2
        ax.plot(
            x_line,
            y_line,
            color=color,
            linewidth=1.2,
            linestyle="-",
            alpha=0.9,
            label=f"{_stage_label(fit.stage)} fit, R$^2$={fit.r_squared:.3f}",
        )

    ax.set_xlabel("Scan rate (mV/s)")
    ax.set_ylabel("Capacitive current density (mA/cm$^2$)")
    ax.legend(frameon=False, fontsize=SMALL_FONT_SIZE - 1)


def _plot_lsv_panel(
    ax: plt.Axes,
    traces: list[CharacterizationTrace],
    min_time_s: float = 0.0,
    config: ProcessingConfig | None = None,
) -> None:
    """Plot characterization LSV traces.

    Args:
        ax (plt.Axes): Target axes.
        traces (list[CharacterizationTrace]): LSV traces.
        min_time_s (float, optional): Drop early transient points at or before this time.
            Defaults to 0.0.
    """
    config = config or get_processing_config()
    ax.set_title("LSV", fontsize=TITLE_FONT_SIZE)
    if not traces:
        draw_missing(ax, "No LSV files found")
        return

    colors = {"prerx": plt.get_cmap("Blues")(0.55), "postrx": plt.get_cmap("Blues")(0.85)}
    for trace in traces:
        data = trace.data
        if min_time_s > 0 and "Time (s)" in data.columns:
            data = data[data["Time (s)"] > float(min_time_s)]
        if data.empty:
            continue

        potential_v = data["Potential (V)"]
        current_density = _current_density_ma_cm2(data["Current (A)"], config)
        ax.plot(
            potential_v,
            current_density,
            linewidth=1.2,
            color=colors.get(trace.stage, "0.35"),
            label=trace.label,
        )

    ax.set_xlabel("Measured potential (V)")
    ax.set_ylabel("Current density (mA/cm$^2$)")
    ax.legend(frameon=False, fontsize=SMALL_FONT_SIZE)


def _plot_applied_vs_measured_panel(
    ax: plt.Axes,
    lsv_traces: list[CharacterizationTrace],
    cv_traces: list[CharacterizationTrace],
) -> None:
    """Plot applied potential against measured potential for characterization traces.

    Args:
        ax (plt.Axes): Target axes.
        lsv_traces (list[CharacterizationTrace]): LSV traces.
        cv_traces (list[CharacterizationTrace]): ECSA CV traces.
    """
    ax.set_title("Applied vs measured potential", fontsize=TITLE_FONT_SIZE)
    plotted_ranges: list[np.ndarray] = []

    for trace in cv_traces:
        if "Applied potential (V)" not in trace.data.columns:
            continue
        applied = trace.data["Applied potential (V)"].to_numpy(dtype=float)
        measured = trace.data["Potential (V)"].to_numpy(dtype=float)
        finite = np.isfinite(applied) & np.isfinite(measured)
        if not np.any(finite):
            continue

        ax.plot(
            applied[finite],
            measured[finite],
            linewidth=0.8,
            color="0.65",
            alpha=0.35,
            label="ECSA CVs" if not plotted_ranges else None,
        )
        plotted_ranges.extend([applied[finite], measured[finite]])

    colors = {"prerx": plt.get_cmap("Blues")(0.55), "postrx": plt.get_cmap("Oranges")(0.65)}
    for trace in lsv_traces:
        if "Applied potential (V)" not in trace.data.columns:
            continue
        applied = trace.data["Applied potential (V)"].to_numpy(dtype=float)
        measured = trace.data["Potential (V)"].to_numpy(dtype=float)
        finite = np.isfinite(applied) & np.isfinite(measured)
        if not np.any(finite):
            continue

        ax.plot(
            applied[finite],
            measured[finite],
            linewidth=1.2,
            color=colors.get(trace.stage, "0.25"),
            label=f"{trace.label} LSV",
        )
        plotted_ranges.extend([applied[finite], measured[finite]])

    if not plotted_ranges:
        draw_missing(ax, "No applied potential columns found")
        return

    values = np.concatenate(plotted_ranges)
    min_value = float(np.nanmin(values))
    max_value = float(np.nanmax(values))
    padding = (max_value - min_value) * 0.04 if max_value > min_value else 0.05
    diagonal = np.asarray([min_value - padding, max_value + padding], dtype=float)
    ax.plot(diagonal, diagonal, color="0.25", linewidth=0.9, linestyle=":", label="Ideal")
    ax.set_xlim(diagonal[0], diagonal[1])
    ax.set_ylim(diagonal[0], diagonal[1])
    ax.set_xlabel("Applied potential (V)")
    ax.set_ylabel("Measured potential (V)")
    ax.legend(frameon=False, fontsize=SMALL_FONT_SIZE - 1)


def plot_electrochemical_characterization_summary(
    experiment_id: int,
    out_path: Path | None = None,
    base_data_dir: Path = DEFAULT_BASE_DATA_DIR,
    stage: str | None = None,
    min_lsv_time_s: float = 0.0,
) -> Path:
    """Create a 2x2 electrochemical characterization summary plot.

    Args:
        experiment_id (int): Experiment ID.
        out_path (Path | None, optional): Output PNG path. Defaults to
            `base_data_dir / "process" / "electrochemical_characterization_summary" /
            f"ID{experiment_id}_electrochemical_characterization_summary.png"`.
        base_data_dir (Path, optional): Base ammonia data directory. Defaults to
            `C:\\Users\\LAB-CO2MAP\\ammonia_data`.
        stage (str | None, optional): Optional stage filter such as `prerx` or `postrx`.
            Defaults to None.
        min_lsv_time_s (float, optional): Drop early LSV transient points at or before this time.
            Defaults to 0.0.

    Returns:
        Path: Saved plot path.
    """
    base_data_dir = Path(base_data_dir)
    folder_electrosynthesis = base_data_dir / "electrosynthesis"

    if out_path is None:
        suffix = f"_{stage}" if stage is not None else ""
        out_path = (
            base_data_dir
            / "process"
            / "electrochemical_characterization_summary"
            / f"ID{experiment_id}_electrochemical_characterization_summary{suffix}.png"
        )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    config = get_processing_config()
    cv_traces = _load_ecsa_cv_traces(experiment_id, folder_electrosynthesis, stage=stage)
    lsv_traces = _load_lsv_traces(experiment_id, folder_electrosynthesis, stage=stage)
    capacitance_fits = _calculate_capacitance_fits(cv_traces, config=config)

    fig, axes = plt.subplots(2, 2, figsize=(15, 11), constrained_layout=True)
    safe_plot_panel(
        axes[0, 0],
        "ECSA CV overlay",
        "No ECSA CV files found",
        _plot_ecsa_cv_overlay_panel,
        cv_traces,
        config=config,
    )
    safe_plot_panel(
        axes[0, 1],
        "ECSA capacitance fit",
        "Not enough ECSA CV points",
        _plot_capacitance_panel,
        capacitance_fits,
    )
    safe_plot_panel(
        axes[1, 0],
        "LSV",
        "No LSV files found",
        _plot_lsv_panel,
        lsv_traces,
        min_time_s=min_lsv_time_s,
        config=config,
    )
    safe_plot_panel(
        axes[1, 1],
        "Applied vs measured potential",
        "No applied potential columns found",
        _plot_applied_vs_measured_panel,
        lsv_traces,
        cv_traces,
    )

    stage_text = f" ({_stage_label(stage)})" if stage is not None else ""
    fig.suptitle(
        f"Experiment ID{experiment_id} electrochemical characterization{stage_text}",
        fontsize=TITLE_FONT_SIZE + 2,
    )
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    return out_path


def _stage_specific_out_path(out_path: Path | None, stage: str) -> Path | None:
    """Build a stage-specific path when one base output path is provided.

    Args:
        out_path (Path | None): User-provided base output path.
        stage (str): Characterization stage, such as `prerx` or `postrx`.

    Returns:
        Path | None: Output path with the stage appended before the suffix, or None.
    """
    if out_path is None:
        return None

    out_path = Path(out_path)
    return out_path.with_name(f"{out_path.stem}_{stage}{out_path.suffix}")


def plot_electrochemical_characterization_stage_summaries(
    experiment_id: int,
    out_path: Path | None = None,
    base_data_dir: Path = DEFAULT_BASE_DATA_DIR,
    stages: tuple[str, ...] = ("prerx", "postrx"),
    min_lsv_time_s: float = 0.0,
) -> list[Path]:
    """Create separate electrochemical characterization summaries by stage.

    Args:
        experiment_id (int): Experiment ID.
        out_path (Path | None, optional): Optional base output PNG path. When provided,
            the stage is appended before the suffix. Defaults to None.
        base_data_dir (Path, optional): Base ammonia data directory. Defaults to
            `C:\\Users\\LAB-CO2MAP\\ammonia_data`.
        stages (tuple[str, ...], optional): Stages to plot. Defaults to ("prerx", "postrx").
        min_lsv_time_s (float, optional): Drop early LSV transient points at or before this time.
            Defaults to 0.0.

    Returns:
        list[Path]: Saved plot paths.
    """
    saved_paths: list[Path] = []
    for stage in stages:
        saved_paths.append(
            plot_electrochemical_characterization_summary(
                experiment_id,
                out_path=_stage_specific_out_path(out_path, stage),
                base_data_dir=base_data_dir,
                stage=stage,
                min_lsv_time_s=min_lsv_time_s,
            )
        )

    return saved_paths


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the summary script.

    Returns:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Create 2x2 electrochemical characterization summary plots."
    )
    parser.add_argument(
        "experiment_id",
        type=int,
        nargs="?",
        default=149,
        help="Experiment ID to plot. Defaults to 149.",
    )
    parser.add_argument(
        "--base-data-dir",
        type=Path,
        default=DEFAULT_BASE_DATA_DIR,
        help="Base data directory containing the electrosynthesis folder.",
    )
    parser.add_argument(
        "--out-path",
        type=Path,
        default=None,
        help=(
            "Output PNG path. With no --stage, _prerx and _postrx are appended before "
            "the suffix. Defaults to the process folder in the base data directory."
        ),
    )
    parser.add_argument(
        "--stage",
        choices=["prerx", "postrx"],
        default=None,
        help="Optional characterization stage filter. If omitted, both stages are plotted separately.",
    )
    parser.add_argument(
        "--min-lsv-time-s",
        type=float,
        default=0.0,
        help="Drop LSV points at or before this time in seconds. Defaults to 0.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.stage is None:
        saved_paths = plot_electrochemical_characterization_stage_summaries(
            args.experiment_id,
            out_path=args.out_path,
            base_data_dir=args.base_data_dir,
            min_lsv_time_s=args.min_lsv_time_s,
        )
        for saved in saved_paths:
            print(f"Saved plot: {saved}")
    else:
        saved = plot_electrochemical_characterization_summary(
            args.experiment_id,
            out_path=args.out_path,
            base_data_dir=args.base_data_dir,
            stage=args.stage,
            min_lsv_time_s=args.min_lsv_time_s,
        )
        print(f"Saved plot: {saved}")
