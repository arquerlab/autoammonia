from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_ELECTROSYNTHESIS_DIR = Path(r"C:\Users\LAB-CO2MAP\ammonia_data\electrosynthesis")
CP_FILE_PATTERN = "*_cell*_method_CP*.csv"
MEASURED_CURRENT_COLUMN = "Current (A)"
APPLIED_CURRENT_COLUMN = "Applied current (A)"
TIME_COLUMN = "Time (s)"


@dataclass
class CurrentDeviationAccumulator:
    """Accumulate current-deviation statistics for one experiment ID.

    Attributes:
        experiment_id (int): Experiment ID parsed from the CP filename.
        file_count (int): Number of CP files included in the summary.
        point_count (int): Number of valid current points included in the summary.
        measured_current_sum_a (float): Sum of measured current values in A.
        applied_current_sum_a (float): Sum of applied current values in A.
        deviation_sum_a (float): Sum of signed deviations in A, measured minus applied.
        absolute_deviation_sum_a (float): Sum of absolute deviations in A.
    """

    experiment_id: int
    file_count: int = 0
    point_count: int = 0
    measured_current_sum_a: float = 0.0
    applied_current_sum_a: float = 0.0
    deviation_sum_a: float = 0.0
    absolute_deviation_sum_a: float = 0.0

    def add_file(self) -> None:
        """Count one CP file for this experiment."""
        self.file_count += 1

    def add_points(self, measured_current_a: pd.Series, applied_current_a: pd.Series) -> None:
        """Add valid current points from a CP data chunk.

        Args:
            measured_current_a (pd.Series): Measured current values in A.
            applied_current_a (pd.Series): Applied current values in A.
        """
        deviation_a = measured_current_a - applied_current_a
        self.point_count += int(len(deviation_a))
        self.measured_current_sum_a += float(measured_current_a.sum())
        self.applied_current_sum_a += float(applied_current_a.sum())
        self.deviation_sum_a += float(deviation_a.sum())
        self.absolute_deviation_sum_a += float(deviation_a.abs().sum())

    def to_summary(self) -> "CurrentDeviationSummary":
        """Convert accumulated sums into average current-deviation metrics.

        Returns:
            CurrentDeviationSummary: Averaged statistics for one experiment ID.

        Raises:
            ValueError: If no valid current points were accumulated.
        """
        if self.point_count == 0:
            raise ValueError(f"No valid current points for experiment {self.experiment_id}")

        mean_applied_current_a = self.applied_current_sum_a / self.point_count
        mean_deviation_a = self.deviation_sum_a / self.point_count
        percent_deviation = (
            mean_deviation_a / mean_applied_current_a * 100.0
            if not np.isclose(mean_applied_current_a, 0.0)
            else np.nan
        )

        return CurrentDeviationSummary(
            experiment_id=self.experiment_id,
            file_count=self.file_count,
            point_count=self.point_count,
            mean_applied_current_a=mean_applied_current_a,
            mean_measured_current_a=self.measured_current_sum_a / self.point_count,
            mean_deviation_a=mean_deviation_a,
            mean_absolute_deviation_a=self.absolute_deviation_sum_a / self.point_count,
            percent_deviation=percent_deviation,
        )


@dataclass(frozen=True)
class CurrentDeviationSummary:
    """Average current-deviation statistics for one experiment ID.

    Attributes:
        experiment_id (int): Experiment ID parsed from the CP filename.
        file_count (int): Number of CP files included in the summary.
        point_count (int): Number of valid current points included in the summary.
        mean_applied_current_a (float): Mean applied current in A.
        mean_measured_current_a (float): Mean measured current in A.
        mean_deviation_a (float): Mean signed deviation in A, measured minus applied.
        mean_absolute_deviation_a (float): Mean absolute deviation in A.
        percent_deviation (float): Mean signed deviation as percent of mean applied current.
    """

    experiment_id: int
    file_count: int
    point_count: int
    mean_applied_current_a: float
    mean_measured_current_a: float
    mean_deviation_a: float
    mean_absolute_deviation_a: float
    percent_deviation: float


def parse_experiment_id(path: Path) -> int | None:
    """Parse the experiment ID from an electrosynthesis CP filename.

    Args:
        path (Path): CP file path, usually named like `137_cell01_method_CP.csv`.

    Returns:
        int | None: Parsed experiment ID, or None if the filename does not match.
    """
    match = re.match(r"(?P<experiment_id>\d+)_cell\d+_method_CP", path.name)
    if match is None:
        return None
    return int(match.group("experiment_id"))


def iter_cp_files(folder: Path = DEFAULT_ELECTROSYNTHESIS_DIR) -> list[Path]:
    """List electrosynthesis CP CSV files in experiment ID order.

    Args:
        folder (Path, optional): Electrosynthesis data folder. Defaults to
            DEFAULT_ELECTROSYNTHESIS_DIR.

    Returns:
        list[Path]: Sorted CP CSV paths.
    """
    return sorted(
        folder.glob(CP_FILE_PATTERN),
        key=lambda path: (parse_experiment_id(path) is None, parse_experiment_id(path) or -1, path.name),
    )


