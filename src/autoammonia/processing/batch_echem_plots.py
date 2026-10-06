import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np

from autoammonia.processing.conversions import corrected_current_a, current_density_a_cm2, potential_agagcl_3m_to_rhe


def plot_ediss(experiment_id: int) -> None:
    """
    Plot the EDiss curve for a given experiment.
    """
    folder = r'C:\Users\LAB-CO2MAP\ammonia_data\electrodissolution'
    match = list(Path(folder).glob(f'{experiment_id}_cell*_method_OCP*'))
    path = match[0]
    df = pd.read_csv(path)
    plt.plot(df['Time (s)'], df['Potential (V)'])
    plt.close()

def plot_lsv(experiment_id: int) -> None:
    """
    Plot the LSV curve for a given experiment.
    """
    folder = r'C:\Users\LAB-CO2MAP\ammonia_data\electrosynthesis'
    match = list(Path(folder).glob(f'{experiment_id}_cell*_method_LSV*'))
    for path in match:
        df = pd.read_csv(path)
        df = df[df['Time (s)'] > 5]
        e_rhe = potential_agagcl_3m_to_rhe(df["Potential (V)"], ph=6.5, ref_offset_v=0.210)
        plt.plot(e_rhe, corrected_current_a(df["Current (A)"]), label='prerx' if 'prerx' in path.name else 'postrx')
    plt.legend(frameon=False)
    plt.xlabel('Potential (V vs RHE)')
    plt.ylabel('Current (A)')
    plt.title('LSV Curve')
    plt.close()


def plot_lsv_summary(
    experiment_ids: list[int],
    nrows: int = 4,
    ncols: int = 2,
    min_time_s: float = 5.0,
    ph: float = 6.5,
    ref_offset_v: float = 0.210,
    out_path: str | Path | None = None,
) -> Path:
    """Plot LSVs for many experiments in a multi-panel summary figure.

    Each subplot corresponds to one experiment ID and overlays all matching LSV files
    (e.g. pre/post rx) found in the electrosynthesis folder.

    Args:
        experiment_ids (list[int]): Experiment IDs to include (e.g. list(range(79, 87))).
        nrows (int, optional): Rows in the grid. Defaults to 4.
        ncols (int, optional): Columns in the grid. Defaults to 2.
        min_time_s (float, optional): Drop early transient points with Time (s) <= min_time_s.
            Defaults to 5.0.
        ph (float, optional): Electrolyte pH for RHE conversion. Defaults to 6.5.
        ref_offset_v (float, optional): Ag/AgCl (3M KCl) offset vs SHE, in volts.
            Defaults to 0.210.
        out_path (str | Path | None, optional): Where to save the PNG. If None, saves to
            `C:\\Users\\LAB-CO2MAP\\ammonia_data\\process\\lsv_summary_<min>_<max>.png`.

    Returns:
        Path: Saved image path.
    """
    folder = Path(r"C:\Users\LAB-CO2MAP\ammonia_data\electrosynthesis")
    if out_path is None:
        out_dir = Path(r"C:\Users\LAB-CO2MAP\ammonia_data\process")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"lsv_summary_{min(experiment_ids)}_{max(experiment_ids)}.png"
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Preload all data and compute global axis limits for consistent scales.
    exp_data: list[tuple[int, list[tuple[str, pd.DataFrame]]]] = []
    all_v: list[np.ndarray] = []
    all_i: list[np.ndarray] = []

    for exp_id in experiment_ids:
        matches = sorted(folder.glob(f"{exp_id}_cell*_method_LSV*"))
        traces: list[tuple[str, pd.DataFrame]] = []
        for p in matches:
            df = pd.read_csv(p)
            if "Time (s)" not in df.columns or "Potential (V)" not in df.columns or "Current (A)" not in df.columns:
                continue
            df = df[df["Time (s)"] > float(min_time_s)]
            if df.empty:
                continue
            label = "prerx" if "prerx" in p.name else ("postrx" if "postrx" in p.name else p.stem)
            traces.append((label, df))
            e_rhe = potential_agagcl_3m_to_rhe(df["Potential (V)"], ph=ph, ref_offset_v=ref_offset_v)
            all_v.append(np.asarray(e_rhe, dtype=float))
            all_i.append(current_density_a_cm2(df["Current (A)"].to_numpy(dtype=float)))
        exp_data.append((int(exp_id), traces))

    if not all_v or not all_i:
        raise FileNotFoundError("No LSV files found for the requested experiment IDs")

    v_min = float(np.nanmin(np.concatenate(all_v)))
    v_max = float(np.nanmax(np.concatenate(all_v)))
    i_min = float(np.nanmin(np.concatenate(all_i)))
    i_max = float(np.nanmax(np.concatenate(all_i)))

    fig, axes = plt.subplots(
        nrows=nrows,
        ncols=ncols,
        sharex=True,
        sharey=True,
        figsize=(10, 12),
        constrained_layout=True,
    )
    axes = np.array(axes).reshape(nrows, ncols)

    for k, (exp_id, traces) in enumerate(exp_data):
        r = k // ncols
        c = k % ncols
        if r >= nrows:
            break
        ax = axes[r, c]

        # Use a consistent Blues palette for pre/post where possible.
        color_map = {"prerx": plt.get_cmap("Blues")(0.35), "postrx": plt.get_cmap("Blues")(0.85)}

        for label, df in traces:
            e_rhe = potential_agagcl_3m_to_rhe(df["Potential (V)"], ph=ph, ref_offset_v=ref_offset_v)
            ax.plot(
                e_rhe,
                current_density_a_cm2(df["Current (A)"]),
                linewidth=1.2,
                alpha=0.9,
                color=color_map.get(label),
            )

        ax.set_title(f"ID{exp_id}", fontsize=10)
        ax.set_xlim(v_min, v_max)
        ax.set_ylim(i_min, i_max)
        ax.grid(True, alpha=0.2)

        # Only left column shows y-axis
        if c != 0:
            ax.set_ylabel("")
            ax.tick_params(axis="y", which="both", left=False, labelleft=False)

        # Only bottom row shows x-axis label
        if r != nrows - 1:
            ax.set_xlabel("")
            ax.tick_params(axis="x", which="both", labelbottom=False)

    axes[-1, 0].set_xlabel("Potential (V vs RHE)")
    axes[-1, 1].set_xlabel("Potential (V vs RHE)")
    for rr in range(nrows):
        axes[rr, 0].set_ylabel("Current Density (A/cm$^2$)")

    fig.suptitle("LSV summary", fontsize=12)
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    return out_path

