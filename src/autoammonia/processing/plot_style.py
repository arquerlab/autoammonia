from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np


FONT_FAMILY = "Arial"
BASE_FONT_SIZE = 16
TITLE_FONT_SIZE = 19
SMALL_FONT_SIZE = 14
AXIS_LABEL_FONT_SIZE = 18
TICK_FONT_SIZE = 16


def configure_summary_fonts() -> None:
    """Configure matplotlib defaults for summary figures."""
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


def format_value(value: float | None, precision: int = 3) -> str:
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


def draw_missing(ax: plt.Axes, message: str) -> None:
    """Draw a centered missing-data message on an axes.

    Args:
        ax (plt.Axes): Target axes.
        message (str): Message to show.
    """
    ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)


def safe_plot_panel(
    ax: plt.Axes,
    title: str,
    missing_message: str,
    function,
    *args,
    **kwargs,
) -> None:
    """Render a panel and replace failures with a missing-data message.

    Args:
        ax (plt.Axes): Target axes.
        title (str): Title to keep if rendering fails.
        missing_message (str): Message to show if rendering fails.
        function: Plotting callable to execute.
        *args: Positional arguments for the callable.
        **kwargs: Keyword arguments for the callable.
    """
    try:
        function(ax, *args, **kwargs)
    except Exception as exc:
        print(f"Skipping {title}: {exc}")
        ax.clear()
        ax.set_title(title, fontsize=TITLE_FONT_SIZE)
        draw_missing(ax, missing_message)


def safe_result(default_value, description: str, function, *args, **kwargs):
    """Run a data-loading step and return a default value if it fails.

    Args:
        default_value: Value returned if the function raises.
        description (str): Short description printed with the skip message.
        function: Callable to execute.
        *args: Positional arguments for the callable.
        **kwargs: Keyword arguments for the callable.

    Returns:
        Any: Callable result, or the default value on failure.
    """
    try:
        return function(*args, **kwargs)
    except Exception as exc:
        print(f"Skipping {description}: {exc}")
        return default_value


def style_table(
    table: plt.Table,
    header_rows: int = 1,
    header_color: str = "#1f4e79",
    body_color: str = "#f7fbff",
    alternate_body_color: str = "#eaf2fb",
    edge_color: str = "white",
) -> None:
    """Apply shared formatting to matplotlib tables.

    Args:
        table (plt.Table): Table artist to format.
        header_rows (int, optional): Number of header rows. Defaults to 1.
        header_color (str, optional): Header background color.
        body_color (str, optional): Body background color.
        alternate_body_color (str, optional): Alternating body row color.
        edge_color (str, optional): Cell edge color.
    """
    for (row, column), cell in table.get_celld().items():
        cell.set_edgecolor(edge_color)
        cell.set_linewidth(1.4)
        cell.PAD = 0.10
        if row < header_rows:
            cell.set_facecolor(header_color)
        else:
            cell.set_facecolor(body_color if row % 2 else alternate_body_color)
        text = cell.get_text()
        text.set_fontfamily(FONT_FAMILY)
        if row < header_rows:
            text.set_weight("bold")
            text.set_color("white")
            text.set_ha("center")
        elif column == 0:
            text.set_weight("bold")
            text.set_ha("left")
        else:
            text.set_ha("center")


def draw_table_panel(
    ax: plt.Axes,
    title: str,
    rows: list[list[str]],
    column_labels: list[str] | None = None,
    font_size: int = BASE_FONT_SIZE,
    column_widths: list[float] | None = None,
) -> None:
    """Draw a table-only panel.

    Args:
        ax (plt.Axes): Target axes.
        title (str): Panel title.
        rows (list[list[str]]): Table rows.
        column_labels (list[str] | None, optional): Optional column labels.
        font_size (int, optional): Table font size.
        column_widths (list[float] | None, optional): Relative column widths.
    """
    ax.axis("off")
    ax.set_title(title, fontsize=TITLE_FONT_SIZE)
    table = ax.table(
        cellText=rows,
        colLabels=column_labels,
        bbox=[0.01, 0.12, 0.98, 0.76],
        cellLoc="left",
        colLoc="left",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(font_size)
    if column_widths is not None:
        for (row, column), cell in table.get_celld().items():
            if column < len(column_widths):
                cell.set_width(column_widths[column])
    table.scale(1.1, 2.2)
    style_table(table, header_rows=1 if column_labels is not None else 0)
