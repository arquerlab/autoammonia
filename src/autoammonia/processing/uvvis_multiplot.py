from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Spectrum:
    """A single UV-Vis spectrum trace."""

    wavenumber_cm_inv: np.ndarray
    absorbance: np.ndarray
    label: str


@dataclass(frozen=True)
class ExperimentSpectra:
    """All spectra for one experiment."""

    experiment_id: int
    date_str: str
    spectra: list[Spectrum]


def wavelength_nm_to_wavenumber_cm_inv(wavelength_nm: np.ndarray) -> np.ndarray:
    """Convert wavelength in nm to wavenumber in cm^-1.

    Args:
        wavelength_nm (np.ndarray): Wavelengths in nm.

    Returns:
        np.ndarray: Wavenumber in cm^-1.
    """
    # 1 nm = 1e-7 cm, so wavenumber (cm^-1) = 1 / (wavelength_cm) = 1e7 / wavelength_nm
    return 1e7 / wavelength_nm


def _safe_numeric(series: pd.Series) -> np.ndarray:
    return pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)


def load_experiment_spectra(
    experiment_id: int,
    folder_uvvis: Path,
    wavelength_nm_min: float = 530.0,
    wavelength_nm_max: float = 850.0,
    use_background_corrected: bool = False,
    smoothing_window: int = 0,
) -> ExperimentSpectra:
    """Load all UV-Vis spectra files for one experiment.

    Args:
        experiment_id (int): Experiment ID (e.g. 85).
        folder_uvvis (Path): Root folder containing UV-Vis CSV files.
        wavelength_nm_min (float, optional): Min wavelength to keep. Defaults to 530.0.
        wavelength_nm_max (float, optional): Max wavelength to keep. Defaults to 850.0.
        use_background_corrected (bool, optional): If True, subtract last absorption value
            as a background offset. Defaults to False.
        smoothing_window (int, optional): If > 1, apply rolling mean smoothing over this
            window size. Defaults to 0 (disabled).

    Returns:
        ExperimentSpectra: All spectra for the experiment.
    """
    files = sorted(folder_uvvis.glob(f"ID{experiment_id}_RXT*_VIAL*"))
    spectra: list[Spectrum] = []
    ctimes: list[float] = []

    for f in files:
        df = pd.read_csv(f)
        if "Wavelength (nm)" not in df.columns or "Absorption" not in df.columns:
            continue

        wl = _safe_numeric(df["Wavelength (nm)"])
        ab = _safe_numeric(df["Absorption"])

        m = np.isfinite(wl) & np.isfinite(ab) & (wl >= wavelength_nm_min) & (wl <= wavelength_nm_max)
        wl = wl[m]
        ab = ab[m]
        if wl.size < 5:
            continue

        if use_background_corrected:
            ab = ab - ab[-1]

        if smoothing_window and smoothing_window > 1:
            ab = (
                pd.Series(ab)
                .rolling(window=int(smoothing_window), min_periods=1, center=True)
                .mean()
                .to_numpy(dtype=float)
            )

        wn = wavelength_nm_to_wavenumber_cm_inv(wl)

        # Sort by wavenumber (ascending) so all plots have consistent left-to-right direction
        idx = np.argsort(wn)
        wn = wn[idx]
        ab = ab[idx]

        spectra.append(Spectrum(wavenumber_cm_inv=wn, absorbance=ab, label=f.name))
        ctimes.append(f.stat().st_ctime)

    date_str = ""
    if ctimes:
        date_str = datetime.fromtimestamp(max(ctimes)).strftime("%Y-%m-%d")

    return ExperimentSpectra(experiment_id=int(experiment_id), date_str=date_str, spectra=spectra)


