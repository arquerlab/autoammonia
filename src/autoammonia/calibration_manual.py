import os
import time
from datetime import datetime
from typing import Any
from prefect import get_run_logger, flow
from prefect.variables import Variable
import numpy as np
import pandas as pd

from .analysis_module import fill_vial_detection_mix
from .hardware.syringe_pumps import syringe_transfer_unlocked, syringe_transfer_uvvis_and_wash, compartment_wash_uvvis, syringe_wash_unlocked
from .config.config import DEFAULT_CONFIG
from .hardware.uv_vis_module import acquire_spectrum

@flow
def calibration(
    calibration_path: str | None = None,
    calibration_file: str | None = None,
    calibration_concentrations: list[float] | None = None,
    **kwargs: Any,
) -> None:
    config = {**DEFAULT_CONFIG, **kwargs}
    calibration_path = calibration_path if calibration_path is not None else config["calibration_path"]
    # Expand user home (e.g. '~') so checks and directory creation match pandas' behavior
    calibration_path = os.path.expanduser(calibration_path)
    os.makedirs(calibration_path, exist_ok=True)
    default_calibration_file = os.path.join(calibration_path, datetime.now().strftime('%y%m%d_%H%M'))
    calibration_file = calibration_file if calibration_file is not None else default_calibration_file
    concentrations = [0.5, 0.25, 0.1, 0.05, 0.025, 0.01, 0.005, 0.0025, 0.001]
    calibration_concentrations = calibration_concentrations if calibration_concentrations is not None else concentrations

    wash_uvvis_repeats = config['uv_vis_wash_repeats_calibration']
    wash_uvvis_volume = config['uv_vis_wash_volume']
    wash_uvvis_speed = config['uv_vis_wash_speed']
    uv_vis_aliquot_volume = config['uv_vis_aliquot_volume']
    uv_vis_integration_time = config['uv_vis_integration_time']
    filling_speed = config['aliquot_filling_speed']
    wash_vial_repeats = config['wash_vial_repeats']
    wash_vial_volume = config['wash_vial_volume']
    wash_vial_speed = config['wash_vial_speed']
    
    logger = get_run_logger()

    aliquot_volumes = []
    for i, concentration in enumerate(calibration_concentrations[-3::-3]):
        for j, ratio in enumerate([4,2,1]):
            aliquot_volume = 0.2 / ratio
            aliquot_volumes.append(aliquot_volume)
    for i in range(9):
        vial = 'vial1'
        Variable.set(vial, {'volume': 1.5, 'max_vol':1.5}, overwrite=True)
        syringe_transfer_uvvis_and_wash(
            syringe_pump='tecanAZ01', aliquot_volume=uv_vis_aliquot_volume, draw_valve_port='water', speed=filling_speed,
            wash_repeats=0, wash_vol=0, wash_speed=wash_vial_speed, **kwargs
        )
        logger.info(f'[calibration] UV-VIS flow cell filled with water (reference)')
        df_ref_dark = acquire_spectrum(spectrometer='UVVIS01', lamp='lamp01', integration_time= uv_vis_integration_time, dark=True)
        logger.info(f'[calibration] Dark reference spectrum acquired')
        df_ref = acquire_spectrum(spectrometer='UVVIS01', lamp='lamp01', integration_time= uv_vis_integration_time, dark=False)
        logger.info(f'[calibration] Reference spectrum acquired')
        inp = input(f'Place vial {i+1} in vial1 location and press Enter to continue')
        syringe_transfer_uvvis_and_wash(
            syringe_pump='tecanAZ01', aliquot_volume=uv_vis_aliquot_volume, draw_valve_port=vial, speed=filling_speed,
            wash_repeats=wash_vial_repeats, wash_vol=wash_vial_volume, wash_speed=wash_vial_speed, **kwargs
        )
        logger.info(f'[calibration] Sample {vial} sent to UV-VIS for measurement')
        df_sample_dark = acquire_spectrum(spectrometer='UVVIS01', lamp='lamp01', integration_time= uv_vis_integration_time, dark=True)
        logger.info(f'[calibration] Sample {vial} dark spectrum acquired')
        df_sample = acquire_spectrum(spectrometer='UVVIS01', lamp='lamp01', integration_time= uv_vis_integration_time, dark=False)
        logger.info(f'[calibration] Sample {vial} spectrum acquired')
        
        df = pd.DataFrame({
            "Wavelength (nm)": df_ref["Wavelength (nm)"],
            "Reference_dark": df_ref_dark["Intensity"],
            "Reference": df_ref["Intensity"],
            "Sample_dark": df_sample_dark["Intensity"],
            "Sample": df_sample["Intensity"],
        })
        df["Reference_dark_corrected"] = df["Reference"] - df["Reference_dark"]
        df["Sample_dark_corrected"] = df["Sample"] - df["Sample_dark"]
        df["Transmittance"] = df["Sample_dark_corrected"] / df["Reference_dark_corrected"]
        df["Absorption"] = -np.log10(df["Transmittance"])
        date_stamp = datetime.now().strftime('%y%m%d_%H%M')
        df.to_csv(os.path.join(calibration_path, f'calibration_{i+1}_{date_stamp}.csv'), index=False)
        logger.info(f'[calibration] Calibration {i+1} saved into {os.path.join(calibration_path, f'calibration_{i+1}.csv')}')
        
        compartment_wash_uvvis(syringe_pump='tecanAZ01', 
                    repeats=wash_uvvis_repeats, wash_vol=wash_uvvis_volume, speed=wash_uvvis_speed, **kwargs)
        logger.info(f'[calibration] UV-VIS flow cell washed with water')
        
    logger.info(f'[calibration] All calibrations saved into {calibration_path}')
def main():
    calibration()
if __name__ == "__main__":
    main()