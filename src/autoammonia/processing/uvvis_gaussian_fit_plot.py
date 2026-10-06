from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit


def gaussian(x: np.ndarray, a: float, b: float, c: float, d: float) -> np.ndarray:
    """Gaussian peak model with baseline.

    Args:
        x (np.ndarray): X values (wavelength in nm).
        a (float): Amplitude.
        b (float): Center (nm).
        c (float): Standard deviation (nm).
        d (float): Baseline offset.

    Returns:
        np.ndarray: Modeled y values.
    """
    return a * np.exp(-((x - b) ** 2) / (2 * c**2)) + d


@dataclass(frozen=True)
class FitResult:
    """Gaussian fit result for one spectrum."""

    amplitude: float
    center_nm: float
    sigma_nm: float
    baseline: float


def get_gaussian_amplitude(
    df_uv: pd.DataFrame,
    wl_min_nm: float = 550.0,
    wl_max_nm: float = 800.0,
    amp_init_min_nm: float = 635.0,
    amp_init_max_nm: float = 670.0,
    center_min_nm: float = 645.0,
    center_max_nm: float = 660.0,
    spike_abs_limit: float = 1.5,
    exclude_region_min_nm: float = 610.0,
    exclude_region_max_nm: float = 705.0,
) -> float:
    """Return fitted Gaussian amplitude for a UV-Vis dataframe.

    This wraps the current project fitting rules:
    - Background-correct raw absorbance (`Abs_zero`).
    - Fit over a broad range (default 550–800 nm).
    - Constrain center to 645–660 nm.
    - If spikes are detected inside 610–705 nm (|Abs_zero| > 1.5), exclude 610–705 nm from fitting.

    Args:
        df_uv (pd.DataFrame): UV-Vis dataframe containing `Wavelength (nm)` and `Absorption`.
        wl_min_nm (float, optional): Min wavelength used for fitting. Defaults to 550.0.
        wl_max_nm (float, optional): Max wavelength used for fitting. Defaults to 800.0.
        amp_init_min_nm (float, optional): Min wavelength for initial amplitude estimate.
            Defaults to 635.0.
        amp_init_max_nm (float, optional): Max wavelength for initial amplitude estimate.
            Defaults to 670.0.
        center_min_nm (float, optional): Minimum allowed Gaussian center (nm). Defaults to 645.0.
        center_max_nm (float, optional): Maximum allowed Gaussian center (nm). Defaults to 660.0.
        spike_abs_limit (float, optional): Spike threshold for triggering region exclusion.
            Defaults to 1.5.
        exclude_region_min_nm (float, optional): Region exclusion min wavelength. Defaults to 610.0.
        exclude_region_max_nm (float, optional): Region exclusion max wavelength. Defaults to 705.0.

    Returns:
        float: Fitted amplitude. Returns NaN if fitting fails.
    """
    try:
        df = get_abs_zero(df_uv)
        fit = fit_peak_gaussian(
            df,
            wl_min_nm=wl_min_nm,
            wl_max_nm=wl_max_nm,
            amp_init_min_nm=amp_init_min_nm,
            amp_init_max_nm=amp_init_max_nm,
            center_min_nm=center_min_nm,
            center_max_nm=center_max_nm,
            spike_abs_limit=spike_abs_limit,
            exclude_region_min_nm=exclude_region_min_nm,
            exclude_region_max_nm=exclude_region_max_nm,
        )
        amp = float(fit.amplitude)
        return amp if np.isfinite(amp) else float("nan")
    except Exception:
        return float("nan")


def get_abs_zero(df_uv: pd.DataFrame) -> pd.DataFrame:
    """Compute background-corrected absorbance (no smoothing).

    Args:
        df_uv (pd.DataFrame): UV-Vis dataframe with `Absorption`.

    Returns:
        pd.DataFrame: Copy with `Abs_zero`.
    """
    df = df_uv.copy()
    df["Abs_zero"] = df["Absorption"] - df["Absorption"].iloc[-1]
    return df


