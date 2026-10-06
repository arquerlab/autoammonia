from __future__ import annotations

import numpy as np
import pandas as pd


def corrected_current_a(
    current_a: pd.Series | np.ndarray,
    current_correction_factor: float = 1.0,
) -> np.ndarray:
    """Convert measured potentiostat current (A) to EU-convention corrected current (A).

    Multiplies by -1 once to convert US convention exports to EU convention, then
    applies current_correction_factor. All current processing must use this function.

    Args:
        current_a (pd.Series | np.ndarray): Measured current in A from the potentiostat.
        current_correction_factor (float, optional): Hardware correction factor.
            Defaults to 1.0.

    Returns:
        np.ndarray: Corrected current in A.
    """
    return -np.asarray(current_a, dtype=float) * float(current_correction_factor)


def current_density_a_cm2(
    current_a: pd.Series | np.ndarray,
    electrode_area_cm2: float,
    current_correction_factor: float = 1.0,
) -> np.ndarray:
    """Convert measured current to current density in A/cm^2.

    Args:
        current_a (pd.Series | np.ndarray): Measured current in A.
        electrode_area_cm2 (float): Electrode area in cm^2.
        current_correction_factor (float, optional): Hardware correction factor.
            Defaults to 1.0.

    Returns:
        np.ndarray: Current density in A/cm^2.
    """
    return corrected_current_a(current_a, current_correction_factor) / float(electrode_area_cm2)


def current_density_ma_cm2(
    current_a: pd.Series | np.ndarray,
    electrode_area_cm2: float,
    current_correction_factor: float = 1.0,
) -> np.ndarray:
    """Convert measured current in A to corrected current density in mA/cm^2.

    Args:
        current_a (pd.Series | np.ndarray): Measured current in A.
        electrode_area_cm2 (float): Electrode area in cm^2.
        current_correction_factor (float, optional): Hardware correction factor.
            Defaults to 1.0.

    Returns:
        np.ndarray: Corrected current density in mA/cm^2.
    """
    return (
        corrected_current_a(current_a, current_correction_factor)
        * 1000.0
        / float(electrode_area_cm2)
    )


def potential_agagcl_3m_to_rhe(
    potential_v: pd.Series | np.ndarray,
    ph: float = 6.5,
    ref_offset_v: float = 0.210,
) -> pd.Series | np.ndarray:
    """Convert potential from Ag/AgCl (3M KCl) to RHE.

    Args:
        potential_v (pd.Series | np.ndarray): Potential vs Ag/AgCl (3M KCl), in volts.
        ph (float, optional): Electrolyte pH. Defaults to 6.5.
        ref_offset_v (float, optional): Ag/AgCl offset vs SHE in volts. Defaults to 0.210.

    Returns:
        pd.Series | np.ndarray: Potential converted to V vs RHE.
    """
    return -np.asarray(potential_v, dtype=float) + float(ref_offset_v) + 0.05916 * float(ph)