def add_cp_file_to_accumulator(
    path: Path,
    accumulator: CurrentDeviationAccumulator,
    min_time_s: float | None = None,
    chunksize: int = 250_000,
) -> None:
    """Read one CP file and add its current deviation to an accumulator.

    Args:
        path (Path): CP CSV path.
        accumulator (CurrentDeviationAccumulator): Accumulator for the file's experiment ID.
        min_time_s (float | None, optional): Ignore points with time below this value in seconds.
            Defaults to None.
        chunksize (int, optional): Number of CSV rows to read per chunk. Defaults to 250000.

    Raises:
        ValueError: If the CP CSV does not contain required current columns.
    """
    required_columns = {MEASURED_CURRENT_COLUMN, APPLIED_CURRENT_COLUMN}
    columns_to_read = set(required_columns)
    if min_time_s is not None:
        columns_to_read.add(TIME_COLUMN)

    accumulator.add_file()
    try:
        chunks = pd.read_csv(path, usecols=lambda column: column in columns_to_read, chunksize=chunksize)
        for chunk in chunks:
            if not required_columns.issubset(chunk.columns):
                missing_columns = ", ".join(sorted(required_columns - set(chunk.columns)))
                raise ValueError(f"{path} is missing required columns: {missing_columns}")

            if min_time_s is not None:
                if TIME_COLUMN not in chunk.columns:
                    raise ValueError(f"{path} is missing required column: {TIME_COLUMN}")
                time_s = pd.to_numeric(chunk[TIME_COLUMN], errors="coerce")
                chunk = chunk[time_s >= float(min_time_s)]

            measured_current_a = pd.to_numeric(chunk[MEASURED_CURRENT_COLUMN], errors="coerce")
            applied_current_a = pd.to_numeric(chunk[APPLIED_CURRENT_COLUMN], errors="coerce")
            valid = measured_current_a.notna() & applied_current_a.notna()
            if not valid.any():
                continue

            accumulator.add_points(
                measured_current_a=measured_current_a[valid],
                applied_current_a=applied_current_a[valid],
            )
    except ValueError:
        raise


def summarize_current_deviations(
    folder: Path = DEFAULT_ELECTROSYNTHESIS_DIR,
    min_time_s: float | None = None,
    chunksize: int = 250_000,
) -> list[CurrentDeviationSummary]:
    """Summarize average current deviations for all electrosynthesis CP files.

    Args:
        folder (Path, optional): Electrosynthesis data folder. Defaults to
            DEFAULT_ELECTROSYNTHESIS_DIR.
        min_time_s (float | None, optional): Ignore points with time below this value in seconds.
            Defaults to None.
        chunksize (int, optional): Number of CSV rows to read per chunk. Defaults to 250000.

    Returns:
        list[CurrentDeviationSummary]: One summary row per experiment ID.
    """
    accumulators: dict[int, CurrentDeviationAccumulator] = {}
    for path in iter_cp_files(folder):
        experiment_id = parse_experiment_id(path)
        if experiment_id is None:
            print(f"Skipping CP file with unrecognized name: {path.name}")
            continue

        accumulator = accumulators.setdefault(
            experiment_id,
            CurrentDeviationAccumulator(experiment_id=experiment_id),
        )
        try:
            add_cp_file_to_accumulator(
                path=path,
                accumulator=accumulator,
                min_time_s=min_time_s,
                chunksize=chunksize,
            )
        except ValueError as exc:
            print(f"Skipping {path.name}: {exc}")

    return [accumulator.to_summary() for accumulator in accumulators.values() if accumulator.point_count > 0]


def print_current_deviations(summaries: list[CurrentDeviationSummary]) -> None:
    """Print average applied-vs-measured current deviations.

    Args:
        summaries (list[CurrentDeviationSummary]): Summary rows to print.
    """
    if not summaries:
        print("No electrosynthesis CP files with valid current data found.")
        return

    print(
        "exp_id,n_files,n_points,mean_applied_mA,mean_measured_mA,"
        "mean_deviation_mA,mean_abs_deviation_mA,percent_deviation"
    )
    for summary in sorted(summaries, key=lambda row: row.experiment_id):
        print(
            f"{summary.experiment_id},"
            f"{summary.file_count},"
            f"{summary.point_count},"
            f"{summary.mean_applied_current_a * 1000.0:.6f},"
            f"{summary.mean_measured_current_a * 1000.0:.6f},"
            f"{summary.mean_deviation_a * 1000.0:.6f},"
            f"{summary.mean_absolute_deviation_a * 1000.0:.6f},"
            f"{summary.percent_deviation:.3f}"
        )


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the current-deviation summary script.

    Returns:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Compare applied current against measured current for electrosynthesis CP files."
    )
    parser.add_argument(
        "--folder",
        type=Path,
        default=DEFAULT_ELECTROSYNTHESIS_DIR,
        help="Folder containing electrosynthesis CP CSV files.",
    )
    parser.add_argument(
        "--min-time-s",
        type=float,
        default=None,
        help="Optional lower time cutoff in seconds for excluding startup transients.",
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=250_000,
        help="CSV rows to read per chunk.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    current_summaries = summarize_current_deviations(
        folder=args.folder,
        min_time_s=args.min_time_s,
        chunksize=args.chunksize,
    )
    print_current_deviations(current_summaries)