def plot_uvvis_multiplot(
    experiment_ids: list[int],
    folder_uvvis: Path,
    out_path: Path,
    nrows: int = 4,
    ncols: int = 2,
    wavelength_nm_min: float = 530.0,
    wavelength_nm_max: float = 850.0,
    use_background_corrected: bool = False,
    smoothing_window: int = 0,
) -> Path:
    """Create a 4x2 multiplot of absorbance vs wavenumber.

    - All subplots share the same x/y scale.
    - Only the left column shows y-axis ticks/label.

    Args:
        experiment_ids (list[int]): Exactly 8 IDs recommended for a 4x2 grid.
        folder_uvvis (Path): Folder containing UV-Vis CSV files.
        out_path (Path): Where to save the plot image.
        nrows (int, optional): Rows. Defaults to 4.
        ncols (int, optional): Columns. Defaults to 2.
        wavelength_nm_min (float, optional): Min wavelength to plot. Defaults to 530.0.
        wavelength_nm_max (float, optional): Max wavelength to plot. Defaults to 850.0.
        use_background_corrected (bool, optional): Whether to background-correct absorbance.
            Defaults to False.
        smoothing_window (int, optional): Rolling mean window. Defaults to 0.

    Returns:
        Path: Saved path.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    experiments = [
        load_experiment_spectra(
            experiment_id=eid,
            folder_uvvis=folder_uvvis,
            wavelength_nm_min=wavelength_nm_min,
            wavelength_nm_max=wavelength_nm_max,
            use_background_corrected=use_background_corrected,
            smoothing_window=smoothing_window,
        )
        for eid in experiment_ids
    ]

    # Consistent "Blues" scale across all subplots: map trace index -> blue shade.
    max_traces = max((len(e.spectra) for e in experiments), default=1)
    cmap = plt.get_cmap("Blues")
    color_positions = (
        np.linspace(0.9, 0.35, max_traces) if max_traces > 1 else np.array([0.7])
    )

    # Compute global limits across all traces
    all_x = []
    all_y = []
    for e in experiments:
        for s in e.spectra:
            all_x.append(s.wavenumber_cm_inv)
            all_y.append(s.absorbance)

    if not all_x:
        raise FileNotFoundError("No UV-Vis spectra found for the requested experiment IDs")

    x_min = float(np.nanmin(np.concatenate(all_x)))
    x_max = float(np.nanmax(np.concatenate(all_x)))
    y_min = float(np.nanmin(np.concatenate(all_y)))
    y_max = float(np.nanmax(np.concatenate(all_y)))

    fig, axes = plt.subplots(
        nrows=nrows,
        ncols=ncols,
        sharex=True,
        sharey=True,
        figsize=(6, 12),
        constrained_layout=True,
    )
    axes = np.array(axes).reshape(nrows, ncols)

    for k, e in enumerate(experiments):
        r = k // ncols
        c = k % ncols
        if r >= nrows:
            break
        ax = axes[r, c]

        for j, s in enumerate(e.spectra):
            ax.plot(
                s.wavenumber_cm_inv,
                s.absorbance,
                linewidth=1.0,
                alpha=0.9,
                color=cmap(color_positions[min(j, max_traces - 1)]),
            )

        title = f"ID{e.experiment_id}"
        if e.date_str:
            title += f"  ({e.date_str})"
        ax.set_title(title, fontsize=10)
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(-2, 2)
        ax.grid(True, alpha=0.2)

        # Only left column shows y-axis
        if c != 0:
            ax.set_ylabel("")
            ax.tick_params(axis="y", which="both", left=False, labelleft=False)

        # Only bottom row shows x-axis label
        if r != nrows - 1:
            ax.set_xlabel("")
            ax.tick_params(axis="x", which="both", labelbottom=False)

    # Shared labels (left and bottom only)
    axes[-1, 0].set_xlabel(r"Wavenumber (cm$^{-1}$)")
    axes[-1, 1].set_xlabel(r"Wavenumber (cm$^{-1}$)")
    axes[0, 0].set_ylabel("Absorbance (a.u.)")
    axes[1, 0].set_ylabel("Absorbance (a.u.)")
    axes[2, 0].set_ylabel("Absorbance (a.u.)")
    axes[3, 0].set_ylabel("Absorbance (a.u.)")

    fig.suptitle("UV-Vis spectra (absorbance vs wavenumber)", fontsize=12)
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    return out_path


if __name__ == "__main__":
    folder = Path(r"C:\Users\LAB-CO2MAP\ammonia_data\uvvis")
    out_dir = Path(r"C:\Users\LAB-CO2MAP\ammonia_data\process")

    # Default 8 experiments for a 4x2 grid.
    experiment_ids = list(range(79, 87))
    out_file = out_dir / f"uvvis_multiplot_{min(experiment_ids)}_{max(experiment_ids)}.png"

    saved = plot_uvvis_multiplot(
        experiment_ids=experiment_ids,
        folder_uvvis=folder,
        out_path=out_file,
        nrows=4,
        ncols=2,
        wavelength_nm_min=530.0,
        wavelength_nm_max=850.0,
        use_background_corrected=False,
        smoothing_window=0,
    )
    print(f"Saved plot: {saved}")

