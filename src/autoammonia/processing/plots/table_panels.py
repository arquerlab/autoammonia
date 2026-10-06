from __future__ import annotations

import matplotlib.pyplot as plt

from autoammonia.processing.plot_style import SMALL_FONT_SIZE, draw_table_panel


def plot_composition_table(
    ax: plt.Axes,
    experiment_id: int,
    catalyst_text: str,
    electrolyte_text: str,
) -> None:
    """Draw catalyst and electrolyte composition rows.

    Args:
        ax (plt.Axes): Target axes.
        experiment_id (int): Experiment ID.
        catalyst_text (str): Formatted catalyst composition.
        electrolyte_text (str): Formatted electrolyte composition.
    """
    rows = [
        ["Catalyst composition", catalyst_text],
        ["Electrolyte composition", electrolyte_text],
    ]
    draw_table_panel(
        ax,
        f"ID{experiment_id} compositions",
        rows,
        column_labels=["Item", "Composition"],
        font_size=SMALL_FONT_SIZE,
    )


def plot_metrics_table(
    ax: plt.Axes,
    experiment_id: int,
    metric_rows: list[list[str]],
) -> None:
    """Draw LSV and double-layer capacitance metric rows.

    Args:
        ax (plt.Axes): Target axes.
        experiment_id (int): Experiment ID.
        metric_rows (list[list[str]]): Metric table rows.
    """
    draw_table_panel(
        ax,
        f"ID{experiment_id} metrics",
        metric_rows,
        column_labels=["Metric", "Unit", "Before", "After"],
        font_size=SMALL_FONT_SIZE,
        column_widths=[0.46, 0.12, 0.21, 0.21],
    )
