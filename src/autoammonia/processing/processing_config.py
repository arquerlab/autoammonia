from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from autoammonia.config.config import PROCESSING_CONFIG


@dataclass(frozen=True)
class ProcessingConfig:
    """Static offline analysis constants loaded from processing_config.toml.

    Attributes:
        electrode_area_cm2 (float): Geometric electrode area in cm^2.
        current_correction_factor (float): Multiplier applied to measured potentiostat current (A).
        target_current_density_ma_cm2 (float): Target current density for eta metrics in mA/cm^2.
        calibration_factor (float): Absorbance to concentration calibration factor.
        absorbance_metric (str): `peak_corrected` or `gaussian`.
        absorbance_peak_min_nm (float): Lower bound of absorbance peak band in nm.
        absorbance_peak_max_nm (float): Upper bound of absorbance peak band in nm.
        uvvis_plot_min_nm (float): Minimum wavelength shown in summary UV-Vis plots in nm.
        uvvis_plot_max_nm (float): Maximum wavelength shown in summary UV-Vis plots in nm.
        absorbance_rolling_window (int): Rolling mean window for absorbance smoothing.
        koh_start_experiment_id (int): Experiment ID from which KOH pH applies.
        default_ph (float): Default electrolyte pH for RHE conversion.
        koh_ph (float): pH for KOH experiments.
        ref_offset_v_agagcl_3m (float): Ag/AgCl (3M KCl) offset vs SHE in volts.
        mols_electrons_per_nh3 (float): Electrons consumed per NH3 molecule.
        faraday_constant_c_mol (float): Faraday constant in C/mol.
        molar_mass_n_g_mol (float): Molar mass of nitrogen in g/mol.
    """

    electrode_area_cm2: float
    current_correction_factor: float
    target_current_density_ma_cm2: float
    calibration_factor: float
    absorbance_metric: str
    absorbance_peak_min_nm: float
    absorbance_peak_max_nm: float
    uvvis_plot_min_nm: float
    uvvis_plot_max_nm: float
    absorbance_rolling_window: int
    koh_start_experiment_id: int
    default_ph: float
    koh_ph: float
    ref_offset_v_agagcl_3m: float
    mols_electrons_per_nh3: float
    faraday_constant_c_mol: float
    molar_mass_n_g_mol: float


def get_processing_config() -> ProcessingConfig:
    """Load static processing constants from processing_config.toml.

    Returns:
        ProcessingConfig: Parsed processing configuration.
    """
    cfg = PROCESSING_CONFIG
    return ProcessingConfig(
        electrode_area_cm2=float(cfg["electrode_area_cm2"]),
        current_correction_factor=float(cfg["current_correction_factor"]),
        target_current_density_ma_cm2=float(cfg["target_current_density_ma_cm2"]),
        calibration_factor=float(cfg["calibration_factor"]),
        absorbance_metric=str(cfg["absorbance_metric"]),
        absorbance_peak_min_nm=float(cfg["absorbance_peak_min_nm"]),
        absorbance_peak_max_nm=float(cfg["absorbance_peak_max_nm"]),
        uvvis_plot_min_nm=float(cfg.get("uvvis_plot_min_nm", 500.0)),
        uvvis_plot_max_nm=float(cfg.get("uvvis_plot_max_nm", 850.0)),
        absorbance_rolling_window=int(cfg["absorbance_rolling_window"]),
        koh_start_experiment_id=int(cfg["koh_start_experiment_id"]),
        default_ph=float(cfg["default_ph"]),
        koh_ph=float(cfg["koh_ph"]),
        ref_offset_v_agagcl_3m=float(cfg["ref_offset_v_agagcl_3m"]),
        mols_electrons_per_nh3=float(cfg["mols_electrons_per_nh3"]),
        faraday_constant_c_mol=float(cfg["faraday_constant_c_mol"]),
        molar_mass_n_g_mol=float(cfg["molar_mass_n_g_mol"]),
    )


def rhe_ph_for_experiment(experiment_id: int, config: ProcessingConfig | None = None) -> float:
    """Return electrolyte pH used for RHE conversion for one experiment ID.

    Args:
        experiment_id (int): Experiment ID.
        config (ProcessingConfig | None, optional): Processing config. Defaults to loaded config.

    Returns:
        float: pH 14.0 from koh_start_experiment_id onward, otherwise default_ph.
    """
    config = config or get_processing_config()
    return (
        config.koh_ph
        if int(experiment_id) >= config.koh_start_experiment_id
        else config.default_ph
    )


def setpoint_current_density_ma_cm2(current_ma: float, electrode_area_cm2: float) -> float:
    """Convert a setpoint current in mA to current density in mA/cm^2.

    Args:
        current_ma (float): Setpoint current in mA.
        electrode_area_cm2 (float): Electrode area in cm^2.

    Returns:
        float: Current density in mA/cm^2.
    """
    return float(current_ma) / float(electrode_area_cm2)


def expand_data_path(data_path: str | Path) -> Path:
    """Expand a configured data path including home directory shortcuts.

    Args:
        data_path (str | Path): Path from experiment config snapshot.

    Returns:
        Path: Expanded absolute path.
    """
    return Path(data_path).expanduser().resolve()
