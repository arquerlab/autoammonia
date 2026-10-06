from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd

from autoammonia.processing.echem_traces import load_uvvis_spectra
from autoammonia.processing.fe import build_fe_interval_breakdowns, format_fe_table_rows
from autoammonia.processing.plots.uvvis_panels import plot_absorbance_publication_panel
from autoammonia.processing.processing_config import get_processing_config


DEFAULT_EXPERIMENT_ID = 122
DEFAULT_PLOT_MIN_WAVELENGTH_NM = 500.0
FIGURE_WIDTH_MM = 210.0
FIGURE_HEIGHT_MM = 70.0
MM_PER_INCH = 25.4
ABSORBANCE_PALETTE_START = "#d7eadfff"
ABSORBANCE_PALETTE_END = "#2f7f73ff"
ACCENT_BLUE_GREY = "#adc4ceff"
ACCENT_BLUE = "#7ba4d9ff"
ACCENT_RED = "#d97878ff"
ACCENT_PINK = "#dbccccff"
CALIBRATION_SPECTRA_COLORS = [
    "#d7eadfff",
    "#b7d8c6ff",
    "#98c3a6ff",
    "#70ad97ff",
    "#4b968aff",
    "#2f7f73ff",
    "#155f66ff",
]


def configure_arial_fonts() -> None:
    """Configure Matplotlib to use Arial fonts throughout the figure."""
    plt.rcParams.update(
        {
            "font.family": "Arial",
            "font.sans-serif": ["Arial"],
            "mathtext.fontset": "custom",
            "mathtext.rm": "Arial",
            "mathtext.it": "Arial:italic",
            "mathtext.bf": "Arial:bold",
            "axes.labelsize": 8,
            "axes.titlesize": 9,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 6,
        }
    )


def mm_to_inches(value_mm: float) -> float:
    """Convert millimeters to inches.

    Args:
        value_mm (float): Length in millimeters.

    Returns:
        float: Length in inches.
    """
    return value_mm / MM_PER_INCH


def absorbance_colormap() -> LinearSegmentedColormap:
    """Return the shared green absorbance colormap.

    Returns:
        LinearSegmentedColormap: Colormap from light green to darker green.
    """
    return LinearSegmentedColormap.from_list(
        "absorbance_green",
        [ABSORBANCE_PALETTE_START, ABSORBANCE_PALETTE_END],
    )


def add_empty_panel(ax: plt.Axes) -> None:
    """Leave an axis intentionally empty.

    Args:
        ax (plt.Axes): Axis to clear.
    """
    ax.axis("off")


def add_panel_label(ax: plt.Axes, label: str) -> None:
    """Add a bold panel label to an axis.

    Args:
        ax (plt.Axes): Axis where the label is added.
        label (str): Panel label text.
    """
    ax.text(
        -0.14,
        1.08,
        label,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=10,
        fontweight="bold",
        family="Arial",
    )


def plot_calibration_spectra_panel(
    ax: plt.Axes,
    calibration_spectra_path: Path,
    min_wavelength_nm: float,
) -> None:
    """Plot calibration spectra in the first figure panel.

    Args:
        ax (plt.Axes): Axis where calibration spectra are drawn.
        calibration_spectra_path (Path): CSV with `wl` and concentration spectra columns.
        min_wavelength_nm (float): Minimum wavelength shown in nm.
    """
    df = pd.read_csv(calibration_spectra_path)
    wavelength_nm = pd.to_numeric(df["wl"], errors="coerce")
    spectra = sorted(
        [(column, float(column)) for column in df.columns if column != "wl"],
        key=lambda item: item[1],
    )
    colors = CALIBRATION_SPECTRA_COLORS
    if len(spectra) > len(colors):
        cmap = absorbance_colormap()
        colors = [cmap(position) for position in np.linspace(0.0, 1.0, len(spectra))]

    for color, (column, concentration) in zip(colors, spectra):
        absorbance = pd.to_numeric(df[column], errors="coerce")
        mask = wavelength_nm >= float(min_wavelength_nm)
        ax.plot(
            wavelength_nm[mask],
            absorbance[mask],
            linewidth=1.15,
            color=color,
            label=f"{concentration:g} mg/L",
        )

    ax.set_title("Calibration spectra")
    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Absorbance (a.u.)")
    ax.set_xlim(left=float(min_wavelength_nm), right=850.0)
    ax.legend(frameon=False, fontsize=5, loc="upper right", title="N")