def fit_peak_gaussian(
    df_uv: pd.DataFrame,
    wl_min_nm: float = 550.0,
    wl_max_nm: float = 800.0,
    amp_init_min_nm: float = 635.0,
    amp_init_max_nm: float = 670.0,
    center_min_nm: float = 645.0,
    center_max_nm: float = 660.0,
    spike_abs_limit: float = 1.5,
    exclude_region_min_nm: float = 610.0,
    exclude_region_max_nm: float = 705.0,
) -> FitResult:
    """Fit a Gaussian peak over a broad wavelength range.

    Args:
        df_uv (pd.DataFrame): UV-Vis dataframe containing `Wavelength (nm)` and `Abs_zero`.
        wl_min_nm (float, optional): Min wavelength used for fitting. Defaults to 450.0.
        wl_max_nm (float, optional): Max wavelength used for fitting. Defaults to 850.0.
        amp_init_min_nm (float, optional): Min wavelength for initial amplitude estimate
            (mean Abs_zero in this band). Defaults to 635.0.
        amp_init_max_nm (float, optional): Max wavelength for initial amplitude estimate.
            Defaults to 670.0.
        center_min_nm (float, optional): Minimum allowed Gaussian center (nm). Defaults to 645.0.
        center_max_nm (float, optional): Maximum allowed Gaussian center (nm). Defaults to 660.0.
        spike_abs_limit (float, optional): Drop only points where `Abs_zero` spikes beyond
            `[-spike_abs_limit, spike_abs_limit]`. Defaults to 1.5.
        exclude_region_min_nm (float, optional): Min wavelength of a region to exclude from fitting
            only if spikes are detected within that region. Defaults to 610.0.
        exclude_region_max_nm (float, optional): Max wavelength of a region to exclude from fitting
            only if spikes are detected within that region. Defaults to 705.0.

    Returns:
        FitResult: Fitted parameters.
    """
    clean = df_uv.loc[
        df_uv["Wavelength (nm)"].between(wl_min_nm, wl_max_nm),
        ["Wavelength (nm)", "Abs_zero"],
    ].copy()
    clean = clean.replace([np.inf, -np.inf], np.nan).dropna()

    # If there are spikes inside 610–705 nm, exclude that whole region from fitting.
    if (
        np.isfinite(spike_abs_limit)
        and spike_abs_limit > 0
        and np.isfinite(exclude_region_min_nm)
        and np.isfinite(exclude_region_max_nm)
        and exclude_region_max_nm > exclude_region_min_nm
    ):
        region = clean.loc[
            clean["Wavelength (nm)"].between(exclude_region_min_nm, exclude_region_max_nm)
        ]
        has_spikes = (~region["Abs_zero"].between(-spike_abs_limit, spike_abs_limit)).any()
        if bool(has_spikes):
            clean = clean.loc[
                ~clean["Wavelength (nm)"].between(exclude_region_min_nm, exclude_region_max_nm)
            ].copy()

    x = clean["Wavelength (nm)"].to_numpy(dtype=float)
    y = clean["Abs_zero"].to_numpy(dtype=float)
    if len(x) < 6:
        raise ValueError("Not enough points for Gaussian fit")

    amp_band = df_uv.loc[
        df_uv["Wavelength (nm)"].between(amp_init_min_nm, amp_init_max_nm),
        "Abs_zero",
    ]
    a0 = float(pd.to_numeric(amp_band, errors="coerce").dropna().mean())
    if not np.isfinite(a0):
        a0 = float(np.nanmax(y))

    b0 = float(np.clip(652.0, center_min_nm, center_max_nm))
    d0 = float(np.nanmin(y))
    p0 = [a0, b0, 20.0, d0]

    # Bounds: constrain center, keep sigma positive.
    lower = [0, center_min_nm, 0.5, 0]
    upper = [np.inf, center_max_nm, 80.0, 1e-9]
    popt, _ = curve_fit(gaussian, x, y, p0=p0, bounds=(lower, upper), maxfev=10000)
    return FitResult(
        amplitude=float(popt[0]),
        center_nm=float(popt[1]),
        sigma_nm=float(popt[2]),
        baseline=float(popt[3]),
    )


