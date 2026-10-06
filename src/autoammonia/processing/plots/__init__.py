"""Matplotlib panel modules for experiment summary figures."""

from autoammonia.processing.plots.echem_panels import plot_lsv_panel, plot_ocp_overlay_panel
from autoammonia.processing.plots.protocol_panels import plot_cp_panel, plot_reaction_trace_panel
from autoammonia.processing.plots.table_panels import plot_composition_table, plot_metrics_table
from autoammonia.processing.plots.uvvis_panels import plot_absorbance_with_fe

__all__ = [
    "plot_absorbance_with_fe",
    "plot_composition_table",
    "plot_cp_panel",
    "plot_lsv_panel",
    "plot_metrics_table",
    "plot_ocp_overlay_panel",
    "plot_reaction_trace_panel",
]