def plot_calibration_curve_panel(ax: plt.Axes, calibration_plot_path: Path) -> None:
    """Plot calibration points, fit, equation, and R squared.

    Args:
        ax (plt.Axes): Axis where the calibration curve is drawn.
        calibration_plot_path (Path): CSV with `NH3 conc`, `Abs`, and `Abs fit` columns.
    """
    df = pd.read_csv(calibration_plot_path)
    df["NH3 conc"] = pd.to_numeric(df["NH3 conc"], errors="coerce")
    df["Abs"] = pd.to_numeric(df["Abs"], errors="coerce")
    df["Abs fit"] = pd.to_numeric(df["Abs fit"], errors="coerce")
    df = df.dropna(subset=["NH3 conc", "Abs", "Abs fit"]).sort_values("NH3 conc")

    concentration = df["NH3 conc"].to_numpy(dtype=float)
    absorbance = df["Abs"].to_numpy(dtype=float)
    absorbance_fit = df["Abs fit"].to_numpy(dtype=float)
    slope, intercept = np.polyfit(concentration, absorbance_fit, deg=1)
    residual_sum_squares = float(np.sum((absorbance - absorbance_fit) ** 2))
    total_sum_squares = float(np.sum((absorbance - np.mean(absorbance)) ** 2))
    r_squared = 1.0 - residual_sum_squares / total_sum_squares

    ax.scatter(
        concentration,
        absorbance,
        s=18,
        color=ACCENT_BLUE,
        edgecolor="white",
        linewidth=0.4,
        label="Abs",
        zorder=3,
    )
    ax.plot(
        concentration,
        absorbance_fit,
        color=ACCENT_RED,
        linestyle="--",
        linewidth=1.1,
        label="Abs fit",
    )
    ax.text(
        0.05,
        0.95,
        f"Abs = {slope:.4f} C + {intercept:.4f}\n$R^2$ = {r_squared:.4f}",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=7,
        family="Arial",
    )
    ax.set_title("Calibration curve")
    ax.set_xlabel("N concentration (mg/L)")
    ax.set_ylabel("Absorbance (a.u.)")
    ax.legend(frameon=False, loc="lower right")


def plot_absorbance_panel(
    ax: plt.Axes,
    experiment_id: int,
    folder_uvvis: Path,
    folder_electrosynthesis: Path,
    min_wavelength_nm: float,
) -> None:
    """Plot absorbance spectra and an FE table for one experiment.

    Args:
        ax (plt.Axes): Axis where the absorbance plot is drawn.
        experiment_id (int): Experiment ID.
        folder_uvvis (Path): Folder containing UV-Vis CSV files.
        folder_electrosynthesis (Path): Folder containing electrosynthesis CSV files.
        min_wavelength_nm (float): Minimum wavelength shown in nm.
    """
    config = get_processing_config()
    spectra = load_uvvis_spectra(
        experiment_id,
        folder_uvvis,
        wavelength_min_nm=min_wavelength_nm,
        wavelength_max_nm=850.0,
    )
    fe_rows = format_fe_table_rows(
        build_fe_interval_breakdowns(
            experiment_id,
            folder_uvvis,
            folder_electrosynthesis,
            config=config,
        )
    )
    plot_absorbance_publication_panel(
        ax,
        experiment_id,
        spectra,
        fe_rows,
        min_wavelength_nm=min_wavelength_nm,
        peak_min_nm=config.absorbance_peak_min_nm,
        peak_max_nm=config.absorbance_peak_max_nm,
        title_font_size=9,
        legend_font_size=6,
    )


