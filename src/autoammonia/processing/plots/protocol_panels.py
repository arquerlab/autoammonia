from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from autoammonia.processing.conversions import current_density_ma_cm2, potential_agagcl_3m_to_rhe
from autoammonia.processing.echem_traces import EchemTrace
from autoammonia.processing.plot_style import SMALL_FONT_SIZE, TITLE_FONT_SIZE, draw_missing
from autoammonia.processing.processing_config import ProcessingConfig, get_processing_config


def annotate_setpoint_current_density(ax: plt.Axes, j_set_ma_cm2: float | None) -> None:
    """Annotate a CP panel with the configured setpoint current density.

    Args:
        ax (plt.Axes): Target axes.
        j_set_ma_cm2 (float | None): Setpoint current density in mA/cm^2.
    """
    if j_set_ma_cm2 is None or not np.isfinite(j_set_ma_cm2):
        return
    ax.text(
        0.02,
        0.97,
        rf"$j_{{set}}$ = {j_set_ma_cm2:.2f} mA/cm$^2$",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=SMALL_FONT_SIZE,
        bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none", "pad": 2.0},
    )


def plot_cp_panel(
    ax: plt.Axes,
    trace: EchemTrace | None,
    title: str,
    *,
    ph: float,
    ref_offset_v: float,
    show_current: bool = False,
    j_set_ma_cm2: float | None = None,
    config: ProcessingConfig | None = None,
) -> None:
    """Plot one CP or OCP potential-time trace versus RHE.

    Args:
        ax (plt.Axes): Target axes.
        trace (EchemTrace | None): Loaded trace.
        title (str): Panel title.
        ph (float): Electrolyte pH for RHE conversion.
        ref_offset_v (float): Ag/AgCl reference offset in volts.
        show_current (bool, optional): Plot current on a secondary y-axis if available.
        j_set_ma_cm2 (float | None, optional): Setpoint current density annotation.
        config (ProcessingConfig | None, optional): Processing config.
    """
    config = config or get_processing_config()
    ax.set_title(title, fontsize=TITLE_FONT_SIZE)
    if trace is None:
        draw_missing(ax, f"No {title} file found")
        return

    potential_rhe = potential_agagcl_3m_to_rhe(
        trace.data["Potential (V)"], ph=ph, ref_offset_v=ref_offset_v
    )
    potential_line = ax.plot(
        trace.data["Time (s)"],
        potential_rhe,
        linewidth=1.0,
        color=plt.get_cmap("Blues")(0.75),
        label="Potential",
    )
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Potential (V vs RHE)")
    annotate_setpoint_current_density(ax, j_set_ma_cm2)

    if show_current and "Current (A)" in trace.data.columns:
        current_density_values = current_density_ma_cm2(
            trace.data["Current (A)"].to_numpy(dtype=float),
            config.electrode_area_cm2,
            config.current_correction_factor,
        )
        time_s = trace.data["Time (s)"].to_numpy(dtype=float)
        finite = np.isfinite(time_s) & np.isfinite(current_density_values)
        if np.any(finite):
            ax_current = ax.twinx()
            current_line = ax_current.plot(
                time_s[finite],
                current_density_values[finite],
                linewidth=1.0,
                color="#b45f06",
                label="Current density",
            )
            ax_current.set_ylabel("Current density (mA/cm$^2$)")
            lines = potential_line + current_line
            labels = [line.get_label() for line in lines]
            ax.legend(lines, labels, frameon=False, fontsize=SMALL_FONT_SIZE)


def plot_reaction_trace_panel(
    ax: plt.Axes,
    trace: EchemTrace | None,
    *,
    ph: float,
    ref_offset_v: float,
    j_set_ma_cm2: float | None = None,
    config: ProcessingConfig | None = None,
) -> None:
    """Plot reaction CP, or reaction CA if CP is unavailable.

    Args:
        ax (plt.Axes): Target axes.
        trace (EchemTrace | None): Loaded reaction trace.
        ph (float): Electrolyte pH for RHE conversion.
        ref_offset_v (float): Ag/AgCl reference offset in volts.
        j_set_ma_cm2 (float | None, optional): Reaction setpoint current density.
        config (ProcessingConfig | None, optional): Processing config.
    """
    config = config or get_processing_config()
    if trace is None:
        ax.set_title("Reaction CP/CA", fontsize=TITLE_FONT_SIZE)
        draw_missing(ax, "No Reaction CP or CA file found")
        return

    if trace.label == "Reaction CA":
        ax.set_title("Reaction CA", fontsize=TITLE_FONT_SIZE)
        time_s = trace.data["Time (s)"].to_numpy(dtype=float)
        current_density_values = current_density_ma_cm2(
            trace.data["Current (A)"].to_numpy(dtype=float),
            config.electrode_area_cm2,
            config.current_correction_factor,
        )
        finite_current = np.isfinite(time_s) & np.isfinite(current_density_values)
        if not np.any(finite_current):
            draw_missing(ax, "Reaction CA current data unavailable")
            return

        current_line = ax.plot(
            time_s[finite_current],
            current_density_values[finite_current],
            linewidth=1.0,
            color="#b45f06",
            label="Current density",
        )
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Current density (mA/cm$^2$)")
        annotate_setpoint_current_density(ax, j_set_ma_cm2)

        potential_column = (
            "Applied potential (V)"
            if "Applied potential (V)" in trace.data.columns
            else "Potential (V)"
            if "Potential (V)" in trace.data.columns
            else None
        )
        if potential_column is not None:
            potential = trace.data[potential_column].to_numpy(dtype=float)
            potential_rhe = np.asarray(
                potential_agagcl_3m_to_rhe(potential, ph=ph, ref_offset_v=ref_offset_v),
                dtype=float,
            )
            finite_potential = np.isfinite(time_s) & np.isfinite(potential_rhe)
            if np.any(finite_potential):
                ax_potential = ax.twinx()
                potential_line = ax_potential.plot(
                    time_s[finite_potential],
                    potential_rhe[finite_potential],
                    linewidth=1.0,
                    color=plt.get_cmap("Blues")(0.75),
                    label="Applied potential",
                )
                ax_potential.set_ylabel("Applied potential (V vs RHE)")
                lines = current_line + potential_line
                labels = [line.get_label() for line in lines]
                ax.legend(lines, labels, frameon=False, fontsize=SMALL_FONT_SIZE)
        else:
            ax.legend(frameon=False, fontsize=SMALL_FONT_SIZE)
        return

    plot_cp_panel(
        ax,
        trace,
        trace.label,
        ph=ph,
        ref_offset_v=ref_offset_v,
        show_current=True,
        j_set_ma_cm2=j_set_ma_cm2,
        config=config,
    )