def plot_csv(experiment_id: int) -> None:
    """
    Plot the CSV file for a given experiment.
    """
    folder = r'C:\Users\LAB-CO2MAP\ammonia_data\electrosynthesis'
    matches = list(Path(folder).glob(f"{experiment_id}_cell*_method_CV_prerx_ECSA_rate_*"))
    for path in matches:
        df = pd.read_csv(path)
        plt.plot(df['Time (s)'], df['Potential (V)'])
    plt.close()


def plot_ca_summary(
    experiment_ids: list[int],
    nrows: int = 4,
    ncols: int = 2,
    min_time_s: float = 5.0,
    out_path: str | Path | None = None,
) -> Path:
    """Plot CA traces for many experiments in a multi-panel summary figure.

    Each subplot corresponds to one experiment ID and overlays all matching CA files
    found in the electrosynthesis folder.

    Args:
        experiment_ids (list[int]): Experiment IDs to include (e.g. list(range(79, 87))).
        nrows (int, optional): Rows in the grid. Defaults to 4.
        ncols (int, optional): Columns in the grid. Defaults to 2.
        min_time_s (float, optional): Drop early transient points with Time (s) <= min_time_s.
            Defaults to 5.0.
        out_path (str | Path | None, optional): Where to save the PNG. If None, saves to
            `C:\\Users\\LAB-CO2MAP\\ammonia_data\\process\\ca_summary_<min>_<max>.png`.

    Returns:
        Path: Saved image path.
    """
    folder = Path(r"C:\Users\LAB-CO2MAP\ammonia_data\electrosynthesis")
    if out_path is None:
        out_dir = Path(r"C:\Users\LAB-CO2MAP\ammonia_data\process")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"ca_summary_{min(experiment_ids)}_{max(experiment_ids)}.png"
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    exp_data: list[tuple[int, list[tuple[str, pd.DataFrame]]]] = []
    all_t: list[np.ndarray] = []
    all_i: list[np.ndarray] = []

    for exp_id in experiment_ids:
        matches = sorted(folder.glob(f"{exp_id}_cell*_method_CA*"))
        traces: list[tuple[str, pd.DataFrame]] = []
        for p in matches:
            df = pd.read_csv(p)
            if "Time (s)" not in df.columns or "Current (A)" not in df.columns:
                continue
            df = df[df["Time (s)"] > float(min_time_s)]
            if df.empty:
                continue

            label = p.stem
            traces.append((label, df))
            all_t.append(df["Time (s)"].to_numpy(dtype=float))
            all_i.append(current_density_a_cm2(df["Current (A)"].to_numpy(dtype=float)))
        exp_data.append((int(exp_id), traces))

    if not all_t or not all_i:
        raise FileNotFoundError("No CA files found for the requested experiment IDs")

    t_min = float(np.nanmin(np.concatenate(all_t)))
    t_max = float(np.nanmax(np.concatenate(all_t)))
    i_min = float(np.nanmin(np.concatenate(all_i)))
    i_max = float(np.nanmax(np.concatenate(all_i)))

    fig, axes = plt.subplots(
        nrows=nrows,
        ncols=ncols,
        sharex=True,
        sharey=True,
        figsize=(10, 12),
        constrained_layout=True,
    )
    axes = np.array(axes).reshape(nrows, ncols)

    for k, (exp_id, traces) in enumerate(exp_data):
        r = k // ncols
        c = k % ncols
        if r >= nrows:
            break
        ax = axes[r, c]

        # Consistent blues for all CA traces in a subplot (usually 1 file anyway).
        for j, (_label, df) in enumerate(traces):
            ax.plot(
                df["Time (s)"],
                current_density_a_cm2(df["Current (A)"]),
                linewidth=1.2,
                alpha=0.9,
                color=plt.get_cmap("Blues")(0.6),
            )

        ax.set_title(f"ID{exp_id}", fontsize=10)
        ax.set_xlim(t_min, t_max)
        ax.set_ylim(i_min, i_max)
        ax.grid(True, alpha=0.2)

        if c != 0:
            ax.set_ylabel("")
            ax.tick_params(axis="y", which="both", left=False, labelleft=False)

        if r != nrows - 1:
            ax.set_xlabel("")
            ax.tick_params(axis="x", which="both", labelbottom=False)

    axes[-1, 0].set_xlabel("Time (s)")
    axes[-1, 1].set_xlabel("Time (s)")
    for rr in range(nrows):
        axes[rr, 0].set_ylabel("Current Density (A/cm$^2$)")

    fig.suptitle("CA summary", fontsize=12)
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    return out_path

if __name__ == "__main__":
    plot_ediss(84)
    plot_lsv(84)
    plot_csv(80)
    saved = plot_lsv_summary(list(range(79, 87)), ph=6.5, ref_offset_v=0.210)
    print(f"Saved LSV summary: {saved}")
    saved_ca = plot_ca_summary(list(range(79, 87)))
    print(f"Saved CA summary: {saved_ca}")