def plot_filtered_and_fit(
    df_uv: pd.DataFrame,
    fit: FitResult,
    out_path: Path,
    wl_min_nm: float = 450.0,
    wl_max_nm: float = 850.0,
) -> Path:
    """Plot Abs_zero and fitted Gaussian overlay.

    Args:
        df_uv (pd.DataFrame): Dataframe with `Wavelength (nm)` and `Abs_zero`.
        fit (FitResult): Fit parameters.
        out_path (Path): PNG path to save.
        wl_min_nm (float, optional): Min x for plotting. Defaults to 450.0.
        wl_max_nm (float, optional): Max x for plotting. Defaults to 850.0.

    Returns:
        Path: Saved plot path.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df = df_uv.copy()
    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=["Wavelength (nm)", "Abs_zero"])
    x_all = df["Wavelength (nm)"].to_numpy(dtype=float)
    y_all = df["Abs_zero"].to_numpy(dtype=float)

    x_fit = np.linspace(wl_min_nm, wl_max_nm, 400)
    y_fit = gaussian(x_fit, fit.amplitude, fit.center_nm, fit.sigma_nm, fit.baseline)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(x_all, y_all, linewidth=1.0, label="Abs_zero")
    ax.plot(x_fit, y_fit, linewidth=2.0, label=f"Gaussian fit (A={fit.amplitude:.4f})")
    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Absorbance (a.u.)")
    ax.set_title("Abs_zero with Gaussian fit")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    return out_path


def run_for_experiment(
    experiment_id: int,
    folder_uvvis: Path,
    out_dir: Path,
) -> None:
    """Generate fit-overlay plots for all UV-Vis files of one experiment.

    Args:
        experiment_id (int): Experiment ID (e.g. 85).
        folder_uvvis (Path): Folder containing UV-Vis CSVs.
        out_dir (Path): Output directory for PNGs.
    """
    files = sorted(folder_uvvis.glob(f"ID{experiment_id}_RXT*_VIAL*"))
    if not files:
        raise FileNotFoundError(f"No UV-Vis files found for ID{experiment_id} in {folder_uvvis}")

    for f in files:
        df = pd.read_csv(f)
        df = get_abs_zero(df)
        try:
            fit = fit_peak_gaussian(df)
        except Exception:
            continue

        out_path = out_dir / f"{f.stem}_gaussian_fit.png"
        plot_filtered_and_fit(df, fit, out_path=out_path)
        print(f"{f.name}: amplitude={fit.amplitude:.6f}  saved={out_path}")


def plot_three_in_one(
    experiment_id: int,
    folder_uvvis: Path,
    out_path: Path,
    wl_plot_min_nm: float = 450.0,
    wl_plot_max_nm: float = 850.0,
    wl_fit_min_nm: float = 450.0,
    wl_fit_max_nm: float = 850.0,
) -> Path | None:
    """Plot three filtered spectra and their Gaussian fits on one graph.

    Args:
        experiment_id (int): Experiment ID (e.g. 85).
        folder_uvvis (Path): Folder containing UV-Vis CSVs.
        out_path (Path): Output PNG path.
        wl_plot_min_nm (float, optional): Min wavelength shown on the plot. Defaults to 450.0.
        wl_plot_max_nm (float, optional): Max wavelength shown on the plot. Defaults to 850.0.
        wl_fit_min_nm (float, optional): Min wavelength used for fitting. Defaults to 450.0.
        wl_fit_max_nm (float, optional): Max wavelength used for fitting. Defaults to 850.0.

    Returns:
        Path | None: Saved plot path, or None if the experiment has fewer than three UV-Vis files.
    """
    files = sorted(folder_uvvis.glob(f"ID{experiment_id}_RXT*_VIAL*"))
    if len(files) < 3:
        print(
            f"Skipping ID{experiment_id}: need at least 3 UV-Vis files, found {len(files)}"
        )
        return None

    # Prefer chronological order by RXT value if possible; fall back to filename sort.
    files = files[:3]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))

    x_fit = np.linspace(wl_fit_min_nm, wl_fit_max_nm, 600)

    for f in files:
        df = pd.read_csv(f)
        df = get_abs_zero(df)
        df = df.replace([np.inf, -np.inf], np.nan).dropna(
            subset=["Wavelength (nm)", "Abs_zero"]
        )

        df_plot = df.loc[df["Wavelength (nm)"].between(wl_plot_min_nm, wl_plot_max_nm)].copy()
        x_all = df_plot["Wavelength (nm)"].to_numpy(dtype=float)
        y_all = df_plot["Abs_zero"].to_numpy(dtype=float)

        try:
            fit = fit_peak_gaussian(df, wl_min_nm=wl_fit_min_nm, wl_max_nm=wl_fit_max_nm)
        except Exception:
            fit = None

        label_base = f.stem.split("_VIAL", 1)[-1]
        (line,) = ax.plot(x_all, y_all, linewidth=1.2, label=f"{label_base} Abs_zero")
        color = line.get_color()

        if fit is not None:
            y_fit = gaussian(x_fit, fit.amplitude, fit.center_nm, fit.sigma_nm, fit.baseline)
            ax.plot(
                x_fit,
                y_fit,
                linewidth=2.0,
                linestyle="--",
                color=color,
                label=f"{label_base} fit (A={fit.amplitude:.4f})",
            )

    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Absorbance (a.u.)")
    ax.set_title(f"ID{experiment_id}: Abs_zero + Gaussian fits")
    ax.set_xlim(wl_plot_min_nm, wl_plot_max_nm)
    ax.set_ylim(-2, 2)
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, fontsize=9, ncol=1)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    return out_path


if __name__ == "__main__":
    folder_uvvis = Path(r"C:\Users\LAB-CO2MAP\ammonia_data\uvvis")
    out_dir = Path(r"C:\Users\LAB-CO2MAP\ammonia_data\process\uvvis_gaussian_fits")
    for experiment_id in range(121, 138):
        out_one = out_dir / f"ID{experiment_id}_three_gaussian_fits.png"
        try:
            saved = plot_three_in_one(
                experiment_id=experiment_id,
                folder_uvvis=folder_uvvis,
                out_path=out_one,
            )
        except Exception as exc:
            print(f"Skipping ID{experiment_id}: {exc}")
            continue

        if saved is not None:
            print(f"Saved plot: {saved}")


