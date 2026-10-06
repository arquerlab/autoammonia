from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class EchemTrace:
    """Electrochemical trace loaded from one CSV file.

    Attributes:
        label (str): Trace label used in plots.
        path (Path): Source CSV path.
        data (pd.DataFrame): Trace dataframe.
    """

    label: str
    path: Path
    data: pd.DataFrame


def safe_read_csv(path: Path, required_columns: set[str]) -> pd.DataFrame | None:
    """Read a CSV if all required columns are present.

    Args:
        path (Path): CSV path.
        required_columns (set[str]): Columns required for downstream processing.

    Returns:
        pd.DataFrame | None: Dataframe, or None if invalid.
    """
    try:
        df = pd.read_csv(path)
    except Exception:
        return None

    if not required_columns.issubset(df.columns):
        return None

    for column in required_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df.dropna(subset=list(required_columns)).reset_index(drop=True)


def read_large_trace_csv(
    path: Path,
    required_columns: set[str],
    optional_columns: set[str] | None = None,
    max_points: int = 12000,
    chunksize: int = 100000,
) -> pd.DataFrame | None:
    """Read and downsample a potentially large electrochemical trace CSV.

    Args:
        path (Path): CSV path.
        required_columns (set[str]): Columns required for plotting.
        optional_columns (set[str] | None, optional): Extra columns to keep when present.
        max_points (int, optional): Maximum plotted points. Defaults to 12000.
        chunksize (int, optional): Rows read per chunk. Defaults to 100000.

    Returns:
        pd.DataFrame | None: Downsampled dataframe, or None if invalid.
    """
    pieces: list[pd.DataFrame] = []
    per_chunk_points = max(200, max_points // 20)
    columns_to_keep = required_columns | (optional_columns or set())

    try:
        chunks = pd.read_csv(
            path,
            usecols=lambda column: column in columns_to_keep,
            chunksize=chunksize,
        )
        for chunk in chunks:
            if not required_columns.issubset(chunk.columns):
                return None
            chunk = chunk.copy()
            for column in columns_to_keep:
                if column not in chunk.columns:
                    continue
                chunk[column] = pd.to_numeric(chunk[column], errors="coerce")
            chunk = chunk.dropna(subset=list(required_columns))
            if chunk.empty:
                continue

            step = max(1, int(np.ceil(len(chunk) / per_chunk_points)))
            pieces.append(chunk.iloc[::step])
    except Exception:
        return None

    if not pieces:
        return None

    df = pd.concat(pieces, ignore_index=True)
    if len(df) > max_points:
        positions = np.linspace(0, len(df) - 1, max_points).astype(int)
        df = df.iloc[positions]
    return df.reset_index(drop=True)


def load_lsv_traces(experiment_id: int, folder: Path) -> dict[str, EchemTrace]:
    """Load pre- and post-reaction LSV traces.

    Args:
        experiment_id (int): Experiment ID.
        folder (Path): Electrosynthesis data folder.

    Returns:
        dict[str, EchemTrace]: Loaded traces keyed by `prerx` and `postrx`.
    """
    traces: dict[str, EchemTrace] = {}
    required_columns = {"Time (s)", "Potential (V)", "Current (A)"}

    for stage in ("prerx", "postrx"):
        matches = sorted(folder.glob(f"{experiment_id}_cell*_method_LSV_{stage}*.csv"))
        if not matches:
            continue
        df = safe_read_csv(matches[0], required_columns)
        if df is None or df.empty:
            continue
        traces[stage] = EchemTrace(label=stage, path=matches[0], data=df)

    return traces


def load_single_trace(
    experiment_id: int,
    folder: Path,
    pattern: str,
    label: str,
) -> EchemTrace | None:
    """Load the first matching time/potential/current trace.

    Args:
        experiment_id (int): Experiment ID.
        folder (Path): Folder to search.
        pattern (str): Glob pattern suffix after the experiment ID.
        label (str): Trace label.

    Returns:
        EchemTrace | None: Loaded trace, or None if unavailable.
    """
    matches = sorted(folder.glob(f"{experiment_id}_{pattern}"))
    if not matches:
        return None

    required_columns = {"Time (s)", "Potential (V)"}
    df = read_large_trace_csv(
        matches[0],
        required_columns,
        optional_columns={"Current (A)"},
    )
    if df is None or df.empty:
        return None
    return EchemTrace(label=label, path=matches[0], data=df)


def load_trace_with_columns(
    experiment_id: int,
    folder: Path,
    pattern: str,
    label: str,
    required_columns: set[str],
    optional_columns: set[str] | None = None,
) -> EchemTrace | None:
    """Load the first matching trace with custom required and optional columns.

    Args:
        experiment_id (int): Experiment ID.
        folder (Path): Folder to search.
        pattern (str): Glob pattern suffix after the experiment ID.
        label (str): Trace label.
        required_columns (set[str]): Columns required for plotting.
        optional_columns (set[str] | None, optional): Extra columns to keep when present.

    Returns:
        EchemTrace | None: Loaded trace, or None if unavailable.
    """
    matches = sorted(folder.glob(f"{experiment_id}_{pattern}"))
    if not matches:
        return None

    df = read_large_trace_csv(
        matches[0],
        required_columns,
        optional_columns=optional_columns,
    )
    if df is None or df.empty:
        return None
    return EchemTrace(label=label, path=matches[0], data=df)


def load_reaction_trace(experiment_id: int, folder: Path) -> EchemTrace | None:
    """Load reaction CP, falling back to reaction CA if CP is unavailable.

    Args:
        experiment_id (int): Experiment ID.
        folder (Path): Electrosynthesis folder.

    Returns:
        EchemTrace | None: Reaction CP or CA trace, or None if neither exists.
    """
    cp_trace = load_single_trace(
        experiment_id,
        folder,
        "cell*_method_CP*.csv",
        "Reaction CP",
    )
    if cp_trace is not None:
        return cp_trace

    return load_trace_with_columns(
        experiment_id,
        folder,
        "cell*_method_CA*.csv",
        "Reaction CA",
        required_columns={"Time (s)", "Current (A)"},
        optional_columns={"Applied potential (V)", "Potential (V)"},
    )


def load_uvvis_spectra(
    experiment_id: int,
    folder: Path,
    wavelength_min_nm: float = 500.0,
    wavelength_max_nm: float = 850.0,
) -> list[tuple[str, pd.DataFrame]]:
    """Load UV-Vis spectra and add background-corrected absorbance.

    Args:
        experiment_id (int): Experiment ID.
        folder (Path): UV-Vis folder.
        wavelength_min_nm (float, optional): Minimum wavelength to plot.
        wavelength_max_nm (float, optional): Maximum wavelength to plot.

    Returns:
        list[tuple[str, pd.DataFrame]]: Spectrum labels and dataframes.
    """
    spectra: list[tuple[str, pd.DataFrame]] = []
    required_columns = {"Wavelength (nm)", "Absorption"}

    for path in sorted(folder.glob(f"ID{experiment_id}_RXT*_VIAL*")):
        df = safe_read_csv(path, required_columns)
        if df is None or df.empty:
            continue
        df = df[df["Wavelength (nm)"].between(wavelength_min_nm, wavelength_max_nm)].copy()
        if df.empty:
            continue
        df["Abs_zero"] = df["Absorption"] - df["Absorption"].iloc[-1]
        label = label_from_uvvis_path(path)
        spectra.append((label, df))

    return spectra


def label_from_uvvis_path(path: Path) -> str:
    """Build a compact label from a UV-Vis filename.

    Args:
        path (Path): UV-Vis file path.

    Returns:
        str: Compact trace label.
    """
    match = re.search(r"RXT(\d+).*VIAL(.+?)(?:\.csv)?$", path.name)
    if not match:
        return path.stem
    return f"{int(match.group(1))} s, {match.group(2)}"