def create_figure(
    experiment_id: int,
    folder_uvvis: Path,
    folder_electrosynthesis: Path,
    calibration_spectra_path: Path,
    calibration_plot_path: Path,
    out_dir: Path,
    min_wavelength_nm: float = DEFAULT_PLOT_MIN_WAVELENGTH_NM,
) -> tuple[Path, Path]:
    """Create a 1x3 figure with the absorbance panel in column 3.

    Args:
        experiment_id (int): Experiment ID.
        folder_uvvis (Path): Folder containing UV-Vis CSV files.
        folder_electrosynthesis (Path): Folder containing electrosynthesis CSV files.
        calibration_spectra_path (Path): Calibration spectra CSV path.
        calibration_plot_path (Path): Calibration curve CSV path.
        out_dir (Path): Output folder.
        min_wavelength_nm (float, optional): Minimum wavelength shown in nm. Defaults to
            DEFAULT_PLOT_MIN_WAVELENGTH_NM.

    Returns:
        tuple[Path, Path]: Saved PNG and SVG figure paths.
    """
    configure_arial_fonts()
    out_dir.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(
        1,
        3,
        figsize=(mm_to_inches(FIGURE_WIDTH_MM), mm_to_inches(FIGURE_HEIGHT_MM)),
        constrained_layout=True,
    )
    plot_calibration_spectra_panel(
        ax=axes[0],
        calibration_spectra_path=calibration_spectra_path,
        min_wavelength_nm=min_wavelength_nm,
    )
    add_panel_label(axes[0], "a")
    plot_calibration_curve_panel(
        ax=axes[1],
        calibration_plot_path=calibration_plot_path,
    )
    add_panel_label(axes[1], "b")
    plot_absorbance_panel(
        ax=axes[2],
        experiment_id=experiment_id,
        folder_uvvis=folder_uvvis,
        folder_electrosynthesis=folder_electrosynthesis,
        min_wavelength_nm=min_wavelength_nm,
    )
    add_panel_label(axes[2], "c")

    png_path = out_dir / f"ID{experiment_id}_fe_absorbance_1x3.png"
    svg_path = out_dir / f"ID{experiment_id}_fe_absorbance_1x3.svg"
    fig.savefig(png_path, dpi=300)
    fig.savefig(svg_path, dpi=300)
    plt.close(fig)
    return png_path, svg_path


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Create a 210 mm wide 1x3 FE figure with one absorbance panel."
    )
    parser.add_argument(
        "--experiment-id",
        type=int,
        default=DEFAULT_EXPERIMENT_ID,
        help="Experiment ID to plot. Defaults to 122.",
    )
    parser.add_argument(
        "--uvvis-folder",
        type=Path,
        required=True,
        help="Folder containing UV-Vis CSV files.",
    )
    parser.add_argument(
        "--electrosynthesis-folder",
        type=Path,
        required=True,
        help="Folder containing electrosynthesis CSV files.",
    )
    parser.add_argument(
        "--calibration-spectra",
        type=Path,
        required=True,
        help="Calibration spectra CSV path.",
    )
    parser.add_argument(
        "--calibration-plot",
        type=Path,
        required=True,
        help="Calibration curve CSV path.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Folder where the figure is saved.",
    )
    parser.add_argument(
        "--min-wavelength-nm",
        type=float,
        default=DEFAULT_PLOT_MIN_WAVELENGTH_NM,
        help="Minimum wavelength shown in the absorbance plot.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    saved_png_path, saved_svg_path = create_figure(
        experiment_id=args.experiment_id,
        folder_uvvis=args.uvvis_folder,
        folder_electrosynthesis=args.electrosynthesis_folder,
        calibration_spectra_path=args.calibration_spectra,
        calibration_plot_path=args.calibration_plot,
        out_dir=args.out_dir,
        min_wavelength_nm=args.min_wavelength_nm,
    )
    print(f"Saved 1x3 FE figure PNG: {saved_png_path}")
    print(f"Saved 1x3 FE figure SVG: {saved_svg_path}")
