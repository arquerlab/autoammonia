from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from autoammonia.processing.plot_style import SMALL_FONT_SIZE, TITLE_FONT_SIZE, draw_missing, style_table


def plot_absorbance_spectra(
    ax: plt.Axes,
    spectra: list[tuple[str, pd.DataFrame]],
    *,
    xlabel: str = "Wavelength (nm)",
    ylabel: str = "Abs_zero (a.u.)",
    legend_loc: str = "center right",
    linewidth: float = 1.2,
    cmap_name: str = "Blues",
) -> None:
    """Plot background-corrected UV-Vis spectra on one axes.

    Args:
        ax (plt.Axes): Target axes.
        spectra (list[tuple[str, pd.DataFrame]]): Spectrum labels and dataframes.
        xlabel (str, optional): X-axis label.
        ylabel (str, optional): Y-axis label.
        legend_loc (str, optional): Legend location.
        linewidth (float, optional): Line width.
        cmap_name (str, optional): Matplotlib colormap name.
    """
    if not spectra:
        draw_missing(ax, "No UV-Vis files found")
        return

    cmap = plt.get_cmap(cmap_name)
    colors = np.linspace(0.35, 0.9, len(spectra))
    for color_position, (label, df) in zip(colors, spectra):
        ax.plot(
            df["Wavelength (nm)"],
            df["Abs_zero"],
            linewidth=linewidth,
            color=cmap(color_position),
            label=label,
        )
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.legend(frameon=False, fontsize=SMALL_FONT_SIZE, loc=legend_loc)


def plot_fe_table_inset(
    ax: plt.Axes,
    fe_rows: list[list[str]],
    *,
    bbox: list[float] | tuple[float, float, float, float] = (0.58, 0.64, 0.40, 0.34),
    font_size: int = SMALL_FONT_SIZE,
) -> None:
    """Add an interval FE table inset to an axes.

    Args:
        ax (plt.Axes): Target axes.
        fe_rows (list[list[str]]): FE table rows.
        bbox (list[float] | tuple[float, float, float, float], optional): Table bounding box.
        font_size (int, optional): Table font size.
    """
    table = ax.table(
        cellText=fe_rows,
        colLabels=["t (s)", r"$\Delta$Abs", "FE (%)"],
        loc="upper right",
        bbox=bbox,
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(font_size)
    style_table(table, header_rows=1)


def plot_absorbance_with_fe(
    ax: plt.Axes,
    spectra: list[tuple[str, pd.DataFrame]],
    fe_rows: list[list[str]],
    experiment_id: int,
    *,
    wavelength_min_nm: float = 500.0,
    wavelength_max_nm: float = 850.0,
) -> None:
    """Plot UV-Vis absorbance with an interval FE inset table.

    Args:
        ax (plt.Axes): Target axes.
        spectra (list[tuple[str, pd.DataFrame]]): Loaded spectra.
        fe_rows (list[list[str]]): FE table rows.
        experiment_id (int): Experiment ID.
        wavelength_min_nm (float, optional): X-axis minimum in nm. Defaults to 500.0.
        wavelength_max_nm (float, optional): X-axis maximum in nm. Defaults to 850.0.
    """
    plot_absorbance_spectra(ax, spectra)
    ax.set_title(f"ID{experiment_id} UV-Vis absorbance", fontsize=TITLE_FONT_SIZE)
    if spectra:
        ax.set_xlim(wavelength_min_nm, wavelength_max_nm)
        plot_fe_table_inset(ax, fe_rows)


def plot_absorbance_publication_panel(
    ax: plt.Axes,
    experiment_id: int,
    spectra: list[tuple[str, pd.DataFrame]],
    fe_rows: list[list[str]],
    *,
    min_wavelength_nm: float,
    peak_min_nm: float,
    peak_max_nm: float,
    peak_band_color: str = "#dbccccff",
    cmap_name: str = "absorbance_green",
    title_font_size: int = TITLE_FONT_SIZE,
    legend_font_size: int = SMALL_FONT_SIZE,
) -> None:
    """Plot a publication-style absorbance panel with peak band and FE inset.

    Args:
        ax (plt.Axes): Target axes.
        experiment_id (int): Experiment ID.
        spectra (list[tuple[str, pd.DataFrame]]): Loaded spectra.
        fe_rows (list[list[str]]): FE table rows.
        min_wavelength_nm (float): Minimum wavelength shown in nm.
        peak_min_nm (float): Peak band minimum wavelength in nm.
        peak_max_nm (float): Peak band maximum wavelength in nm.
        peak_band_color (str, optional): Peak band fill color.
        cmap_name (str, optional): Colormap name or registered custom name.
        title_font_size (int, optional): Title font size.
        legend_font_size (int, optional): Legend font size.
    """
    if not spectra:
        draw_missing(ax, f"No data for ID{experiment_id}")
        return

    if cmap_name == "absorbance_green":
        from matplotlib.colors import LinearSegmentedColormap

        cmap = LinearSegmentedColormap.from_list(
            "absorbance_green",
            ["#d7eadfff", "#2f7f73ff"],
        )
    else:
        cmap = plt.get_cmap(cmap_name)

    colors = np.linspace(0.0, 1.0, len(spectra))
    max_absorbance = 0.0
    for color_position, (label, df) in zip(colors, spectra):
        df_plot = df[df["Wavelength (nm)"] >= float(min_wavelength_nm)].copy()
        if df_plot.empty:
            continue
        max_absorbance = max(max_absorbance, float(df_plot["Abs_zero"].max()))
        ax.plot(
            df_plot["Wavelength (nm)"],
            df_plot["Abs_zero"],
            linewidth=1.0,
            color=cmap(color_position),
            label=label,
        )

    ax.axvspan(peak_min_nm, peak_max_nm, color=peak_band_color, alpha=0.35, linewidth=0)
    ax.set_title(f"ID{experiment_id} absorbance", fontsize=title_font_size)
    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Absorbance (a.u.)")
    ax.set_xlim(left=float(min_wavelength_nm))
    if max_absorbance > 0.0:
        ax.set_ylim(top=max_absorbance * 1.10)
    ax.legend(frameon=False, loc="upper left", fontsize=legend_font_size)
    plot_fe_table_inset(
        ax,
        fe_rows,
        bbox=(0.58, 0.64, 0.39, 0.30),
        font_size=6,
    )
