from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from autoammonia.processing.conversions import current_density_ma_cm2, potential_agagcl_3m_to_rhe
from autoammonia.processing.echem_traces import EchemTrace
from autoammonia.processing.plot_style import SMALL_FONT_SIZE, TITLE_FONT_SIZE, draw_missing
from autoammonia.processing.processing_config import ProcessingConfig, get_processing_config


def plot_lsv_panel(
    ax: plt.Axes,
    traces: dict[str, EchemTrace],
    ph: float,
    ref_offset_v: float,
    config: ProcessingConfig | None = None,
) -> None:
    """Plot pre/post LSV traces versus RHE.

    Args:
        ax (plt.Axes): Target axes.
        traces (dict[str, EchemTrace]): LSV traces keyed by stage.
        ph (float): Electrolyte pH.
        ref_offset_v (float): Ag/AgCl reference offset in volts.
        config (ProcessingConfig | None, optional): Processing config.
    """
    config = config or get_processing_config()
    ax.set_title("LSV before/after reaction", fontsize=TITLE_FONT_SIZE)
    if not traces:
        draw_missing(ax, "No LSV files found")
        return

    colors = {"prerx": plt.get_cmap("Blues")(0.45), "postrx": plt.get_cmap("Blues")(0.85)}
    labels = {"prerx": "Before reaction", "postrx": "After reaction"}
    for stage, trace in traces.items():
        potential_rhe = potential_agagcl_3m_to_rhe(
            trace.data["Potential (V)"], ph=ph, ref_offset_v=ref_offset_v
        )
        current_density_a_cm2 = (
            current_density_ma_cm2(
                trace.data["Current (A)"].to_numpy(dtype=float),
                config.electrode_area_cm2,
                config.current_correction_factor,
            )
            / 1000.0
        )
        ax.plot(
            potential_rhe,
            current_density_a_cm2,
            linewidth=1.2,
            color=colors.get(stage),
            label=labels.get(stage, stage),
        )

    target_a_cm2 = config.target_current_density_ma_cm2 / 1000.0
    ax.axhline(target_a_cm2, color="0.5", linewidth=0.8, linestyle=":")
    ax.axhline(-target_a_cm2, color="0.5", linewidth=0.8, linestyle=":")
    ax.set_xlabel("Potential (V vs RHE)")
    ax.set_ylabel("Current density (A/cm^2)")
    ax.legend(frameon=False, fontsize=SMALL_FONT_SIZE)


def plot_ocp_overlay_panel(
    ax: plt.Axes,
    prerx_trace: EchemTrace | None,
    postrx_trace: EchemTrace | None,
    ph: float,
    ref_offset_v: float,
) -> None:
    """Plot before and after reaction OCP traces versus RHE.

    Args:
        ax (plt.Axes): Target axes.
        prerx_trace (EchemTrace | None): Before-reaction OCP trace.
        postrx_trace (EchemTrace | None): After-reaction OCP trace.
        ph (float): Electrolyte pH for RHE conversion.
        ref_offset_v (float): Ag/AgCl reference offset in volts.
    """
    traces = [
        ("Before reaction", prerx_trace, plt.get_cmap("Blues")(0.45)),
        ("After reaction", postrx_trace, plt.get_cmap("Blues")(0.85)),
    ]
    plotted = False
    for label, trace, color in traces:
        if trace is None:
            continue
        potential_rhe = potential_agagcl_3m_to_rhe(
            trace.data["Potential (V)"], ph=ph, ref_offset_v=ref_offset_v
        )
        ax.plot(
            trace.data["Time (s)"],
            potential_rhe,
            linewidth=1.2,
            color=color,
            label=label,
        )
        plotted = True

    ax.set_title("OCP before/after reaction", fontsize=TITLE_FONT_SIZE)
    if not plotted:
        draw_missing(ax, "No reaction OCP files found")
        return

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Potential (V vs RHE)")
    ax.legend(frameon=False, fontsize=SMALL_FONT_SIZE)
